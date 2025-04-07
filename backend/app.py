from flask import Flask, jsonify, render_template, request
# Removed dotenv imports, as config.py now handles it
import os
import json # Import json module
import database
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
import logging # Import logging
from log_setup import setup_logger # Import logger setup directly
import config # Import config for log file path

# --- Logger ---
# Note: Gunicorn has its own logging, but we can add Flask-specific logs too.
# For production with Gunicorn, configure Gunicorn's logging options instead of basicConfig.
logger = setup_logger('web_app', config.LOG_FILE_WEB)
# -------------


app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')

# Initialize database (optional here if scheduler runs first)
# database.init_db()

@app.route('/')
def index():
    """Serves the main HTML page."""
    # We'll render the main HTML file from the frontend directory
    # Need to create frontend/index.html later
    return render_template('index.html')

@app.route('/api/highlighted-stocks')
def get_highlighted_stocks():
    """API endpoint to get the highlighted stocks for the latest scored date."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    try:
        # Find the most recent date for which scores exist
        cursor.execute("SELECT MAX(date) FROM daily_scores")
        latest_date_row = cursor.fetchone()
        if not latest_date_row or not latest_date_row[0]:
            print("No scores found in the database.")
            return jsonify([]) # Return empty list if no scores yet

        latest_date = latest_date_row[0]
        print(f"Fetching highlighted stocks for date: {latest_date}")

        # Fetch scores and company info for the latest date
        cursor.execute("""
            SELECT
                ds.ticker,
                c.name,
                c.sector,
                ds.score,
                ds.price_change_pct,
                ds.volume_ratio,
                ds.avg_sentiment,
                ds.pe_ratio,
                ds.dividend_yield,
                ds.price_vs_ma50, -- Add MA status column
                ds.rsi, -- Add RSI column
                ds.macd_signal, -- Add MACD signal column
                ds.bbands_signal, -- Add BBands signal column
                ds.debt_to_equity, -- Add Debt-to-Equity column
                ds.pb_ratio -- Add Price-to-Book column
            FROM daily_scores ds
            JOIN companies c ON ds.ticker = c.ticker
            WHERE ds.date = ?
            ORDER BY ds.score DESC -- Default sort by score descending
        """, (latest_date,))

        # Convert rows to dicts and handle non-JSON serializable values (Infinity, NaN)
        stocks_data = []
        for row in cursor.fetchall():
            stock_dict = dict(row)
            for key, value in stock_dict.items():
                # Replace float('inf'), float('-inf'), float('nan') with None
                if isinstance(value, float) and (value == float('inf') or value == float('-inf') or value != value): # Check for NaN
                    stock_dict[key] = None
            stocks_data.append(stock_dict)

        conn.close()
        return jsonify(stocks_data)

    except Exception as e:
        logger.exception(f"Error fetching highlighted stocks from DB: {e}") # Log traceback
        if conn:
            conn.close()
        return jsonify({"error": "Failed to fetch stock data"}), 500


@app.route('/api/stock-details/<ticker>')
def get_stock_details(ticker):
    """API endpoint to get details for a specific stock."""
    ticker = ticker.upper() # Ensure ticker is uppercase
    conn = database.get_db_connection()
    cursor = conn.cursor()

    details = {'ticker': ticker}

    try:
        # Get company info
        cursor.execute("SELECT name, sector FROM companies WHERE ticker = ?", (ticker,))
        company_info = cursor.fetchone()
        if company_info:
            details['name'] = company_info['name']
            details['sector'] = company_info['sector']
        else:
             details['name'] = f"{ticker} (Not found)"
             details['sector'] = "N/A"

        # Get price history (e.g., last 3 months)
        three_months_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT date, close_price
            FROM price_history
            WHERE ticker = ? AND date >= ?
            ORDER BY date ASC
        """, (ticker, three_months_ago))
        details['price_history'] = [
            {'date': row['date'], 'price': row['close_price']}
            for row in cursor.fetchall()
        ]

        # Get the latest Gemini analysis summary and score
        # Get the most recent Gemini analysis summary, score, and points available for the ticker
        cursor.execute("""
            SELECT gemini_summary, sentiment_score, bullish_points, bearish_points
            FROM news_articles
            WHERE ticker = ?
            ORDER BY published_date DESC, fetched_date DESC
            LIMIT 1
        """, (ticker,))
        analysis_row = cursor.fetchone()
        if analysis_row:
            details['gemini_summary'] = analysis_row['gemini_summary']
            # Parse the JSON strings back into lists
            try:
                details['bullish_points'] = json.loads(analysis_row['bullish_points'] or '[]')
            except json.JSONDecodeError:
                details['bullish_points'] = ["Error decoding bullish points."]
            try:
                details['bearish_points'] = json.loads(analysis_row['bearish_points'] or '[]')
            except json.JSONDecodeError:
                details['bearish_points'] = ["Error decoding bearish points."]
            # Optionally include the sentiment score if needed on frontend details
            # details['gemini_sentiment'] = analysis_row['sentiment_score']
        else:
            details['gemini_summary'] = "No analysis available for the latest date."
            details['bullish_points'] = []
            details['bearish_points'] = []
            # details['gemini_sentiment'] = None

        conn.close()
        return jsonify(details)

    except Exception as e:
        logger.exception(f"Error fetching details for {ticker} from DB: {e}") # Log traceback
        if conn:
            conn.close()
        return jsonify({"error": f"Failed to fetch details for {ticker}"}), 500

# --- Portfolio Endpoints ---

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """API endpoint to get all portfolio holdings."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        # Fetch portfolio holdings along with company name and latest price/score for context
        cursor.execute("""
            SELECT
                p.id, p.ticker, p.quantity, p.purchase_price, p.purchase_date,
                c.name,
                (SELECT close_price FROM price_history ph
                 WHERE ph.ticker = p.ticker ORDER BY ph.date DESC LIMIT 1) as latest_price,
                (SELECT score FROM daily_scores ds
                 WHERE ds.ticker = p.ticker ORDER BY ds.date DESC LIMIT 1) as latest_score
            FROM portfolio p
            JOIN companies c ON p.ticker = c.ticker
            ORDER BY p.purchase_date DESC, p.ticker ASC
        """)
        portfolio_data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(portfolio_data)
    except Exception as e:
        logger.exception(f"Error fetching portfolio from DB: {e}") # Log traceback
        if conn: conn.close()
        return jsonify({"error": "Failed to fetch portfolio data"}), 500

@app.route('/api/portfolio', methods=['POST'])
def add_portfolio_holding():
    """API endpoint to add a new holding to the portfolio."""
    data = request.get_json()
    ticker = data.get('ticker', '').upper()
    quantity = data.get('quantity')
    purchase_price = data.get('purchase_price')
    purchase_date = data.get('purchase_date') # Expecting YYYY-MM-DD

    # Basic Validation
    if not all([ticker, quantity, purchase_price, purchase_date]):
        return jsonify({"error": "Missing required fields (ticker, quantity, purchase_price, purchase_date)"}), 400
    try:
        quantity = int(quantity)
        purchase_price = float(purchase_price)
        # Validate date format
        datetime.strptime(purchase_date, '%Y-%m-%d')
        if quantity <= 0 or purchase_price <= 0:
            raise ValueError("Quantity and price must be positive.")
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid data type or value for quantity, purchase_price, or purchase_date (YYYY-MM-DD)"}), 400

    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if ticker exists in companies table (optional but good practice)
        cursor.execute("SELECT ticker FROM companies WHERE ticker = ?", (ticker,))
        if not cursor.fetchone():
             # Optionally, try to add the company if it's missing?
             # For now, just return an error if it's not tracked.
             conn.close()
             return jsonify({"error": f"Ticker '{ticker}' not found in tracked companies. Please ensure it's part of the S&P 600 list and meets price criteria."}), 404

        cursor.execute("""
            INSERT INTO portfolio (ticker, quantity, purchase_price, purchase_date)
            VALUES (?, ?, ?, ?)
        """, (ticker, quantity, purchase_price, purchase_date))
        conn.commit()
        holding_id = cursor.lastrowid
        conn.close()
        return jsonify({"message": "Holding added successfully", "id": holding_id}), 201
    except Exception as e:
        logger.exception(f"Error adding portfolio holding to DB: {e}") # Log traceback
        if conn: conn.rollback(); conn.close()
        return jsonify({"error": "Failed to add portfolio holding"}), 500

@app.route('/api/portfolio/<int:holding_id>', methods=['DELETE'])
def delete_portfolio_holding(holding_id):
    """API endpoint to delete a specific holding from the portfolio."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if holding exists before deleting
        cursor.execute("SELECT id FROM portfolio WHERE id = ?", (holding_id,))
        holding = cursor.fetchone()
        if not holding:
            conn.close()
            return jsonify({"error": "Holding not found"}), 404

        cursor.execute("DELETE FROM portfolio WHERE id = ?", (holding_id,))
        conn.commit()
        conn.close()
        # Check if deletion was successful (optional, commit implies success if no error)
        # cursor.execute("SELECT id FROM portfolio WHERE id = ?", (holding_id,))
        # if cursor.fetchone():
        #     # This shouldn't happen if DELETE worked
        #     return jsonify({"error": "Failed to delete holding"}), 500

        return jsonify({"message": "Holding deleted successfully"}), 200
    except Exception as e:
        logger.exception(f"Error deleting portfolio holding {holding_id} from DB: {e}") # Log traceback
        if conn: conn.rollback(); conn.close()
        return jsonify({"error": "Failed to delete portfolio holding"}), 500


if __name__ == '__main__':
    # Note: Use 'flask run' in development, or a proper WSGI server in production
    app.run(debug=True)


# --- Admin Interface Endpoints ---
import subprocess
import config # Re-import for log paths
import re

def get_last_log_entry_info(log_file_path):
    """Helper to get timestamp and status from the last relevant log entry."""
    try:
        # Use absolute path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        absolute_log_path = os.path.join(project_root, log_file_path)

        if not os.path.exists(absolute_log_path):
            return None, "Log file not found"

        # Read last few lines to find start/finish/error markers
        num_lines_to_check = 50
        with open(absolute_log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-num_lines_to_check:]

        last_status = "Unknown"
        last_timestamp = None
        # Search backwards for the most recent status indicator
        for line in reversed(lines):
            timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
            if timestamp_match:
                current_timestamp = timestamp_match.group(1)
                if "=== Starting" in line or "--- Running script" in line:
                    if last_timestamp is None: # Only update if we haven't found a finish/error yet
                       last_status = "Running/Incomplete"
                       last_timestamp = current_timestamp
                elif "successfully at" in line or "=== Finished" in line:
                    last_status = "Success"
                    last_timestamp = current_timestamp
                    break # Found the latest completion status
                elif "failed with return code" in line or "!!! An unexpected error occurred" in line:
                    last_status = "Failed"
                    last_timestamp = current_timestamp
                    break # Found the latest completion status

        return last_timestamp, last_status

    except Exception as e:
        logger.error(f"Error reading log file {log_file_path}: {e}")
        return None, "Error reading log"


@app.route('/admin')
def admin_page():
    """Serves the admin HTML page."""
    return render_template('admin.html')

@app.route('/api/admin/status')
def get_admin_status():
    """API endpoint to get status of services and last job runs."""
    status_data = {"timestamp": datetime.now().isoformat()}

    # Check systemd service status (simple check if active)
    try:
        web_status = subprocess.run(['systemctl', 'is-active', 'stockapp-web.service'], capture_output=True, text=True)
        status_data['web_service_active'] = web_status.stdout.strip() == 'active'
    except Exception as e:
        logger.warning(f"Could not check systemd status for stockapp-web.service: {e}")
        status_data['web_service_active'] = None # Indicate unknown

    try:
        scheduler_status = subprocess.run(['systemctl', 'is-active', 'stockapp-scheduler.service'], capture_output=True, text=True)
        status_data['scheduler_service_active'] = scheduler_status.stdout.strip() == 'active'
    except Exception as e:
        logger.warning(f"Could not check systemd status for stockapp-scheduler.service: {e}")
        status_data['scheduler_service_active'] = None # Indicate unknown

    # Get last run info from logs
    status_data['last_fetcher_run'], status_data['last_fetcher_status'] = get_last_log_entry_info(config.LOG_FILE_FETCHER)
    status_data['last_scorer_run'], status_data['last_scorer_status'] = get_last_log_entry_info(config.LOG_FILE_SCORER)
    status_data['last_analysis_run'], status_data['last_analysis_status'] = get_last_log_entry_info(config.LOG_FILE_ANALYSIS)

    return jsonify(status_data)


@app.route('/api/admin/logs/<log_type>')
def get_logs(log_type):
    """API endpoint to retrieve recent log file content."""
    log_files = {
        "web": config.LOG_FILE_WEB,
        "scheduler": config.LOG_FILE_SCHEDULER,
        "fetcher": config.LOG_FILE_FETCHER,
        "scorer": config.LOG_FILE_SCORER,
        "analysis": config.LOG_FILE_ANALYSIS,
    }

    if log_type not in log_files:
        return jsonify({"error": "Invalid log type specified"}), 400

    log_file_path = log_files[log_type]
    try:
        lines = int(request.args.get('lines', 100)) # Get number of lines from query param
        lines = max(10, min(lines, 1000)) # Clamp lines between 10 and 1000
    except ValueError:
        lines = 100

    try:
        # Use absolute path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        absolute_log_path = os.path.join(project_root, log_file_path)

        if not os.path.exists(absolute_log_path):
            return jsonify({"log_content": f"Log file not found: {log_file_path}"}), 404

        # Use tail command for efficiency
        process = subprocess.run(['tail', '-n', str(lines), absolute_log_path], capture_output=True, text=True, check=True)
        log_content = process.stdout
        return jsonify({"log_content": log_content})

    except subprocess.CalledProcessError as e:
         logger.error(f"Error running tail command for {log_file_path}: {e}")
         return jsonify({"error": f"Failed to read log file using tail: {e.stderr}"}), 500
    except Exception as e:
        logger.exception(f"Error reading log file {log_file_path}: {e}")
        return jsonify({"error": "Failed to read log file"}), 500
