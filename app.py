from flask import Flask, render_template, request, jsonify, send_file
from utils.scrape_sanctions import scrape_sanctions_update
from utils.parse_sanctions import parse_sanctions_text
from utils.process_entries import extract_entries, process_entry, extract_regimes
import os
import pandas as pd
import json
from datetime import datetime
import io
from dotenv import load_dotenv
import anthropic
import functools
import time
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Use a fixed secret key from environment variables, fallback to random if not set
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# Configure Anthropic client if key is available
try:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not found in environment variables")
        client = None
    else:
        client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    print(f"Could not initialize Anthropic client: {e}")
    client = None

# Simple in-memory cache
cache = {}

def timed_lru_cache(seconds=600, maxsize=128):
    """LRU cache decorator with expiration"""
    def decorator(func):
        @functools.lru_cache(maxsize=maxsize)
        def time_aware_func(time_hash, *args, **kwargs):
            return func(*args, **kwargs)

        def wrapper(*args, **kwargs):
            # Round time to nearest expiry bucket
            time_hash = int(time.time() / seconds)
            return time_aware_func(time_hash, *args, **kwargs)

        return wrapper
    return decorator

@timed_lru_cache(seconds=3600)  # Cache scraping results for 1 hour
def cached_scrape_sanctions_update(url):
    """Wrapper for scrape_sanctions_update with caching"""
    return scrape_sanctions_update(url)

@app.route('/api/start-scrape', methods=['POST'])
def start_scrape():
    """Start a new scraping job"""
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        # Get the result
        result = cached_scrape_sanctions_update(url)
        
        # Parse the result to get counts
        counts = parse_sanctions_text(result)
        
        # Store in cache with a hash of the result
        result_hash = str(hash(result))
        cache[f"result_{result_hash}"] = result
        cache[f"counts_{result_hash}"] = counts
        
        return jsonify({
            'status': 'completed',
            'url': url,
            'result_hash': result_hash,
            'counts': counts
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        })

@app.route('/', methods=['GET'])
def index():
    step = request.args.get('step', 'initial')
    
    if step == 'overview':
        # Get data from request args
        url = request.args.get('url')
        result_hash = request.args.get('result_hash')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Invalid request. Please start over.",
                                  step='initial')
        
        # Get data from cache
        result = cache.get(f"result_{result_hash}", "")
        counts = cache.get(f"counts_{result_hash}", {})
        
        return render_template('index.html', 
                              result=result, 
                              url=url,
                              counts=counts,
                              step='overview')
    
    elif step == 'confirm':
        # Get data from request args
        result_hash = request.args.get('result_hash')
        url = request.args.get('url', '')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Invalid request. Please start over.",
                                  step='initial')
        
        # Get data from cache
        result = cache.get(f"result_{result_hash}", "")
        counts = cache.get(f"counts_{result_hash}", {})
        
        # Extract entries by category (only if not already cached)
        entries_key = f"entries_{result_hash}"
        if entries_key not in cache:
            entries = extract_entries(result)
            cache[entries_key] = entries
        else:
            entries = cache[entries_key]
        
        return render_template('index.html', 
                              result=result, 
                              url=url,
                              counts=counts,
                              entries=entries,
                              step='confirm')
    
    elif step == 'processed':
        # Get data from request args
        result_hash = request.args.get('result_hash')
        url = request.args.get('url', '')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Invalid request. Please start over.",
                                  step='initial')
        
        # Get cached data
        result = cache.get(f"result_{result_hash}", "")
        entries = cache.get(f"entries_{result_hash}", {})
        
        # Check if already processed
        processed_key = f"processed_{result_hash}"
        if processed_key in cache:
            processed_data = cache[processed_key]
            return render_template('index.html', 
                                  result=result, 
                                  url=url,
                                  processed_data=processed_data,
                                  step='processed')
        
        # Process each entry using the existing function
        processed_data = []
        
        # Check if Anthropic client is available
        if client is None:
            error_msg = "Anthropic API key is invalid or not configured. Check your .env file."
            print(error_msg)
            return render_template('index.html', 
                                  error=error_msg,
                                  url=url,
                                  step='confirm')
        
        try:
            # Process each category and entry in batches
            for category, entry_list in entries.items():
                for i, entry_text in enumerate(entry_list):
                    try:
                        # Skip empty entries
                        if not entry_text.strip():
                            continue
                        
                        # Check if individual entry is cached
                        entry_cache_key = f"entry_{hash(entry_text)}_{category}"
                        if entry_cache_key in cache:
                            processed_entry = cache[entry_cache_key]
                        else:
                            # Process the entry using existing function
                            processed_entry = process_entry(entry_text, category)
                            # Cache the processed entry
                            cache[entry_cache_key] = processed_entry
                        
                        processed_data.append(processed_entry)
                    except Exception as e:
                        print(f"Error processing entry: {e}")
                        # Add a fallback entry
                        processed_data.append({
                            "name": entry_text.split(',')[0] if ',' in entry_text else entry_text[:50],
                            "nationality": "Unknown",
                            "category": category.capitalize(),
                            "Regime": extract_regimes(entry_text),
                            "issue": True,
                            "notes": entry_text
                        })
        except Exception as e:
            print(f"Error in processing entries: {e}")
            return render_template('index.html', 
                                  error=f"Error processing entries: {str(e)}",
                                  url=url,
                                  step='confirm')
        
        # Cache the processed results
        cache[processed_key] = processed_data
        
        return render_template('index.html', 
                              result=result, 
                              url=url,
                              processed_data=processed_data,
                              step='processed')
    
    # Default: show initial form
    return render_template('index.html', step='initial')

@app.route('/download/<format_type>')
def download(format_type):
    result_hash = request.args.get('result_hash')
    url = request.args.get('url', '')
    
    processed_key = f"processed_{result_hash}"
    processed_data = cache.get(processed_key, [])
    
    if not processed_data:
        return "No processed data available", 400
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if format_type == 'csv':
        # Check if CSV is already cached
        csv_key = f"csv_{result_hash}"
        if csv_key in cache:
            output = io.BytesIO()
            output.write(cache[csv_key].encode('utf-8'))
            output.seek(0)
        else:
            # Create in-memory CSV file that matches the process_entries.py format
            output = io.StringIO()
            import csv as csv_module
            writer = csv_module.writer(output)
            
            # Write header - must match process_entries.py exactly
            writer.writerow(['Date', 'Action', 'Name', 'Additional information', 'Country', 'Category', 'Regime'])
            
            # Write data rows
            for item in processed_data:
                # Extract date from URL if last 8 characters are digits (YYYYMMDD format)
                date = ""
                if url[-8:].isdigit():
                    date = url[-8:]
                
                # Format regimes as comma-separated string
                regimes = item.get('Regime', [])
                if isinstance(regimes, list):
                    regimes = ', '.join(regimes)
                
                writer.writerow([
                    date,
                    'Added',  # Default action
                    item.get('name', ''),
                    item.get('notes', ''),
                    item.get('nationality', ''),
                    item.get('category', ''),
                    regimes
                ])
            
            # Cache the CSV content
            csv_content = output.getvalue()
            cache[csv_key] = csv_content
            
            # Reset and convert to bytes
            output = io.BytesIO()
            output.write(csv_content.encode('utf-8'))
            output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'sanctions_processed_{timestamp}.csv'
        )
    
    elif format_type == 'json':
        # Create JSON response
        json_data = json.dumps(processed_data, indent=2)
        
        # Create response
        output = io.BytesIO()
        output.write(json_data.encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'sanctions_processed_{timestamp}.json'
        )
    
    return "Invalid format type", 400

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Use cached version if available
    result = cached_scrape_sanctions_update(url)
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(debug=True) 