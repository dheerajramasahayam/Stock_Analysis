#!/bin/bash

# Basic Deployment Script for Stock Analyzer

# --- Configuration ---
APP_DIR="/home/hasher/Stocks_Analysis" # IMPORTANT: Change this to the actual deployment path on your server
GIT_REPO="https://github.com/dheerajramasahayam/Stock_Analysis.git" # IMPORTANT: Change this to your Git repo URL (e.g., git@github.com:user/repo.git)
PYTHON_VERSION="python3.12" # Or python3, adjust if needed
VENV_DIR="backend/venv"

# --- Environment Variables (Set these on your server!) ---
# export GEMINI_API_KEY="your_gemini_key"
# export BRAVE_API_KEY="your_brave_key"
# ---------------------------------------------------------

echo "--- Starting Deployment ---"
date

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

# --- Python Virtual Environment ---
echo "Setting up virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_VERSION -m venv $VENV_DIR || exit 1
fi

# Activate virtual environment (for this script's context) and install/update dependencies
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || exit 1
deactivate # Deactivate after installing

# --- Database Initialization (Run only if DB doesn't exist) ---
if [ ! -f "stocks.db" ]; then
    echo "Initializing database..."
    $VENV_DIR/bin/python backend/database.py || exit 1
    echo "Running initial data fetch (this may take a long time)..."
    $VENV_DIR/bin/python backend/data_fetcher.py || exit 1 # Run fetcher only on first setup
    echo "Running initial scoring..."
    $VENV_DIR/bin/python backend/scorer.py || exit 1 # Run scorer only on first setup
else
    echo "Database already exists, skipping initialization and initial data fetch/score."
    # Optional: Run database migrations/updates if needed in the future
    # $VENV_DIR/bin/python backend/database.py # Ensure schema is up-to-date
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
