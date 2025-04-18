#!/usr/bin/env python3
# scrapers/yellowpages_scraper.py - YellowPages scraper for LeadFinder

import time
import random
import re
import datetime
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from config import YELLOWPAGES_BASE_URL, SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX, logger
from scrapers.base_scraper import BaseScraper
from utils.selenium_utils import (
    wait_for_element, wait_for_elements, safe_click, 
    get_text_safely, get_attribute_safely
)
from utils.console import create_progress

class YellowPagesScraper(BaseScraper):
    """Scrapes business data from YellowPages.com"""
    
    def __init__(self, db):
        super().__init__(db)
        self.source_name = "YellowPages"
    
    def search_businesses(self, city: str, state: str, category: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for businesses in a specific city and category"""
        companies = []
        
        try:
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
            search_url = f"{YELLOWPAGES_BASE_URL}/{formatted_category}/{formatted_location}"
            
            logger.info(f"Searching YellowPages: {search_url}")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            wait_for_element(self.driver, By.CLASS_NAME, "search-results", timeout=15)
            
            results_found = 0
            page = 1
            
            # Create progress display
            progress, task = create_progress(f"Scraping business data...", max_results)
            
            with progress:
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
                                company['name'] = get_text_safely(name_element[0])
                            else:
                                continue  # Skip if no name found
                            
                            # Extract address
                            address_element = element.find_elements(By.CLASS_NAME, "street-address")
                            if address_element:
                                company['address'] = get_text_safely(address_element[0])
                            
                            # Extract locality (city, state, zip)
                            locality_element = element.find_elements(By.CLASS_NAME, "locality")
                            if locality_element:
                                locality = get_text_safely(locality_element[0])
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
                                company['phone'] = get_text_safely(phone_element[0])
                            
                            # Extract website if available
                            website_element = element.find_elements(By.CSS_SELECTOR, "a.track-visit-website")
                            if website_element:
                                company['website'] = get_attribute_safely(website_element[0], "href")
                            
                            # Extract categories/services
                            categories_element = element.find_elements(By.CLASS_NAME, "categories")
                            if categories_element:
                                company['category'] = get_text_safely(categories_element[0])
                            else:
                                company['category'] = category
                            
                            # Extract years in business if available
                            years_element = element.find_elements(By.CSS_SELECTOR, ".years-in-business .number")
                            if years_element:
                                years_in_business = get_text_safely(years_element[0])
                                # Estimate year founded
                                current_year = datetime.datetime.now().year
                                try:
                                    years = int(years_in_business)
                                    company['year_built'] = str(current_year - years)
                                except ValueError:
                                    pass
                            
                            # Add source and calculate lead score
                            company = self.add_source_info(company)
                            
                            # Add to results
                            companies.append(company)
                            results_found += 1
                            progress.update(task, advance=1)
                            
                            # Small sleep to avoid overloading the server
                            time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))
                            
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
                            safe_click(self.driver, next_button[0])
                            page += 1
                            
                            # Wait for next page to load
                            wait_for_element(self.driver, By.CLASS_NAME, "search-results", timeout=15)
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
            return companies
    
    def get_business_details(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a business"""
        if not company.get('name') or not company.get('city'):
            return company
        
        try:
            # Construct search URL for specific business
            business_name = company['name'].lower().replace(' ', '-')
            city_state = f"{company['city'].lower().replace(' ', '-')}-{company['state'].lower()}"
            search_url = f"{YELLOWPAGES_BASE_URL}/search?search_terms={business_name}&geo_location_terms={city_state}"
            
            logger.info(f"Getting details for {company['name']}: {search_url}")
            
            # Navigate to search page
            self.driver.get(search_url)
            
            # Wait for results to load
            try:
                wait_for_element(self.driver, By.CLASS_NAME, "search-results", timeout=15)
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
                    found_name = get_text_safely(name_element[0])
                    if self.similar_names(found_name, company['name']):
                        # Click on the business name to go to detail page
                        safe_click(self.driver, name_element[0])
                        
                        # Wait for detail page to load
                        wait_for_element(self.driver, By.CLASS_NAME, "business-card", timeout=15)
                        
                        # Extract detailed information
                        self._extract_business_details(company)
                        break
                except Exception as e:
                    logger.error(f"Error processing search result: {e}")
                    continue
            
            return company
            
        except Exception as e:
            logger.error(f"Error getting business details: {e}")
            return company
    
    def _extract_business_details(self, company: Dict[str, Any]) -> None:
        """Extract detailed business information from the detail page"""
        try:
            # Extract business description
            description_element = self.driver.find_elements(By.CLASS_NAME, "business-description")
            if description_element:
                company['description'] = get_text_safely(description_element[0])
            
            # Extract services
            services_elements = self.driver.find_elements(By.CSS_SELECTOR, ".services ul li")
            if services_elements:
                services = [get_text_safely(element) for element in services_elements]
                if services:
                    if 'category' in company:
                        company['category'] = f"{company['category']}, {', '.join(services)}"
                    else:
                        company['category'] = ', '.join(services)
            
            # Extract contact information
            contact_elements = self.driver.find_elements(By.CSS_SELECTOR, ".contact h2")
            for element in contact_elements:
                title = get_text_safely(element)
                if title.lower() in ["owner", "manager", "president", "ceo"]:
                    company['contact_title'] = title
                    try:
                        name_element = element.find_element(By.XPATH, "following-sibling::p")
                        if name_element:
                            company['contact_person'] = get_text_safely(name_element)
                    except Exception:
                        pass
            
            # Extract more details from about section
            about_elements = self.driver.find_elements(By.CSS_SELECTOR, ".about dt")
            for element in about_elements:
                label = get_text_safely(element).lower()
                try:
                    value_element = element.find_element(By.XPATH, "following-sibling::dd[1]")
                    
                    if not value_element:
                        continue
                        
                    value = get_text_safely(value_element)
                    
                    if "year established" in label and value:
                        company['year_built'] = value
                    elif "building size" in label and value:
                        company['building_size'] = value
                    elif "email" in label and value:
                        company['email'] = value
                except Exception:
                    continue
            
            # Recalculate lead score with new information
            company['lead_score'] = self.calculate_lead_score(company)
            
        except Exception as e:
            logger.error(f"Error extracting business details: {e}")