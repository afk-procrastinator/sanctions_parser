# Sanctions Update Scraper

A tool for scraping sanctions updates from websites.

## Features

- Command-line interface for scraping sanctions updates
- Web interface for easily accessing the tool in a browser
- API endpoint for programmatic access
- Preserves formatting in the extracted content

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Command-line Interface

```
python scrape_sanctions.py
```

Follow the prompts to enter the URL to scrape.

### Web Interface

To run the web application:

```
python app.py
```

Then open your browser to http://127.0.0.1:5000/

### API Usage

You can also access the scraper via an API endpoint:

```
POST /api/scrape
Content-Type: application/json

{
    "url": "https://example.com/sanctions-page"
}
```
