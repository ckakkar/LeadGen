#!/usr/bin/env python3
# config.py - Configuration settings for LeadFinder

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Application version
VERSION = "1.0.0"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("leadfinder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("leadfinder")

# Default config paths
CONFIG_DIR = os.path.expanduser("~/.leadfinder")
DATABASE_PATH = os.path.join(CONFIG_DIR, "leadfinder.db")

# Output directory for exports
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Documents/LeadFinder")
OUTPUT_DIR = os.path.expanduser(os.getenv("OUTPUT_DIR", DEFAULT_OUTPUT_DIR))

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    AI_ENABLED = True
else:
    AI_ENABLED = False
    logger.warning("OpenAI API key not found. AI features will be disabled.")

# OpenAI model to use for AI features
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

# Selenium configuration
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
SELENIUM_WINDOW_SIZE = os.getenv("SELENIUM_WINDOW_SIZE", "1920x1080")
SELENIUM_USER_AGENT = os.getenv(
    "SELENIUM_USER_AGENT", 
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
)

# Rate limiting configuration
SCRAPE_DELAY_MIN = float(os.getenv("SCRAPE_DELAY_MIN", "0.5"))
SCRAPE_DELAY_MAX = float(os.getenv("SCRAPE_DELAY_MAX", "1.5"))

# Batch processing sizes
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))

# Cache settings
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_EXPIRY = int(os.getenv("CACHE_EXPIRY", "86400"))  # Default: 24 hours

# API endpoints
YELLOWPAGES_BASE_URL = "https://www.yellowpages.com"
GOOGLE_MAPS_BASE_URL = "https://www.google.com/maps/search/"

# Database initialization SQL
DB_INIT_SQL = """
-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zipcode TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    category TEXT,
    building_size TEXT,
    year_built TEXT,
    description TEXT,
    source TEXT,
    lead_score INTEGER,
    ai_analysis TEXT,
    contact_person TEXT,
    contact_title TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Export history
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    export_type TEXT,
    file_path TEXT,
    record_count INTEGER,
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search history
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_type TEXT,
    search_term TEXT,
    results_count INTEGER,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cache table
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""