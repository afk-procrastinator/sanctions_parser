from flask import Flask, render_template, request, jsonify, send_file, make_response, redirect, url_for, session
from utils.scrape_sanctions import scrape_sanctions_update
from utils.parse_sanctions import parse_sanctions_text
from utils.process_entries import extract_entries, process_entry, extract_regimes
from utils.entity_list_parser import fetch_entity_list_xml, parse_entity_list
from utils.csv_generator import generate_entity_list_csv
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
import threading
import csv
import logging
import re

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
        
        return render_template('sanctions.html', 
                              result=result, 
                              url=url,
                              counts=counts,
                              step='overview')
    
    elif step == 'confirm':
        # Get data from request args
        result_hash = request.args.get('result_hash')
        url = request.args.get('url', '')
        
        if not result_hash:
            return render_template('sanctions.html', 
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
        
        return render_template('sanctions.html', 
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
            return render_template('sanctions.html', 
                                  error="Invalid request. Please start over.",
                                  step='initial')
        
        # Get cached data
        result = cache.get(f"result_{result_hash}", "")
        entries = cache.get(f"entries_{result_hash}", {})
        
        # Check if already processed
        processed_key = f"processed_{result_hash}"
        if processed_key in cache:
            processed_data = cache[processed_key]
            return render_template('sanctions.html', 
                                  result=result, 
                                  url=url,
                                  result_hash=result_hash,
                                  processed_data=processed_data,
                                  step='processed')
        
        # Create the session ID for tracking this processing job
        session_id = str(uuid.uuid4())
        # Store initial status in cache
        cache[f"status_{session_id}"] = {
            "status": "starting",
            "processed": 0,
            "total": sum(len(entries_list) for entries_list in entries.values()),
            "current_category": "",
            "current_index": 0
        }
        
        # Process entries in background thread to avoid blocking
        def process_entries_background():
            try:
                # Process each category and entry in batches
                total_processed = 0
                processed_data = []
                
                for category, entry_list in entries.items():
                    # Update status for new category
                    cache[f"status_{session_id}"] = {
                        "status": "processing",
                        "processed": total_processed,
                        "total": sum(len(entries_list) for entries_list in entries.values()),
                        "current_category": category,
                        "current_index": 0
                    }
                    
                    for i, entry_text in enumerate(entry_list):
                        try:
                            # Skip empty entries
                            if not entry_text.strip():
                                continue
                            
                            # Update processing status
                            cache[f"status_{session_id}"] = {
                                "status": "processing",
                                "processed": total_processed,
                                "total": sum(len(entries_list) for entries_list in entries.values()),
                                "current_category": category,
                                "current_index": i + 1
                            }
                            
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
                            total_processed += 1
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
                            total_processed += 1
                
                # Update status to complete
                cache[f"status_{session_id}"] = {
                    "status": "complete",
                    "processed": total_processed,
                    "total": sum(len(entries_list) for entries_list in entries.values())
                }
                
                # Cache the processed results
                cache[f"processed_{result_hash}"] = processed_data
                
            except Exception as e:
                print(f"Background processing error: {e}")
                # Update status to error
                cache[f"status_{session_id}"] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Check if Anthropic client is available
        if client is None:
            error_msg = "Anthropic API key is invalid or not configured. Check your .env file."
            print(error_msg)
            return render_template('sanctions.html', 
                                  error=error_msg,
                                  url=url,
                                  step='confirm')
        
        # Start the background processing thread
        processing_thread = threading.Thread(target=process_entries_background)
        processing_thread.daemon = True
        processing_thread.start()
        
        # Return template with loading state
        return render_template('sanctions.html', 
                              result=result, 
                              url=url,
                              processing_status="in_progress",
                              session_id=session_id,
                              result_hash=result_hash,
                              step='processed')
    
    # Default: show initial form
    return render_template('sanctions.html', step='initial')

@app.route('/entity-list', methods=['GET'])
def entity_list():
    """Page for entity list processing"""
    step = request.args.get('step', 'initial')
    
    # Default: show initial form
    return render_template('entity_list.html', step='initial')

@app.route('/download/<format_type>')
def download(format_type):
    # Get the most recent CSV file from the workspace directory
    if format_type == 'csv':
        try:
            # List all CSV files matching the pattern
            csv_files = [f for f in os.listdir('.') if f.startswith('sanctions_processed_') and f.endswith('.csv')]
            if not csv_files:
                return "No CSV files found", 404
            
            # Get the most recent file
            latest_file = max(csv_files)
            
            # Send the file
            return send_file(
                latest_file,
                as_attachment=True,
                download_name=latest_file
            )
        except Exception as e:
            return f"Error accessing CSV file: {str(e)}", 500
    
    elif format_type == 'json':
        # For JSON, we'll still use the cache since we don't save JSON files
        result_hash = request.args.get('result_hash')
        if not result_hash:
            return "Missing result_hash parameter", 400
        
        processed_key = f"processed_{result_hash}"
        processed_data = cache.get(processed_key, [])
        
        if not processed_data:
            return "No processed data available", 400
        
        # Create JSON response
        response = make_response(json.dumps(processed_data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        response.headers['Content-Disposition'] = f'attachment; filename=sanctions_processed_{timestamp}.json'
        return response
    
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

@app.route('/api/processing-status', methods=['GET'])
def processing_status():
    """Get the current processing status for a job"""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"error": "Session ID is required"}), 400
    
    status_key = f"status_{session_id}"
    status = cache.get(status_key, {"status": "not_found"})
    
    return jsonify(status)

@app.route('/api/fetch-xml', methods=['POST'])
def fetch_xml():
    """API endpoint to fetch XML data from the provided URL"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        # Fetch the XML data
        xml_content = fetch_entity_list_xml(url)
        
        # Generate a unique ID for this result
        result_id = str(uuid.uuid4())
        
        # Store the XML content in the cache
        cache[f"xml_{result_id}"] = xml_content
        
        return jsonify({
            'status': 'success',
            'result_id': result_id,
            'xml': xml_content
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/process-entity-xml', methods=['POST'])
def process_entity_xml():
    """API endpoint to process entity list XML data"""
    data = request.json
    result_id = data.get('result_id')
    xml_content = data.get('xml_content')
    
    # Either use the provided XML content or retrieve from cache
    if not xml_content and not result_id:
        return jsonify({'error': 'Either result_id or xml_content is required'}), 400
    
    if not xml_content:
        xml_content = cache.get(f"xml_{result_id}")
        if not xml_content:
            return jsonify({'error': 'XML content not found in cache'}), 404
    
    try:
        # Log the XML content for debugging
        if len(xml_content) > 500:
            logging.info(f"Processing XML content (first 500 chars): {xml_content[:500]}...")
        else:
            logging.info(f"Processing XML content: {xml_content}")
            
        # Parse the XML data
        result = parse_entity_list(xml_content)
        
        # Store the parsed result in the cache
        if result_id:
            cache[f"parsed_{result_id}"] = result
        
        return jsonify({
            'status': 'success',
            'result': result
        })
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logging.error(f"Error processing XML content: {str(e)}")
        logging.error(f"Traceback: {error_traceback}")
        
        return jsonify({
            'status': 'error',
            'error': str(e),
            'traceback': error_traceback if app.debug else None
        }), 500

@app.route('/process-entity-url', methods=['POST'])
def process_entity_url():
    """Route to handle form submission for entity list URL processing"""
    url = request.form.get('entityUrl')
    
    if not url:
        return render_template('entity_list.html', error='URL is required', step='initial')
    
    try:
        # Fetch the XML data
        xml_content = fetch_entity_list_xml(url)
        
        # Generate a unique ID for this result
        result_id = str(uuid.uuid4())
        
        # Store the XML content in the cache
        cache[f"xml_{result_id}"] = xml_content
        
        # Parse the entities
        entities_data = parse_entity_list(xml_content)
        cache[f"parsed_{result_id}"] = entities_data
        
        # Return the result to the template
        return render_template('entity_list.html', 
                              step='processed',
                              result_id=result_id,
                              xml_content=xml_content,
                              entities_data=entities_data,
                              url=url)
    except Exception as e:
        return render_template('entity_list.html', error=str(e), step='initial')

@app.route('/api/download-entity-csv', methods=['POST'])
def download_entity_csv():
    """Generates and returns the entity list as a CSV file."""
    data = request.get_json()
    if not data or 'entities' not in data or 'xml_url' not in data:
        return jsonify({'error': 'Missing entities or xml_url in request'}), 400

    entities = data['entities']
    xml_url = data['xml_url']

    if not isinstance(entities, list):
        return jsonify({'error': 'Invalid format for entities'}), 400
        
    if not isinstance(xml_url, str) or not xml_url:
        return jsonify({'error': 'Invalid xml_url'}), 400

    try:
        # Generate CSV content using the utility function
        csv_data = generate_entity_list_csv(entities, xml_url)
        
        # --- Add Logging --- 
        print(f"[Debug] Received xml_url for CSV download: {xml_url}")
        # --- End Add Logging ---

        # Determine filename from URL or use a default
        doc_id = 'download' # Default if regex fails
        filename_match = re.search(r'/([^/]+)\.xml$', xml_url)

        # --- Add Logging --- 
        if filename_match:
            print(f"[Debug] Regex matched: {filename_match.group(1)}")
            doc_id = filename_match.group(1)
        else:
            print(f"[Debug] Regex did not match.")
        # --- End Add Logging ---

        filename = f"entity_list_{doc_id}.csv"

        # Create response
        response = make_response(csv_data)
        # Ensure filename is quoted in the header
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Content-Type"] = "text/csv"
        return response

    except Exception as e:
        logger.error(f"Error generating entity CSV: {e}", exc_info=True)
        return jsonify({'error': 'Failed to generate CSV file'}), 500

@app.route('/sanctions')
def sanctions_redirect():
    """Redirect /sanctions to the main index page."""
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True) 