import os
import anthropic
from dotenv import load_dotenv
from utils.process_entries import main as process_entries_main

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize the Anthropic client
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not found in environment variables")
            return
        
        print(f"API key found: {bool(api_key)}")
        client = anthropic.Anthropic(api_key=api_key)
        print("Anthropic client initialized successfully")
        
        # Run a test call to verify API connectivity
        test_response = client.messages.create(
            model="claude-3-5-haiku-2024-10-22",
            max_tokens=10,
            messages=[{"role": "user", "content": "Test"}]
        )
        print("Test API call successful!")
        
        # Pass the client to the process_entries main function
        process_entries_main(client)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    main() 