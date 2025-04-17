# LeadFinder: Real-Time Lead Generation Tool
LeadFinder is a powerful command-line tool that actively scrapes the web to find potential clients for LogicLamp Technologies' energy efficiency solutions. Unlike tools that rely on mock data, LeadFinder discovers real leads by location with lead scoring and AI-powered analysis.

## Features

- **Real-Time Web Scraping**: Find businesses in specific cities using multiple data sources
- **Intelligent Lead Scoring**: Automatically rank prospects based on their potential need for energy solutions
- **AI-Powered Analysis**: Use OpenAI to identify energy efficiency opportunities for each lead
- **Personalized Outreach**: Generate customized email templates for the most promising prospects
- **HubSpot Integration**: Export leads in HubSpot-compatible format for seamless CRM integration
- **Interactive Command Line**: User-friendly interface with color-coded outputs and progress tracking

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/leadfinder.git
cd leadfinder

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install required packages
pip install -r requirements.txt

# Make the script executable (Unix-like systems)
chmod +x leadfinder.py

# Set up your OpenAI API key for AI features
echo "OPENAI_API_KEY=your_key_here" > .env
```

### Requirements

- Python 3.8+
- Chrome browser (for Selenium web scraping)
- OpenAI API key (for AI analysis)
- Required Python packages:
  - selenium
  - webdriver-manager
  - beautifulsoup4
  - openai
  - rich
  - pandas
  - python-dotenv

## Usage

### Finding Leads in a Specific City

```bash
# Find potential clients in San Francisco
./leadfinder.py find "San Francisco" CA

# Specify business category for more targeted results
./leadfinder.py find "Chicago" IL --category "office buildings"

# Get more leads with detailed information
./leadfinder.py find "Miami" FL --count 30 --details

# Specify data source (yellowpages or googlemaps)
./leadfinder.py find "Boston" MA --source yellowpages
```

### Working with Your Lead Database

```bash
# View overall statistics
./leadfinder.py dashboard

# List top leads from your database
./leadfinder.py list --limit 15

# Filter leads by location or score
./leadfinder.py list --city "Dallas" --min-score 70

# View detailed information about a specific lead
./leadfinder.py view 123
```

### AI-Enhanced Features

```bash
# Generate personalized outreach email for a specific lead
./leadfinder.py outreach --id 123

# Generate emails for your top 5 leads
./leadfinder.py outreach --count 5 --min-score 75

# Export outreach emails to a file
./leadfinder.py outreach --count 10 --export
```

### Exporting Data

```bash
# Export leads to CSV
./leadfinder.py export

# Export in HubSpot-compatible format
./leadfinder.py export --format hubspot

# Export only high-quality leads
./leadfinder.py export --min-score 80
```

## How It Works

### Data Sources

LeadFinder uses multiple scraping engines to find potential clients:

1. **YellowPages Scraper**: Searches YellowPages.com for businesses in specified categories and locations
2. **Google Maps Scraper**: Finds businesses through Google Maps search results
3. **Future Sources**: The architecture supports adding additional scraping engines

### Lead Scoring

The tool automatically scores leads (0-100) based on:

1. **Building Age**: Older buildings typically have greater energy-saving opportunities
2. **Building Size**: Larger buildings generally represent larger potential projects
3. **Business Type**: Different businesses have different energy profiles
4. **Website Presence**: Indicates an established business
5. **Contact Availability**: More points if decision-maker contact info is available

### AI Enhancement

When OpenAI integration is enabled, LeadFinder:

1. Analyzes each lead to identify specific energy efficiency opportunities
2. Refines lead scores based on AI assessment
3. Generates personalized outreach emails highlighting the most relevant benefits

## Extending LeadFinder

The modular architecture allows for easy extension:

1. Add new data sources by creating scrapers that follow the same interface
2. Enhance the lead scoring algorithm with industry-specific criteria
3. Add export formats for different CRM systems

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

Web scraping should be performed responsibly and ethically. This tool includes rate limiting and randomized delays to avoid overloading servers. Always check the terms of service for websites you're scraping and ensure your usage complies with applicable laws and regulations.

---

Created by [Your Name] - [GitHub Profile Link]