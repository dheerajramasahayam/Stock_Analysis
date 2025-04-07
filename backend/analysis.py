import sqlite3
import pandas as pd
import database # Import database module to get connection function
from datetime import datetime, timedelta
import numpy as np # For handling potential NaN/Inf

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
    print(f"--- Analyzing Score Performance for the last {days_history} days ---")
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
            print("No score data with next-day performance found in the specified date range.")
            conn.close()
            return

        # Load into pandas DataFrame
        df = pd.DataFrame(data, columns=['date', 'score', 'next_day_perf_pct'])

        # Handle potential non-finite values just in case
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df.dropna(subset=['score', 'next_day_perf_pct'], inplace=True)

        if df.empty:
            print("No valid score data with next-day performance found after cleaning.")
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

        print("\n--- Performance Analysis Results ---")
        print(analysis)
        print("------------------------------------")

        # --- Store results in database ---
        print("Storing analysis results in database...")
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
                print(f"Successfully stored {len(rows_to_insert)} analysis results.")
            except Exception as db_e:
                conn.rollback()
                print(f"Error storing analysis results: {db_e}")
        else:
            print("No analysis results generated to store.")
        # ---------------------------------

    except Exception as e:
        print(f"An error occurred during analysis: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    import sys
    import config # Import config to get default days

    # Default to config value, allow override from command line
    default_days = config.ANALYSIS_HISTORY_DAYS
    days_to_analyze = default_days

    if len(sys.argv) > 1:
        try:
            days_to_analyze = int(sys.argv[1])
            if days_to_analyze <= 0:
                print("Error: days_history argument must be positive.", file=sys.stderr)
                sys.exit(1)
            print(f"Using command line argument for history: {days_to_analyze} days.")
        except ValueError:
            print(f"Error: Invalid days_history argument '{sys.argv[1]}'. Using default: {default_days} days.", file=sys.stderr)
            days_to_analyze = default_days
    else:
         print(f"Using default history: {default_days} days.")


    analyze_performance(days_history=days_to_analyze)
