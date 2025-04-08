import os
from dotenv import load_dotenv

# Define PROJECT_ROOT based on this file's location BEFORE loading .env
# Assumes config.py is in backend/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env file from project root
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    # Try loading from one level up if running script directly from backend? Less ideal.
    dotenv_path_alt = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(dotenv_path_alt):
         load_dotenv(dotenv_path=dotenv_path_alt)
         print(f"Warning: Loaded .env from {dotenv_path_alt}")
    else:
        print(f"Warning: .env file not found at expected location: {dotenv_path}")


# Configuration settings for the Stock Analyzer application

# --- API Keys ---
# Read from environment variables (loaded from .env by load_dotenv above)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY')
GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-1.5-flash-latest') # Default if not set

# --- Data Fetching ---
# Use absolute path based on project root
TICKER_LIST_FILE = os.path.join(PROJECT_ROOT, "backend", "sp600_tickers.txt") # Original
# TICKER_LIST_FILE = os.path.join(PROJECT_ROOT, "backend", "sp600_tickers_test.txt") # Using test file
MIN_PRICE_FILTER = 1.00 # Exclude stocks below $1.00
MAX_PRICE_FILTER = 50.00 # Exclude stocks above $50.00
ALLOWED_SECTORS = ["Technology", "Healthcare", "Industrials"] # Filter for these sectors (Note: Using Industrials instead of Defense as yfinance often uses broader categories)

# --- Scoring Parameters (Tunable) ---
# NEWS_SENTIMENT_DAYS = 3     # Look at news from the last X days (Currently using Gemini daily analysis)
PRICE_MOMENTUM_DAYS = 5     # Look at price change over the last X trading days
VOLUME_AVG_DAYS = 20        # Calculate average volume over the last X trading days

PRICE_MOMENTUM_THRESHOLD_PCT = 3.0 # Pct price increase needed for positive momentum points
VOLUME_RATIO_THRESHOLD = 1.5       # Volume ratio needed for positive volume points

# Points
SENTIMENT_POSITIVE_PTS = 2
SENTIMENT_NEUTRAL_PTS = 0
SENTIMENT_NEGATIVE_PTS = -1 # Penalize negative sentiment slightly

PRICE_POSITIVE_PTS = 1
PRICE_NEUTRAL_PTS = 0
PRICE_NEGATIVE_PTS = -1 # Penalize negative momentum

VOLUME_HIGH_PTS = 1
VOLUME_NORMAL_PTS = 0

# P/E Ratio (Lower is often better, but depends on sector; using simple thresholds)
PE_LOW_THRESHOLD = 15 # Below this gets points
PE_HIGH_THRESHOLD = 30 # Above this loses points
PE_LOW_PTS = 1
PE_NEUTRAL_PTS_PE = 0 # Renamed to avoid conflict
PE_HIGH_PTS = -1

# Dividend Yield (Higher is better for income)
DIV_YIELD_THRESHOLD = 0.02 # Above 2% gets points
DIV_YIELD_PTS = 1

# Moving Average (Price vs. 50-day SMA)
MA_PERIOD = 50
MA_PRICE_ABOVE_PTS = 1
MA_PRICE_BELOW_PTS = -1

# RSI (Relative Strength Index) - Graded Points
RSI_PERIOD = 14
RSI_VERY_OVERSOLD_THRESHOLD = 20 # Below this is very oversold
RSI_OVERSOLD_THRESHOLD = 30      # Below this is oversold
RSI_OVERBOUGHT_THRESHOLD = 70    # Above this is overbought
RSI_VERY_OVERBOUGHT_THRESHOLD = 80 # Above this is very overbought

RSI_VERY_OVERSOLD_PTS = 2
RSI_OVERSOLD_PTS = 1
RSI_NEUTRAL_PTS = 0
RSI_OVERBOUGHT_PTS = -1
RSI_VERY_OVERBOUGHT_PTS = -2


# MACD (Moving Average Convergence Divergence)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
MACD_CROSS_BULLISH_PTS = 1
MACD_CROSS_BEARISH_PTS = -1

# Bollinger Bands (BBands)
BBANDS_PERIOD = 20
BBANDS_STDDEV = 2.0
BBANDS_LOWER_CROSS_PTS = 1 # Price crossing below lower band
BBANDS_UPPER_CROSS_PTS = -1 # Price crossing above upper band

# Debt-to-Equity Ratio
DE_RATIO_LOW_THRESHOLD = 0.5 # Below this is good
DE_RATIO_HIGH_THRESHOLD = 1.5 # Above this is potentially risky
DE_RATIO_LOW_PTS = 1
DE_RATIO_HIGH_PTS = -1

# Price-to-Book (P/B) Ratio
PB_RATIO_LOW_THRESHOLD = 1.0 # Below this is good
PB_RATIO_HIGH_THRESHOLD = 3.0 # Above this might be high (varies by industry)
PB_RATIO_LOW_PTS = 1
PB_RATIO_HIGH_PTS = -1

# Price-to-Sales (P/S) Ratio
PS_RATIO_LOW_THRESHOLD = 1.0 # Below this is generally good
PS_RATIO_HIGH_THRESHOLD = 4.0 # Above this might be high (varies by industry)
PS_RATIO_LOW_PTS = 1
PS_RATIO_HIGH_PTS = -1

# 200-day Moving Average (Price vs. MA200)
MA200_PRICE_ABOVE_PTS = 1
MA200_PRICE_BELOW_PTS = -1

# Average True Range (ATR) - 14 day default
ATR_PERIOD = 14
# Thresholds might need tuning based on typical ATR values for the index/price range
# Example: Score positively if ATR is below 5% of price, negatively if above 15%?
# Let's use simpler absolute thresholds for now, assuming prices around $1-$50
ATR_LOW_THRESHOLD = 0.5  # Below this = low volatility
ATR_HIGH_THRESHOLD = 2.0 # Above this = high volatility
ATR_LOW_PTS = 1
ATR_HIGH_PTS = -1

# --- Scoring Weights (Adjust to prioritize factors) ---
WEIGHT_SENTIMENT = 1.0
WEIGHT_MOMENTUM = 1.0
WEIGHT_VOLUME = 1.0
WEIGHT_PE_RATIO = 1.0
WEIGHT_DIVIDEND = 1.0
WEIGHT_MA50 = 1.0
WEIGHT_RSI = 1.0
WEIGHT_MACD = 1.0
WEIGHT_BBANDS = 1.0
WEIGHT_DE_RATIO = 1.0
WEIGHT_PB_RATIO = 1.0
WEIGHT_PS_RATIO = 1.0
WEIGHT_MA200 = 1.0
WEIGHT_ATR = 1.0 # Add weight for ATR

# --- Portfolio ---
PORTFOLIO_SELL_SCORE_THRESHOLD = -1 # Suggest selling if score drops below this

# --- Scheduling ---
SCHEDULE_TIME = "19:00" # Time to run daily (e.g., 7:00 PM)
ANALYSIS_HISTORY_DAYS = 90 # Default days for performance analysis

# --- API Endpoints ---
BRAVE_SEARCH_ENDPOINT = 'https://api.search.brave.com/res/v1/web/search' # Using WEB Search endpoint

# --- Logging ---
LOG_FILE_SCHEDULER = "logs/scheduler.log"
LOG_FILE_FETCHER = "logs/fetcher.log"
LOG_FILE_SCORER = "logs/scorer.log"
LOG_FILE_ANALYSIS = "logs/analysis.log"
LOG_FILE_WEB = "logs/web.log" # For Flask/Gunicorn logs
LOG_MAX_BYTES = 10 * 1024 * 1024 # 10 MB
LOG_BACKUP_COUNT = 5
