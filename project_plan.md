# Stock Analysis Web Application - Project Plan (Phase 1)

## 1. Objective
Create a web application to automatically scan and highlight potentially interesting stocks from selected sectors based on recent news sentiment, price momentum, and trading volume activity. The goal is to provide users with data-driven starting points for further research.

## 2. Phase 1 Scope
This initial phase focuses on building the core functionality using readily available data sources and standard analysis techniques. Future phases will explore integrating advanced AI (like Google Gemini) for deeper news analysis and potentially incorporating broader market factors.

## 3. Company Selection
*   **Sectors:** Technology, Healthcare, and Defense.
*   **Method:** Identify relevant sector-specific ETFs (e.g., XLK for Tech, XLV for Health, ITA/PPA for Defense). Periodically fetch the list of companies held within these ETFs to define the universe of stocks to track.

## 4. Data Fetching (Scheduled Task - e.g., Daily)
*   **Source 1: Yahoo Finance (via `yfinance` library)**
    *   Fetch historical price data (for charting).
    *   Fetch current price and daily volume.
    *   Fetch basic company information/fundamentals if needed for display (e.g., Market Cap).
*   **Source 2: Brave Search API**
    *   For each tracked company, fetch recent news articles (e.g., last 24-48 hours).
    *   Extract URL, title, snippet, and publication date.

## 5. Data Storage & Analysis
*   **Database:** Use SQLite to store:
    *   Tracked company list (Ticker, Name, Sector).
    *   Fetched news articles (Company Ticker, URL, Title, Snippet, Date, Calculated Sentiment Score).
    *   Historical price data (Ticker, Date, Close Price) for charting purposes.
*   **News Filtering:** Implement basic logic to attempt to prioritize company-specific news over general market commentary (e.g., check for ticker/company name prominence in title/snippet).
*   **Sentiment Analysis:** Use a standard Python library (e.g., VADER Sentiment) to analyze the sentiment of each fetched news snippet. Store the resulting score (e.g., compound score ranging -1 to +1) in the database.
*   **Financial Analysis:**
    *   Calculate short-term price momentum (e.g., percentage change over the last 5 trading days).
    *   Calculate recent average trading volume (e.g., 20-day average) and compare yesterday's volume to this average.

## 6. Highlighting & Scoring Logic
*   Develop a numerical scoring system calculated daily for each tracked stock.
*   **Factors:**
    *   **Recent News Sentiment:** Average sentiment score of news from the last ~3 days. (e.g., Positive avg = +2 pts, Neutral = 0, Negative = -1).
    *   **Short-Term Price Momentum:** Price change over the last ~5 days. (e.g., >+3% = +1 pt, 0-3% = 0, Negative = -1 pt).
    *   **Trading Volume Activity:** Yesterday's volume compared to the recent average. (e.g., >1.5x avg = +1 pt, Normal = 0 pts).
*   **Output:** A total score per stock. Higher scores indicate more positive signals based on this logic. Thresholds and points are tunable.

## 7. User Interface
*   **Technology:** HTML, CSS, JavaScript. Consider using a charting library like Chart.js.
*   **Main Page (Dashboard):**
    *   Display a list of the highlighted stocks (e.g., top N stocks by score, or all stocks above a certain score threshold).
    *   **Default Sort Order:** Descending by score (highest score first).
    *   **Controls:** Allow users to filter the list by Sector (Tech, Healthcare, Defense) and re-sort by Score, Price Change, or Latest News Date.
*   **Detail View (Accessed by clicking a stock on the dashboard):**
    *   Display company name and ticker.
    *   Show a **Price Trend Chart** (e.g., line chart of closing prices for the last 3 months).
    *   Display key data points used in scoring (e.g., recent price change %, volume ratio, avg sentiment).
    *   List the stored **News History** for the stock (Date, Snippet, Sentiment Score).

## 8. Technology Stack (Proposed)
*   **Backend:** Python
    *   Web Framework: Flask or FastAPI
    *   Libraries: `requests` (for APIs), `yfinance`, `pandas` (optional, for data manipulation), `vaderSentiment` (or similar), `schedule` (for running daily tasks), `sqlite3`.
*   **Frontend:** HTML, CSS, JavaScript, Chart.js.
*   **Database:** SQLite.

## 9. Requirements
*   **Brave Search API Key:** User needs to obtain this.

## 10. Phase 2 Scope (Future Enhancements)

*   **Gemini API Integration for News Analysis:**
    *   Replace or augment the basic sentiment analysis (VADER) with calls to the Google Gemini API.
    *   Use Gemini to generate concise summaries of recent news for each stock.
    *   Leverage Gemini for more nuanced sentiment scoring based on the full article context (if feasible via snippets or scraping).
    *   Utilize Gemini to identify key themes, topics, or entities (like products, executives, competitors) mentioned in the news.
    *   Explore using Gemini to detect mentions of macroeconomic or geopolitical factors within the news context provided.
*   **Broader Factor Integration (Investigation & Potential Implementation):**
    *   Research and identify reliable, accessible data sources (free or paid APIs) for:
        *   Key Macroeconomic Indicators (e.g., interest rate changes, inflation reports via FRED API).
        *   Analyst Ratings/Price Targets (if feasible sources are found).
        *   Significant Industry News/Trends (potentially via specialized news feeds or curated sources).
    *   If suitable data sources are identified, design prompts and logic for the Gemini API (or other methods) to incorporate this broader context into the stock analysis or scoring. This requires significant R&D.
*   **User Features:**
    *   Implement user registration and login.
    *   Allow users to create and manage personalized watchlists of stocks they want to track closely.
*   **Algorithm Refinement:**
    *   Analyze the performance of the Phase 1 scoring algorithm.
    *   Tune scoring parameters (thresholds, point values) based on observed results.
    *   Potentially incorporate new factors identified during Phase 2 research into the scoring model.
