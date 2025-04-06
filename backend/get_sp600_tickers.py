import requests
from bs4 import BeautifulSoup
import re
import sys

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
OUTPUT_FILE = "backend/sp600_tickers.txt"

def fetch_sp600_tickers():
    """Fetches the S&P 600 tickers from Wikipedia."""
    try:
        response = requests.get(WIKIPEDIA_URL, headers={'User-Agent': 'MyStockAnalyzerApp/1.0'})
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find the table containing the components - usually the first wikitable on the page
        # We might need to adjust this selector if the page structure changes
        table = soup.find('table', {'class': 'wikitable sortable'})
        if not table:
            print("Error: Could not find the components table on the Wikipedia page.", file=sys.stderr)
            return []

        tickers = set()
        rows = table.find_all('tr')
        for row in rows[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) > 0:
                ticker = cells[0].text.strip()
                # Validate ticker format (uppercase letters, possibly with .A/.B)
                if re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", ticker):
                    tickers.add(ticker)
                else:
                    print(f"  Skipping invalid ticker format: {ticker}", file=sys.stderr)


        if not tickers:
             print("Error: No tickers extracted from the table. Check table structure/selectors.", file=sys.stderr)
             return []

        return sorted(list(tickers))

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Wikipedia page: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Error parsing Wikipedia page: {e}", file=sys.stderr)
        return []

def save_tickers(tickers, filename=OUTPUT_FILE):
    """Saves the list of tickers to a file, one per line."""
    if not tickers:
        print("No tickers to save.", file=sys.stderr)
        return False
    try:
        with open(filename, 'w') as f:
            for ticker in tickers:
                f.write(ticker + '\n') # Use actual newline character
        print(f"Successfully saved {len(tickers)} tickers to {filename}")
        return True
    except IOError as e:
        print(f"Error writing tickers to file {filename}: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print(f"Fetching S&P 600 tickers from {WIKIPEDIA_URL}...")
    extracted_tickers = fetch_sp600_tickers()

    if extracted_tickers:
        if not save_tickers(extracted_tickers):
             sys.exit(1) # Exit if saving failed
    else:
        print("Ticker extraction failed.", file=sys.stderr)
        sys.exit(1) # Exit if extraction failed
