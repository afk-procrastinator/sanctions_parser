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
fi

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv .venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

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

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To run the application:${NC}"
echo "1. Run the application: python app.py"
echo "2. Open your browser and go to: http://127.0.0.1:5000"

# Check if user wants to run the application now
read -p "Would you like to run the application now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Starting the application...${NC}"
    source .venv/bin/activate
    python app.py
fi 