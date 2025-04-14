#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting setup for Sanctions Update Scraper...${NC}"

# Check if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}Detected macOS system${NC}"
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install Python if not installed
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Installing Python...${NC}"
        brew install python
    fi

    # Install pip if not installed
    if ! command -v pip3 &> /dev/null; then
        echo -e "${YELLOW}Installing pip...${NC}"
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python3 get-pip.py
        rm get-pip.py
    fi

    # Install git if not installed
    if ! command -v git &> /dev/null; then
        echo -e "${YELLOW}Installing git...${NC}"
        brew install git
    fi
fi

# Check for any git changes and pull from remote
if [ -d ".git" ]; then
    echo -e "${YELLOW}Checking for git changes...${NC}"
    git pull
fi

# Create virtual environment if it doesn't exist
echo -e "${YELLOW}Checking for virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    echo "# Add your Anthropic API key below" > .env
    echo "ANTHROPIC_API_KEY=your_api_key_here" >> .env
    echo -e "${RED}Please edit the .env file and add your Anthropic API key${NC}"
fi

# Make the script executable
chmod +x app.py

# Checking to see if anything's running on port 5000 and killing it
if lsof -i :5000; then
    echo -e "${YELLOW}Killing process on port 5000...${NC}"
    lsof -i :5000 | awk '{print $2}' | xargs kill
fi

echo -e "${GREEN}Setup complete! Starting and opening browser...${NC}"
# Run the Flask app in the background
flask run &

# Wait for the server to start
sleep 2

# Open the browser
open http://127.0.0.1:5000