import sqlite3
from dotenv import load_dotenv # Import load_dotenv
import os
import sys

# Load environment variables from .env file BEFORE importing other modules that need them
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Path to .env in root
load_dotenv(dotenv_path=dotenv_path)

import database # To use get_db_connection
from datetime import datetime, timedelta
import pandas as pd # Using pandas for easier calculations
import pandas_ta as ta # Import pandas-ta
import config # Import the config file

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
        price_change_pct = None
        volume_ratio = None
        gemini_sentiment = None
        pe_ratio = None
        dividend_yield = None
        price_vs_ma50_status = 'N/A' # Initialize MA status
        rsi_value = None # Initialize RSI value

        # --- Fetch Fundamental Data (P/E, Dividend Yield) ---
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
        if gemini_sentiment > 0.15: # Slightly higher threshold for Gemini? Tunable.
            score += config.SENTIMENT_POSITIVE_PTS
        elif gemini_sentiment < -0.15: # Tunable.
             score += config.SENTIMENT_NEGATIVE_PTS
        else:
            score += config.SENTIMENT_NEUTRAL_PTS

        # 2. Calculate Price Momentum & Volume Ratio (Keep this logic)
        cursor.execute("""
            SELECT date, close_price, volume
            FROM price_history
            WHERE ticker = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """, (ticker, price_start_date_db_fetch, target_date_str)) # Use wider fetch date range
        price_rows = cursor.fetchall()

        # Now perform calculations if we have *at least* the minimum days needed for momentum
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
                    if price_change_pct > config.PRICE_MOMENTUM_THRESHOLD_PCT: # Use config
                        score += config.PRICE_POSITIVE_PTS # Use config
                    elif price_change_pct < 0:
                        score += config.PRICE_NEGATIVE_PTS # Use config
                    else:
                        score += config.PRICE_NEUTRAL_PTS # Use config
                else:
                    score += config.PRICE_NEUTRAL_PTS # Use config
            else:
                 score += config.PRICE_NEUTRAL_PTS # Use config

            # Volume Ratio
            if len(df) >= config.VOLUME_AVG_DAYS + 1: # Use config
                avg_volume = df['volume'].iloc[-1 - config.VOLUME_AVG_DAYS:-1].mean() # Use config
                latest_volume = df['volume'].iloc[-1]
                if avg_volume > 0: # Avoid division by zero
                    volume_ratio = latest_volume / avg_volume
                    if volume_ratio > config.VOLUME_RATIO_THRESHOLD: # Use config
                        score += config.VOLUME_HIGH_PTS # Use config
                    else:
                        score += config.VOLUME_NORMAL_PTS # Use config
                else:
                    score += config.VOLUME_NORMAL_PTS # Use config
            else:
                score += config.VOLUME_NORMAL_PTS # Use config

            # 3. Calculate 50-day SMA and compare
            if len(df) >= config.MA_PERIOD:
                df['SMA_50'] = df['close_price'].rolling(window=config.MA_PERIOD).mean()
                latest_price = df['close_price'].iloc[-1]
                latest_sma = df['SMA_50'].iloc[-1]
                if not pd.isna(latest_sma): # Check if SMA calculation was successful
                    if latest_price > latest_sma:
                        score += config.MA_PRICE_ABOVE_PTS
                        price_vs_ma50_status = 'above'
                    elif latest_price < latest_sma:
                        score += config.MA_PRICE_BELOW_PTS
                        price_vs_ma50_status = 'below'
                    # No points if exactly equal
                else:
                    print(f"  SMA calculation resulted in NaN for {ticker}.")
                    price_vs_ma50_status = 'N/A' # Keep as N/A if SMA is NaN
            else:
                 print(f"  Not enough data for {config.MA_PERIOD}-day SMA for {ticker}.")
                 price_vs_ma50_status = 'N/A' # Keep as N/A

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
                    # Score RSI
                    if rsi_value < config.RSI_OVERSOLD_THRESHOLD:
                        score += config.RSI_OVERSOLD_PTS
                    elif rsi_value > config.RSI_OVERBOUGHT_THRESHOLD:
                        score += config.RSI_OVERBOUGHT_PTS
                    # No points for neutral RSI
                else:
                    print(f"  RSI calculation failed or resulted in NaN for {ticker}.")
                    rsi_value = None # Ensure it's None if calc failed
            else:
                print(f"  Not enough data for {config.RSI_PERIOD}-day RSI for {ticker}.")
                rsi_value = None

        else:
            print(f"  Not enough price history data for {ticker} to calculate momentum/volume/MA/RSI.")
            # Assign neutral scores if not enough data
            score += config.PRICE_NEUTRAL_PTS # Use config
            score += config.VOLUME_NORMAL_PTS # Use config
            price_vs_ma50_status = 'N/A' # Ensure status is N/A

        # 4. Score P/E Ratio
        if pe_ratio is not None:
            if pe_ratio < config.PE_LOW_THRESHOLD and pe_ratio > 0: # Use config & Ensure P/E is positive
                score += config.PE_LOW_PTS # Use config
            elif pe_ratio > config.PE_HIGH_THRESHOLD: # Use config
                score += config.PE_HIGH_PTS # Use config
            else:
                score += config.PE_NEUTRAL_PTS_PE # Use config
        else:
            score += config.PE_NEUTRAL_PTS_PE # Use config

        # 5. Score Dividend Yield
        if dividend_yield is not None and dividend_yield > config.DIV_YIELD_THRESHOLD: # Use config
            score += config.DIV_YIELD_PTS # Use config
        # No points added or subtracted otherwise for dividend yield


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
            rsi_value # Store RSI value
        ))

    # Insert all calculated scores into the database
    try:
        cursor.executemany("""
            INSERT OR REPLACE INTO daily_scores
            (ticker, date, score, price_change_pct, volume_ratio, avg_sentiment, pe_ratio, dividend_yield, price_vs_ma50, rsi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, all_scores) # Added rsi
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
