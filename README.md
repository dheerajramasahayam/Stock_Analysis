# Stock Analyzer Application

This application analyzes stocks from the S&P 600 index, filters them based on price and sector, calculates a composite score based on various technical and fundamental factors (including AI-driven sentiment analysis), provides a web dashboard to view highlighted stocks, manage a personal portfolio, and includes tools for deployment and performance analysis.

## Features

*   **Data Fetching:**
    *   Retrieves S&P 600 tickers from `backend/sp600_tickers.txt`.
    *   Filters tickers based on price (default: $1-$50) and allowed sectors (default: Technology, Healthcare, Industrials) defined in `backend/config.py`.
    *   Fetches 6 months of historical price data (including Open price) using `yfinance`.
    *   Uses Google Gemini (model configurable via `.env`) and Brave Search API to perform AI analysis on recent web search results (combining results from multiple queries) for each stock, generating a summary, bullish points, bearish points, and a sentiment score.
    *   Stores company info, price history, and AI analysis in an SQLite database (`stocks.db`).
*   **Scoring:**
    *   Calculates a daily composite score for each tracked stock based on a weighted combination of:
        *   Price Momentum (5-day change %)
        *   Volume Ratio (vs. 20-day average)
        *   Gemini Sentiment Score
        *   P/E Ratio (Lower is better)
        *   Dividend Yield (Higher is better)
        *   Price vs. 50-day SMA (Above is better)
        *   RSI (14-day) (Oversold is better, Overbought is worse)
        *   MACD Crossover (Bullish cross is better, Bearish cross is worse)
        *   Bollinger Bands Crossover (Crossing lower band is better, crossing upper band is worse)
        *   Debt-to-Equity Ratio (Lower is better)
    *   Weights for each factor are configurable in `backend/config.py`.
    *   Calculates and stores next-day open price and performance percentage (`next_day_perf_pct`) for analysis.
    *   Stores daily scores and indicator signals/values in the database.
    *   Includes detailed logging of the scoring breakdown.
*   **Web Dashboard (Flask):**
    *   Displays highlighted stocks, sorted by score by default.
    *   Shows all calculated indicators (Price vs MA50, RSI, MACD Signal, BBands Signal, Debt/Equity) on stock cards.
    *   Allows filtering displayed stocks by sector.
    *   Allows sorting displayed stocks by various criteria.
    *   Shows detailed view with price chart, AI summary, and AI-identified bullish/bearish points when a stock card is clicked.
*   **Portfolio Management:**
    *   Allows users to add/delete personal stock holdings (ticker, quantity, purchase price, date).
    *   Displays current portfolio with Gain/Loss % based on the latest fetched price.
    *   Provides a basic "Consider Sell" suggestion if a holding's score drops below a configurable threshold.
*   **Performance Analysis (`backend/analysis.py`):**
    *   Analyzes historical correlation between scores and next-day performance.
    *   Groups scores into buckets and calculates average performance per bucket.
    *   Stores analysis results daily in the `performance_analysis` table.
*   **Scheduling:**
    *   Includes a scheduler (`backend/scheduler.py`) to automate daily data fetching, scoring, and performance analysis (default: 7:00 PM for data/scoring, 8:00 PM for analysis).
*   **Configuration:**
    *   Centralized configuration in `backend/config.py`.
    *   API keys (Gemini, Brave) and Gemini Model Name are read from environment variables (loaded from `.env` file via `python-dotenv`). An example `.env.example` is provided.
*   **Deployment Ready:**
    *   Includes `requirements.txt` for dependencies.
    *   Includes `.gitignore` to exclude sensitive/unnecessary files.
    *   Includes example `systemd` service files (`stockapp-web.service`, `stockapp-scheduler.service`) for managing the web app (via Gunicorn) and the scheduler *without* a virtual environment. Assumes user-wide package installation.
    *   Includes a basic deployment script (`deploy.sh`) adapted for user-wide package installation.
    *   Includes an example Nginx configuration (`stockanalyzer.nginx`) for reverse proxy setup.

## Setup and Running Locally

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/dheerajramasahayam/Stock_Analysis.git
    cd Stock_Analysis
    ```
2.  **Install Python 3:** Ensure you have a compatible Python 3 version installed (e.g., 3.10+).
3.  **Install dependencies (User-wide):**
    ```bash
    python3 -m pip install --upgrade pip
    python3 -m pip install --user -r requirements.txt
    ```
    *Note: If executables like `gunicorn` or `flask` aren't found later, you might need to add the user's local bin directory to your system's PATH (e.g., `export PATH="$HOME/.local/bin:$PATH"` in your `~/.bashrc` or `~/.profile`).*
4.  **Create and Configure `.env` file:**
    *   Copy the example: `cp .env.example .env`
    *   Edit the `.env` file and add your actual API keys:
        ```dotenv
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
        BRAVE_API_KEY="YOUR_BRAVE_API_KEY_HERE"
        # Optionally change the model
        # GEMINI_MODEL_NAME="gemini-1.5-flash-latest"
        ```
5.  **Initialize Database & Fetch Initial Data:**
    *   Run the database setup:
        ```bash
        python3 backend/database.py
        ```
    *   Run the data fetcher (this will take time, especially the first time):
        ```bash
        python3 backend/data_fetcher.py
        ```
    *   Run the scorer for the first time (calculates score for *yesterday*):
        ```bash
        python3 backend/scorer.py
        ```
    *   (Optional) Run scorer for *today* to have current data visible immediately:
        ```bash
        # Replace YYYY-MM-DD with today's date
        python3 backend/scorer.py YYYY-MM-DD
        ```
6.  **Run the Web Application:**
    ```bash
    # Ensure flask command is available (might be in ~/.local/bin)
    flask --app backend/app run --host=0.0.0.0
    ```
    *   Access the dashboard from your browser at `http://localhost:5000` or `http://<your-local-ip>:5000`. The `--host=0.0.0.0` makes it accessible on your local network.
7.  **(Optional) Run the Scheduler:**
    To run the daily updates automatically, stop the Flask app (Ctrl+C) and run the scheduler instead (it needs to run continuously):
    ```bash
    python3 backend/scheduler.py
    ```
    *Note: The web app will not be accessible while only the scheduler is running.*

## Configuration (`backend/config.py`)

This file contains settings for:
*   API Keys & Model Name (read from environment via `.env`)
*   Data fetching parameters (ticker list file, price filters, allowed sectors)
*   Scoring parameters (indicator periods, thresholds, points)
*   Scoring weights for each factor
*   Portfolio sell threshold
*   Scheduler time
*   API endpoints

## Deployment

Refer to `deploy.sh`, `stockapp-web.service`, `stockapp-scheduler.service`, and `stockanalyzer.nginx` for deployment examples using systemd and Gunicorn on a Linux server (adapted for user-wide package installation). Remember to:
*   Set environment variables on the server (e.g., using the `EnvironmentFile` directive in the `.service` files pointing to an `.env` file in the project root).
*   Customize paths and user/group in the service files and `deploy.sh`.
*   Ensure the user's `$HOME/.local/bin` is in the PATH used by systemd or use full paths in `ExecStart`.
*   Place service files in `/etc/systemd/system/`.
*   Enable and start services using `systemctl`.
*   Configure a reverse proxy (Nginx/Apache) using the example config or your own.
