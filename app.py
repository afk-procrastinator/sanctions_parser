from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from utils.scrape_sanctions import scrape_sanctions_update
from utils.parse_sanctions import parse_sanctions_text
from utils.process_entries import extract_entries, process_entry, extract_regimes
from utils.auth import verify_password
import os
import pandas as pd
import json
from datetime import datetime, timedelta
import io
from dotenv import load_dotenv
import anthropic
import threading
import functools
import time
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # Session timeout in seconds

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

# Simple in-memory cache and job tracking
cache = {}
jobs = {}

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

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

        # Add clear method
        wrapper.cache_clear = time_aware_func.cache_clear
        return wrapper
    return decorator

@timed_lru_cache(seconds=3600)  # Cache scraping results for 1 hour
def cached_scrape_sanctions_update(url):
    """Cached version of the scrape function"""
    return scrape_sanctions_update(url)

def process_job(job_id, url):
    """Background processing function"""
    try:
        # Update job status
        jobs[job_id]['status'] = 'scraping'
        
        # Scrape the data
        result = scrape_sanctions_update(url)
        
        # Store in cache
        result_hash = hash(result)
        cache_key = f"result_{result_hash}"
        cache[cache_key] = result
        
        # Parse counts
        counts = parse_sanctions_text(result)
        cache[f"counts_{result_hash}"] = counts
        
        # Extract entries
        entries = extract_entries(result)
        cache[f"entries_{result_hash}"] = entries
        
        # Update job status
        jobs[job_id].update({
            'status': 'completed',
            'result_hash': result_hash,
            'url': url,
            'counts': counts
        })
        
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['error'] = str(e)

@app.route('/api/start-scrape', methods=['POST'])
@login_required
def start_scrape():
    """Start a new scraping job"""
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize job
    jobs[job_id] = {
        'status': 'pending',
        'url': url,
        'started_at': datetime.now().isoformat()
    }
    
    # Start background processing
    thread = threading.Thread(target=process_job, args=(job_id, url))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/api/check-status/<job_id>')
@login_required
def check_status(job_id):
    """Check the status of a scraping job"""
    job = jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job['status'] == 'completed':
        # Store in session for the main page
        session['url'] = job['url']
        session['result_hash'] = job['result_hash']
        
        return jsonify({
            'status': 'completed',
            'url': job['url'],
            'counts': job['counts']
        })
    
    elif job['status'] == 'error':
        return jsonify({
            'status': 'error',
            'error': job.get('error', 'Unknown error')
        })
    
    return jsonify({'status': job['status']})

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Check if already logged in
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        if verify_password(password):
            session['logged_in'] = True
            # Set session to permanent if remember me is checked
            session.permanent = remember
            # Set session lifetime based on remember me
            if remember:
                app.permanent_session_lifetime = timedelta(days=30)  # 30 days
            else:
                app.permanent_session_lifetime = timedelta(hours=1)  # 1 hour
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear all session data
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
@login_required
def index():
    step = request.args.get('step', 'initial')
    
    if step == 'overview':
        # Get data from session
        url = session.get('url')
        result_hash = session.get('result_hash')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Session expired. Please start over.",
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
        # Get data from session
        result_hash = session.get('result_hash')
        url = session.get('url', '')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Session expired. Please start over.",
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
        # Get data from session
        result_hash = session.get('result_hash')
        url = session.get('url', '')
        
        if not result_hash:
            return render_template('index.html', 
                                  error="Session expired. Please start over.",
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
        
        if entries:
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
@login_required
def download(format_type):
    result_hash = session.get('result_hash')
    url = session.get('url', '')
    
    #if not result_hash:
    #    return "Session expired, please start over", 400
    
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
            
            # Extract date from URL if last 8 characters are digits (YYYYMMDD format)
            date = ""
            if url and url[-8:].isdigit():
                date = url[-8:]
            
            # Write data rows using the same logic as in process_entries.py
            for entry in processed_data:
                # Get category and determine action
                category = entry.get('category', '')
                # Determine action based on category
                action = "Delisting" if category.lower() in ["deletion", "deletions"] else "Designation"
                
                # Skip entries categorized as "change" or "changes"
                if category.lower() in ["change", "changes"]:
                    continue
                
                # Extract nationality/country
                country = entry.get('nationality', '')
                
                # Get name
                name = entry.get('name', '')
                
                # Get additional information (notes)
                additional_info = entry.get('notes', '')
                
                # Standardize category to one of the accepted values
                raw_category = entry.get('category', category.capitalize())
                if raw_category.lower() in ['individual', 'individuals', 'person', 'persons']:
                    entry_category = 'Individual'
                elif raw_category.lower() in ['entity', 'entities', 'organization', 'organisations', 'organizations']:
                    entry_category = 'Entity'
                elif raw_category.lower() in ['vessel', 'vessels', 'ship', 'ships']:
                    entry_category = 'Vessel'
                elif raw_category.lower() in ['aircraft', 'plane', 'planes', 'airplane', 'airplanes']:
                    entry_category = 'Aircraft'
                else:
                    # Default to Entity if not one of the standard categories
                    entry_category = 'Entity'
                
                # Get regimes as comma-separated string
                regimes = ', '.join(entry.get('Regime', []))
                
                # Write row
                writer.writerow([date, action, name, additional_info, country, entry_category, regimes])
            
            mem_val = output.getvalue()
            
            # Cache the CSV
            cache[csv_key] = mem_val
            
            # Create response
            output = io.BytesIO()
            output.write(mem_val.encode('utf-8'))
            output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'sanctions_processed_{timestamp}.csv'
        )
        
    elif format_type == 'json':
        # Check if JSON is already cached
        json_key = f"json_{result_hash}"
        if json_key in cache:
            output = io.BytesIO()
            output.write(cache[json_key].encode('utf-8'))
            output.seek(0)
        else:
            # Create JSON
            json_data = json.dumps(processed_data, indent=2)
            # Cache the JSON
            cache[json_key] = json_data
            
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
@login_required
def api_scrape():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    # Use cached version if available
    result = cached_scrape_sanctions_update(url)
    return jsonify({"result": result})

# Implement cache management for production use
@app.route('/admin/clear-cache', methods=['POST'])
@login_required
def clear_cache():
    # Require an admin token for security
    token = request.form.get('token')
    if token != os.getenv('ADMIN_TOKEN'):
        return jsonify({"error": "Unauthorized"}), 401
    
    # Clear all caches
    cache.clear()
    cached_scrape_sanctions_update.cache_clear()
    
    return jsonify({"message": "Cache cleared successfully"})

if __name__ == '__main__':
    # Use a different port to avoid conflicts
    app.run(debug=True, port=5001, threaded=True) 