import os
from dotenv import load_dotenv

# Load .env file from project root (one level up from this config file's directory)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    print("Warning: .env file not found at expected location:", dotenv_path)


# Configuration settings for the Stock Analyzer application

# --- API Keys ---
# Read from environment variables (loaded from .env by load_dotenv above)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
BRAVE_API_KEY = os.getenv('BRAVE_API_KEY')
GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-1.5-flash-latest') # Default if not set

# --- Data Fetching ---
TICKER_LIST_FILE = "backend/sp600_tickers.txt"
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

# RSI (Relative Strength Index)
RSI_PERIOD = 14
RSI_OVERSOLD_THRESHOLD = 30 # Below this is considered oversold (potential buy signal)
RSI_OVERBOUGHT_THRESHOLD = 70 # Above this is considered overbought (potential sell signal)
RSI_OVERSOLD_PTS = 1
RSI_OVERBOUGHT_PTS = -1

# --- Scoring Weights (Adjust to prioritize factors) ---
WEIGHT_SENTIMENT = 1.0
WEIGHT_MOMENTUM = 1.0
WEIGHT_VOLUME = 1.0
WEIGHT_PE_RATIO = 1.0
WEIGHT_DIVIDEND = 1.0
WEIGHT_MA50 = 1.0
WEIGHT_RSI = 1.0

# --- Portfolio ---
PORTFOLIO_SELL_SCORE_THRESHOLD = -1 # Suggest selling if score drops below this

# --- Scheduling ---
SCHEDULE_TIME = "19:00" # Time to run daily (e.g., 7:00 PM)

# --- API Endpoints ---
BRAVE_SEARCH_ENDPOINT = 'https://api.search.brave.com/res/v1/web/search' # Using WEB Search endpoint
