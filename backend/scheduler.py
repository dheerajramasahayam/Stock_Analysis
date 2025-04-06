import schedule
import time
import subprocess
import sys
from datetime import datetime, timedelta
import config # Import the config file

# --- Configuration ---
PYTHON_EXECUTABLE = "backend/venv/bin/python" # Path to venv python - Keep this or make configurable?
DATA_FETCHER_SCRIPT = "backend/data_fetcher.py"
SCORER_SCRIPT = "backend/scorer.py"
# SCHEDULE_TIME = "19:00" # Use from config
# --------------------

def run_script(script_path):
    """Runs a given Python script using the specified interpreter."""
    try:
        print(f"--- Running script: {script_path} at {datetime.now()} ---")
        process = subprocess.run(
            [PYTHON_EXECUTABLE, script_path],
            capture_output=True,
            text=True,
            check=True # Raise an exception if the script fails
        )
        print(f"--- Script {script_path} Output ---")
        print(process.stdout)
        if process.stderr:
            print(f"--- Script {script_path} Errors ---", file=sys.stderr)
            print(process.stderr, file=sys.stderr)
        print(f"--- Finished script: {script_path} at {datetime.now()} ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! Script {script_path} failed with return code {e.returncode} !!!", file=sys.stderr)
        print(f"--- Error Output ---", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        print(f"--- Standard Output ---", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        return False
    except Exception as e:
        print(f"!!! An unexpected error occurred while running {script_path}: {e} !!!", file=sys.stderr)
        return False

def daily_job():
    """The job to be run daily."""
    print(f"Starting daily job at {datetime.now()}...")

    # 1. Run the data fetcher (includes Gemini analysis)
    print("Step 1: Running data fetcher...")
    fetch_success = run_script(DATA_FETCHER_SCRIPT)
    if not fetch_success:
        print("Data fetching failed. Skipping scoring for today.")
        return # Don't proceed if fetching failed

    # 2. Run the scorer
    print("Step 2: Running scorer...")
    # Calculate score for the previous day (assuming data fetch ran after market close)
    score_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        print(f"--- Running script: {SCORER_SCRIPT} for date {score_date} at {datetime.now()} ---")
        process = subprocess.run(
            [PYTHON_EXECUTABLE, SCORER_SCRIPT, score_date], # Pass date as argument
            capture_output=True,
            text=True,
            check=True
        )
        print(f"--- Script {SCORER_SCRIPT} Output ---")
        print(process.stdout)
        if process.stderr:
            print(f"--- Script {SCORER_SCRIPT} Errors ---", file=sys.stderr)
            print(process.stderr, file=sys.stderr)
        print(f"--- Finished script: {SCORER_SCRIPT} at {datetime.now()} ---")
    except subprocess.CalledProcessError as e:
        print(f"!!! Script {SCORER_SCRIPT} failed with return code {e.returncode} !!!", file=sys.stderr)
        print(f"--- Error Output ---", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        print(f"--- Standard Output ---", file=sys.stderr)
    except Exception as e:
        print(f"!!! An unexpected error occurred while running {SCORER_SCRIPT}: {e} !!!", file=sys.stderr)


    print(f"Daily job finished at {datetime.now()}.")

# --- Schedule the Job ---
print(f"Scheduling daily job to run at {config.SCHEDULE_TIME}...") # Use config
schedule.every().day.at(config.SCHEDULE_TIME).do(daily_job) # Use config

# --- Run Initial Job Immediately (Optional) ---
# print("Running initial job now...")
# daily_job()
# print("Initial job finished.")
# ---------------------------------------------

print("Scheduler started. Waiting for scheduled time...")
while True:
    schedule.run_pending()
    time.sleep(60) # Check every minute
