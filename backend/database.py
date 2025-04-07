import sqlite3
import os

# Define database path relative to the project root (one level up from backend)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(PROJECT_ROOT, 'stocks.db')

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Return rows as dictionary-like objects
    return conn

def init_db():
    """Initializes the database schema if tables don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # --- Create Tables ---

    # Companies Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT NOT NULL
        )
    ''')

    # News Articles Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL, -- URL might become less relevant if using Gemini summary
            title TEXT NOT NULL, -- Title might become less relevant
            snippet TEXT, -- Snippet might become less relevant
            published_date TEXT NOT NULL, -- Date of original article if found, otherwise analysis date
            fetched_date TEXT NOT NULL, -- Store as ISO 8601 string (Date of analysis)
            sentiment_score REAL, -- Store Gemini sentiment score
            gemini_summary TEXT, -- Store the summary generated by Gemini
            bullish_points TEXT, -- Store JSON list of bullish points
            bearish_points TEXT, -- Store JSON list of bearish points
            FOREIGN KEY (ticker) REFERENCES companies (ticker)
        )
    ''')
    # Index for faster lookups by ticker and date
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_news_ticker_date ON news_articles (ticker, published_date DESC);
    ''')


    # Price History Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL, -- Store as YYYY-MM-DD
            open_price REAL, -- Added Open Price
            close_price REAL NOT NULL,
            volume INTEGER,
            PRIMARY KEY (ticker, date),
            FOREIGN KEY (ticker) REFERENCES companies (ticker)
        )
    ''')

    # Daily Scores Table (to store the calculated score for highlighting)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_scores (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL, -- Store as YYYY-MM-DD
            score REAL NOT NULL,
            price_change_pct REAL,
            volume_ratio REAL,
            avg_sentiment REAL, -- Holds Gemini sentiment score
            pe_ratio REAL, -- Add P/E ratio
            dividend_yield REAL, -- Add Dividend Yield
            price_vs_ma50 TEXT, -- Add MA comparison ('above', 'below', 'N/A')
            rsi REAL, -- Add RSI value
            macd_signal TEXT, -- Add MACD signal ('bullish_cross', 'bearish_cross', 'neutral')
            bbands_signal TEXT, -- Add Bollinger Bands signal ('cross_lower', 'cross_upper', 'neutral')
            debt_to_equity REAL, -- Add Debt-to-Equity ratio
            next_day_open_price REAL, -- Store next day's open price for comparison
            next_day_perf_pct REAL, -- Store performance (Close[D] -> Open[D+1]) %
            pb_ratio REAL, -- Add Price-to-Book ratio
            PRIMARY KEY (ticker, date),
            FOREIGN KEY (ticker) REFERENCES companies (ticker)
        )
    ''')
    # Index for faster lookups by date and score
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_scores_date_score ON daily_scores (date DESC, score DESC);
    ''')

    # Portfolio Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date TEXT NOT NULL, -- Store as YYYY-MM-DD
            FOREIGN KEY (ticker) REFERENCES companies (ticker)
        )
    ''')

    # --- Add open_price column to price_history if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE price_history ADD COLUMN open_price REAL")
        print("Added open_price column to price_history table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("open_price column already exists in price_history.")
        else: raise e

    # Performance Analysis Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_analysis (
            analysis_date TEXT NOT NULL, -- Date the analysis was run (YYYY-MM-DD)
            score_bucket TEXT NOT NULL, -- e.g., "Score >= 4"
            avg_next_day_perf REAL, -- Average next_day_perf_pct for this bucket
            count INTEGER NOT NULL, -- Number of data points in this bucket for the analyzed period
            PRIMARY KEY (analysis_date, score_bucket)
        )
    ''')


    # --- Add gemini_summary column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE news_articles ADD COLUMN gemini_summary TEXT")
        print("Added gemini_summary column to news_articles table.")
    except sqlite3.OperationalError as e:
        # Ignore error if column already exists
        if "duplicate column name" in str(e):
            print("gemini_summary column already exists.")
        else:
            raise e # Reraise other operational errors

    # --- Add pe_ratio column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN pe_ratio REAL")
        print("Added pe_ratio column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("pe_ratio column already exists.")
        else: raise e

    # --- Add dividend_yield column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN dividend_yield REAL")
        print("Added dividend_yield column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("dividend_yield column already exists.")
        else: raise e

    # --- Add price_vs_ma50 column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN price_vs_ma50 TEXT")
        print("Added price_vs_ma50 column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("price_vs_ma50 column already exists.")
        else: raise e

    # --- Add rsi column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN rsi REAL")
        print("Added rsi column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("rsi column already exists.")
        else: raise e

    # --- Add bullish_points column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE news_articles ADD COLUMN bullish_points TEXT")
        print("Added bullish_points column to news_articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("bullish_points column already exists.")
        else: raise e

    # --- Add bearish_points column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE news_articles ADD COLUMN bearish_points TEXT")
        print("Added bearish_points column to news_articles table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("bearish_points column already exists.")
        else: raise e

    # --- Add macd_signal column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN macd_signal TEXT")
        print("Added macd_signal column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("macd_signal column already exists.")
        else: raise e

    # --- Add bbands_signal column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN bbands_signal TEXT")
        print("Added bbands_signal column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("bbands_signal column already exists.")
        else: raise e

    # --- Add debt_to_equity column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN debt_to_equity REAL")
        print("Added debt_to_equity column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("debt_to_equity column already exists.")
        else: raise e

    # --- Add next_day_open_price column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN next_day_open_price REAL")
        print("Added next_day_open_price column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("next_day_open_price column already exists.")
        else: raise e

    # --- Add next_day_perf_pct column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN next_day_perf_pct REAL")
        print("Added next_day_perf_pct column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("next_day_perf_pct column already exists.")
        else: raise e

    # --- Add pb_ratio column if it doesn't exist ---
    try:
        cursor.execute("ALTER TABLE daily_scores ADD COLUMN pb_ratio REAL")
        print("Added pb_ratio column to daily_scores table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("pb_ratio column already exists.")
        else: raise e

    conn.commit()
    conn.close()
    print("Database schema initialization/update complete.")

if __name__ == '__main__':
    # Allow running this script directly to initialize the DB
    print(f"Initializing database '{DATABASE_NAME}'...")
    init_db()
