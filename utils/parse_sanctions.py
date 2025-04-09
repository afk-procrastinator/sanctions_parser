import re
from utils.scrape_sanctions import scrape_sanctions_update

def normalize_category(category):
    """
    Normalize category names to standard forms.
    
    Args:
        category (str): Raw category name from the text
        
    Returns:
        str: Normalized category name
    """
    # Convert to lowercase for consistent comparison
    category = category.lower()
    
    # Category mapping to standardize categories
    category_mapping = {
        'individual': 'Individual',
        'individuals': 'Individual',
        'person': 'Individual',
        'persons': 'Individual',
        'entity': 'Entity',
        'entities': 'Entity',
        'organization': 'Entity',
        'organizations': 'Entity',
        'company': 'Entity',
        'companies': 'Entity',
        'vessel': 'Vessel',
        'vessels': 'Vessel',
        'ship': 'Vessel',
        'ships': 'Vessel',
        'aircraft': 'Aircraft',
        'aircrafts': 'Aircraft',
        'plane': 'Aircraft',
        'planes': 'Aircraft'
    }
    
    return category_mapping.get(category, category.capitalize())

def parse_sanctions_text(text):
    """
    Parse sanctions update text and count entries by category.
    
    Args:
        text (str): The sanctions update text to parse
        
    Returns:
        dict: Dictionary with categories as keys and entry counts as values
    """
    # Split the text into lines
    lines = text.split('\n')
    
    results = {}
    current_category = None
    current_count = 0
    
    # Regular expression to match category headers - handles various formats
    category_pattern = r"The following (\w+)(?:s)? (?:has|have) been (?:added|removed|modified|updated)"
    # Pattern to match the start of an entry (typically starts with a name or identifier)
    entry_pattern = r"^[A-Z0-9]"  # Entries typically start with capital letters or numbers
    
    for line in lines:
        # Check for category headers
        category_match = re.search(category_pattern, line, re.IGNORECASE)
        if category_match:
            # If we were counting a previous category, save its count
            if current_category:
                results[current_category] = current_count
            
            # Start counting new category
            raw_category = category_match.group(1)
            current_category = normalize_category(raw_category)
            current_count = 0
            continue
            
        # Count entries (non-empty lines that start with capital letters or numbers)
        if current_category and line.strip() and re.match(entry_pattern, line.strip()):
            current_count += 1
    
    # Save the count for the last category
    if current_category:
        results[current_category] = current_count
        
    return results

def main():
    # Get URL from user
    url = input("Enter the URL to scrape: ")
    
    # Get the sanctions text
    text = scrape_sanctions_update(url)
    
    # Parse the text
    results = parse_sanctions_text(text)
    
    # Print results
    print("\nSanctions Update Summary:")
    print("-" * 30)
    for category, count in results.items():
        print(f"{category}: {count} entries")

if __name__ == "__main__":
    main() 