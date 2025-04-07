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
from log_setup import setup_logger # Import logger setup
import numpy as np # For handling potential NaN/Inf

# --- Logger ---
logger = setup_logger('scorer', config.LOG_FILE_SCORER)
# -------------

def calculate_scores_for_date(target_date_str):
    """
    Calculates scores for all tracked companies for a specific date
    based on data already fetched and stored in the database.
    """
    logger.info(f"Starting score calculation for date: {target_date_str}...")
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Get list of all tracked tickers
    cursor.execute("SELECT ticker FROM companies")
    tickers = [row['ticker'] for row in cursor.fetchall()]

    if not tickers:
        logger.warning("No companies found in the database to score.")
        conn.close()
        return

    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    # Fetch a larger window from DB to ensure enough data for calculations within pandas
    # Fetch approx 100+ calendar days history ending a few days after target date
    # Need enough history *before* target_date for longest indicator (MACD needs ~35 trading days, MA=50)
    # Fetching 100 calendar days prior should be sufficient buffer
    price_start_date_db_fetch = (target_date - timedelta(days=100)).strftime('%Y-%m-%d')
    price_end_date_db_fetch = (target_date + timedelta(days=4)).strftime('%Y-%m-%d') # Look a few days ahead for next_day_open

    all_scores = []

    for ticker in tickers:
        logger.debug(f"Scoring {ticker}...")
        score = 0.0 # Initialize score as float
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
        pb_ratio = None # Initialize P/B ratio
        ps_ratio = None # Initialize P/S ratio
        next_day_open = None # Initialize next day open
        next_day_perf = None # Initialize next day performance %

        # --- Fetch Fundamental Data (P/E, Dividend Yield, D/E, P/B, P/S) ---
        try:
            import yfinance as yf
            import time
            stock_info = yf.Ticker(ticker).info
            # Fetch and convert P/E ratio
            try:
                pe_value = stock_info.get('trailingPE')
                pe_ratio = float(pe_value) if pe_value is not None else None
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert P/E ratio '{pe_value}' to float for {ticker}.")
                 pe_ratio = None
            # Fetch and convert dividend yield
            try:
                div_value = stock_info.get('dividendYield')
                dividend_yield = float(div_value) if div_value is not None else None
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert Dividend Yield '{div_value}' to float for {ticker}.")
                 dividend_yield = None
            # Fetch and convert Debt-to-Equity ratio
            try:
                de_value = stock_info.get('debtToEquity')
                if de_value is not None:
                    # Normalize D/E (sometimes reported as %, sometimes as ratio)
                    debt_to_equity = float(de_value) / 100.0 if float(de_value) > 5 else float(de_value)
                else:
                    debt_to_equity = None
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert Debt-to-Equity '{de_value}' to float for {ticker}.")
                 debt_to_equity = None
            # Fetch and convert Price-to-Book ratio
            try:
                pb_value = stock_info.get('priceToBook')
                pb_ratio = float(pb_value) if pb_value is not None else None
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert Price-to-Book '{pb_value}' to float for {ticker}.")
                 pb_ratio = None
            # Fetch and convert Price-to-Sales ratio
            try:
                ps_value = stock_info.get('priceToSalesTrailing12Months')
                ps_ratio = float(ps_value) if ps_value is not None else None
            except (ValueError, TypeError):
                 logger.warning(f"Could not convert Price-to-Sales '{ps_value}' to float for {ticker}.")
                 ps_ratio = None

            time.sleep(0.2) # Small delay
        except Exception as e:
            logger.warning(f"Could not fetch yfinance info for fundamentals for {ticker}: {e}")
        # ----------------------------------------------------

        # 1. Get Gemini Sentiment Score for the target date
        cursor.execute("""
            SELECT sentiment_score
            FROM news_articles
            WHERE ticker = ? AND published_date = ?
            ORDER BY fetched_date DESC LIMIT 1
        """, (ticker, target_date_str))
        result = cursor.fetchone()
        gemini_sentiment = result['sentiment_score'] if result and result['sentiment_score'] is not None else 0.0
        sentiment_pts = 0
        if gemini_sentiment > 0.15: sentiment_pts = config.SENTIMENT_POSITIVE_PTS
        elif gemini_sentiment < -0.15: sentiment_pts = config.SENTIMENT_NEGATIVE_PTS
        else: sentiment_pts = config.SENTIMENT_NEUTRAL_PTS
        score += sentiment_pts * config.WEIGHT_SENTIMENT
        score_details['sentiment'] = {'value': gemini_sentiment, 'pts': sentiment_pts, 'weighted_pts': sentiment_pts * config.WEIGHT_SENTIMENT}

        # 2. Fetch Price History
        cursor.execute("""
            SELECT date, open_price, close_price, volume
            FROM price_history
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (ticker, price_start_date_db_fetch, price_end_date_db_fetch))
        price_rows = cursor.fetchall()

        df_full = pd.DataFrame() # Initialize empty
        df = pd.DataFrame()      # Initialize empty

        if price_rows:
            df_full = pd.DataFrame(price_rows, columns=['date', 'open_price', 'close_price', 'volume'])
            df_full['date'] = pd.to_datetime(df_full['date'])
            df_full = df_full.set_index('date')
            # Filter DataFrame to data up to the target_date for scoring
            df = df_full.loc[df_full.index <= target_date_str].copy()
        else:
             logger.warning(f"No price history found for {ticker} in range {price_start_date_db_fetch} to {price_end_date_db_fetch}.")

        # --- Calculate Technical Indicators & Scores (if enough data in df) ---
        if len(df) >= config.PRICE_MOMENTUM_DAYS:
            # Price Momentum
            if len(df) >= config.PRICE_MOMENTUM_DAYS:
                price_end = df['close_price'].iloc[-1]
                price_start = df['close_price'].iloc[-1 - config.PRICE_MOMENTUM_DAYS]
                momentum_pts = config.PRICE_NEUTRAL_PTS # Default
                if price_start != 0:
                    price_change_pct = ((price_end - price_start) / price_start) * 100
                    if price_change_pct > config.PRICE_MOMENTUM_THRESHOLD_PCT: momentum_pts = config.PRICE_POSITIVE_PTS
                    elif price_change_pct < 0: momentum_pts = config.PRICE_NEGATIVE_PTS
                score += momentum_pts * config.WEIGHT_MOMENTUM
                score_details['momentum'] = {'value': price_change_pct, 'pts': momentum_pts, 'weighted_pts': momentum_pts * config.WEIGHT_MOMENTUM}
            else: # Should not happen due to outer check, but safe fallback
                 momentum_pts = config.PRICE_NEUTRAL_PTS
                 score += momentum_pts * config.WEIGHT_MOMENTUM
                 score_details['momentum'] = {'value': None, 'pts': momentum_pts, 'weighted_pts': momentum_pts * config.WEIGHT_MOMENTUM}

            # Volume Ratio
            if len(df) >= config.VOLUME_AVG_DAYS + 1:
                avg_volume = df['volume'].iloc[-1 - config.VOLUME_AVG_DAYS:-1].mean()
                latest_volume = df['volume'].iloc[-1]
                volume_pts = config.VOLUME_NORMAL_PTS # Default
                if avg_volume > 0:
                    volume_ratio = latest_volume / avg_volume
                    if volume_ratio > config.VOLUME_RATIO_THRESHOLD: volume_pts = config.VOLUME_HIGH_PTS
                score += volume_pts * config.WEIGHT_VOLUME
                score_details['volume'] = {'value': volume_ratio, 'pts': volume_pts, 'weighted_pts': volume_pts * config.WEIGHT_VOLUME}
            else:
                volume_pts = config.VOLUME_NORMAL_PTS
                score += volume_pts * config.WEIGHT_VOLUME
                score_details['volume'] = {'value': None, 'pts': volume_pts, 'weighted_pts': volume_pts * config.WEIGHT_VOLUME}

            # 50-day SMA
            ma_pts = 0
            if len(df) >= config.MA_PERIOD:
                df['SMA_50'] = df['close_price'].rolling(window=config.MA_PERIOD).mean()
                latest_price = df['close_price'].iloc[-1]
                latest_sma = df['SMA_50'].iloc[-1]
                if not pd.isna(latest_sma):
                    if latest_price > latest_sma:
                        ma_pts = config.MA_PRICE_ABOVE_PTS
                        price_vs_ma50_status = 'above'
                    elif latest_price < latest_sma:
                        ma_pts = config.MA_PRICE_BELOW_PTS
                        price_vs_ma50_status = 'below'
                    score += ma_pts * config.WEIGHT_MA50
                else:
                    logger.warning(f"SMA calculation resulted in NaN for {ticker}.")
                    price_vs_ma50_status = 'N/A'
                score_details['ma50'] = {'value': price_vs_ma50_status, 'pts': ma_pts, 'weighted_pts': ma_pts * config.WEIGHT_MA50}
            else:
                 logger.warning(f"Not enough data ({len(df)} days) for {config.MA_PERIOD}-day SMA for {ticker}.")
                 price_vs_ma50_status = 'N/A'
                 score_details['ma50'] = {'value': price_vs_ma50_status, 'pts': 0, 'weighted_pts': 0}

            # RSI
            rsi_pts = 0
            if len(df) >= config.RSI_PERIOD + 1:
                if not pd.api.types.is_datetime64_any_dtype(df.index): df.index = pd.to_datetime(df.index)
                df.ta.rsi(length=config.RSI_PERIOD, append=True)
                rsi_col_name = f'RSI_{config.RSI_PERIOD}'
                if rsi_col_name in df.columns and not pd.isna(df[rsi_col_name].iloc[-1]):
                    rsi_value = df[rsi_col_name].iloc[-1]
                    if rsi_value < config.RSI_OVERSOLD_THRESHOLD: rsi_pts = config.RSI_OVERSOLD_PTS
                    elif rsi_value > config.RSI_OVERBOUGHT_THRESHOLD: rsi_pts = config.RSI_OVERBOUGHT_PTS
                    score += rsi_pts * config.WEIGHT_RSI
                else:
                    logger.warning(f"RSI calculation failed or resulted in NaN for {ticker}.")
                    rsi_value = None
                score_details['rsi'] = {'value': rsi_value, 'pts': rsi_pts, 'weighted_pts': rsi_pts * config.WEIGHT_RSI}
            else:
                logger.warning(f"Not enough data ({len(df)} days) for {config.RSI_PERIOD}-day RSI for {ticker}.")
                rsi_value = None
                score_details['rsi'] = {'value': None, 'pts': 0, 'weighted_pts': 0}

            # MACD
            macd_pts = 0
            if len(df) >= config.MACD_SLOW + config.MACD_SIGNAL:
                df.ta.macd(fast=config.MACD_FAST, slow=config.MACD_SLOW, signal=config.MACD_SIGNAL, append=True)
                macd_line_col = f'MACD_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}'
                signal_line_col = f'MACDs_{config.MACD_FAST}_{config.MACD_SLOW}_{config.MACD_SIGNAL}'
                if macd_line_col in df.columns and signal_line_col in df.columns and \
                   not pd.isna(df[macd_line_col].iloc[-1]) and not pd.isna(df[signal_line_col].iloc[-1]) and \
                   not pd.isna(df[macd_line_col].iloc[-2]) and not pd.isna(df[signal_line_col].iloc[-2]):
                    macd_now, signal_now = df[macd_line_col].iloc[-1], df[signal_line_col].iloc[-1]
                    macd_prev, signal_prev = df[macd_line_col].iloc[-2], df[signal_line_col].iloc[-2]
                    if macd_prev < signal_prev and macd_now > signal_now:
                        macd_pts = config.MACD_CROSS_BULLISH_PTS
                        macd_signal_status = 'bullish_cross'
                    elif macd_prev > signal_prev and macd_now < signal_now:
                        macd_pts = config.MACD_CROSS_BEARISH_PTS
                        macd_signal_status = 'bearish_cross'
                    score += macd_pts * config.WEIGHT_MACD
                else:
                    logger.warning(f"MACD calculation failed or not enough data points for crossover check for {ticker}.")
                    macd_signal_status = 'N/A'
            else:
                logger.warning(f"Not enough data ({len(df)} days) for MACD calculation for {ticker}.")
                macd_signal_status = 'N/A'
            score_details['macd'] = {'value': macd_signal_status, 'pts': macd_pts, 'weighted_pts': macd_pts * config.WEIGHT_MACD}

            # Bollinger Bands
            bbands_pts = 0
            if len(df) >= config.BBANDS_PERIOD:
                df.ta.bbands(length=config.BBANDS_PERIOD, std=config.BBANDS_STDDEV, append=True)
                lower_band_col = f'BBL_{config.BBANDS_PERIOD}_{config.BBANDS_STDDEV}'
                upper_band_col = f'BBU_{config.BBANDS_PERIOD}_{config.BBANDS_STDDEV}'
                if lower_band_col in df.columns and upper_band_col in df.columns and \
                   not pd.isna(df['close_price'].iloc[-1]) and not pd.isna(df[lower_band_col].iloc[-1]) and \
                   not pd.isna(df['close_price'].iloc[-2]) and not pd.isna(df[lower_band_col].iloc[-2]) and \
                   not pd.isna(df[upper_band_col].iloc[-1]) and not pd.isna(df[upper_band_col].iloc[-2]):
                    price_now, lower_now, upper_now = df['close_price'].iloc[-1], df[lower_band_col].iloc[-1], df[upper_band_col].iloc[-1]
                    price_prev, lower_prev, upper_prev = df['close_price'].iloc[-2], df[lower_band_col].iloc[-2], df[upper_band_col].iloc[-2]
                    if price_prev > lower_prev and price_now < lower_now:
                        bbands_pts = config.BBANDS_LOWER_CROSS_PTS
                        bbands_signal_status = 'cross_lower'
                    elif price_prev < upper_prev and price_now > upper_now:
                        bbands_pts = config.BBANDS_UPPER_CROSS_PTS
                        bbands_signal_status = 'cross_upper'
                    score += bbands_pts * config.WEIGHT_BBANDS
                else:
                    logger.warning(f"BBands calculation failed or not enough data points for crossover check for {ticker}.")
                    bbands_signal_status = 'N/A'
            else:
                logger.warning(f"Not enough data ({len(df)} days) for Bollinger Bands calculation for {ticker}.")
                bbands_signal_status = 'N/A'
            score_details['bbands'] = {'value': bbands_signal_status, 'pts': bbands_pts, 'weighted_pts': bbands_pts * config.WEIGHT_BBANDS}

            # Calculate Next Day Performance (Close[D] -> Open[D+1])
            next_day_data = df_full.loc[df_full.index > target_date_str]
            if not next_day_data.empty:
                next_day_open = next_day_data['open_price'].iloc[0]
                current_close = df['close_price'].iloc[-1]
                if current_close and next_day_open and current_close > 0:
                    next_day_perf = ((next_day_open - current_close) / current_close) * 100
                else:
                    logger.warning(f"Could not calculate next day perf for {ticker} on {target_date_str} due to missing/zero prices (Close={current_close}, NextOpen={next_day_open}).")
            else:
                logger.warning(f"No price data found for {ticker} after {target_date_str} to calculate next day performance.")

        else: # Not enough history for even basic momentum
            logger.warning(f"Not enough price history data ({len(price_rows)} days) for {ticker} to calculate any technical indicators.")
            # Assign neutral scores for all technicals
            score_details['momentum'] = {'value': None, 'pts': config.PRICE_NEUTRAL_PTS, 'weighted_pts': config.PRICE_NEUTRAL_PTS * config.WEIGHT_MOMENTUM}
            score_details['volume'] = {'value': None, 'pts': config.VOLUME_NORMAL_PTS, 'weighted_pts': config.VOLUME_NORMAL_PTS * config.WEIGHT_VOLUME}
            score_details['ma50'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            score_details['rsi'] = {'value': None, 'pts': 0, 'weighted_pts': 0}
            score_details['macd'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            score_details['bbands'] = {'value': 'N/A', 'pts': 0, 'weighted_pts': 0}
            score += config.PRICE_NEUTRAL_PTS * config.WEIGHT_MOMENTUM
            score += config.VOLUME_NORMAL_PTS * config.WEIGHT_VOLUME
            price_vs_ma50_status = 'N/A'
            macd_signal_status = 'N/A'
            bbands_signal_status = 'N/A'

        # Score P/E Ratio
        pe_pts = config.PE_NEUTRAL_PTS_PE # Default
        if pe_ratio is not None:
            if pe_ratio < config.PE_LOW_THRESHOLD and pe_ratio > 0: pe_pts = config.PE_LOW_PTS
            elif pe_ratio > config.PE_HIGH_THRESHOLD: pe_pts = config.PE_HIGH_PTS
        score += pe_pts * config.WEIGHT_PE_RATIO
        score_details['pe_ratio'] = {'value': pe_ratio, 'pts': pe_pts, 'weighted_pts': pe_pts * config.WEIGHT_PE_RATIO}

        # Score Dividend Yield
        div_pts = 0 # Default
        if dividend_yield is not None and dividend_yield > config.DIV_YIELD_THRESHOLD:
            div_pts = config.DIV_YIELD_PTS
        score += div_pts * config.WEIGHT_DIVIDEND
        score_details['dividend'] = {'value': dividend_yield, 'pts': div_pts, 'weighted_pts': div_pts * config.WEIGHT_DIVIDEND}

        # Score Debt-to-Equity Ratio
        de_pts = 0 # Default
        if debt_to_equity is not None:
            if debt_to_equity < config.DE_RATIO_LOW_THRESHOLD and debt_to_equity >= 0: de_pts = config.DE_RATIO_LOW_PTS
            elif debt_to_equity > config.DE_RATIO_HIGH_THRESHOLD: de_pts = config.DE_RATIO_HIGH_PTS
        score += de_pts * config.WEIGHT_DE_RATIO
        score_details['debt_equity'] = {'value': debt_to_equity, 'pts': de_pts, 'weighted_pts': de_pts * config.WEIGHT_DE_RATIO}

        # Score Price-to-Book Ratio
        pb_pts = 0 # Default
        if pb_ratio is not None:
             if pb_ratio < config.PB_RATIO_LOW_THRESHOLD and pb_ratio > 0: pb_pts = config.PB_RATIO_LOW_PTS
             elif pb_ratio > config.PB_RATIO_HIGH_THRESHOLD: pb_pts = config.PB_RATIO_HIGH_PTS
        score += pb_pts * config.WEIGHT_PB_RATIO
        score_details['pb_ratio'] = {'value': pb_ratio, 'pts': pb_pts, 'weighted_pts': pb_pts * config.WEIGHT_PB_RATIO}

        # Score Price-to-Sales Ratio
        ps_pts = 0 # Default
        if ps_ratio is not None:
             if ps_ratio < config.PS_RATIO_LOW_THRESHOLD and ps_ratio > 0: ps_pts = config.PS_RATIO_LOW_PTS
             elif ps_ratio > config.PS_RATIO_HIGH_THRESHOLD: ps_pts = config.PS_RATIO_HIGH_PTS
        score += ps_pts * config.WEIGHT_PS_RATIO
        score_details['ps_ratio'] = {'value': ps_ratio, 'pts': ps_pts, 'weighted_pts': ps_pts * config.WEIGHT_PS_RATIO}


        # Log the final score and breakdown
        logger.info(f"Scored {ticker} for {target_date_str}: Final Score={score:.2f}, Breakdown={score_details}")

        # Store the calculated score and components
        all_scores.append((
            ticker,
            target_date_str,
            score,
            price_change_pct,
            volume_ratio,
            gemini_sentiment,
            pe_ratio,
            dividend_yield,
            price_vs_ma50_status,
            rsi_value,
            macd_signal_status,
            bbands_signal_status,
            debt_to_equity,
            pb_ratio, # Store P/B ratio
            ps_ratio, # Store P/S ratio
            next_day_open,
            next_day_perf
        ))

    # Insert all calculated scores into the database
    try:
        cursor.executemany("""
            INSERT OR REPLACE INTO daily_scores
            (ticker, date, score, price_change_pct, volume_ratio, avg_sentiment, pe_ratio, dividend_yield, price_vs_ma50, rsi, macd_signal, bbands_signal, debt_to_equity, pb_ratio, ps_ratio, next_day_open_price, next_day_perf_pct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, all_scores) # Added ps_ratio and next day perf columns
        conn.commit()
        logger.info(f"Successfully calculated and stored scores for {len(all_scores)} tickers.")
    except Exception as e:
        conn.rollback()
        logger.exception(f"Error storing calculated scores: {e}") # Log traceback

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
            logger.error(f"Invalid date format '{target_date_str}'. Please use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"No date provided, defaulting to yesterday: {target_date_str}")

    calculate_scores_for_date(target_date_str)
