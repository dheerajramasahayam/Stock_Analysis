import google.generativeai as genai
import requests
import os
import json
import time
import config # Import the config file
import sys # Import sys for exiting

# --- API Key Validation ---
if not config.GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not set or found in config.", file=sys.stderr)
    sys.exit(1) # Exit if key is missing
if not config.BRAVE_API_KEY:
    print("ERROR: BRAVE_API_KEY environment variable not set or found in config.", file=sys.stderr)
    sys.exit(1) # Exit if key is missing
# --------------------------

# Configure Gemini
try:
    genai.configure(api_key=config.GEMINI_API_KEY)
    # Use the model name specified in the config (read from environment)
    model_name = config.GEMINI_MODEL_NAME
    query_generation_model = genai.GenerativeModel(model_name)
    analysis_model = genai.GenerativeModel(model_name)
    print(f"Gemini models initialized with: {model_name}")
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    query_generation_model = None
    analysis_model = None

def generate_search_queries(ticker, company_name):
    """Uses Gemini to generate relevant search queries for a stock."""
    if not query_generation_model:
        print("Error: Gemini query generation model not initialized.")
        return []

    prompt = f"""
    Generate 3 diverse search queries to find recent news and analysis about factors affecting the stock performance of {company_name} (ticker: {ticker}).
    Focus on potential catalysts, risks, financial health, and recent developments.
    Output the queries as a JSON list of strings. Example: ["query 1", "query 2", "query 3"]
    """
    try:
        response = query_generation_model.generate_content(prompt)
        # Attempt to parse the JSON response, handling potential markdown/formatting
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        queries = json.loads(cleaned_response)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            print(f"  Gemini generated queries for {ticker}: {queries}")
            return queries
        else:
            print(f"  Error: Gemini query generation returned unexpected format for {ticker}: {response.text}")
            return []
    except Exception as e:
        print(f"  Error generating search queries for {ticker} with Gemini: {e}")
        print(f"  Gemini Raw Response: {response.text if 'response' in locals() else 'N/A'}")
        return []

def search_with_brave(query):
    """Performs a search using the Brave Search API."""
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': config.BRAVE_API_KEY # Use key from config
    }
    params = {
        'q': query,
        'country': 'us',
        'search_lang': 'en',
        'spellcheck': 'false',
        'count': 5 # Limit to 5 results for analysis
    }
    try:
        print(f"    Executing Brave search: {query}")
        response = requests.get(config.BRAVE_SEARCH_ENDPOINT, headers=headers, params=params, timeout=10) # Use endpoint from config
        response.raise_for_status()
        data = response.json()
        results = []
        # Parse Web Search results (adjust keys as needed based on actual API response)
        if 'web' in data and 'results' in data['web'] and data['web']['results']:
            for item in data['web']['results']:
                 # Extract relevant fields - names might differ slightly (e.g., description vs snippet)
                 results.append({
                     'title': item.get('title'),
                     'snippet': item.get('description'), # Web results often use 'description'
                     'url': item.get('url'),
                     'date': item.get('page_age') # Web results might use 'page_age'
                 })
        print(f"    Brave Web search returned {len(results)} results.")
        return results
    except requests.exceptions.RequestException as e:
        print(f"    Error during Brave search for query '{query}': {e}")
        return []
    except Exception as e:
        print(f"    Unexpected error during Brave search processing for query '{query}': {e}")
        return []

def analyze_search_results(ticker, company_name, search_results):
    """Uses Gemini to analyze search results and provide summary/sentiment."""
    if not analysis_model:
        print("Error: Gemini analysis model not initialized.")
        return {"summary": "Error: Analysis model not available.", "sentiment_score": 0.0}
    if not search_results:
        return {"summary": "No search results found to analyze.", "sentiment_score": 0.0, "bullish_points": [], "bearish_points": []}

    # Prepare context from search results, limiting total results to avoid excessive context
    context = ""
    max_context_results = 6 # Limit total results fed to analysis model
    for i, result in enumerate(search_results[:max_context_results]):
        context += f"Result {i+1}:\nTitle: {result.get('title', 'N/A')}\nSnippet: {result.get('snippet', 'N/A')}\nDate: {result.get('date', 'N/A')}\nURL: {result.get('url', 'N/A')}\n\n"

    prompt = f"""
    Analyze the following recent web search results regarding {company_name} ({ticker}).
    Based *only* on the provided search results context:
    1. Provide a brief, neutral summary (2-3 sentences) of the key factors or news currently impacting the stock.
    2. List the top 1-2 bullish points mentioned in the results (as a JSON list of strings). If none, use an empty list [].
    3. List the top 1-2 bearish points mentioned in the results (as a JSON list of strings). If none, use an empty list [].
    4. Provide an overall sentiment score based *only* on these results, ranging from -1.0 (very negative) to +1.0 (very positive), with 0.0 being neutral.

    Search Results Context:
    {context}

    Output the result STRICTLY as a JSON object with keys "summary" (string), "bullish_points" (list of strings), "bearish_points" (list of strings), and "sentiment_score" (float).
    Example: {{"summary": "Recent news highlights concerns about X but also potential growth in Y.", "bullish_points": ["Potential growth in Y mentioned in Result 3."], "bearish_points": ["Concerns about X noted in Result 1.", "Result 5 mentions market headwinds."], "sentiment_score": -0.2}}
    """

    try:
        response = analysis_model.generate_content(prompt)
        # Attempt to parse the JSON response, handling potential markdown/formatting
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        analysis = json.loads(cleaned_response)

        # Validate structure
        if isinstance(analysis, dict) and \
           "summary" in analysis and \
           "bullish_points" in analysis and isinstance(analysis["bullish_points"], list) and \
           "bearish_points" in analysis and isinstance(analysis["bearish_points"], list) and \
           "sentiment_score" in analysis:
             # Ensure score is a float
             try:
                 analysis["sentiment_score"] = float(analysis["sentiment_score"])
             except (ValueError, TypeError):
                 print(f"  Warning: Could not convert sentiment score '{analysis['sentiment_score']}' to float for {ticker}. Defaulting to 0.0.")
                 analysis["sentiment_score"] = 0.0

             print(f"  Gemini analysis for {ticker}: Score={analysis['sentiment_score']:.2f}, Summary='{analysis['summary'][:50]}...'")
             # Ensure points are lists of strings (handle potential non-string items)
             analysis["bullish_points"] = [str(item) for item in analysis["bullish_points"]]
             analysis["bearish_points"] = [str(item) for item in analysis["bearish_points"]]
             return analysis
        else:
             print(f"  Error: Gemini analysis returned unexpected JSON structure for {ticker}: {cleaned_response}")
             # Return default structure on format error
             return {"summary": "Analysis format error.", "sentiment_score": 0.0, "bullish_points": [], "bearish_points": []}

    except json.JSONDecodeError as e:
        print(f"  Error decoding Gemini JSON response for {ticker}: {e}")
        print(f"  Gemini Raw Response: {cleaned_response if 'cleaned_response' in locals() else 'N/A'}")
        return {"summary": "Analysis JSON error.", "sentiment_score": 0.0, "bullish_points": [], "bearish_points": []}
    except Exception as e:
        print(f"  Error analyzing search results for {ticker} with Gemini: {e}")
        print(f"  Gemini Raw Response: {response.text if 'response' in locals() else 'N/A'}")
        return {"summary": "Analysis error.", "sentiment_score": 0.0, "bullish_points": [], "bearish_points": []}


def get_analysis_for_stock(ticker, company_name):
    """Orchestrates the process: generate query, search, analyze."""
    print(f"--- Starting Gemini analysis for {ticker} ---")
    search_queries = generate_search_queries(ticker, company_name)

    # Default result structure
    default_result = {"summary": "Analysis failed.", "sentiment_score": 0.0, "bullish_points": [], "bearish_points": []}

    if not search_queries:
        default_result["summary"] = "Failed to generate search queries."
        return default_result

    # Search for each query and collect results
    all_search_results = []
    max_results_per_query = 2 # Limit results from each query to keep context manageable
    for i, query in enumerate(search_queries):
        # Add delay between Brave API calls, especially after the first one
        if i > 0:
            time.sleep(1)
        results = search_with_brave(query)
        if results:
            all_search_results.extend(results[:max_results_per_query])

    # Remove potential duplicate URLs before analysis
    seen_urls = set()
    unique_results = []
    for result in all_search_results:
        url = result.get('url')
        if url and url not in seen_urls:
            unique_results.append(result)
            seen_urls.add(url)

    # Use logging module if available, otherwise print
    try:
        import logging
        logging.info(f"Collected {len(unique_results)} unique search results from {len(search_queries)} queries for {ticker}.")
    except ImportError:
        # Use logging module if available, otherwise print
        try:
            import logging
            logging.info(f"Collected {len(unique_results)} unique search results from {len(search_queries)} queries for {ticker}.")
        except ImportError:
             # Fallback print if logging fails to import (less likely now but safe)
             print(f"INFO: Collected {len(unique_results)} unique search results from {len(search_queries)} queries for {ticker}.")


    if not unique_results:
        default_result["summary"] = "No unique search results found after querying."
        return default_result

    analysis = analyze_search_results(ticker, company_name, unique_results) # Pass unique results
    print(f"--- Finished Gemini analysis for {ticker} ---")
    return analysis


if __name__ == '__main__':
    # Example usage:
    ticker_to_test = 'AAPL' # Replace with a relevant small-cap ticker if needed
    company_name_test = 'Apple Inc.' # Replace accordingly
    analysis_result = get_analysis_for_stock(ticker_to_test, company_name_test)
    print("\n--- Example Analysis Result ---")
    print(json.dumps(analysis_result, indent=2))
    print("-----------------------------")
