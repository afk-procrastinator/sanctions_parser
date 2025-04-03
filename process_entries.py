import re
from scrape_sanctions import scrape_sanctions_update
from parse_sanctions import parse_sanctions_text
import anthropic
import json
from dotenv import load_dotenv
import os
from datetime import datetime
import csv

# Load environment variables
load_dotenv()
client = anthropic.Anthropic()

def extract_regimes(text):
    """
    Extract regime codes from brackets in the text.
    Example: "[SDGT] [IFSR]" -> ["SDGT", "IFSR"]
    """
    regimes = []
    # Find all text within square brackets
    matches = re.findall(r'\[(.*?)\]', text)
    for match in matches:
        # Split in case there are multiple codes in one bracket
        codes = [code.strip() for code in match.split()]
        regimes.extend(codes)
    return regimes

def extract_entries(text):
    """
    Extract individual entries from the sanctions text.
    
    Args:
        text (str): Full sanctions text
    
    Returns:
        dict: Dictionary with categories as keys and lists of entries as values
    """
    lines = text.split('\n')
    entries = {}
    current_category = None
    current_entry = []
    
    category_pattern = r"The following (\w+)(?:s)? (?:has|have) been"
    entry_pattern = r"^[A-Z0-9]"
    
    for line in lines:
        category_match = re.search(category_pattern, line)
        if category_match:
            # Save previous category's entries if they exist
            if current_category and current_entry:
                if current_category not in entries:
                    entries[current_category] = []
                entries[current_category].append('\n'.join(current_entry))
                current_entry = []
            
            current_category = category_match.group(1)
            if current_category not in entries:
                entries[current_category] = []
            continue
        
        # If line starts with capital letter or number, it's a new entry
        if current_category and line.strip() and re.match(entry_pattern, line.strip()):
            if current_entry:  # Save previous entry if it exists
                entries[current_category].append('\n'.join(current_entry))
                current_entry = []
            current_entry = [line.strip()]
        elif current_entry and line.strip():  # Continue current entry
            current_entry.append(line.strip())
    
    # Save the last entry
    if current_category and current_entry:
        entries[current_category].append('\n'.join(current_entry))
    
    return entries

def load_prompt_template():
    """Load the prompt template from the file"""
    with open('prompts/SDN_individuals.txt', 'r') as f:
        content = f.read()
        return content  # Return the entire template including examples

def extract_json_from_response(response_text):
    """
    Carefully extract JSON from Claude's response, handling various formats.
    """
    # Clean up the text first
    cleaned = response_text.replace('```json', '').replace('```', '')
    # Remove any non-ASCII characters
    cleaned = ''.join(char for char in cleaned if ord(char) < 128)
    # Replace any escaped newlines or tabs
    cleaned = cleaned.replace('\\n', ' ').replace('\\t', ' ')
    # Replace multiple whitespace with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Remove any whitespace around colons in key-value pairs
    cleaned = re.sub(r'\s*:\s*', ':', cleaned)
    cleaned = cleaned.strip()
    
    # Try to find a JSON object
    try:
        # Find the outermost matching braces
        start_idx = cleaned.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found")
        
        # Track brace depth to find matching end brace
        depth = 0
        end_idx = -1
        
        for i in range(start_idx, len(cleaned)):
            if cleaned[i] == '{':
                depth += 1
            elif cleaned[i] == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            raise ValueError("No matching end brace found")
        
        # Extract the JSON string
        json_str = cleaned[start_idx:end_idx]
        
        # Additional cleaning of the JSON string
        # Fix common issues with quotes
        json_str = re.sub(r'(?<!\\)"', '\\"', json_str)  # Escape unescaped quotes
        json_str = re.sub(r'\\+"', '"', json_str)  # Fix multiple escapes
        # Ensure property names are properly quoted
        json_str = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
        
        # Parse the JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as je:
            raise
    
    except (ValueError, json.JSONDecodeError) as e:
        # Fallback: Try to extract individual fields
        try:
            # Look for name field
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', cleaned)
            if name_match:
                return {
                    "name": name_match.group(1),
                    "notes": cleaned,
                    "nationality": "Unknown",
                    "category": "Unknown",
                    "Regime": [],
                    "issue": True
                }
        except Exception:
            pass
        
        raise ValueError("Could not extract valid JSON from response")

def process_entry(entry_text, category):
    """
    Process a single entry using Claude to extract structured information.
    
    Args:
        entry_text (str): The raw entry text
        category (str): The category of the entry (individual, entity, vessel, etc.)
    
    Returns:
        dict: Structured information about the entry
    """
    try:
        # Load the prompt template
        prompt_template = load_prompt_template()
        
        # Create the full prompt with examples and raw data
        prompt = prompt_template.replace('{{RAW_DATA}}', entry_text)
        
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Get the response text
        response_text = message.content[0].text.strip()
        
        # Try to parse the JSON response
        try:
            result = extract_json_from_response(response_text)
            # Ensure category is properly capitalized
            if 'category' not in result:
                result['category'] = category.capitalize()
            
            # Manually extract regimes and override the LLM's extraction
            regimes = extract_regimes(entry_text)
            if regimes:
                result['Regime'] = regimes
            
            return result
        except Exception as json_error:
            print(f"\nError parsing JSON response: {str(json_error)}")
            raise
    
    except Exception as e:
        print(f"Error processing entry: {str(e)}")
        print(f"Entry text: {entry_text[:100]}...")
        # Extract regimes even in error case
        regimes = extract_regimes(entry_text)
        # Create a basic structured response
        name = entry_text.split(',')[0].strip() if ',' in entry_text else entry_text.split()[0]
        return {
            "name": name,
            "notes": entry_text,
            "nationality": "Unknown",
            "category": category.capitalize(),
            "Regime": regimes if regimes else [],
            "issue": True
        }

def main():
    # Get URL from user
    url = input("Enter the URL to scrape: ")
    
    # Get the sanctions text
    text = scrape_sanctions_update(url)
    
    # Extract entries by category
    entries = extract_entries(text)
    
    # Show overview and ask for confirmation
    print("\nSanctions Update Overview:")
    print("-" * 50)
    for category, category_entries in entries.items():
        print(f"\n{category.upper()}:")
        print(f"Total entries: {len(category_entries)}")
    
    # Ask for confirmation
    confirmation = input("\nWould you like to proceed with processing these entries? (y/n): ")
    if confirmation.lower() != 'y':
        print("Operation cancelled by user.")
        return
    
    # Process each entry with the LLM
    processed_entries = {}
    
    print("\nProcessing entries...")
    for category, category_entries in entries.items():
        print(f"\nProcessing {category} entries...")
        processed_entries[category] = []
        
        for i, entry in enumerate(category_entries, 1):
            print(f"  Processing {category} entry {i}/{len(category_entries)}")
            processed = process_entry(entry, category)
            processed_entries[category].append(processed)
    
    # Extract date from URL if last 8 characters are digits (YYYYMMDD format)
    date = ""
    if url[-8:].isdigit():
        date = url[-8:]
    
    # Save results to a CSV file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"sanctions_processed_{timestamp}.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(['Date', 'Action', 'Name', 'Additional information', 'Country', 'Category', 'Regime'])
        
        # Write data
        for category, entries_list in processed_entries.items():
            for entry in entries_list:
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
    
    print(f"\nProcessing complete! Results saved to {output_file}")
    
    # Print a summary
    print("\nProcessing Summary:")
    print("-" * 30)
    total_entries = 0
    for category, entries in processed_entries.items():
        if category.lower() not in ["change", "changes"]:
            count = len(entries)
            total_entries += count
            print(f"{category}: {count} entries processed")
    print(f"Total entries in CSV: {total_entries}")

if __name__ == "__main__":
    main() 