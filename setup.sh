#!/bin/bash
# setup.sh - Setup script for LeadFinder

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   LeadFinder Setup Script   ${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if Python 3 is installed
echo -e "\n${YELLOW}Checking Python installation...${NC}"
if command -v python3 &>/dev/null; then
    python_version=$(python3 --version)
    echo -e "${GREEN}✓ $python_version is installed${NC}"
else
    echo -e "${RED}✗ Python 3 is not installed. Please install Python 3.8 or higher.${NC}"
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

# Create necessary directories
echo -e "\n${YELLOW}Creating necessary directories...${NC}"
mkdir -p models
mkdir -p scrapers
mkdir -p ai
mkdir -p exporters
mkdir -p utils
mkdir -p data
echo -e "${GREEN}✓ Created package directories${NC}"

# Create .env file if it doesn't exist
echo -e "\n${YELLOW}Checking environment configuration...${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}→ .env file already exists${NC}"
else
    echo -e "${YELLOW}→ Creating .env file${NC}"
    # Create basic .env file
    cat > .env << EOL
# LeadFinder Environment Configuration

# OpenAI API Key (required for AI features)
# Sign up at https://platform.openai.com/signup
OPENAI_API_KEY=your_openai_api_key_here

# Output directory for exports (defaults to ~/Documents/LeadFinder if not set)
OUTPUT_DIR=~/Documents/LeadFinder

# Database configuration
# This is the location where the LeadFinder database will be stored
# DATABASE_PATH=~/.leadfinder/leadfinder.db

# Selenium WebDriver Options
# SELENIUM_HEADLESS=true
# SELENIUM_WINDOW_SIZE=1920x1080
EOL
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}→ Please edit the .env file to add your OpenAI API key${NC}"
fi

# Make scripts executable
echo -e "\n${YELLOW}Making scripts executable...${NC}"
chmod +x leadfinder.py
echo -e "${GREEN}✓ Made leadfinder.py executable${NC}"

# Create output directory
echo -e "\n${YELLOW}Creating output directory...${NC}"
output_dir=$(grep "OUTPUT_DIR" .env | cut -d '=' -f2)
if [ -z "$output_dir" ]; then
    output_dir="~/Documents/LeadFinder"
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
echo -e "${GREEN}✅ LeadFinder setup complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}Quick start commands:${NC}"
echo -e "  ./leadfinder.py dashboard        - Show main dashboard"
echo -e "  ./leadfinder.py find \"Chicago\" IL - Find leads in Chicago, IL"
echo -e "  ./leadfinder.py ai-find \"San Francisco\" CA - Generate AI leads"
echo -e "  ./leadfinder.py list             - List companies in database"
echo -e "  ./leadfinder.py help             - Show all available commands"

echo -e "\n${YELLOW}Project structure:${NC}"
echo -e "  leadfinder.py           - Main entry point"
echo -e "  config.py               - Configuration settings"
echo -e "  database.py             - Database operations"
echo -e "  models/                 - Data models"
echo -e "  scrapers/               - Web scrapers"
echo -e "  ai/                     - AI functionality"
echo -e "  exporters/              - Export functionality"
echo -e "  utils/                  - Utility functions"
echo -e "${BLUE}========================================${NC}"