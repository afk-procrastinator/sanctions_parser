import requests
from bs4 import BeautifulSoup
import re

def scrape_sanctions_update(url):
    """
    Scrapes text content between specific phrases from a webpage,
    preserving newlines and formatting.
    
    Args:
        url (str): The URL of the webpage to scrape
        
    Returns:
        str: Extracted text between the specified phrases with preserved formatting
    """
    try:
        # Send HTTP request to the URL
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Convert <br> and </p> tags to newlines before getting text
        for br in soup.find_all('br'):
            br.replace_with('\n')
        for p in soup.find_all('p'):
            p.append('\n')
        
        # Get text content with preserved newlines
        text_content = soup.get_text(separator='\n')
        
        # Find the start and end positions
        start_phrase = "Specially Designated Nationals List Update"
        end_phrase = "Unrelated Administrative List Updates"
        
        start_pos = text_content.find(start_phrase)
        end_pos = text_content.find(end_phrase)
        
        if start_pos == -1 or end_pos == -1:
            return "Could not find one or both of the specified phrases in the webpage."
        
        # Extract the text between these positions
        # Include the start phrase but exclude the end phrase
        extracted_text = text_content[start_pos:end_pos].strip()
        
        # Clean up multiple consecutive newlines while preserving paragraph structure
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', extracted_text)
        
        return cleaned_text
        
    except requests.RequestException as e:
        return f"Error fetching the webpage: {str(e)}"
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == "__main__":
    # Example usage
    url = input("Enter the URL to scrape: ")
    result = scrape_sanctions_update(url)
    print("\nExtracted content:")
    print("-" * 80)
    print(result)
    print("-" * 80) 