import yfinance as yf
import requests
# from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer # No longer needed
import sqlite3
import database # To use get_db_connection
import gemini_analyzer # Import the new module
from datetime import datetime, timedelta, date # Add date import
import time
import os
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file BEFORE importing other modules that need them
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env') # Path to .env in root
load_dotenv(dotenv_path=dotenv_path)

import config # Import the config file

# sentiment_analyzer = SentimentIntensityAnalyzer() # No longer needed

def load_tickers_from_file(filename=config.TICKER_LIST_FILE): # Use config
    """Loads tickers from a file, one per line."""
    try:
        with open(filename, 'r') as f:
            tickers = [line.strip() for line in f if line.strip()]
        # --- Limit tickers for testing ---
        limit = 15
        tickers = tickers[:limit]
        print(f"Loaded {len(tickers)} tickers from {filename} (Limited to {limit} for testing)")
        # ---------------------------------
        return tickers
    except FileNotFoundError:
        print(f"Error: Ticker file not found at {filename}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error reading ticker file {filename}: {e}", file=sys.stderr)
        return []

def get_etf_holdings(etf_ticker):
    """
    Placeholder function to fetch ETF holdings.
    Requires implementation using a library or web scraping.
    Returns a list of tickers.
    """
    print(f"TODO: Implement fetching holdings for {etf_ticker}")
    # Example: return ['AAPL', 'MSFT', ...]
    return []

def update_company_list():
    """
    Fetches company list from file, gets info/price, applies filter,
    and updates the database.
    """
    conn = database.get_db_connection()
    cursor = conn.cursor()
    print("Updating company list from file and applying filters...")

    source_tickers = load_tickers_from_file()
    if not source_tickers:
        conn.close()
        return []

    # --- Debugging ---
    print(f"Debug: Type of source_tickers: {type(source_tickers)}")
    if isinstance(source_tickers, list):
        print(f"Debug: First 5 tickers loaded: {source_tickers[:5]}")
    else:
        print(f"Debug: source_tickers is not a list!")
    # --- End Debugging ---

    valid_tickers = set()
    processed_count = 0
    skipped_count = 0

    for ticker in source_tickers:
        processed_count += 1
        print(f"Processing ticker {processed_count}/{len(source_tickers)}: {ticker}")
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
                print(f"  Skipping {ticker}: Price ({current_price}) is {reason}.")
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
                print(f"  Skipping {ticker}: Sector '{sector}' not in allowed list {config.ALLOWED_SECTORS}.")
                skipped_count += 1
                continue

            print(f"  Adding/Updating: {ticker} - {name} (Sector: {sector}, Price: {current_price:.2f})")
            cursor.execute(
                "INSERT OR REPLACE INTO companies (ticker, name, sector) VALUES (?, ?, ?)",
                (ticker, name, sector)
            )
            valid_tickers.add(ticker)
            time.sleep(0.2) # Shorter delay as we filter more

        except Exception as e:
            print(f"  Error processing {ticker}: {e}")
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
    print(f"Company list update complete. Processed: {processed_count}, Added/Updated: {len(valid_tickers)}, Skipped (filter/error): {skipped_count}")
    return sorted(list(valid_tickers))

def fetch_price_history(ticker, period="6mo"): # Fetch 6 months history
    """Fetches historical price data for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        # Ensure columns exist
        if 'Close' not in hist.columns or 'Volume' not in hist.columns:
             print(f"Warning: Missing 'Close' or 'Volume' for {ticker}")
             return []
        prices = []
        for index, row in hist.iterrows():
            prices.append({
                'date': index.strftime('%Y-%m-%d'),
                'close_price': row['Close'],
                'volume': int(row['Volume']) if row['Volume'] else 0
            })
        return prices
    except Exception as e:
        print(f"Error fetching price history for {ticker}: {e}")
        return []

def fetch_news(ticker, company_name, days=3):
    """Fetches news articles for a ticker using Brave Search API."""
    query = f'"{company_name}" OR "{ticker}" stock news' # More specific query
    print(f"  Brave search query: {query}")
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': BRAVE_API_KEY
    }
    params = {
        'q': query,
        # 'freshness': f'{days}d', # Removing freshness to broaden search
        'text_decorations': 'false',
        'spellcheck': 'false',
        'country': 'us', # Explicitly add country
        'search_lang': 'en', # Explicitly add language
    }
    try:
        response = requests.get(BRAVE_SEARCH_ENDPOINT, headers=headers, params=params)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        articles = []
        results_found = False
        if 'results' in data and data['results']:
            for item in data['results']:
                if item.get('type') == 'news':
                    results_found = True
                    article = item.get('news', {})
                    meta = article.get('meta_url', {})
                    articles.append({
                        'url': article.get('url'),
                        'title': article.get('title'),
                        'snippet': article.get('snippet'),
                        'published_date': article.get('date'), # Assuming Brave provides usable date string
                        'source': meta.get('hostname')
                    })
        if not results_found:
            print(f"  Brave API returned successfully but found 0 news results for {ticker}.")
            # Consider logging data['query'] or other response parts for debugging
            # print(f"  Brave API Response Data: {data}")
        return articles
    except requests.exceptions.RequestException as e:
        print(f"  Error fetching news for {ticker} from Brave API (RequestException): {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Brave API Response Status: {e.response.status_code}")
            try:
                print(f"  Brave API Response Body: {e.response.json()}") # Try parsing as JSON
            except requests.exceptions.JSONDecodeError:
                print(f"  Brave API Response Body (non-JSON): {e.response.text}")
        return []
    except Exception as e:
        # Catch other potential errors (e.g., JSON parsing if response is not JSON)
        print(f"  Unexpected error processing Brave API response for {ticker}: {e}")
        return []


def analyze_sentiment(text):
    """Analyzes sentiment of a text snippet using VADER."""
    if not text:
        return 0.0
    vs = sentiment_analyzer.polarity_scores(text)
    return vs['compound'] # Compound score ranges from -1 (most negative) to +1 (most positive)

def update_data_for_ticker(ticker):
    """Fetches and updates all data for a single ticker."""
    print(f"--- Processing {ticker} ---")
    conn = database.get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()

    # 1. Fetch and store price history
    print(f"  Fetching price history for {ticker}...")
    prices = fetch_price_history(ticker, period="6mo") # Fetch 6 months for charting/SMA
    if prices:
        for price_data in prices:
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO price_history (ticker, date, close_price, volume) VALUES (?, ?, ?, ?)",
                    (ticker, price_data['date'], price_data['close_price'], price_data['volume'])
                )
            except sqlite3.IntegrityError:
                 print(f"  Warning: Duplicate price data for {ticker} on {price_data['date']}")
            except Exception as e:
                 print(f"  Error inserting price data for {ticker} on {price_data['date']}: {e}")
        conn.commit()
        print(f"  Stored {len(prices)} price points for {ticker}.")
    else:
        print(f"  No price history found or error fetching for {ticker}.")


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
        cursor.execute(
            """
            INSERT OR REPLACE INTO news_articles
            (ticker, url, title, snippet, published_date, fetched_date, sentiment_score, gemini_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                placeholder_url, # Unique placeholder URL
                placeholder_title,
                None, # Snippet no longer directly stored
                analysis_date_str, # Use analysis date
                now_iso, # Fetched/Analysis timestamp
                analysis_result.get('sentiment_score', 0.0),
                analysis_result.get('summary', 'Analysis failed.')
            )
        )
        conn.commit()
        print(f"  Stored Gemini analysis for {ticker}.")
    except Exception as e:
        print(f"  Error inserting Gemini analysis for {ticker}: {e}")
        conn.rollback() # Rollback on error

    conn.close()
    print(f"--- Finished processing {ticker} ---")
    time.sleep(1) # Add delay between processing tickers

def run_data_fetch_pipeline():
    """Runs the full data fetching and processing pipeline."""
    print("Starting data fetch pipeline...")
    print("Ensuring database schema is up-to-date...")
    database.init_db() # Explicitly ensure DB schema exists before loading tickers
    print("Database schema check complete.")

    tickers_to_process = update_company_list()

    if not tickers_to_process:
        print("No tickers found to process. Exiting.")
        return

    print(f"Processing data for {len(tickers_to_process)} tickers...")
    for ticker in tickers_to_process:
        update_data_for_ticker(ticker)

    print("Data fetch pipeline finished.")

if __name__ == '__main__':
    run_data_fetch_pipeline()
    # TODO: Implement scoring logic calculation after data fetching
    # TODO: Implement scheduling using the 'schedule' library
