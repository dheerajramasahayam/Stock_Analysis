import sqlite3
# Removed dotenv imports, as config.py now handles it
import os
import sys
import logging # Import logging
import sqlite3
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file BEFORE importing other modules that need them
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Path to .env in root
load_dotenv(dotenv_path=dotenv_path)

import database # To use get_db_connection
from datetime import datetime, timedelta
import pandas as pd # Using pandas for easier calculations
import pandas_ta as ta # Import pandas-ta
import config # Import the config file

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# ---------------------

def calculate_scores_for_date(target_date_str):
    """
    Calculates scores for all tracked companies for a specific date
    based on data already fetched and stored in the database.
    """
    print(f"Calculating scores for date: {target_date_str}...")
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Get list of all tracked tickers
    cursor.execute("SELECT ticker FROM companies")
    tickers = [row['ticker'] for row in cursor.fetchall()]

    if not tickers:
        print("No companies found in the database to score.")
        conn.close()
        return

    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    # Fetch a larger window from DB to ensure enough data for calculations within pandas
    # Fetch approx 100 calendar days history ending on the target_date
    price_start_date_db_fetch = (target_date - timedelta(days=100)).strftime('%Y-%m-%d')

    all_scores = []

    for ticker in tickers:
        print(f"  Scoring {ticker}...")
        score = 0
        score_details = {} # Dictionary to hold points for each factor
        price_change_pct = None
        volume_ratio = None
        gemini_sentiment = None
        pe_ratio = None
        dividend_yield = None
        price_vs_ma50_status = 'N/A' # Initialize MA status
        rsi_value = None # Initialize RSI value
        macd_signal_status = 'neutral' # Initialize MACD signal
        bbands_signal_status = 'neutral' # Initialize BBands signal
        debt_to_equity = None # Initialize D/E ratio
        next_day_open = None # Initialize next day open
        next_day_perf = None # Initialize next day performance %

        # --- Fetch Fundamental Data (P/E, Dividend Yield, D/E) ---
        # We need to fetch this fresh as it's not stored in price_history
        try:
            # Import yfinance and time here if not already imported globally
            import yfinance as yf
            import time
            stock_info = yf.Ticker(ticker).info
            # Fetch and convert P/E ratio, handling potential errors/None
            try:
                pe_value = stock_info.get('trailingPE')
                pe_ratio = float(pe_value) if pe_value is not None else None
            except (ValueError, TypeError):
                 print(f"  Warning: Could not convert P/E ratio '{pe_value}' to float for {ticker}.")
                 pe_ratio = None

            # Fetch and convert dividend yield
            try:
                div_value = stock_info.get('dividendYield')
                dividend_yield = float(div_value) if div_value is not None else None
            except (ValueError, TypeError):
                 print(f"  Warning: Could not convert Dividend Yield '{div_value}' to float for {ticker}.")
                 dividend_yield = None

            # Fetch and convert Debt-to-Equity ratio
            try:
                de_value = stock_info.get('debtToEquity')
                debt_to_equity = float(de_value) if de_value is not None else None
            except (ValueError, TypeError):
                 print(f"  Warning: Could not convert Debt-to-Equity '{de_value}' to float for {ticker}.")
                 debt_to_equity = None

            time.sleep(0.2) # Small delay
        except Exception as e:
            print(f"  Warning: Could not fetch yfinance info for P/E/Div Yield for {ticker}: {e}")
        # ----------------------------------------------------


        # 1. Get Gemini Sentiment Score for the target date
        # Assumes gemini_analyzer stores one record per day with published_date = analysis_date
        cursor.execute("""
            SELECT sentiment_score
            FROM news_articles
            WHERE ticker = ? AND published_date = ?
            ORDER BY fetched_date DESC LIMIT 1
        """, (ticker, target_date_str))
        result = cursor.fetchone()
        gemini_sentiment = result['sentiment_score'] if result and result['sentiment_score'] is not None else 0.0 # Default to neutral

        # Apply points based on Gemini sentiment
        sentiment_pts = 0
        if gemini_sentiment > 0.15: # Slightly higher threshold for Gemini? Tunable.
            sentiment_pts = config.SENTIMENT_POSITIVE_PTS
        elif gemini_sentiment < -0.15: # Tunable.
             sentiment_pts = config.SENTIMENT_NEGATIVE_PTS
        else:
            sentiment_pts = config.SENTIMENT_NEUTRAL_PTS
        score += sentiment_pts * config.WEIGHT_SENTIMENT # Apply weight
        score_details['sentiment'] = {'value': gemini_sentiment, 'pts': sentiment_pts, 'weighted_pts': sentiment_pts * config.WEIGHT_SENTIMENT}

        # 2. Fetch Price History (including one day after target_date for performance calc)
        next_day_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
        # Adjust fetch range slightly to ensure we get D+1 if it exists
        price_end_date_db_fetch = (target_date + timedelta(days=4)).strftime('%Y-%m-%d') # Look a few days ahead

        cursor.execute("""
            SELECT date, close_price, volume, open_price -- Fetch Open price too
            FROM price_history
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (ticker, price_start_date_db_fetch, price_end_date_db_fetch)) # Use wider fetch date range
        price_rows = cursor.fetchall()

        # Create DataFrame
        if price_rows:
            df_full = pd.DataFrame(price_rows, columns=['date', 'close_price', 'volume', 'open_price'])
            df_full['date'] = pd.to_datetime(df_full['date'])
            df_full = df_full.set_index('date')

            # Filter DataFrame to only include data up to the target_date for scoring calculations
            df = df_full.loc[df_full.index <= target_date_str].copy()
        else:
            df = pd.DataFrame() # Empty DataFrame if no history

        # Now perform calculations if we have *at least* the minimum days needed for momentum in df
        if len(price_rows) >= config.PRICE_MOMENTUM_DAYS:
            # Use pandas for easier calculation
            df = pd.DataFrame(price_rows, columns=['date', 'close_price', 'volume'])
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Price Momentum
            if len(df) >= config.PRICE_MOMENTUM_DAYS: # Use config
                price_end = df['close_price'].iloc[-1]
                price_start = df['close_price'].iloc[-1 - config.PRICE_MOMENTUM_DAYS] # Use config
                if price_start != 0: # Avoid division by zero
                    price_change_pct = ((price_end - price_start) / price_start) * 100
                    momentum_pts = 0
                    if price_change_pct > config.PRICE_MOMENTUM_THRESHOLD_PCT: # Use config
                        momentum_pts = config.PRICE_POSITIVE_PTS # Use config
                    elif price_change_pct < 0:
                        momentum_pts = config.PRICE_NEGATIVE_PTS # Use config
                    else:
                        momentum_pts = config.PRICE_NEUTRAL_PTS # Use config
                else:
                    momentum_pts = config.PRICE_NEUTRAL_PTS # Use config
                score += momentum_pts * config.WEIGHT_MOMENTUM # Apply weight
                score_details['momentum'] = {'value': price_change_pct, 'pts': momentum_pts, 'weighted_pts': momentum_pts * config.WEIGHT_MOMENTUM}
            else:
                 momentum_pts = config.PRICE_NEUTRAL_PTS # Use config
                 score += momentum_pts * config.WEIGHT_MOMENTUM # Apply weight
                 score_details['momentum'] = {'value': None, 'pts': momentum_pts, 'weighted_pts': momentum_pts * config.WEIGHT_MOMENTUM}


            # Volume Ratio
            if len(df) >= config.VOLUME_AVG_DAYS + 1: # Use config
                avg_volume = df['volume'].iloc[-1 - config.VOLUME_AVG_DAYS:-1].mean() # Use config
                latest_volume = df['volume'].iloc[-1]
                if avg_volume > 0: # Avoid division by zero
                    volume_ratio = latest_volume / avg_volume
                    volume_pts = 0
                    if volume_ratio > config.VOLUME_RATIO_THRESHOLD: # Use config
                        volume_pts = config.VOLUME_HIGH_PTS # Use config
                    else:
                        volume_pts = config.VOLUME_NORMAL_PTS # Use config
                else:
                    volume_pts = config.VOLUME_NORMAL_PTS # Use config
                score += volume_pts * config.WEIGHT_VOLUME # Apply weight
                score_details['volume'] = {'value': volume_ratio, 'pts': volume_pts, 'weighted_pts': volume_pts * config.WEIGHT_VOLUME}
            else:
                volume_pts = config.VOLUME_NORMAL_PTS # Use config
                score += volume_pts * config.WEIGHT_VOLUME # Apply weight
                score_details['volume'] = {'value': None, 'pts': volume_pts, 'weighted_pts': volume_pts * config.WEIGHT_VOLUME}

            # 3. Calculate 50-day SMA and compare
            if len(df) >= config.MA_PERIOD:
                df['SMA_50'] = df['close_price'].rolling(window=config.MA_PERIOD).mean()
                latest_price = df['close_price'].iloc[-1]
                latest_sma = df['SMA_50'].iloc[-1]
                ma_pts = 0
                if not pd.isna(latest_sma): # Check if SMA calculation was successful
                    if latest_price > latest_sma:
                        ma_pts = config.MA_PRICE_ABOVE_PTS
                        price_vs_ma50_status = 'above'
                    elif latest_price < latest_sma:
                        ma_pts = config.MA_PRICE_BELOW_PTS
                        price_vs_ma50_status = 'below'
                    # No points if exactly equal
                    score += ma_pts * config.WEIGHT_MA50 # Apply weight
                else:
                    logging.warning(f"SMA calculation resulted in NaN for {ticker}.")
                    price_vs_ma50_status = 'N/A' # Keep as N/A if SMA is NaN
                score_details['ma50'] = {'value': price_vs_ma50_status, 'pts': ma_pts, 'weighted_pts': ma_pts * config.WEIGHT_MA50}
            else:
                 logging.warning(f"Not enough data for {config.MA_PERIOD}-day SMA for {ticker}.")
                 price_vs_ma50_status = 'N/A' # Keep as N/A
                 score_details['ma50'] = {'value': price_vs_ma50_status, 'pts': 0, 'weighted_pts': 0}


            # 4. Calculate RSI
            if len(df) >= config.RSI_PERIOD + 1: # Need enough data points for RSI calc
                # Ensure the index is datetime for pandas_ta
                if not pd.api.types.is_datetime64_any_dtype(df.index):
                     df.index = pd.to_datetime(df.index)
                # Calculate RSI
                df.ta.rsi(length=config.RSI_PERIOD, append=True) # Appends column like 'RSI_14'
                rsi_col_name = f'RSI_{config.RSI_PERIOD}'
                if rsi_col_name in df.columns and not pd.isna(df[rsi_col_name].iloc[-1]):
                    rsi_value = df[rsi_col_name].iloc[-1]
                    rsi_pts = 0
                    # Score RSI
                    if rsi_value < config.RSI_OVERSOLD_THRESHOLD:
                        rsi_pts = config.RSI_OVERSOLD_PTS
                    elif rsi_value > config.RSI_OVERBOUGHT_THRESHOLD:
                        rsi_pts = config.RSI_OVERBOUGHT_PTS
                    # No points for neutral RSI
                    score += rsi_pts * config.WEIGHT_RSI # Apply weight
                else:
                    logging.warning(f"RSI calculation failed or resulted in NaN for {ticker}.")
                    rsi_value = None # Ensure it's None if calc failed
                score_details['rsi'] = {'value': rsi_value, 'pts': rsi_pts, 'weighted_pts': rsi_pts * config.WEIGHT_RSI}
            else:
                logging.warning(f"Not enough data for {config.RSI_PERIOD}-day RSI for {ticker}.")
                rsi_value = None
                score_details['rsi'] = {'value': None, 'pts': 0, 'weighted_pts': 0}

            # 5. Calculate MACD and check for crossover
            macd_pts = 0
            # Need enough data points for MACD calculation (depends on slow period + signal period)
            if len(df) >= config.MACD_SLOW + config.MACD_SIGNAL:
                # Calculate MACD
                df.ta.macd(fast=config.MACD_FAST, slow=config.MACD_SLOW, signal=config.MACD_SIGNAL, append=True)
                macd_line_col = f'MACD_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}'
                signal_line_col = f'MACDs_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}'

                # Check if columns exist and have at least 2 non-NaN values at the end
                if macd_line_col in df.columns and signal_line_col in df.columns and \
                   not pd.isna(df[macd_line_col].iloc[-1]) and not pd.isna(df[signal_line_col].iloc[-1]) and \
                   not pd.isna(df[macd_line_col].iloc[-2]) and not pd.isna(df[signal_line_col].iloc[-2]):

                    # Check for crossover in the last period
                    macd_now = df[macd_line_col].iloc[-1]
                    signal_now = df[signal_line_col].iloc[-1]
                    macd_prev = df[macd_line_col].iloc[-2]
                    signal_prev = df[signal_line_col].iloc[-2]

                    # Bullish crossover: MACD was below signal, now above
                    if macd_prev < signal_prev and macd_now > signal_now:
                        macd_pts = config.MACD_CROSS_BULLISH_PTS
                        macd_signal_status = 'bullish_cross'
                    # Bearish crossover: MACD was above signal, now below
                    elif macd_prev > signal_prev and macd_now < signal_now:
                        macd_pts = config.MACD_CROSS_BEARISH_PTS
                        macd_signal_status = 'bearish_cross'
                    # else: neutral (no crossover)

                    score += macd_pts * config.WEIGHT_MACD # Apply weight
                else:
                    logging.warning(f"MACD calculation failed or not enough data points for crossover check for {ticker}.")
                    macd_signal_status = 'N/A' # Indicate calculation issue
            else:
                logging.warning(f"Not enough data for MACD calculation for {ticker}.")
                macd_signal_status = 'N/A' # Indicate not enough data
            score_details['macd'] = {'value': macd_signal_status, 'pts': macd_pts, 'weighted_pts': macd_pts * config.WEIGHT_MACD}

            # 6. Calculate Bollinger Bands and check for crossover
            bbands_pts = 0
            if len(df) >= config.BBANDS_PERIOD:
                # Calculate BBands
                df.ta.bbands(length=config.BBANDS_PERIOD, std=config.BBANDS_STDDEV, append=True)
                lower_band_col = f'BBL_{config.BBANDS_PERIOD}_{config.BBANDS_STDDEV}'
                upper_band_col = f'BBU_{config.BBANDS_PERIOD}_{config.BBANDS_STDDEV}'

                # Check if columns exist and have at least 2 non-NaN values at the end
                if lower_band_col in df.columns and upper_band_col in df.columns and \
                   not pd.isna(df['close_price'].iloc[-1]) and not pd.isna(df[lower_band_col].iloc[-1]) and \
                   not pd.isna(df['close_price'].iloc[-2]) and not pd.isna(df[lower_band_col].iloc[-2]) and \
                   not pd.isna(df[upper_band_col].iloc[-1]) and not pd.isna(df[upper_band_col].iloc[-2]):

                    price_now = df['close_price'].iloc[-1]
                    lower_now = df[lower_band_col].iloc[-1]
                    upper_now = df[upper_band_col].iloc[-1]
                    price_prev = df['close_price'].iloc[-2]
                    lower_prev = df[lower_band_col].iloc[-2]
                    upper_prev = df[upper_band_col].iloc[-2]

                    # Bullish signal: Price crosses below lower band
                    if price_prev > lower_prev and price_now < lower_now:
                        bbands_pts = config.BBANDS_LOWER_CROSS_PTS
                        bbands_signal_status = 'cross_lower'
                    # Bearish signal: Price crosses above upper band
                    elif price_prev < upper_prev and price_now > upper_now:
                        bbands_pts = config.BBANDS_UPPER_CROSS_PTS
                        bbands_signal_status = 'cross_upper'
                    # else: neutral

                    score += bbands_pts * config.WEIGHT_BBANDS # Apply weight
                else:
                    logging.warning(f"BBands calculation failed or not enough data points for crossover check for {ticker}.")
                    bbands_signal_status = 'N/A'
            else:
                logging.warning(f"Not enough data for Bollinger Bands calculation for {ticker}.")
                bbands_signal_status = 'N/A'
            score_details['bbands'] = {'value': bbands_signal_status, 'pts': bbands_pts, 'weighted_pts': bbands_pts * config.WEIGHT_BBANDS}

            # 7. Calculate Next Day Performance
            # Find the next trading day's data in the full history
            next_day_data = df_full.loc[df_full.index > target_date_str]
            if not next_day_data.empty:
                next_day_open = next_day_data['open_price'].iloc[0]
                current_close = df['close_price'].iloc[-1] # Close price on target_date
                if current_close and next_day_open and current_close > 0:
                    next_day_perf = ((next_day_open - current_close) / current_close) * 100
                else:
                    logging.warning(f"Could not calculate next day perf for {ticker} on {target_date_str} due to missing/zero prices.")
            else:
                logging.warning(f"No price data found for {ticker} after {target_date_str} to calculate next day performance.")


        else:
            logging.warning(f"Not enough price history data for {ticker} to calculate momentum/volume/MA/RSI/MACD/BBands.")
            # Assign neutral scores if not enough data
            # Assign neutral scores if not enough data for technicals
            score_details['momentum'] = {'value': None, 'pts': config.PRICE_NEUTRAL_PTS, 'weighted_pts': config.PRICE_NEUTRAL_PTS * config.WEIGHT_MOMENTUM}
            score_details['volume'] = {'value': None, 'pts': config.VOLUME_NORMAL_PTS, 'weighted_pts': config.VOLUME_NORMAL_PTS * config.WEIGHT_VOLUME}
            score_details['ma50'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            score_details['rsi'] = {'value': None, 'pts': 0, 'weighted_pts': 0}
            score_details['macd'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            score_details['bbands'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            # Next day perf is not scored, just recorded
            score += config.PRICE_NEUTRAL_PTS * config.WEIGHT_MOMENTUM # Apply weight
            score += config.VOLUME_NORMAL_PTS * config.WEIGHT_VOLUME # Apply weight
            price_vs_ma50_status = 'N/A' # Ensure status is N/A
            macd_signal_status = 'N/A' # Ensure status is N/A
            bbands_signal_status = 'N/A' # Ensure status is N/A

        # 9. Score P/E Ratio
        if pe_ratio is not None:
            pe_pts = 0
            if pe_ratio < config.PE_LOW_THRESHOLD and pe_ratio > 0: # Use config & Ensure P/E is positive
                pe_pts = config.PE_LOW_PTS # Use config
            elif pe_ratio > config.PE_HIGH_THRESHOLD: # Use config
                pe_pts = config.PE_HIGH_PTS # Use config
            else:
                pe_pts = config.PE_NEUTRAL_PTS_PE # Use config
        else:
            pe_pts = config.PE_NEUTRAL_PTS_PE # Use config
        score += pe_pts * config.WEIGHT_PE_RATIO # Apply weight
        score_details['pe_ratio'] = {'value': pe_ratio, 'pts': pe_pts, 'weighted_pts': pe_pts * config.WEIGHT_PE_RATIO}

        # 10. Score Dividend Yield
        div_pts = 0
        if dividend_yield is not None and dividend_yield > config.DIV_YIELD_THRESHOLD: # Use config
            div_pts = config.DIV_YIELD_PTS # Use config
        # No points added or subtracted otherwise for dividend yield
        score += div_pts * config.WEIGHT_DIVIDEND # Apply weight
        score_details['dividend'] = {'value': dividend_yield, 'pts': div_pts, 'weighted_pts': div_pts * config.WEIGHT_DIVIDEND}

        # 11. Score Debt-to-Equity Ratio
        de_pts = 0
        if debt_to_equity is not None:
            if debt_to_equity < config.DE_RATIO_LOW_THRESHOLD and debt_to_equity >= 0: # Lower is better (must be non-negative)
                de_pts = config.DE_RATIO_LOW_PTS
            elif debt_to_equity > config.DE_RATIO_HIGH_THRESHOLD:
                de_pts = config.DE_RATIO_HIGH_PTS
            # else: neutral
        # No points if unavailable
        score += de_pts * config.WEIGHT_DE_RATIO # Apply weight
        score_details['debt_equity'] = {'value': debt_to_equity, 'pts': de_pts, 'weighted_pts': de_pts * config.WEIGHT_DE_RATIO}


        # Log the final score and breakdown (now includes weighted points)
        logging.info(f"Scored {ticker} for {target_date_str}: Final Score={score}, Breakdown={score_details}")

        # Store the calculated score and components
        all_scores.append((
            ticker,
            target_date_str,
            score,
            price_change_pct,
            volume_ratio,
            gemini_sentiment, # Store gemini sentiment
            pe_ratio, # Store P/E
            dividend_yield, # Store Div Yield
            price_vs_ma50_status, # Store MA status
            rsi_value, # Store RSI value
            macd_signal_status, # Store MACD signal
            bbands_signal_status, # Store BBands signal
            debt_to_equity, # Store D/E ratio
            next_day_open, # Store next day open
            next_day_perf # Store next day performance %
        ))

    # Insert all calculated scores into the database
    try:
        cursor.executemany("""
            INSERT OR REPLACE INTO daily_scores
            (ticker, date, score, price_change_pct, volume_ratio, avg_sentiment, pe_ratio, dividend_yield, price_vs_ma50, rsi, macd_signal, bbands_signal, debt_to_equity, next_day_open_price, next_day_perf_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, all_scores) # Added next day perf columns
        conn.commit()
        print(f"Successfully calculated and stored scores for {len(all_scores)} tickers.")
    except Exception as e:
        conn.rollback()
        print(f"Error storing calculated scores: {e}")

    conn.close()


if __name__ == '__main__':
    import sys
    # Get target date from command line argument, default to yesterday if not provided
    if len(sys.argv) > 1:
        target_date_str = sys.argv[1]
        try:
            # Validate date format
            datetime.strptime(target_date_str, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format '{target_date_str}'. Please use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)
    else:
        target_date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"No date provided, defaulting to yesterday: {target_date_str}")

    calculate_scores_for_date(target_date_str)
