# Stock Analyzer Application

This application analyzes stocks from the S&P 600 index, filters them based on price and sector, calculates a composite score based on various technical and fundamental factors (including AI-driven sentiment analysis), and provides a web dashboard to view highlighted stocks and manage a personal portfolio.

## Features

*   **Data Fetching:**
    *   Retrieves S&P 600 tickers.
    *   Filters tickers based on price (default: $1-$50) and allowed sectors (default: Technology, Healthcare, Industrials) defined in `backend/config.py`.
    *   Fetches 6 months of historical price data using `yfinance`.
    *   Uses Google Gemini and Brave Search API to perform AI analysis on recent web search results for each stock, generating a summary and sentiment score.
    *   Stores company info, price history, and AI analysis in an SQLite database (`stocks.db`).
*   **Scoring:**
    *   Calculates a daily composite score for each tracked stock based on:
        *   Price Momentum (5-day change %)
        *   Volume Ratio (vs. 20-day average)
        *   Gemini Sentiment Score
        *   P/E Ratio (Lower is better)
        *   Dividend Yield (Higher is better)
        *   Price vs. 50-day SMA (Above is better)
    *   Stores daily scores in the database.
*   **Web Dashboard (Flask):**
    *   Displays highlighted stocks, sorted by score by default.
    *   Allows filtering displayed stocks by sector.
    *   Allows sorting displayed stocks by various criteria.
    *   Shows detailed view with price chart and AI summary when a stock card is clicked.
*   **Portfolio Management:**
    *   Allows users to add/delete personal stock holdings (ticker, quantity, purchase price, date).
    *   Displays current portfolio with Gain/Loss % based on the latest fetched price.
    *   Provides a basic "Consider Sell" suggestion if a holding's score drops below a configurable threshold.
*   **Scheduling:**
    *   Includes a scheduler (`backend/scheduler.py`) to automate daily data fetching and scoring (default: 7:00 PM).
*   **Configuration:**
    *   Centralized configuration in `backend/config.py`.
    *   API keys (Gemini, Brave) are read from environment variables (`GEMINI_API_KEY`, `BRAVE_API_KEY`).
*   **Deployment Ready:**
    *   Includes `requirements.txt` for dependencies.
    *   Includes `.gitignore` to exclude sensitive/unnecessary files.
    *   Includes example `systemd` service files (`stockapp-web.service`, `stockapp-scheduler.service`) for managing the web app (via Gunicorn) and the scheduler.
    *   Includes a basic deployment script (`deploy.sh`).

## Setup and Running Locally

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/dheerajramasahayam/Stock_Analysis.git
    cd Stock_Analysis
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv backend/venv
    source backend/venv/bin/activate
    ```
    *(On Windows use `backend\venv\Scripts\activate`)*
3.  **Install dependencies:**
    ```bash
    pip install --upgrade pip
    pip install -r requirements.txt
    ```
4.  **Set Environment Variables:**
    You **must** set the API keys as environment variables. You can do this temporarily in your terminal:
    ```bash
    export GEMINI_API_KEY="your_actual_gemini_key"
    export BRAVE_API_KEY="your_actual_brave_key"
    ```
    *(On Windows use `set GEMINI_API_KEY=your_key` and `set BRAVE_API_KEY=your_key`)*
    *Note: For persistent setting, add these to your shell profile (`.bashrc`, `.zshrc`) or use a `.env` file with a library like `python-dotenv` (not currently implemented).*
5.  **Initialize Database & Fetch Initial Data:**
    *   Run the database setup:
        ```bash
        python backend/database.py
        ```
    *   Run the data fetcher (this will take a long time for the full list):
        ```bash
        python backend/data_fetcher.py
        ```
    *   Run the scorer for the first time:
        ```bash
        python backend/scorer.py
        ```
6.  **Run the Web Application:**
    ```bash
    flask --app backend/app run
    ```
    Access the dashboard at `http://127.0.0.1:5000`.
7.  **(Optional) Run the Scheduler:**
    To run the daily updates automatically, stop the Flask app (Ctrl+C) and run the scheduler instead (it needs to run continuously):
    ```bash
    python backend/scheduler.py
    ```
    You would then typically run the Flask app separately or use the systemd services for deployment.

## Configuration (`backend/config.py`)

This file contains settings for:
*   API Keys (read from environment)
*   Data fetching parameters (ticker list file, price filters, allowed sectors)
*   Scoring parameters (days, thresholds, points)
*   Portfolio sell threshold
*   Scheduler time
*   API endpoints

## Deployment

Refer to `deploy.sh`, `stockapp-web.service`, and `stockapp-scheduler.service` for deployment examples using systemd and Gunicorn on a Linux server. Remember to:
*   Set environment variables on the server.
*   Customize paths and user/group in the service files.
*   Place service files in `/etc/systemd/system/`.
*   Enable and start services using `systemctl`.
*   Configure a reverse proxy (Nginx/Apache) is recommended for production.
