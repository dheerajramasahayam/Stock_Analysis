import schedule
import time
import subprocess
import sys
from datetime import datetime, timedelta
# Removed dotenv imports, as config.py now handles it
import os
import config # Import the config file
from log_setup import setup_logger # Import logger setup

# --- Logger ---
logger = setup_logger('scheduler', config.LOG_FILE_SCHEDULER)
# -------------

# --- Configuration ---
PYTHON_EXECUTABLE = "/usr/bin/python3" # Use the system python used for user install
DATA_FETCHER_SCRIPT = "data_fetcher.py" # Just the filename
SCORER_SCRIPT = "scorer.py" # Just the filename
ANALYSIS_SCRIPT = "analysis.py" # Just the filename
ANALYSIS_HISTORY_DAYS = 90 # Analyze last 90 days of performance
# SCHEDULE_TIME = "19:00" # Use from config
# --------------------

def run_script(script_path, script_logger_name, script_log_file):
    """Runs a given Python script using the specified interpreter and logs its output."""
    script_logger = setup_logger(script_logger_name, script_log_file) # Setup logger for the script
    logger.info(f"--- Running script: {script_path} at {datetime.now()} ---")
    try:
        # Use Popen to potentially capture output line-by-line if needed,
        # but run() is simpler for just capturing final output.
        process = subprocess.run(
            script_path.split(), # Split command and args
            capture_output=True,
            text=True,
            check=True # Raise an exception if the script fails
        )
        # Log stdout and stderr to the specific script's log file
        if process.stdout:
            script_logger.info(f"--- Script Output ---\n{process.stdout.strip()}")
        if process.stderr:
            script_logger.error(f"--- Script Errors ---\n{process.stderr.strip()}")
        logger.info(f"--- Finished script: {script_path} successfully at {datetime.now()} ---")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"!!! Script {script_path} failed with return code {e.returncode} !!!")
        if e.stderr:
            script_logger.error(f"--- Error Output ---\n{e.stderr.strip()}")
            logger.error(f"--- Error Output ---\n{e.stderr.strip()}") # Also log to scheduler log
        if e.stdout:
             script_logger.info(f"--- Standard Output (during error) ---\n{e.stdout.strip()}")
             logger.info(f"--- Standard Output (during error) ---\n{e.stdout.strip()}")
        return False
    except Exception as e:
        logger.exception(f"!!! An unexpected error occurred while running {script_path}: {e} !!!") # Log traceback
        return False

def daily_job():
    """The job to be run daily."""
    logger.info("=== Starting Daily Job ===")

    # 1. Run the data fetcher (includes Gemini analysis)
    logger.info("Step 1: Running data fetcher...")
    fetch_command = [PYTHON_EXECUTABLE, DATA_FETCHER_SCRIPT]
    fetch_success = run_script(' '.join(fetch_command), 'data_fetcher', config.LOG_FILE_FETCHER)
    if not fetch_success:
        logger.error("Data fetching failed. Skipping scoring and analysis for today.")
        return # Don't proceed if fetching failed

    # 2. Run the scorer
    logger.info("Step 2: Running scorer...")
    # Calculate score for the previous day (assuming data fetch ran after market close)
    score_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    score_command = [PYTHON_EXECUTABLE, SCORER_SCRIPT, score_date]
    score_success = run_script(' '.join(score_command), 'scorer', config.LOG_FILE_SCORER)
    if not score_success:
        logger.error("Scoring script failed. Skipping analysis for today.")
        # Continue to analysis anyway? Or stop? Stopping for now.
        return

    # 3. Run the performance analysis
    logger.info("Step 3: Running performance analysis...")
    analysis_command = [PYTHON_EXECUTABLE, ANALYSIS_SCRIPT, str(ANALYSIS_HISTORY_DAYS)]
    run_script(' '.join(analysis_command), 'analysis', config.LOG_FILE_ANALYSIS)


    logger.info("=== Daily Job Finished ===")


# --- Schedule the Job ---
logger.info(f"Scheduling daily data/scoring/analysis job to run at {config.SCHEDULE_TIME}...")
schedule.every().day.at(config.SCHEDULE_TIME).do(daily_job)


# --- Run Initial Job Immediately (Optional) ---
# logger.info("Running initial job now...")
# daily_job()
# logger.info("Initial job finished.")
# ---------------------------------------------

logger.info("Scheduler started. Waiting for scheduled time...")
while True:
    schedule.run_pending()
    time.sleep(60) # Check every minute
