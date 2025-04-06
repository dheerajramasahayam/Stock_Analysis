#!/bin/bash

# Basic Deployment Script for Stock Analyzer

# --- Configuration ---
APP_DIR="/home/hasher/Stocks_Analysis" # IMPORTANT: Change this to the actual deployment path on your server
GIT_REPO="https://github.com/dheerajramasahayam/Stock_Analysis.git" # IMPORTANT: Change this to your Git repo URL (e.g., git@github.com:user/repo.git)
PYTHON_VERSION="python3" # Or python3, adjust if needed
# VENV_DIR="backend/venv" # No longer using venv

# --- Environment Variables (Set these on your server!) ---
# export GEMINI_API_KEY="your_gemini_key"
# export BRAVE_API_KEY="your_brave_key"
# ---------------------------------------------------------

echo "--- Starting Deployment ---"
date

# --- Source .env file if it exists ---
if [ -f ".env" ]; then
    echo "Loading environment variables from .env file..."
    set -o allexport # Export all variables defined in the sourced file
    source .env
    set +o allexport # Stop exporting variables
else
    echo "INFO: .env file not found, relying on system environment variables."
fi

# --- Check for required environment variables ---
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY environment variable is not set. Exiting."
    exit 1
fi
if [ -z "$BRAVE_API_KEY" ]; then
    echo "ERROR: BRAVE_API_KEY environment variable is not set. Exiting."
    exit 1
fi

# --- Navigate to App Directory ---
# Create directory if it doesn't exist
mkdir -p $APP_DIR
cd $APP_DIR || exit 1 # Exit if cd fails

# --- Git Operations ---
# Check if it's a git repo, clone if not, pull if it is
if [ ! -d ".git" ]; then
    echo "Cloning repository..."
    git clone $GIT_REPO . || exit 1
else
    echo "Pulling latest changes..."
    git pull || exit 1
fi

# --- Install/Update Dependencies (User-wide) ---
echo "Installing/Updating Python dependencies for user..."
$PYTHON_VERSION -m pip install --upgrade pip
$PYTHON_VERSION -m pip install --user -r requirements.txt || exit 1
# Ensure the user's local bin directory is in the PATH if needed
# export PATH="$HOME/.local/bin:$PATH" # May need to add this to ~/.bashrc or ~/.profile

# --- Database Initialization (Run only if DB doesn't exist) ---
# Note: Assumes the .env file is loaded for these script runs too
if [ ! -f "stocks.db" ]; then
    echo "Initializing database..."
    $PYTHON_VERSION backend/database.py || exit 1
    echo "Running initial data fetch (this may take a long time)..."
    $PYTHON_VERSION backend/data_fetcher.py || exit 1 # Run fetcher only on first setup
    echo "Running initial scoring..."
    $PYTHON_VERSION backend/scorer.py || exit 1 # Run scorer only on first setup
else
    echo "Database already exists, skipping initialization and initial data fetch/score."
    # Optional: Run database migrations/updates if needed in the future
    # $PYTHON_VERSION backend/database.py # Ensure schema is up-to-date
fi


# --- Restart Services (using systemd example) ---
# Assumes systemd service files are already set up (see next step)
echo "Restarting application services..."
sudo systemctl restart stockapp-web.service
sudo systemctl restart stockapp-scheduler.service

# --- Check Service Status ---
echo "Checking service status..."
sleep 2 # Give services a moment to start/restart
sudo systemctl status stockapp-web.service --no-pager
sudo systemctl status stockapp-scheduler.service --no-pager


echo "--- Deployment Finished ---"
date

exit 0
