import sqlite3
import pandas as pd
import database # Import database module to get connection function
from datetime import datetime, timedelta
import numpy as np # For handling potential NaN/Inf
import config # Import config for log file path
from log_setup import setup_logger # Import logger setup
import sys # Import sys

# --- Logger ---
logger = setup_logger('analysis', config.LOG_FILE_ANALYSIS)
# -------------

# Define score buckets for analysis
SCORE_BUCKETS = [
    (-float('inf'), -2), # Very Low
    (-2, 0),             # Low
    (0, 2),              # Neutral
    (2, 4),              # High
    (4, float('inf'))    # Very High
]
BUCKET_LABELS = [
    "Score < -2",
    "-2 <= Score < 0",
    "0 <= Score < 2",
    "2 <= Score < 4",
    "Score >= 4"
]

def analyze_performance(days_history=30):
    """
    Analyzes the relationship between calculated scores and next-day performance.

    Args:
        days_history (int): How many past days of scores to analyze.
    """
    logger.info(f"--- Starting Score Performance Analysis for the last {days_history} days ---")
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Calculate start date for the query
    end_date = datetime.now().date()
    start_date = (end_date - timedelta(days=days_history)).strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d') # Although we usually score for D-1, query up to today

    try:
        # Query relevant data
        query = """
            SELECT
                date,
                score,
                next_day_perf_pct
            FROM daily_scores
            WHERE date >= ? AND date <= ? AND next_day_perf_pct IS NOT NULL
        """
        cursor.execute(query, (start_date, end_date_str))
        data = cursor.fetchall()

        if not data:
            logger.warning("No score data with next-day performance found in the specified date range.")
            conn.close()
            return

        # Load into pandas DataFrame
        df = pd.DataFrame(data, columns=['date', 'score', 'next_day_perf_pct'])

        # Handle potential non-finite values just in case
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(subset=['score', 'next_day_perf_pct'], inplace=True)

        if df.empty:
            logger.warning("No valid score data with next-day performance found after cleaning.")
            conn.close()
            return

        # Create score buckets
        bins = [b[0] for b in SCORE_BUCKETS] + [SCORE_BUCKETS[-1][1]]
        df['score_bucket'] = pd.cut(df['score'], bins=bins, labels=BUCKET_LABELS, right=False)

        # Group by bucket and calculate stats
        analysis = df.groupby('score_bucket', observed=False).agg(
            average_next_day_perf=('next_day_perf_pct', 'mean'),
            count=('score', 'size')
        )

        logger.info("\n--- Performance Analysis Results ---")
        # Log the DataFrame - consider logging analysis.to_string() for better formatting in logs
        logger.info(f"\n{analysis.to_string()}")
        logger.info("------------------------------------")

        # --- Store results in database ---
        logger.info("Storing analysis results in database...")
        analysis_run_date = datetime.now().strftime('%Y-%m-%d')
        rows_to_insert = []
        # Reset index to access 'score_bucket' as a column
        analysis_reset = analysis.reset_index()

        for index, row in analysis_reset.iterrows():
            # Handle potential NaN in avg_next_day_perf
            avg_perf = row['average_next_day_perf'] if not pd.isna(row['average_next_day_perf']) else None
            rows_to_insert.append((
                analysis_run_date,
                row['score_bucket'],
                avg_perf,
                int(row['count']) # Ensure count is integer
            ))

        if rows_to_insert:
            try:
                cursor.executemany("""
                    INSERT OR REPLACE INTO performance_analysis
                    (analysis_date, score_bucket, avg_next_day_perf, count)
                    VALUES (?, ?, ?, ?)
                """, rows_to_insert)
                conn.commit()
                logger.info(f"Successfully stored {len(rows_to_insert)} analysis results.")
            except Exception as db_e:
                conn.rollback()
                logger.exception(f"Error storing analysis results: {db_e}") # Log traceback
        else:
            logger.warning("No analysis results generated to store.")
        # ---------------------------------

    except Exception as e:
        logger.exception(f"An error occurred during analysis: {e}") # Log traceback
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Default to config value, allow override from command line
    default_days = config.ANALYSIS_HISTORY_DAYS
    days_to_analyze = default_days

    if len(sys.argv) > 1:
        try:
            days_to_analyze = int(sys.argv[1])
            if days_to_analyze <= 0:
                logger.error("days_history argument must be positive.")
                sys.exit(1)
            logger.info(f"Using command line argument for history: {days_to_analyze} days.")
        except ValueError:
            logger.error(f"Invalid days_history argument '{sys.argv[1]}'. Using default: {default_days} days.")
            days_to_analyze = default_days
    else:
         logger.info(f"Using default history: {default_days} days.")


    analyze_performance(days_history=days_to_analyze)
