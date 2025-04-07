import yfinance as yf
import requests
import sqlite3
import database # To use get_db_connection
import gemini_analyzer # Import the new module
from datetime import datetime, timedelta, date # Add date import
import time
import os
import json # Import json module
import sys # Import sys
# Removed dotenv imports, as config.py now handles it
import config # Import the config file
from log_setup import setup_logger # Import logger setup

# --- Logger ---
logger = setup_logger('data_fetcher', config.LOG_FILE_FETCHER)
# -------------

# sentiment_analyzer = SentimentIntensityAnalyzer() # No longer needed

def load_tickers_from_file(filename=config.TICKER_LIST_FILE): # Use config
    """Loads tickers from a file, one per line."""
    logger.debug(f"Attempting to load tickers from: {filename}")
    try:
        with open(filename, 'r') as f:
            tickers = [line.strip() for line in f if line.strip()]
        logger.info(f"Loaded {len(tickers)} tickers from {filename}")
        return tickers
    except FileNotFoundError:
        logger.error(f"Ticker file not found at {filename}")
        return []
    except Exception as e:
        logger.exception(f"Error reading ticker file {filename}: {e}")
        return []

def get_etf_holdings(etf_ticker):
    """
    Placeholder function to fetch ETF holdings.
    Requires implementation using a library or web scraping.
    Returns a list of tickers.
    """
    logger.warning(f"Placeholder function get_etf_holdings called for {etf_ticker}, needs implementation.")
    # Example: return ['AAPL', 'MSFT', ...]
    return []

def update_company_list():
    """
    Fetches company list from file, gets info/price, applies filter,
    and updates the database.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    logger.info("Starting company list update and filtering...")

    source_tickers = load_tickers_from_file()
    if not source_tickers:
        logger.error("No source tickers loaded from file.")
        conn.close()
        return []

    # --- Debugging ---
    logger.debug(f"Source tickers type: {type(source_tickers)}")
    if isinstance(source_tickers, list):
        logger.debug(f"First 5 source tickers: {source_tickers[:5]}")
    # --- End Debugging ---

    valid_tickers = set()
    processed_count = 0
    skipped_count = 0

    for ticker in source_tickers:
        processed_count += 1
        logger.debug(f"Processing ticker {processed_count}/{len(source_tickers)}: {ticker}")
        try:
            stock = yf.Ticker(ticker)
            stock_info = stock.info

            # Apply Price Filter
            current_price = stock_info.get('currentPrice') or stock_info.get('previousClose')
            if current_price is None:
                 # Try fetching last close price if currentPrice is missing
                 hist = stock.history(period="1d")
                 if not hist.empty:
                     current_price = hist['Close'].iloc[-1]

            # Use filters from config
            if current_price is None or not (config.MIN_PRICE_FILTER <= current_price < config.MAX_PRICE_FILTER):
                price_reason = f"below ${config.MIN_PRICE_FILTER:.2f}" if (current_price is not None and current_price < config.MIN_PRICE_FILTER) else f"above ${config.MAX_PRICE_FILTER:.2f}"
                unavailable_reason = "unavailable" if current_price is None else ""
                reason = unavailable_reason or price_reason
                logger.info(f"Skipping {ticker} due to price filter: Price=({current_price}), Reason='{reason}'.")
                skipped_count += 1
                # Optional: Remove from DB if it exists but no longer qualifies
                # cursor.execute("DELETE FROM companies WHERE ticker = ?", (ticker,))
                continue

            # Get required info
            name = stock_info.get('longName', f"{ticker} Name Not Found")
            # Determine sector - yfinance info might have 'sector', 'industry', etc.
            # Using 'industry' as a fallback if 'sector' is missing. Could be refined.
            sector = stock_info.get('sector', stock_info.get('industry', 'Unknown'))

            # Apply Sector Filter
            if sector not in config.ALLOWED_SECTORS:
                logger.info(f"Skipping {ticker} due to sector filter: Sector='{sector}'.")
                skipped_count += 1
                continue

            logger.info(f"Adding/Updating company in DB: {ticker} - {name} (Sector: {sector}, Price: {current_price:.2f})")
            cursor.execute(
                "INSERT OR REPLACE INTO companies (ticker, name, sector) VALUES (?, ?, ?)",
                (ticker, name, sector)
            )
            valid_tickers.add(ticker)
            time.sleep(0.2) # Shorter delay as we filter more

        except Exception as e:
            logger.exception(f"Error processing ticker {ticker} during company update: {e}") # Log traceback
            skipped_count += 1

    # Optional: Remove companies from DB that are no longer in the filtered list
    # This requires getting the current list from DB and comparing
    # cursor.execute("SELECT ticker FROM companies")
    # db_tickers = {row['ticker'] for row in cursor.fetchall()}
    # tickers_to_remove = db_tickers - valid_tickers
    # if tickers_to_remove:
    #     print(f"Removing {len(tickers_to_remove)} tickers no longer in filtered list...")
    #     cursor.executemany("DELETE FROM companies WHERE ticker = ?", [(t,) for t in tickers_to_remove])

    conn.commit()
    conn.close()
    logger.info(f"Company list update complete. Processed: {processed_count}, Added/Updated: {len(valid_tickers)}, Skipped (filter/error): {skipped_count}")
    return sorted(list(valid_tickers))

def fetch_price_history(ticker, period="6mo"): # Fetch 6 months history
    """Fetches historical price data for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        # Ensure columns exist (also fetch Open for next-day perf calc)
        if not all(col in hist.columns for col in ['Open', 'Close', 'Volume']):
             logger.warning(f"Missing required columns ('Open', 'Close', 'Volume') in history for {ticker}. Columns found: {list(hist.columns)}")
             return []
        prices = []
        for index, row in hist.iterrows():
            prices.append({
                'date': index.strftime('%Y-%m-%d'),
                'open_price': row['Open'], # Add Open price
                'close_price': row['Close'],
                'volume': int(row['Volume']) if row['Volume'] else 0
            })
        return prices
    except Exception as e:
        logger.exception(f"Error fetching price history for {ticker}: {e}") # Log traceback
        return []

def fetch_news(ticker, company_name, days=3):
    """Fetches news articles for a ticker using Brave Search API. DEPRECATED."""
    # This function is now effectively handled within gemini_analyzer.py
    # Kept here for potential future direct use, but marked as deprecated/unused
    logger.warning("Deprecated function fetch_news called; analysis should be handled by gemini_analyzer.")
    return []


def analyze_sentiment(text):
    """Analyzes sentiment of a text snippet using VADER. DEPRECATED."""
    # This function is no longer used as sentiment comes from Gemini
    logger.warning("Deprecated function analyze_sentiment called.")
    return 0.0


def update_data_for_ticker(ticker):
    """Fetches and updates all data for a single ticker."""
    logger.info(f"--- Starting data update for {ticker} ---")
    conn = database.get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    # 1. Fetch and store price history
    logger.debug(f"Fetching price history for {ticker}...")
    prices = fetch_price_history(ticker, period="6mo") # Fetch 6 months for charting/SMA
    if prices:
        # Also add 'open_price' to the INSERT statement
        for price_data in prices:
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO price_history (ticker, date, open_price, close_price, volume) VALUES (?, ?, ?, ?, ?)",
                    (ticker, price_data['date'], price_data['open_price'], price_data['close_price'], price_data['volume'])
                )
            except sqlite3.IntegrityError:
                 logger.warning(f"Duplicate price data for {ticker} on {price_data['date']}. Skipping insert.")
            except Exception as e:
                 logger.exception(f"Error inserting price data for {ticker} on {price_data['date']}: {e}") # Log traceback
        conn.commit()
        logger.info(f"Stored/Updated {len(prices)} price points for {ticker}.")
    else:
        logger.warning(f"No price history found or error fetching for {ticker}.")


    # Get company name from DB for Gemini analysis
    cursor.execute("SELECT name FROM companies WHERE ticker = ?", (ticker,))
    company_row = cursor.fetchone()
    company_name = company_row['name'] if company_row else ticker # Fallback to ticker if name not found

    # 2. Perform Gemini Analysis (Generates query, searches Brave, analyzes results)
    analysis_result = gemini_analyzer.get_analysis_for_stock(ticker, company_name)
    analysis_date_str = date.today().strftime('%Y-%m-%d') # Use today as the date for the analysis entry

    # 3. Store Gemini Analysis Result
    # We store one entry per ticker per day representing the Gemini analysis
    # Use a placeholder URL/Title as they are less relevant now
    placeholder_url = f"gemini_analysis_{ticker}_{analysis_date_str}"
    placeholder_title = f"Gemini Analysis for {ticker} on {analysis_date_str}"

    try:
        # Use INSERT OR REPLACE to update the analysis if run multiple times on the same day
        # Store lists as JSON strings
        bullish_json = json.dumps(analysis_result.get('bullish_points', []))
        bearish_json = json.dumps(analysis_result.get('bearish_points', []))

        cursor.execute(
            """
            INSERT OR REPLACE INTO news_articles
            (ticker, url, title, snippet, published_date, fetched_date, sentiment_score, gemini_summary, bullish_points, bearish_points)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                placeholder_url, # Unique placeholder URL
                placeholder_title,
                None, # Snippet no longer directly stored
                analysis_date_str, # Use analysis date
                now_iso, # Fetched/Analysis timestamp
                analysis_result.get('sentiment_score', 0.0),
                analysis_result.get('summary', 'Analysis failed.'),
                bullish_json,
                bearish_json
            )
        )
        conn.commit()
        logger.info(f"Stored Gemini analysis for {ticker} for date {analysis_date_str}.")
    except Exception as e:
        logger.exception(f"Error inserting Gemini analysis for {ticker} for date {analysis_date_str}: {e}") # Log full traceback
        conn.rollback() # Rollback on error

    conn.close()
    logger.info(f"--- Finished data update for {ticker} ---")
    time.sleep(1) # Add delay between processing tickers

def run_data_fetch_pipeline():
    """Runs the full data fetching and processing pipeline."""
    logger.info("=== Starting Full Data Fetch Pipeline ===")
    logger.info("Ensuring database schema is up-to-date...")
    database.init_db() # Explicitly ensure DB schema exists before loading tickers
    logger.info("Database schema check complete.")

    tickers_to_process = update_company_list()

    if not tickers_to_process:
        logger.warning("No tickers found to process after filtering. Exiting pipeline.")
        return

    logger.info(f"Beginning data update loop for {len(tickers_to_process)} tickers...")
    for i, ticker in enumerate(tickers_to_process):
        logger.info(f"--- Processing ticker {i+1}/{len(tickers_to_process)}: {ticker} ---")
        update_data_for_ticker(ticker)

    logger.info("=== Full Data Fetch Pipeline Finished ===")

if __name__ == '__main__':
    run_data_fetch_pipeline()
    # TODO: Implement scoring logic calculation after data fetching
    # TODO: Implement scheduling using the 'schedule' library
