#!/bin/bash
# setup.sh - Quick setup script for SustainScan
# Author: Your Name
# Created for LogicLamp Technologies Interview Demo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   SustainScan Setup Script   ${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if Python 3 is installed
echo -e "\n${YELLOW}Checking Python installation...${NC}"
if command -v python3 &>/dev/null; then
    python_version=$(python3 --version)
    echo -e "${GREEN}✓ $python_version is installed${NC}"
else
    echo -e "\033[0;31m✗ Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
    exit 1
fi

# Create virtual environment
echo -e "\n${YELLOW}Setting up virtual environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install requirements
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create .env file if it doesn't exist
echo -e "\n${YELLOW}Checking environment configuration...${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}→ .env file already exists${NC}"
else
    echo -e "${YELLOW}→ Creating .env file from template${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}→ Please edit the .env file to add your OpenAI API key${NC}"
fi

# Make script executable
echo -e "\n${YELLOW}Making sustainscan.py executable...${NC}"
chmod +x sustainscan.py
echo -e "${GREEN}✓ Made sustainscan.py executable${NC}"

# Create output directory
echo -e "\n${YELLOW}Creating output directory...${NC}"
output_dir=$(grep "OUTPUT_DIR" .env | cut -d '=' -f2)
if [ -z "$output_dir" ]; then
    output_dir="~/Documents/SustainScan"
fi
output_dir="${output_dir/#\~/$HOME}"
mkdir -p "$output_dir"
echo -e "${GREEN}✓ Created output directory: $output_dir${NC}"

# Verify OpenAI API key status
echo -e "\n${YELLOW}Checking OpenAI API key...${NC}"
if grep -q "OPENAI_API_KEY=your_openai_api_key_here\|OPENAI_API_KEY=$" .env; then
    echo -e "${YELLOW}⚠ OpenAI API key not configured${NC}"
    echo -e "${YELLOW}→ Edit .env file and add your API key to enable AI features${NC}"
else
    echo -e "${GREEN}✓ OpenAI API key is configured${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ SustainScan setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}Quick start commands:${NC}"
echo -e "  ./sustainscan.py dashboard        - Show main dashboard"
echo -e "  ./sustainscan.py scrape-buildings - Generate sample buildings"
echo -e "  ./sustainscan.py scrape-bids      - Generate sample bids"
echo -e "  ./sustainscan.py analyze-building 1 - Analyze building with AI"
echo -e "  ./sustainscan.py help             - Show all available commands"

echo -e "\n${YELLOW}For your interview demo:${NC}"
echo -e "  Follow the step-by-step guide in 'Interview Demo Script.md'"
echo -e "${BLUE}========================================${NC}"