# Sanctions Update Scraper

A tool for scraping sanctions updates from websites and processing them with LLM to extract structured data.

<<<<<<< HEAD
Designed to be deployed on Vercel, but can also be run locally. 

Clone the repository to your computer, and run using `uv run app.py`. You might need to install dependencies (like brew, uv, etc. )
=======
## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your_api_key_here
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Usage

1. Enter a URL from the OFAC website (e.g., https://ofac.treasury.gov/recent-actions/20250313)
2. The tool will scrape the content and show you an overview
3. Confirm to process the entries with LLM
4. View and download the processed results in CSV or JSON format

## Features

- Web scraping of sanctions updates
- LLM-powered entity extraction
- Structured data output in CSV and JSON formats
- Caching for improved performance
>>>>>>> 20e36c1 (Hard rolling back. RIP.)
