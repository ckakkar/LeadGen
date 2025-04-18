#!/usr/bin/env python3
# scrapers/googlemaps_scraper.py - Google Maps scraper for LeadFinder

import time
import random
import re
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from config import GOOGLE_MAPS_BASE_URL, SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX, logger
from scrapers.base_scraper import BaseScraper
from utils.selenium_utils import (
    wait_for_element, wait_for_elements, safe_click, scroll_down,
    get_text_safely, get_attribute_safely
)
from utils.console import create_progress

class GoogleMapsScraper(BaseScraper):
    """Scrapes business data from Google Maps"""
    
    def __init__(self, db):
        super().__init__(db)
        self.source_name = "Google Maps"
    
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
            search_url = f"{GOOGLE_MAPS_BASE_URL}{query_encoded}"
            
            logger.info(f"Searching Google Maps: {search_url}")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            time.sleep(3)  # Initial wait for results
            
            results_found = 0
            
            # Create progress display
            progress, task = create_progress(f"Scraping business data...", max_results)
            
            with progress:
                # Use JavaScript to scroll through results
                last_height = self.driver.execute_script(
                    "return document.querySelector('.section-layout.section-scrollbox').scrollHeight"
                )
                
                while results_found < max_results:
                    # Get all result elements
                    result_elements = self.driver.find_elements(By.CSS_SELECTOR, ".section-result")
                    
                    # Process visible results
                    for element in result_elements[results_found:]:
                        if results_found >= max_results:
                            break
                            
                        try:
                            # Click on the result to see details
                            safe_click(self.driver, element)
                            
                            # Wait for details panel to load
                            time.sleep(2)
                            
                            # Extract information from details panel
                            company = self._extract_business_info()
                            
                            # Add location if not found in details
                            if 'city' not in company:
                                company['city'] = city
                                company['state'] = state
                            
                            # Add source and calculate lead score
                            company = self.add_source_info(company)
                            
                            # Add to results if we got a name
                            if company.get('name'):
                                companies.append(company)
                                results_found += 1
                                progress.update(task, advance=1)
                            
                            # Go back to results
                            back_button = self.driver.find_elements(By.CSS_SELECTOR, "button.section-back-to-list-button")
                            if back_button:
                                safe_click(self.driver, back_button[0])
                                time.sleep(1)
                            
                            # Small sleep to avoid overloading
                            time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))
                            
                        except Exception as e:
                            logger.error(f"Error processing business element: {e}")
                            # Try to go back to results
                            try:
                                back_button = self.driver.find_elements(By.CSS_SELECTOR, "button.section-back-to-list-button")
                                if back_button:
                                    safe_click(self.driver, back_button[0])
                                    time.sleep(1)
                            except Exception:
                                pass
                            continue
                    
                    # Check if we have enough results
                    if results_found >= max_results:
                        break
                    
                    # Scroll down to load more results
                    self.driver.execute_script(
                        "document.querySelector('.section-layout.section-scrollbox').scrollTo(0, document.querySelector('.section-layout.section-scrollbox').scrollHeight);"
                    )
                    time.sleep(2)
                    
                    # Check if we've reached the end of the scroll
                    new_height = self.driver.execute_script(
                        "return document.querySelector('.section-layout.section-scrollbox').scrollHeight"
                    )
                    
                    if new_height == last_height:
                        # No more results
                        break
                    
                    last_height = new_height
            
            # Record search in database
            self.db.record_search("Google Maps", f"{category} in {city}, {state}", len(companies))
            
            return companies
            
        except Exception as e:
            logger.error(f"Error scraping Google Maps: {e}")
            return companies
    
    def _extract_business_info(self) -> Dict[str, Any]:
        """Extract business information from Google Maps details panel"""
        company = {}
        
        try:
            # Extract name
            name_element = self.driver.find_elements(By.CSS_SELECTOR, "h1.section-hero-header-title-title")
            if name_element:
                company['name'] = get_text_safely(name_element[0])
            
            # Extract address
            address_element = self.driver.find_elements(By.CSS_SELECTOR, "button[data-item-id='address']")
            if address_element:
                full_address = get_text_safely(address_element[0])
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
                company['phone'] = get_text_safely(phone_element[0])
            
            # Extract website
            website_element = self.driver.find_elements(By.CSS_SELECTOR, "a[data-item-id='authority']")
            if website_element:
                company['website'] = get_attribute_safely(website_element[0], "href")
            
            # Extract categories/services
            category_element = self.driver.find_elements(By.CSS_SELECTOR, "button[jsaction='pane.rating.category']")
            if category_element:
                company['category'] = get_text_safely(category_element[0])
            
            # Extract description from reviews or other text
            description_element = self.driver.find_elements(By.CSS_SELECTOR, ".section-editorial-quote")
            if description_element:
                company['description'] = get_text_safely(description_element[0])
            
            # Extract reviews (optional)
            reviews_element = self.driver.find_elements(By.CSS_SELECTOR, ".section-rating-term-list")
            if reviews_element:
                review_points = []
                for review in reviews_element:
                    review_text = get_text_safely(review)
                    if review_text:
                        review_points.append(review_text)
                
                if review_points and not company.get('description'):
                    company['description'] = "Customer reviews highlight: " + "; ".join(review_points)
            
            return company
            
        except Exception as e:
            logger.error(f"Error extracting business info: {e}")
            return company
    
    def get_business_details(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a business"""
        # Google Maps doesn't have separate detail pages, so we already
        # have all the information we can get from the search results
        # This method remains for compatibility with the BaseScraper interface
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