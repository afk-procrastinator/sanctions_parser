import re
from scrape_sanctions import scrape_sanctions_update

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
    
    # Regular expression to match category headers - now handles both singular and plural forms
    category_pattern = r"The following (\w+)(?:s)? (?:has|have) been"
    # Pattern to match the start of an entry (typically starts with a name or identifier)
    entry_pattern = r"^[A-Z0-9]"  # Entries typically start with capital letters or numbers
    
    for line in lines:
        # Check for category headers
        category_match = re.search(category_pattern, line)
        if category_match:
            # If we were counting a previous category, save its count
            if current_category:
                results[current_category] = current_count
            
            # Start counting new category
            current_category = category_match.group(1)
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