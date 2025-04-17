#!/usr/bin/env python3
# leadfinder.py - Real Lead Generation Tool for LogicLamp Technologies
# This tool scrapes real data to find potential clients for energy efficiency solutions

import argparse
import os
import sys
import csv
import json
import sqlite3
import datetime
import pandas as pd
import requests
import time
import random
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import print as rprint
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from dotenv import load_dotenv
import concurrent.futures
import openai

# Load environment variables
load_dotenv()

# Initialize rich console
console = Console()

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

# Application version
VERSION = "1.0.0"

# Default config path
CONFIG_DIR = os.path.expanduser("~/.leadfinder")
DATABASE_PATH = os.path.join(CONFIG_DIR, "leadfinder.db")

# Ensure config directory exists
os.makedirs(CONFIG_DIR, exist_ok=True)

# Initialize OpenAI API
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    openai.api_key = openai_api_key
    AI_ENABLED = True
else:
    AI_ENABLED = False
    logger.warning("OpenAI API key not found. AI features will be disabled.")

# Set cheapest OpenAI model
OPENAI_MODEL = "gpt-3.5-turbo"

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
"""

# Selenium setup
def setup_selenium():
    """Set up and return a Selenium WebDriver"""
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920x1080")
        
        # Add user agent to avoid detection
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        # Install the latest ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set page load timeout
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logger.error(f"Error setting up Selenium: {e}")
        console.print(f"[bold red]Error setting up Selenium: {e}[/bold red]")
        console.print("[yellow]Make sure you have Chrome installed on your system.[/yellow]")
        sys.exit(1)

class Database:
    """Database manager for LeadFinder"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize the database if it doesn't exist"""
        try:
            # Connect to database (creates it if it doesn't exist)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # Execute initialization SQL
            cursor = self.conn.cursor()
            cursor.executescript(DB_INIT_SQL)
            self.conn.commit()
            cursor.close()
            
            logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            console.print(f"[bold red]Error initializing database: {e}[/bold red]")
            sys.exit(1)
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def insert_company(self, company_data: Dict[str, Any]) -> int:
        """Insert a company record and return its ID"""
        try:
            cursor = self.conn.cursor()
            
            # Check if company already exists
            query = "SELECT id FROM companies WHERE name = ? AND city = ?"
            cursor.execute(query, (company_data.get('name'), company_data.get('city')))
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']
            
            # Convert dict to SQL parameters
            columns = ', '.join(company_data.keys())
            placeholders = ', '.join(['?' for _ in company_data])
            values = list(company_data.values())
            
            query = f"INSERT INTO companies ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            self.conn.commit()
            
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error inserting company: {e}")
            return None
    
    def update_company(self, company_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a company record"""
        try:
            cursor = self.conn.cursor()
            
            # Prepare update statement
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(company_id)  # Add ID for WHERE clause
            
            query = f"UPDATE companies SET {set_clause} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()
            
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating company: {e}")
            return False
    
    def get_companies(self, limit: int = 100, offset: int = 0, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get companies with optional filtering"""
        try:
            cursor = self.conn.cursor()
            
            query = "SELECT * FROM companies"
            params = []
            
            # Apply filters if provided
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'id':
                        where_clauses.append("id = ?")
                        params.append(value)
                    elif key == 'city':
                        where_clauses.append("city LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'state':
                        where_clauses.append("state = ?")
                        params.append(value)
                    elif key == 'category':
                        where_clauses.append("category LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'min_lead_score':
                        where_clauses.append("lead_score >= ?")
                        params.append(value)
                    elif key == 'name':
                        where_clauses.append("name LIKE ?")
                        params.append(f"%{value}%")
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            query += " ORDER BY lead_score DESC, scraped_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting companies: {e}")
            return []
    
    def count_companies(self, filters: Dict[str, Any] = None) -> int:
        """Count companies with optional filtering"""
        try:
            cursor = self.conn.cursor()
            
            query = "SELECT COUNT(*) as count FROM companies"
            params = []
            
            # Apply filters if provided
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'city':
                        where_clauses.append("city LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'state':
                        where_clauses.append("state = ?")
                        params.append(value)
                    elif key == 'category':
                        where_clauses.append("category LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'min_lead_score':
                        where_clauses.append("lead_score >= ?")
                        params.append(value)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
        except sqlite3.Error as e:
            logger.error(f"Error counting companies: {e}")
            return 0
    
    def record_export(self, export_type: str, file_path: str, record_count: int) -> int:
        """Record an export operation"""
        try:
            cursor = self.conn.cursor()
            
            query = "INSERT INTO exports (export_type, file_path, record_count) VALUES (?, ?, ?)"
            cursor.execute(query, (export_type, file_path, record_count))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error recording export: {e}")
            return None
    
    def record_search(self, search_type: str, search_term: str, results_count: int) -> int:
        """Record a search operation"""
        try:
            cursor = self.conn.cursor()
            
            query = "INSERT INTO search_history (search_type, search_term, results_count) VALUES (?, ?, ?)"
            cursor.execute(query, (search_type, search_term, results_count))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error recording search: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            cursor = self.conn.cursor()
            
            stats = {}
            
            # Company stats
            cursor.execute("SELECT COUNT(*) as count FROM companies")
            stats['company_count'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT AVG(lead_score) as avg_score FROM companies")
            stats['avg_lead_score'] = cursor.fetchone()['avg_score'] or 0
            
            # City stats
            cursor.execute("SELECT COUNT(DISTINCT city) as count FROM companies")
            stats['city_count'] = cursor.fetchone()['count']
            
            # Category stats
            cursor.execute("SELECT COUNT(DISTINCT category) as count FROM companies")
            stats['category_count'] = cursor.fetchone()['count']
            
            # Search stats
            cursor.execute("SELECT COUNT(*) as count FROM search_history")
            stats['search_count'] = cursor.fetchone()['count']
            
            # Export stats
            cursor.execute("SELECT COUNT(*) as count FROM exports")
            stats['export_count'] = cursor.fetchone()['count']
            
            # AI analysis stats
            cursor.execute("SELECT COUNT(*) as count FROM companies WHERE ai_analysis IS NOT NULL")
            stats['ai_analyzed_count'] = cursor.fetchone()['count']
            
            return stats
        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {}

class YellowPagesScraper:
    """Scrapes business data from YellowPages.com"""
    
    def __init__(self, db: Database):
        self.db = db
        self.driver = None
    
    def __enter__(self):
        self.driver = setup_selenium()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
    
    def search_businesses(self, city: str, state: str, category: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for businesses in a specific city and category"""
        companies = []
        
        try:
            # Construct search URL
            base_url = "https://www.yellowpages.com"
            
            # Format category for URL
            if category:
                # Replace spaces with hyphens and make lowercase
                formatted_category = category.lower().replace(' ', '-')
            else:
                # Default to commercial buildings
                formatted_category = "office-buildings"
            
            # Format city and state
            formatted_location = f"{city.lower().replace(' ', '-')}-{state.lower()}"
            
            # Construct search URL
            search_url = f"{base_url}/{formatted_category}/{formatted_location}"
            
            logger.info(f"Searching YellowPages: {search_url}")
            console.print(f"[yellow]Searching for businesses in {city}, {state}...[/yellow]")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "search-results"))
            )
            
            results_found = 0
            page = 1
            
            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Scraping business data...", total=max_results)
                
                # While we still need more results and haven't hit an error
                while results_found < max_results:
                    # Get all business listings on current page
                    business_elements = self.driver.find_elements(By.CLASS_NAME, "result")
                    
                    if not business_elements:
                        logger.info("No more business results found")
                        break
                    
                    # Process each business listing
                    for element in business_elements:
                        if results_found >= max_results:
                            break
                        
                        try:
                            company = {}
                            
                            # Extract business name
                            name_element = element.find_elements(By.CLASS_NAME, "business-name")
                            if name_element:
                                company['name'] = name_element[0].text.strip()
                            else:
                                continue  # Skip if no name found
                            
                            # Extract address
                            address_element = element.find_elements(By.CLASS_NAME, "street-address")
                            if address_element:
                                company['address'] = address_element[0].text.strip()
                            
                            # Extract locality (city, state, zip)
                            locality_element = element.find_elements(By.CLASS_NAME, "locality")
                            if locality_element:
                                locality = locality_element[0].text.strip()
                                # Try to parse city, state, zip
                                match = re.match(r"(.*?),\s*(\w{2})\s*(\d{5})?", locality)
                                if match:
                                    company['city'] = match.group(1).strip()
                                    company['state'] = match.group(2).strip()
                                    company['zipcode'] = match.group(3) if match.group(3) else ""
                            
                            # If we couldn't parse from locality, use the provided city/state
                            if 'city' not in company:
                                company['city'] = city
                                company['state'] = state
                            
                            # Extract phone
                            phone_element = element.find_elements(By.CLASS_NAME, "phones")
                            if phone_element:
                                company['phone'] = phone_element[0].text.strip()
                            
                            # Extract website if available
                            website_element = element.find_elements(By.CSS_SELECTOR, "a.track-visit-website")
                            if website_element:
                                company['website'] = website_element[0].get_attribute("href")
                            
                            # Extract categories/services
                            categories_element = element.find_elements(By.CLASS_NAME, "categories")
                            if categories_element:
                                company['category'] = categories_element[0].text.strip()
                            else:
                                company['category'] = category
                            
                            # Extract years in business if available
                            years_element = element.find_elements(By.CSS_SELECTOR, ".years-in-business .number")
                            if years_element:
                                years_in_business = years_element[0].text.strip()
                                # Estimate year founded
                                current_year = datetime.datetime.now().year
                                try:
                                    years = int(years_in_business)
                                    company['year_built'] = str(current_year - years)
                                except ValueError:
                                    pass
                            
                            # Add source and timestamp
                            company['source'] = "YellowPages"
                            company['lead_score'] = self.calculate_lead_score(company)
                            
                            # Add to results
                            companies.append(company)
                            results_found += 1
                            progress.update(task, advance=1)
                            
                            # Small sleep to avoid overloading the server
                            time.sleep(random.uniform(0.5, 1.5))
                            
                        except Exception as e:
                            logger.error(f"Error processing business element: {e}")
                            continue
                    
                    # Check if we have enough results
                    if results_found >= max_results:
                        break
                    
                    # Try to go to next page
                    try:
                        next_button = self.driver.find_elements(By.CSS_SELECTOR, "a.next")
                        if next_button and "disabled" not in next_button[0].get_attribute("class"):
                            next_button[0].click()
                            page += 1
                            # Wait for next page to load
                            WebDriverWait(self.driver, 10).until(
                                EC.staleness_of(business_elements[0])
                            )
                            time.sleep(random.uniform(1, 2))
                        else:
                            logger.info("No more pages available")
                            break
                    except Exception as e:
                        logger.error(f"Error navigating to next page: {e}")
                        break
            
            # Record search in database
            self.db.record_search("YellowPages", f"{category} in {city}, {state}", len(companies))
            
            return companies
            
        except Exception as e:
            logger.error(f"Error scraping YellowPages: {e}")
            console.print(f"[bold red]Error scraping YellowPages: {e}[/bold red]")
            return companies
    
    def get_business_details(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a business"""
        if not company.get('name') or not company.get('city'):
            return company
        
        try:
            # Construct search URL for specific business
            business_name = company['name'].lower().replace(' ', '-')
            city_state = f"{company['city'].lower().replace(' ', '-')}-{company['state'].lower()}"
            search_url = f"https://www.yellowpages.com/search?search_terms={business_name}&geo_location_terms={city_state}"
            
            logger.info(f"Getting details for {company['name']}: {search_url}")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "search-results"))
                )
            except TimeoutException:
                logger.warning(f"No results found for {company['name']}")
                return company
            
            # Find the first result that matches our business
            business_elements = self.driver.find_elements(By.CLASS_NAME, "result")
            
            for element in business_elements:
                try:
                    name_element = element.find_elements(By.CLASS_NAME, "business-name")
                    if not name_element:
                        continue
                    
                    # Check if this is the business we're looking for
                    found_name = name_element[0].text.strip()
                    if self.similar_names(found_name, company['name']):
                        # Click on the business name to go to detail page
                        name_element[0].click()
                        
                        # Wait for detail page to load
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "business-card"))
                        )
                        
                        # Extract detailed information
                        self.extract_business_details(company)
                        break
                except Exception as e:
                    logger.error(f"Error processing search result: {e}")
                    continue
            
            return company
            
        except Exception as e:
            logger.error(f"Error getting business details: {e}")
            return company
    
    def extract_business_details(self, company: Dict[str, Any]) -> None:
        """Extract detailed business information from the detail page"""
        try:
            # Extract business description
            description_element = self.driver.find_elements(By.CLASS_NAME, "business-description")
            if description_element:
                company['description'] = description_element[0].text.strip()
            
            # Extract services
            services_elements = self.driver.find_elements(By.CSS_SELECTOR, ".services ul li")
            if services_elements:
                services = [element.text.strip() for element in services_elements]
                if services:
                    if 'category' in company:
                        company['category'] = f"{company['category']}, {', '.join(services)}"
                    else:
                        company['category'] = ', '.join(services)
            
            # Extract contact information
            contact_elements = self.driver.find_elements(By.CSS_SELECTOR, ".contact h2")
            for element in contact_elements:
                title = element.text.strip()
                if title.lower() in ["owner", "manager", "president", "ceo"]:
                    company['contact_title'] = title
                    name_element = element.find_element(By.XPATH, "following-sibling::p")
                    if name_element:
                        company['contact_person'] = name_element.text.strip()
            
            # Extract more details from about section
            about_elements = self.driver.find_elements(By.CSS_SELECTOR, ".about dt")
            for element in about_elements:
                label = element.text.strip().lower()
                value_element = element.find_element(By.XPATH, "following-sibling::dd[1]")
                
                if not value_element:
                    continue
                    
                value = value_element.text.strip()
                
                if "year established" in label and value:
                    company['year_built'] = value
                elif "building size" in label and value:
                    company['building_size'] = value
                elif "email" in label and value:
                    company['email'] = value
            
            # Recalculate lead score with new information
            company['lead_score'] = self.calculate_lead_score(company)
            
        except Exception as e:
            logger.error(f"Error extracting business details: {e}")
    
    def similar_names(self, name1: str, name2: str) -> bool:
        """Check if two business names are similar"""
        name1 = name1.lower()
        name2 = name2.lower()
        
        # Remove common business suffixes
        for suffix in [' inc', ' llc', ' corp', ' company', ' co', ' ltd']:
            name1 = name1.replace(suffix, '')
            name2 = name2.replace(suffix, '')
        
        # Compare cleaned names
        return name1.strip() == name2.strip() or name1.strip() in name2.strip() or name2.strip() in name1.strip()
    
    def calculate_lead_score(self, company: Dict[str, Any]) -> int:
        """Calculate a lead score based on available information"""
        score = 50  # Base score
        
        # Building age
        if company.get('year_built'):
            try:
                year = int(company['year_built'])
                current_year = datetime.datetime.now().year
                age = current_year - year
                
                if age > 30:
                    score += 20
                elif age > 20:
                    score += 15
                elif age > 10:
                    score += 10
            except (ValueError, TypeError):
                pass
        
        # Building size
        if company.get('building_size'):
            size_text = company['building_size'].lower()
            
            if 'sq ft' in size_text:
                # Try to extract square footage
                match = re.search(r'(\d[\d,]*)', size_text)
                if match:
                    try:
                        size = int(match.group(1).replace(',', ''))
                        if size > 100000:
                            score += 20
                        elif size > 50000:
                            score += 15
                        elif size > 20000:
                            score += 10
                    except (ValueError, TypeError):
                        pass
            
            # If we couldn't parse, use keywords
            if 'large' in size_text:
                score += 15
            elif 'medium' in size_text:
                score += 10
        
        # Website available (indicates established business)
        if company.get('website'):
            score += 10
        
        # Contact person available
        if company.get('contact_person'):
            score += 10
        
        # Description available
        if company.get('description'):
            score += 5
        
        # Category/Services
        if company.get('category'):
            category = company['category'].lower()
            
            # Add points for promising categories
            energy_keywords = ['energy', 'utilities', 'building', 'property', 'office', 'commercial', 
                              'industrial', 'manufacturing', 'factory', 'school', 'hospital',
                              'hotel', 'retail', 'restaurant', 'mall', 'warehouse']
            
            for keyword in energy_keywords:
                if keyword in category:
                    score += 5
                    break
        
        # Cap score at 100
        return min(score, 100)

class GoogleMapsScraper:
    """Scrapes business data from Google Maps"""
    
    def __init__(self, db: Database):
        self.db = db
        self.driver = None
    
    def __enter__(self):
        self.driver = setup_selenium()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
    
    def search_businesses(self, city: str, state: str, category: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for businesses in a specific city and category"""
        companies = []
        
        try:
            # Format search query
            if category:
                search_query = f"{category} in {city}, {state}"
            else:
                search_query = f"commercial buildings in {city}, {state}"
            
            # Encode for URL
            query_encoded = search_query.replace(' ', '+')
            
            # Construct search URL
            search_url = f"https://www.google.com/maps/search/{query_encoded}"
            
            logger.info(f"Searching Google Maps: {search_url}")
            console.print(f"[yellow]Searching for businesses in {city}, {state}...[/yellow]")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            time.sleep(3)  # Initial wait for results
            
            results_found = 0
            
            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task(f"Scraping business data...", total=max_results)
                
                # Use JavaScript to scroll through results
                last_height = self.driver.execute_script("return document.querySelector('.section-layout.section-scrollbox').scrollHeight")
                
                while results_found < max_results:
                    # Get all result elements
                    result_elements = self.driver.find_elements(By.CSS_SELECTOR, ".section-result")
                    
                    # Process visible results
                    for element in result_elements[results_found:]:
                        if results_found >= max_results:
                            break
                            
                        try:
                            company = {}
                            
                            # Click on the result to see details
                            element.click()
                            
                            # Wait for details panel to load
                            time.sleep(2)
                            
                            # Extract information from details panel
                            company = self.extract_business_info()
                            
                            # Add location if not found in details
                            if 'city' not in company:
                                company['city'] = city
                                company['state'] = state
                            
                            # Add source and calculate lead score
                            company['source'] = "Google Maps"
                            company['lead_score'] = self.calculate_lead_score(company)
                            
                            # Add to results if we got a name
                            if company.get('name'):
                                companies.append(company)
                                results_found += 1
                                progress.update(task, advance=1)
                            
                            # Go back to results
                            back_button = self.driver.find_elements(By.CSS_SELECTOR, "button.section-back-to-list-button")
                            if back_button:
                                back_button[0].click()
                                time.sleep(1)
                            
                            # Small sleep to avoid overloading
                            time.sleep(random.uniform(0.5, 1.0))
                            
                        except Exception as e:
                            logger.error(f"Error processing business element: {e}")
                            # Try to go back to results
                            try:
                                back_button = self.driver.find_elements(By.CSS_SELECTOR, "button.section-back-to-list-button")
                                if back_button:
                                    back_button[0].click()
                                    time.sleep(1)
                            except:
                                pass
                            continue
                    
                    # Check if we have enough results
                    if results_found >= max_results:
                        break
                    
                    # Scroll down to load more results
                    self.driver.execute_script("document.querySelector('.section-layout.section-scrollbox').scrollTo(0, document.querySelector('.section-layout.section-scrollbox').scrollHeight);")
                    time.sleep(2)
                    
                    # Check if we've reached the end of the scroll
                    new_height = self.driver.execute_script("return document.querySelector('.section-layout.section-scrollbox').scrollHeight")
                    if new_height == last_height:
                        break
                    
                    last_height = new_height
            
            # Record search in database
            self.db.record_search("Google Maps", f"{category} in {city}, {state}", len(companies))
            
            return companies
            
        except Exception as e:
            logger.error(f"Error scraping Google Maps: {e}")
            console.print(f"[bold red]Error scraping Google Maps: {e}[/bold red]")
            return companies
    
    def extract_business_info(self) -> Dict[str, Any]:
        """Extract business information from Google Maps details panel"""
        company = {}
        
        try:
            # Extract name
            name_element = self.driver.find_elements(By.CSS_SELECTOR, "h1.section-hero-header-title-title")
            if name_element:
                company['name'] = name_element[0].text.strip()
            
            # Extract address
            address_element = self.driver.find_elements(By.CSS_SELECTOR, "button[data-item-id='address']")
            if address_element:
                full_address = address_element[0].text.strip()
                # Try to parse city, state, zip
                match = re.search(r"(.*?),\s*(.*?),\s*(\w{2})\s*(\d{5})?", full_address)
                if match:
                    company['address'] = match.group(1).strip()
                    company['city'] = match.group(2).strip()
                    company['state'] = match.group(3).strip()
                    company['zipcode'] = match.group(4) if match.group(4) else ""
                else:
                    company['address'] = full_address
            
            # Extract phone
            phone_element = self.driver.find_elements(By.CSS_SELECTOR, "button[data-item-id='phone:tel']")
            if phone_element:
                company['phone'] = phone_element[0].text.strip()
            
            # Extract website
            website_element = self.driver.find_elements(By.CSS_SELECTOR, "a[data-item-id='authority']")
            if website_element:
                company['website'] = website_element[0].get_attribute("href")
            
            # Extract categories/services
            category_element = self.driver.find_elements(By.CSS_SELECTOR, "button[jsaction='pane.rating.category']")
            if category_element:
                company['category'] = category_element[0].text.strip()
            
            # Extract description from reviews or other text
            description_element = self.driver.find_elements(By.CSS_SELECTOR, ".section-editorial-quote")
            if description_element:
                company['description'] = description_element[0].text.strip()
            
            return company
            
        except Exception as e:
            logger.error(f"Error extracting business info: {e}")
            return company
    
    def calculate_lead_score(self, company: Dict[str, Any]) -> int:
        """Calculate a lead score based on available information"""
        score = 50  # Base score
        
        # Website available (indicates established business)
        if company.get('website'):
            score += 10
        
        # Address available
        if company.get('address'):
            score += 10
        
        # Phone available
        if company.get('phone'):
            score += 5
        
        # Description available
        if company.get('description'):
            score += 5
        
        # Category/Services
        if company.get('category'):
            category = company['category'].lower()
            
            # Add points for promising categories
            energy_keywords = ['energy', 'utilities', 'building', 'property', 'office', 'commercial', 
                              'industrial', 'manufacturing', 'factory', 'school', 'hospital',
                              'hotel', 'retail', 'restaurant', 'mall', 'warehouse']
            
            for keyword in energy_keywords:
                if keyword in category:
                    score += 10
                    break
        
        # Cap score at 100
        return min(score, 100)

class AILeadFinder:
    """Uses OpenAI to proactively find and identify potential leads"""
    
    def __init__(self, db: Database):
        self.db = db
        self.enabled = AI_ENABLED
    
    def find_potential_leads(self, city: str, state: str, industry: str = None) -> List[Dict[str, Any]]:
        """Use AI to generate potential leads based on city, state, and optional industry"""
        if not self.enabled:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return []
        
        try:
            # Prepare context for AI
            context = (
                f"City: {city}\n"
                f"State: {state}\n"
            )
            
            if industry:
                context += f"Industry focus: {industry}\n"
            
            context += (
                "Company type: Looking for businesses that would benefit from energy efficiency solutions, "
                "particularly those with older or larger buildings, or businesses with high energy consumption like: "
                "offices, retail, hospitals, schools, manufacturing, data centers, etc."
            )
            
            # Ask AI to generate potential leads
            console.print(f"[yellow]Using AI to identify potential leads in {city}, {state}...[/yellow]")
            
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert lead researcher for an energy efficiency solutions company. "
                        "Based on the provided city and criteria, generate a list of 5-10 potential "
                        "client businesses that would likely benefit from energy efficiency upgrades. "
                        "For each business, provide:\n"
                        "1. Business name\n"
                        "2. Type of business/industry\n"
                        "3. Likely size (small, medium, large)\n"
                        "4. Why they would benefit from energy efficiency solutions\n"
                        "5. Who the key decision-maker would likely be (role, not specific name)\n"
                        "6. Suggested approach for contacting them\n\n"
                        "Format your response as a structured JSON array with the following fields for each lead: "
                        "name, category, size, reason, contact_title, approach"
                    )},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse AI response - looking for JSON format
            response_text = response.choices[0].message['content']
            
            # Extract JSON array from response
            try:
                # Find JSON array in the response
                import re
                import json
                
                # Try to extract JSON using regex
                json_match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    ai_generated_leads = json.loads(json_str)
                else:
                    # Fall back to trying to parse the whole response
                    ai_generated_leads = json.loads(response_text)
                
                # Convert AI generated leads to our lead format
                leads = []
                for lead in ai_generated_leads:
                    company = {
                        'name': lead.get('name', ''),
                        'category': lead.get('category', ''),
                        'building_size': lead.get('size', ''),
                        'city': city,
                        'state': state,
                        'contact_title': lead.get('contact_title', ''),
                        'description': lead.get('reason', ''),
                        'notes': lead.get('approach', ''),
                        'source': 'AI Generated',
                        'ai_analysis': lead.get('reason', '')
                    }
                    
                    # Calculate a lead score
                    company['lead_score'] = self._calculate_lead_score(company)
                    
                    # Add to results
                    leads.append(company)
                    
                    # Store in database
                    self.db.insert_company(company)
                
                return leads
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to extract structured information manually
                console.print(f"[yellow]Could not parse JSON from AI response. Extracting information manually...[/yellow]")
                
                # Look for numbered list items or business names
                leads = self._extract_leads_from_text(response_text, city, state)
                
                # Store in database
                for company in leads:
                    self.db.insert_company(company)
                
                return leads
                
        except Exception as e:
            logger.error(f"Error using AI to find leads: {e}")
            console.print(f"[bold red]Error using AI to find leads: {e}[/bold red]")
            return []
    
    def research_company(self, company_name: str, city: str, state: str) -> Dict[str, Any]:
        """Use AI to research a specific company and generate lead information"""
        if not self.enabled:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return {}
        
        try:
            # Prepare context for AI
            context = (
                f"Company Name: {company_name}\n"
                f"City: {city}\n"
                f"State: {state}\n"
                f"Research Task: Generate detailed lead information about this company for an energy efficiency solutions provider."
            )
            
            # Ask AI to research the company
            console.print(f"[yellow]Using AI to research {company_name}...[/yellow]")
            
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert lead researcher for an energy efficiency solutions company. "
                        "Research the specified company and provide detailed information that would be helpful "
                        "for sales outreach. If you don't have specific information about this company, "
                        "provide your best educated guess based on similar companies in the same industry and location.\n\n"
                        "Format your response as a structured JSON object with the following fields:\n"
                        "- name: Company name\n"
                        "- address: Likely address or area\n"
                        "- category: Business category/industry\n"
                        "- building_size: Estimated size\n"
                        "- year_built: Estimated year founded or building age\n"
                        "- description: Brief description of the company\n"
                        "- contact_person: Likely decision-maker name (if known, otherwise leave blank)\n"
                        "- contact_title: Likely decision-maker title\n"
                        "- energy_needs: Likely energy efficiency needs\n"
                        "- approach: Suggested sales approach"
                    )},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            # Parse AI response
            response_text = response.choices[0].message['content']
            
            try:
                # Extract JSON from response
                import json
                import re
                
                # Try to extract JSON object
                json_match = re.search(r'\{\s*".*"\s*:.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    company_data = json.loads(json_str)
                else:
                    # Fall back to trying to parse the whole response
                    company_data = json.loads(response_text)
                
                # Convert to our company format
                company = {
                    'name': company_data.get('name', company_name),
                    'address': company_data.get('address', ''),
                    'city': city,
                    'state': state,
                    'category': company_data.get('category', ''),
                    'building_size': company_data.get('building_size', ''),
                    'year_built': company_data.get('year_built', ''),
                    'description': company_data.get('description', ''),
                    'contact_person': company_data.get('contact_person', ''),
                    'contact_title': company_data.get('contact_title', ''),
                    'notes': company_data.get('approach', ''),
                    'source': 'AI Researched',
                    'ai_analysis': company_data.get('energy_needs', '')
                }
                
                # Calculate lead score
                company['lead_score'] = self._calculate_lead_score(company)
                
                # Store in database
                self.db.insert_company(company)
                
                return company
                
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing AI company research response: {e}")
                
                # Create basic company record
                company = {
                    'name': company_name,
                    'city': city,
                    'state': state,
                    'description': response_text[:500],  # Use part of the response as description
                    'source': 'AI Researched (partial)',
                    'notes': 'Error parsing AI response'
                }
                
                # Calculate lead score
                company['lead_score'] = self._calculate_lead_score(company)
                
                # Store in database
                self.db.insert_company(company)
                
                return company
                
        except Exception as e:
            logger.error(f"Error using AI to research company: {e}")
            console.print(f"[bold red]Error using AI to research company: {e}[/bold red]")
            return {'name': company_name, 'city': city, 'state': state, 'source': 'AI Research Failed'}
    
    def identify_lead_sources(self, city: str, state: str) -> str:
        """Use AI to identify potential lead sources specific to a city"""
        if not self.enabled:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return ""
        
        try:
            # Prepare context for AI
            context = (
                f"City: {city}\n"
                f"State: {state}\n"
                f"Task: Identify specific lead sources (websites, directories, organizations, etc.) "
                f"that would be good for finding potential clients for energy efficiency solutions in this location."
            )
            
            # Ask AI to identify lead sources
            console.print(f"[yellow]Using AI to identify lead sources in {city}, {state}...[/yellow]")
            
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert in B2B sales and lead generation for energy efficiency solutions. "
                        "Identify specific lead sources that would be valuable for finding potential clients "
                        "in the specified location. Focus on:\n"
                        "1. Local business directories\n"
                        "2. Industry associations\n"
                        "3. Chamber of commerce\n"
                        "4. Local government resources\n"
                        "5. Specific databases\n"
                        "6. Events or conferences\n\n"
                        "Be specific to the location. Provide the name of each source and a brief explanation "
                        "of why it would be valuable."
                    )},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            return response.choices[0].message['content']
            
        except Exception as e:
            logger.error(f"Error identifying lead sources: {e}")
            console.print(f"[bold red]Error identifying lead sources: {e}[/bold red]")
            return ""
    
    def analyze_market_potential(self, city: str, state: str) -> str:
        """Use AI to analyze the market potential for energy efficiency solutions in a specific city"""
        if not self.enabled:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return ""
        
        try:
            # Prepare context for AI
            context = (
                f"City: {city}\n"
                f"State: {state}\n"
                f"Task: Analyze the market potential for energy efficiency solutions in this location."
            )
            
            # Ask AI to analyze market potential
            console.print(f"[yellow]Using AI to analyze market potential in {city}, {state}...[/yellow]")
            
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert market analyst specializing in energy efficiency and sustainability. "
                        "Analyze the market potential for energy efficiency solutions in the specified location. "
                        "Include in your analysis:\n"
                        "1. Overview of the local business landscape\n"
                        "2. Building stock characteristics (age, types, size)\n"
                        "3. Local energy costs and consumption patterns\n"
                        "4. Regulatory environment and incentives\n"
                        "5. Competitive landscape\n"
                        "6. Top 3-5 industry verticals to target\n"
                        "7. Estimated market size and growth potential\n\n"
                        "Be specific to the location and provide actionable insights."
                    )},
                    {"role": "user", "content": context}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message['content']
            
        except Exception as e:
            logger.error(f"Error analyzing market potential: {e}")
            console.print(f"[bold red]Error analyzing market potential: {e}[/bold red]")
            return ""
    
    def _extract_leads_from_text(self, text: str, city: str, state: str) -> List[Dict[str, Any]]:
        """Extract lead information from non-JSON AI response text"""
        leads = []
        
        # Look for numbered items or sections
        import re
        
        # Try to find business names with details
        business_sections = re.split(r'\d+\.\s+|\n\n+', text)
        
        for section in business_sections:
            if not section.strip():
                continue
                
            # Try to extract business name (usually at the beginning of a section)
            name_match = re.search(r'^([^:\n]+)(?::|$)', section.strip())
            if name_match:
                name = name_match.group(1).strip()
                
                # Skip if this doesn't look like a business name
                if len(name) < 3 or name.lower() in ['business name', 'company']:
                    continue
                
                company = {
                    'name': name,
                    'city': city,
                    'state': state,
                    'source': 'AI Generated',
                    'description': section.strip()
                }
                
                # Try to extract category/industry
                category_match = re.search(r'(?:Type|Category|Industry):\s*([^\n]+)', section, re.IGNORECASE)
                if category_match:
                    company['category'] = category_match.group(1).strip()
                
                # Try to extract size
                size_match = re.search(r'(?:Size|Building Size):\s*([^\n]+)', section, re.IGNORECASE)
                if size_match:
                    company['building_size'] = size_match.group(1).strip()
                
                # Try to extract reason/benefits
                reason_match = re.search(r'(?:Reason|Why|Benefits|Opportunity):\s*([^\n]+(?:\n[^\n:]+)*)', section, re.IGNORECASE)
                if reason_match:
                    company['ai_analysis'] = reason_match.group(1).strip()
                
                # Try to extract contact/decision-maker
                contact_match = re.search(r'(?:Contact|Decision[- ]maker|Key Person):\s*([^\n]+)', section, re.IGNORECASE)
                if contact_match:
                    company['contact_title'] = contact_match.group(1).strip()
                
                # Try to extract approach
                approach_match = re.search(r'(?:Approach|Strategy|How to contact):\s*([^\n]+(?:\n[^\n:]+)*)', section, re.IGNORECASE)
                if approach_match:
                    company['notes'] = approach_match.group(1).strip()
                
                # Calculate lead score
                company['lead_score'] = self._calculate_lead_score(company)
                
                leads.append(company)
        
        return leads
    
    def _calculate_lead_score(self, company: Dict[str, Any]) -> int:
        """Calculate a lead score for AI-generated leads"""
        score = 50  # Base score
        
        # Size factor
        if company.get('building_size'):
            size = company['building_size'].lower()
            if 'large' in size:
                score += 20
            elif 'medium' in size:
                score += 10
            elif 'small' in size:
                score += 5
        
        # Year/age factor
        if company.get('year_built'):
            try:
                year = int(company['year_built'])
                current_year = datetime.datetime.now().year
                age = current_year - year
                
                if age > 30:
                    score += 20
                elif age > 20:
                    score += 15
                elif age > 10:
                    score += 10
            except (ValueError, TypeError):
                # If not a valid year, check for age-related keywords
                year_text = company['year_built'].lower()
                if 'old' in year_text or 'aging' in year_text:
                    score += 15
        
        # Category/industry factor
        if company.get('category'):
            category = company['category'].lower()
            
            high_energy_sectors = ['manufacturing', 'industrial', 'factory', 'warehouse', 
                                  'hospital', 'healthcare', 'hotel', 'lodging', 'data center',
                                  'office building', 'school', 'university', 'retail']
            
            for sector in high_energy_sectors:
                if sector in category:
                    score += 15
                    break
        
        # AI analysis content
        if company.get('ai_analysis'):
            analysis = company['ai_analysis'].lower()
            
            opportunity_keywords = ['high energy', 'inefficient', 'outdated', 'saving', 'cost reduction',
                                   'upgrade', 'retrofit', 'improvement', 'consumption', 'bill', 'expense']
            
            keyword_count = sum(1 for keyword in opportunity_keywords if keyword in analysis)
            score += min(keyword_count * 3, 15)  # Up to 15 points for keywords
        
        # Contact information
        if company.get('contact_title'):
            decision_maker_roles = ['owner', 'ceo', 'president', 'director', 'manager', 'facility']
            
            for role in decision_maker_roles:
                if role.lower() in company.get('contact_title', '').lower():
                    score += 10
                    break
        
        # Cap score at 100
        return min(score, 100)

class AIAnalyzer:
    """Uses OpenAI to analyze and enhance lead data"""
    
    def __init__(self, db: Database):
        self.db = db
        self.enabled = AI_ENABLED
    
    def analyze_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a company to identify energy efficiency opportunities"""
        if not self.enabled:
            return company
        
        try:
            # Prepare company context
            company_context = (
                f"Company: {company.get('name', 'Unknown')}\n"
                f"Category/Industry: {company.get('category', 'Unknown')}\n"
                f"Address: {company.get('address', 'Unknown')}, {company.get('city', '')}, {company.get('state', '')}\n"
                f"Building Size: {company.get('building_size', 'Unknown')}\n"
                f"Year Built/Established: {company.get('year_built', 'Unknown')}\n"
                f"Description: {company.get('description', 'Unknown')}\n"
                f"Contact: {company.get('contact_person', '')}, {company.get('contact_title', '')}\n"
                f"Website: {company.get('website', '')}\n"
            )
            
            # Ask AI to analyze energy efficiency opportunities
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert in energy efficiency and sustainable building solutions. "
                        "Analyze this potential lead to determine their energy efficiency needs and opportunities. "
                        "Focus on identifying their likely energy-related pain points and how LogicLamp Technologies "
                        "(a company specializing in energy efficiency solutions like LED lighting and smart building technologies) "
                        "could help them reduce costs and improve sustainability. "
                        "Provide a brief opportunity assessment and a lead quality score from 0-100 based on their potential "
                        "need for energy efficiency solutions. Higher scores mean better opportunities."
                    )},
                    {"role": "user", "content": company_context}
                ],
                temperature=0.5,
                max_tokens=500
            )
            
            ai_analysis = response.choices[0].message['content']
            
            # Extract lead score from analysis
            score_match = re.search(r'(?:score|rating):\s*(\d+)', ai_analysis, re.IGNORECASE)
            if score_match:
                ai_lead_score = int(score_match.group(1))
                # Blend AI score with algorithm score
                original_score = company.get('lead_score', 50)
                company['lead_score'] = int((original_score + ai_lead_score) / 2)
            
            # Add AI analysis to company
            company['ai_analysis'] = ai_analysis
            
            return company
            
        except Exception as e:
            logger.error(f"Error in AI company analysis: {e}")
            return company
    
    def generate_outreach_email(self, company: Dict[str, Any]) -> str:
        """Generate personalized outreach email for a company"""
        if not self.enabled:
            return "AI features are disabled. Configure your OpenAI API key to use this feature."
        
        try:
            # Prepare company context
            company_context = (
                f"Company: {company.get('name', 'Unknown')}\n"
                f"Category/Industry: {company.get('category', 'Unknown')}\n"
                f"Contact Person: {company.get('contact_person', 'Building Owner/Manager')}, {company.get('contact_title', '')}\n"
                f"Building Size: {company.get('building_size', 'Unknown')}\n"
                f"Year Built/Established: {company.get('year_built', 'Unknown')}\n"
                f"City, State: {company.get('city', '')}, {company.get('state', '')}\n"
                f"Lead Score: {company.get('lead_score', 50)}/100\n"
            )
            
            # Add AI analysis if available
            if company.get('ai_analysis'):
                company_context += f"\nAI Analysis: {company.get('ai_analysis')}\n"
            
            # Ask AI to generate personalized outreach
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a skilled sales development representative for LogicLamp Technologies, "
                        "a company specializing in energy efficiency and sustainability solutions including "
                        "LED lighting retrofits, smart building technologies, and energy management systems. "
                        "Write a personalized, compelling outreach email to this company. "
                        "Format your response with 'Subject: [Your subject line]' on the first line, "
                        "followed by the email body. "
                        "Focus on the specific benefits they would gain based on their profile. "
                        "Keep it concise (150-200 words), professional, and emphasize potential energy savings. "
                        "Do not use pushy sales language. Make it warm and conversational. "
                        "Include a clear call to action for a brief intro call."
                    )},
                    {"role": "user", "content": company_context}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message['content']
            
        except Exception as e:
            logger.error(f"Error generating outreach email: {e}")
            return f"Error generating email: {str(e)}"

class Exporter:
    """Handles exporting data to various formats"""
    
    def __init__(self, db: Database):
        self.db = db
        self.output_dir = os.path.expanduser("~/Documents/LeadFinder")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export_csv(self, companies: List[Dict[str, Any]], filename: str = None) -> str:
        """Export companies to CSV file"""
        if not companies:
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"leads_export_{timestamp}.csv"
        
        # Full path to output file
        output_path = os.path.join(self.output_dir, filename)
        
        # Fields to export (in order)
        fieldnames = [
            'name', 'address', 'city', 'state', 'zipcode', 'phone', 'email', 'website',
            'contact_person', 'contact_title', 'category', 'building_size', 'year_built',
            'lead_score', 'description', 'source', 'notes'
        ]
        
        try:
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                for company in companies:
                    # Only write fields in our fieldnames list
                    row = {field: company.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            
            # Record export in database
            self.db.record_export("csv", output_path, len(companies))
            
            return output_path
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None
    
    def export_hubspot_csv(self, companies: List[Dict[str, Any]], filename: str = None) -> str:
        """Export companies in HubSpot-compatible CSV format"""
        if not companies:
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hubspot_export_{timestamp}.csv"
        
        # Full path to output file
        output_path = os.path.join(self.output_dir, filename)
        
        # Define HubSpot fieldnames mapping
        hubspot_fields = [
            "Company", "First Name", "Last Name", "Email", "Phone", 
            "Address", "City", "State/Region", "Postal Code",
            "Website", "Industry", "Lead Score", "Description", "Notes"
        ]
        
        try:
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=hubspot_fields)
                writer.writeheader()
                
                for company in companies:
                    # Parse contact name into first/last
                    first_name = ""
                    last_name = ""
                    if company.get('contact_person'):
                        name_parts = company['contact_person'].split(' ', 1)
                        first_name = name_parts[0] if name_parts else ''
                        last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    # Create HubSpot record
                    hubspot_record = {
                        "Company": company.get('name', ''),
                        "First Name": first_name,
                        "Last Name": last_name,
                        "Email": company.get('email', ''),
                        "Phone": company.get('phone', ''),
                        "Address": company.get('address', ''),
                        "City": company.get('city', ''),
                        "State/Region": company.get('state', ''),
                        "Postal Code": company.get('zipcode', ''),
                        "Website": company.get('website', ''),
                        "Industry": company.get('category', ''),
                        "Lead Score": company.get('lead_score', ''),
                        "Description": company.get('description', ''),
                        "Notes": company.get('notes', '')
                    }
                    
                    writer.writerow(hubspot_record)
            
            # Record export in database
            self.db.record_export("hubspot_csv", output_path, len(companies))
            
            return output_path
        except Exception as e:
            logger.error(f"Error exporting to HubSpot CSV: {e}")
            return None
    
    def export_outreach_emails(self, companies: List[Dict[str, Any]], emails: List[str], filename: str = None) -> str:
        """Export outreach emails to a text file"""
        if not companies or not emails or len(companies) != len(emails):
            return None
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"outreach_emails_{timestamp}.txt"
        
        # Full path to output file
        output_path = os.path.join(self.output_dir, filename)
        
        try:
            with open(output_path, 'w') as f:
                for i, (company, email) in enumerate(zip(companies, emails)):
                    f.write(f"EMAIL #{i+1}: {company.get('name', 'Unknown Company')}\n")
                    f.write("=" * 70 + "\n\n")
                    f.write(email + "\n\n")
                    f.write("=" * 70 + "\n\n")
            
            # Record export in database
            self.db.record_export("outreach_emails", output_path, len(companies))
            
            return output_path
        except Exception as e:
            logger.error(f"Error exporting outreach emails: {e}")
            return None

class LeadFinder:
    """Main application class"""
    
    def __init__(self):
        """Initialize the application"""
        self.db = Database()
        self.exporter = Exporter(self.db)
        self.ai = AIAnalyzer(self.db)
        self.ai_finder = AILeadFinder(self.db)
    
    def show_welcome(self):
        """Show welcome message"""
        console.print(Panel.fit(
            f"[bold green]LeadFinder v{VERSION}[/bold green]\n\n"
            "[bold]Real Lead Generation Tool for LogicLamp Technologies[/bold]\n\n"
            f"[{'green' if AI_ENABLED else 'red'}]AI Features: {'Enabled' if AI_ENABLED else 'Disabled'}[/]\n\n"
            "Type [cyan]leadfinder help[/cyan] for available commands.",
            title="Welcome to LeadFinder",
            border_style="green"
        ))
    
    def show_dashboard(self):
        """Show dashboard with statistics"""
        stats = self.db.get_stats()
        
        ai_status = "[green]Enabled[/green]" if AI_ENABLED else "[red]Disabled[/red]"
        
        console.print(Panel.fit(
            f"[bold]Lead Database:[/bold] {stats.get('company_count', 0)} companies\n"
            f"[bold]Cities Covered:[/bold] {stats.get('city_count', 0)} cities\n"
            f"[bold]Average Lead Score:[/bold] {stats.get('avg_lead_score', 0):.1f}/100\n"
            f"[bold]AI-Analyzed Leads:[/bold] {stats.get('ai_analyzed_count', 0)}\n\n"
            f"[bold]Searches Performed:[/bold] {stats.get('search_count', 0)}\n"
            f"[bold]Exports Created:[/bold] {stats.get('export_count', 0)}\n\n"
            f"[bold]AI Assistant:[/bold] {ai_status}",
            title="LeadFinder Dashboard",
            border_style="cyan"
        ))
    
    def find_leads(self, city: str, state: str, category: str = None, source: str = "all", count: int = 20, get_details: bool = True) -> List[Dict[str, Any]]:
        """Find leads in a specific city with optional filters"""
        console.print(f"[bold]Finding leads in {city}, {state}...[/bold]")
        
        all_companies = []
        
        # YellowPages scraping
        if source.lower() in ["all", "yellowpages"]:
            with YellowPagesScraper(self.db) as scraper:
                console.print(f"[yellow]Searching YellowPages for businesses in {city}, {state}...[/yellow]")
                companies = scraper.search_businesses(city, state, category, count)
                
                if get_details and companies:
                    console.print(f"[yellow]Getting detailed information for {len(companies)} businesses...[/yellow]")
                    
                    with Progress(
                        TextColumn("[bold blue]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console
                    ) as progress:
                        detail_task = progress.add_task(f"Gathering details...", total=len(companies))
                        
                        for i, company in enumerate(companies):
                            company = scraper.get_business_details(company)
                            companies[i] = company
                            progress.update(detail_task, advance=1)
                
                # Store companies in database
                console.print(f"[yellow]Storing {len(companies)} businesses in database...[/yellow]")
                for company in companies:
                    self.db.insert_company(company)
                
                console.print(f"[green]✓[/green] Found {len(companies)} businesses on YellowPages")
                all_companies.extend(companies)
        
        # Google Maps scraping
        if source.lower() in ["all", "googlemaps"]:
            with GoogleMapsScraper(self.db) as scraper:
                console.print(f"[yellow]Searching Google Maps for businesses in {city}, {state}...[/yellow]")
                companies = scraper.search_businesses(city, state, category, count)
                
                # Store companies in database
                console.print(f"[yellow]Storing {len(companies)} businesses in database...[/yellow]")
                for company in companies:
                    self.db.insert_company(company)
                
                console.print(f"[green]✓[/green] Found {len(companies)} businesses on Google Maps")
                all_companies.extend(companies)
        
        # AI Analysis if enabled and requested
        if AI_ENABLED and get_details:
            with Progress(
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                ai_task = progress.add_task(f"Analyzing leads with AI...", total=len(all_companies))
                
                for i, company in enumerate(all_companies):
                    company = self.ai.analyze_company(company)
                    all_companies[i] = company
                    
                    # Update in database
                    if company.get('id'):
                        self.db.update_company(company['id'], {
                            'ai_analysis': company.get('ai_analysis'),
                            'lead_score': company.get('lead_score')
                        })
                    
                    progress.update(ai_task, advance=1)
                    
                    # Small sleep to avoid rate limits
                    time.sleep(0.5)
        
        # Sort by lead score
        all_companies.sort(key=lambda x: x.get('lead_score', 0), reverse=True)
        
        return all_companies
    
    def ai_find_leads(self, city: str, state: str, industry: str = None):
        """Use AI to identify potential leads in a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Using AI to find leads in {city}, {state}...[/bold]")
        
        # Find potential leads using AI
        leads = self.ai_finder.find_potential_leads(city, state, industry)
        
        if not leads:
            console.print("[yellow]No leads were generated by AI. Try a different location or industry.[/yellow]")
            return
        
        console.print(f"[green]✓[/green] AI generated {len(leads)} potential leads")
        
        # Show generated leads
        table = Table(title=f"AI-Generated Leads for {city}, {state}")
        
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Category")
        table.add_column("Size")
        table.add_column("Key Contact")
        table.add_column("Lead Score", style="bold cyan")
        
        for i, lead in enumerate(leads):
            table.add_row(
                str(lead.get('id', i+1)),
                lead.get('name', 'Unknown'),
                lead.get('category', ''),
                lead.get('building_size', ''),
                lead.get('contact_title', ''),
                f"{lead.get('lead_score', 0)}"
            )
        
        console.print(table)
        
        # Offer to analyze the market as well
        if console.input("\n[bold]Would you like an AI analysis of the market potential in this area? (y/n):[/bold] ").lower() == 'y':
            self.analyze_market(city, state)
    
    def research_company(self, name: str, city: str, state: str):
        """Use AI to research a specific company"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Researching {name} in {city}, {state}...[/bold]")
        
        # Research the company
        company = self.ai_finder.research_company(name, city, state)
        
        if not company:
            console.print(f"[yellow]Could not research company: {name}[/yellow]")
            return
        
        # Display company details
        self.view_company(company.get('id', 0))
        
        # Offer to generate outreach email
        if console.input("\n[bold]Generate outreach email? (y/n):[/bold] ").lower() == 'y':
            self.generate_outreach(id=company.get('id', 0))
    
    def identify_sources(self, city: str, state: str):
        """Identify lead sources for a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Identifying lead sources for {city}, {state}...[/bold]")
        
        # Get lead sources
        sources = self.ai_finder.identify_lead_sources(city, state)
        
        # Display sources
        console.print(Panel.fit(
            f"{sources}",
            title=f"Lead Sources for {city}, {state}",
            border_style="green"
        ))
    
    def analyze_market(self, city: str, state: str):
        """Analyze market potential for a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Analyzing market potential in {city}, {state}...[/bold]")
        
        # Get market analysis
        analysis = self.ai_finder.analyze_market_potential(city, state)
        
        # Display analysis
        console.print(Panel.fit(
            f"{analysis}",
            title=f"Market Analysis: {city}, {state}",
            border_style="green"
        ))
    
    def list_companies(self, limit: int = 10, city: str = None, state: str = None, category: str = None, min_score: int = None):
        """List companies in the database"""
        # Prepare filters
        filters = {}
        if city:
            filters['city'] = city
        if state:
            filters['state'] = state
        if category:
            filters['category'] = category
        if min_score:
            filters['min_lead_score'] = min_score
        
        # Get companies
        companies = self.db.get_companies(limit=limit, filters=filters)
        
        if not companies:
            console.print("[yellow]No companies found matching criteria.[/yellow]")
            return
        
        # Get total count
        total_count = self.db.count_companies(filters)
        
        # Create table
        table = Table(title=f"Top {len(companies)} Companies (Total: {total_count})")
        
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Location")
        table.add_column("Category")
        table.add_column("Contact")
        table.add_column("Phone")
        table.add_column("Lead Score", style="bold cyan")
        table.add_column("AI Analyzed", style="green")
        
        for company in companies:
            # Format location
            location = f"{company.get('city', '')}, {company.get('state', '')}"
            
            # Format contact
            contact = company.get('contact_person', '')
            
            # Format category (truncate if too long)
            category = company.get('category', '')
            if category and len(category) > 30:
                category = category[:27] + "..."
            
            # AI analysis indicator
            ai_analyzed = "✓" if company.get('ai_analysis') else ""
            
            # Add row to table
            table.add_row(
                str(company.get('id', '')),
                company.get('name', ''),
                location,
                category,
                contact,
                company.get('phone', ''),
                f"{company.get('lead_score', 0)}",
                ai_analyzed
            )
        
        console.print(table)
    
    def export_leads(self, format_type: str = "csv", city: str = None, state: str = None, min_score: int = 50, limit: int = 100):
        """Export leads to CSV or HubSpot format"""
        console.print(f"[bold]Exporting leads to {format_type} format...[/bold]")
        
        # Prepare filters
        filters = {}
        if city:
            filters['city'] = city
        if state:
            filters['state'] = state
        if min_score:
            filters['min_lead_score'] = min_score
        
        # Get companies
        companies = self.db.get_companies(limit=limit, filters=filters)
        
        if not companies:
            console.print("[yellow]No companies found matching criteria.[/yellow]")
            return
        
        if format_type.lower() == "hubspot":
            # Export to HubSpot format
            output_path = self.exporter.export_hubspot_csv(companies)
            export_type = "HubSpot"
        else:
            # Export to standard CSV
            output_path = self.exporter.export_csv(companies)
            export_type = "standard"
        
        if output_path:
            console.print(f"[green]✓[/green] Exported {len(companies)} companies to {export_type} CSV: [cyan]{output_path}[/cyan]")
        else:
            console.print(f"[red]✗[/red] Failed to export companies")
    
    def generate_outreach(self, id: int = None, count: int = 5, min_score: int = 70, export: bool = False):
        """Generate AI outreach emails for top leads"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        # Get companies by ID or by filters
        companies = []
        if id is not None:
            companies = self.db.get_companies(filters={"id": id})
            if not companies:
                console.print(f"[yellow]Company with ID {id} not found.[/yellow]")
                return
        else:
            companies = self.db.get_companies(limit=count, filters={"min_lead_score": min_score})
            if not companies:
                console.print(f"[yellow]No companies found with lead score >= {min_score}.[/yellow]")
                return
        
        console.print(f"[bold]Generating outreach emails for {len(companies)} companies...[/bold]")
        
        emails = []
        
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Generating emails...", total=len(companies))
            
            for company in companies:
                email = self.ai.generate_outreach_email(company)
                emails.append(email)
                progress.update(task, advance=1)
                
                # Small sleep to avoid rate limits
                time.sleep(0.5)
        
        # Display or export emails
        if export:
            output_path = self.exporter.export_outreach_emails(companies, emails)
            if output_path:
                console.print(f"[green]✓[/green] Exported {len(emails)} outreach emails: [cyan]{output_path}[/cyan]")
            else:
                console.print(f"[red]✗[/red] Failed to export outreach emails")
        else:
            for i, (company, email) in enumerate(zip(companies, emails)):
                console.print(Panel.fit(
                    f"{email}",
                    title=f"Outreach Email for {company.get('name', 'Unknown')}",
                    border_style="green"
                ))
                
                # If more than one email, add a break between them
                if i < len(emails) - 1:
                    console.print("\n")
    
    def view_company(self, company_id: int):
        """View detailed information about a company"""
        # Get company
        companies = self.db.get_companies(filters={"id": company_id})
        
        if not companies:
            console.print(f"[yellow]Company with ID {company_id} not found.[/yellow]")
            return
        
        company = companies[0]
        
        # Get AI analysis panel if available
        ai_panel = ""
        if company.get('ai_analysis'):
            ai_panel = f"\n\n[bold]AI Analysis:[/bold]\n{company['ai_analysis']}"
        
        # Display company details
        console.print(Panel.fit(
            f"[bold]{company.get('name', 'Unknown')}[/bold]\n\n"
            f"[bold]Address:[/bold] {company.get('address', 'Unknown')}, {company.get('city', '')}, {company.get('state', '')} {company.get('zipcode', '')}\n"
            f"[bold]Contact:[/bold] {company.get('contact_person', 'Unknown')}{', ' + company.get('contact_title', '') if company.get('contact_title') else ''}\n"
            f"[bold]Phone:[/bold] {company.get('phone', 'Unknown')}\n"
            f"[bold]Email:[/bold] {company.get('email', 'Unknown')}\n"
            f"[bold]Website:[/bold] {company.get('website', 'Unknown')}\n\n"
            f"[bold]Category:[/bold] {company.get('category', 'Unknown')}\n"
            f"[bold]Building Size:[/bold] {company.get('building_size', 'Unknown')}\n"
            f"[bold]Year Built/Established:[/bold] {company.get('year_built', 'Unknown')}\n\n"
            f"[bold]Description:[/bold] {company.get('description', 'No description available.')}\n\n"
            f"[bold]Lead Score:[/bold] [cyan]{company.get('lead_score', 0)}/100[/cyan]\n"
            f"[bold]Source:[/bold] {company.get('source', 'Unknown')}\n"
            f"[bold]Scraped At:[/bold] {company.get('scraped_at', 'Unknown')}"
            f"{ai_panel}",
            title=f"Company #{company_id}",
            border_style="green"
        ))
        
        # Offer to generate outreach email
        if AI_ENABLED and console.input("\n[bold]Generate outreach email? (y/n):[/bold] ").lower() == 'y':
            self.generate_outreach(id=company_id)
    
    def run_command(self, args):
        """Run command based on arguments"""
        if not hasattr(args, 'command') or not args.command:
            self.show_welcome()
            return
        
        command = args.command
        
        if command == "dashboard":
            self.show_dashboard()
        
        elif command == "find":
            companies = self.find_leads(
                city=args.city,
                state=args.state,
                category=args.category,
                source=args.source,
                count=args.count,
                get_details=args.details
            )
            
            console.print(f"[green]✓[/green] Found {len(companies)} potential leads")
            
            # Show top leads if we found any
            if companies:
                console.print("\n[bold]Top Leads:[/bold]")
                
                table = Table(title=f"Top {min(10, len(companies))} Leads")
                
                table.add_column("ID", style="dim")
                table.add_column("Name", style="bold")
                table.add_column("Location")
                table.add_column("Phone")
                table.add_column("Category")
                table.add_column("Lead Score", style="bold cyan")
                
                for i, company in enumerate(companies[:10]):
                    table.add_row(
                        str(company.get('id', i+1)),
                        company.get('name', 'Unknown'),
                        f"{company.get('city', '')}, {company.get('state', '')}",
                        company.get('phone', ''),
                        company.get('category', '')[:30] + ('...' if company.get('category', '') and len(company.get('category', '')) > 30 else ''),
                        f"{company.get('lead_score', 0)}"
                    )
                
                console.print(table)
        
        elif command == "ai-find":
            self.ai_find_leads(
                city=args.city,
                state=args.state,
                industry=args.industry
            )
        
        elif command == "research":
            self.research_company(
                name=args.name,
                city=args.city,
                state=args.state
            )
        
        elif command == "sources":
            self.identify_sources(
                city=args.city,
                state=args.state
            )
        
        elif command == "market":
            self.analyze_market(
                city=args.city,
                state=args.state
            )
        
        elif command == "list":
            self.list_companies(
                limit=args.limit,
                city=args.city,
                state=args.state,
                category=args.category,
                min_score=args.min_score
            )
        
        elif command == "export":
            self.export_leads(
                format_type=args.format,
                city=args.city,
                state=args.state,
                min_score=args.min_score,
                limit=args.limit
            )
        
        elif command == "view":
            self.view_company(args.id)
        
        elif command == "outreach":
            self.generate_outreach(
                id=args.id,
                count=args.count,
                min_score=args.min_score,
                export=args.export
            )
        
        else:
            console.print(f"[red]Unknown command: {command}[/red]")
    
    def close(self):
        """Clean up resources"""
        self.db.close()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='LeadFinder - Real Lead Generation Tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Show dashboard with statistics')
    
    # Find leads command (web scraping)
    find_parser = subparsers.add_parser('find', help='Find leads in a specific city using web scraping')
    find_parser.add_argument('city', type=str, help='City name')
    find_parser.add_argument('state', type=str, help='State (2-letter code)')
    find_parser.add_argument('--category', type=str, help='Business category to search (e.g., "office buildings")')
    find_parser.add_argument('--source', type=str, default='all', choices=['all', 'yellowpages', 'googlemaps'], help='Data source to use')
    find_parser.add_argument('--count', type=int, default=20, help='Maximum number of leads to find')
    find_parser.add_argument('--details', action='store_true', help='Get detailed information for each lead')
    
    # AI find leads command
    ai_find_parser = subparsers.add_parser('ai-find', help='Use AI to identify potential leads in a specific city')
    ai_find_parser.add_argument('city', type=str, help='City name')
    ai_find_parser.add_argument('state', type=str, help='State (2-letter code)')
    ai_find_parser.add_argument('--industry', type=str, help='Specific industry to focus on')
    
    # Research company command
    research_parser = subparsers.add_parser('research', help='Use AI to research a specific company')
    research_parser.add_argument('name', type=
                                 
sources_parser = subparsers.add_parser('sources', help='Identify lead sources for a specific city')
    sources_parser.add_argument('city', type=str, help='City name')
    sources_parser.add_argument('state', type=str, help='State (2-letter code)')
    
    # Market analysis command
    market_parser = subparsers.add_parser('market', help='Analyze market potential for a specific city')
    market_parser.add_argument('city', type=str, help='City name')
    market_parser.add_argument('state', type=str, help='State (2-letter code)')
    
    # List leads command
    list_parser = subparsers.add_parser('list', help='List leads in the database')
    list_parser.add_argument('--limit', type=int, default=10, help='Maximum number of leads to list')
    list_parser.add_argument('--city', type=str, help='Filter by city')
    list_parser.add_argument('--state', type=str, help='Filter by state')
    list_parser.add_argument('--category', type=str, help='Filter by category')
    list_parser.add_argument('--min-score', type=int, help='Minimum lead score')
    
    # Export leads command
    export_parser = subparsers.add_parser('export', help='Export leads to CSV')
    export_parser.add_argument('--format', type=str, default='csv', choices=['csv', 'hubspot'], help='Export format')
    export_parser.add_argument('--city', type=str, help='Filter by city')
    export_parser.add_argument('--state', type=str, help='Filter by state')
    export_parser.add_argument('--min-score', type=int, default=50, help='Minimum lead score')
    export_parser.add_argument('--limit', type=int, default=100, help='Maximum number of leads to export')
    
    # View lead command
    view_parser = subparsers.add_parser('view', help='View detailed information about a lead')
    view_parser.add_argument('id', type=int, help='Lead ID')
    
    # Generate outreach command
    outreach_parser = subparsers.add_parser('outreach', help='Generate outreach emails for leads')
    outreach_parser.add_argument('--id', type=int, help='Generate for specific lead ID')
    outreach_parser.add_argument('--count', type=int, default=5, help='Number of emails to generate')
    outreach_parser.add_argument('--min-score', type=int, default=70, help='Minimum lead score')
    outreach_parser.add_argument('--export', action='store_true', help='Export emails to file')
    
    return parser.parse_args()

def main():
    """Main entry point"""
    try:
        args = parse_args()
        app = LeadFinder()
        
        try:
            app.run_command(args)
        finally:
            app.close()
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()