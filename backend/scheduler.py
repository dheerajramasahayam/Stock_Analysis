import schedule
import time
import subprocess
import sys
from datetime import datetime, timedelta
# Removed dotenv imports, as config.py now handles it
import os
import config # Import the config file

# --- Configuration ---
PYTHON_EXECUTABLE = "/usr/bin/python3" # Use the system python used for user install
DATA_FETCHER_SCRIPT = "backend/data_fetcher.py"
SCORER_SCRIPT = "backend/scorer.py"
ANALYSIS_SCRIPT = "backend/analysis.py"
ANALYSIS_HISTORY_DAYS = 90 # Analyze last 90 days of performance
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


def weekly_analysis_job():
    """Runs the performance analysis script."""
    print(f"Starting weekly analysis job at {datetime.now()}...")
    # Pass days from config as argument
    run_script(f"{ANALYSIS_SCRIPT} {ANALYSIS_HISTORY_DAYS}")
    print(f"Weekly analysis job finished at {datetime.now()}.")


# --- Schedule the Jobs ---
print(f"Scheduling daily data/scoring job to run at {config.SCHEDULE_TIME}...")
schedule.every().day.at(config.SCHEDULE_TIME).do(daily_job)

# Schedule analysis job (e.g., every Sunday at 8 PM, after daily job)
analysis_time = (datetime.strptime(config.SCHEDULE_TIME, "%H:%M") + timedelta(hours=1)).strftime("%H:%M")
print(f"Scheduling weekly analysis job to run every Sunday at {analysis_time}...")
schedule.every().sunday.at(analysis_time).do(weekly_analysis_job)


# --- Run Initial Job Immediately (Optional) ---
# print("Running initial job now...")
# daily_job()
# print("Initial job finished.")
# ---------------------------------------------

print("Scheduler started. Waiting for scheduled time...")
while True:
    schedule.run_pending()
    time.sleep(60) # Check every minute
