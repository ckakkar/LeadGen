#!/usr/bin/env python3
# scrapers/base_scraper.py - Base scraper class for LeadFinder

import time
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from selenium.webdriver.chrome.webdriver import WebDriver

from config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX, BATCH_SIZE, logger
from database import Database
from utils.selenium_utils import setup_selenium

class BaseScraper(ABC):
    """Abstract base class for scrapers"""
    
    def __init__(self, db: Database):
        """Initialize the scraper"""
        self.db = db
        self.driver = None
        self.source_name = self.__class__.__name__
    
    def __enter__(self):
        """Setup for context manager - initialize Selenium"""
        self.driver = setup_selenium()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup for context manager - close Selenium"""
        if self.driver:
            self.driver.quit()
    
    @abstractmethod
    def search_businesses(self, city: str, state: str, category: str = None, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search for businesses in a specific city and category"""
        pass
    
    @abstractmethod
    def get_business_details(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a business"""
        pass
    
    def get_business_details_batch(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get detailed information for a batch of businesses"""
        results = []
        for i, company in enumerate(companies):
            # Add a delay to avoid rate limiting
            if i > 0:
                time.sleep(random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX))
                
            try:
                # Check cache first
                cache_key = f"company_details_{self.source_name}_{company.get('name')}_{company.get('city')}_{company.get('state')}"
                cached_details = self.db.cache_get(cache_key)
                
                if cached_details:
                    logger.info(f"Using cached details for {company.get('name')}")
                    results.append({**company, **cached_details})
                    continue
                
                # Get details and add to cache
                detailed_company = self.get_business_details(company)
                self.db.cache_set(cache_key, detailed_company)
                results.append(detailed_company)
                
            except Exception as e:
                logger.error(f"Error getting details for {company.get('name')}: {e}")
                results.append(company)  # Keep original data
                
            # Process in smaller batches to reduce memory usage
            if i > 0 and i % BATCH_SIZE == 0:
                logger.info(f"Processed {i}/{len(companies)} businesses")
        
        return results
    
    def calculate_lead_score(self, company: Dict[str, Any]) -> int:
        """Calculate a lead score for a company - can be overridden by subclass"""
        score = 50  # Base score
        
        # Building age
        if company.get('year_built'):
            try:
                from datetime import datetime
                year = int(company['year_built'])
                current_year = datetime.now().year
                age = current_year - year
                
                if age > 30:
                    score += 20
                elif age > 20:
                    score += 15
                elif age > 10:
                    score += 10
            except (ValueError, TypeError):
                pass
        
        # Website available (indicates established business)
        if company.get('website'):
            score += 10
        
        # Contact details available
        if company.get('contact_person') or company.get('contact_title'):
            score += 10
        
        # Contact email or phone available 
        if company.get('email') or company.get('phone'):
            score += 5
        
        # Description available
        if company.get('description'):
            score += 5
        
        # Building size if available
        if company.get('building_size'):
            size_text = str(company['building_size']).lower()
            if 'large' in size_text:
                score += 15
            elif 'medium' in size_text:
                score += 10
            elif 'small' in size_text:
                score += 5
        
        # Energy-related keywords in description or category
        energy_keywords = ['energy', 'utilities', 'building', 'property', 'office', 'commercial', 
                          'industrial', 'manufacturing', 'factory', 'school', 'hospital',
                          'hotel', 'retail', 'restaurant', 'mall', 'warehouse']
        
        text_to_check = ' '.join([
            str(company.get('description', '')).lower(),
            str(company.get('category', '')).lower()
        ])
        
        keyword_matches = sum(1 for keyword in energy_keywords if keyword in text_to_check)
        score += min(keyword_matches * 3, 15)  # Max 15 points for keywords
        
        # Cap score at 100
        return min(score, 100)
    
    @staticmethod
    def similar_names(name1: str, name2: str) -> bool:
        """Check if two business names are similar"""
        name1 = name1.lower()
        name2 = name2.lower()
        
        # Remove common business suffixes
        for suffix in [' inc', ' llc', ' corp', ' company', ' co', ' ltd']:
            name1 = name1.replace(suffix, '')
            name2 = name2.replace(suffix, '')
        
        # Compare cleaned names
        return name1.strip() == name2.strip() or name1.strip() in name2.strip() or name2.strip() in name1.strip()
    
    def add_source_info(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Add source information to company data"""
        if 'source' not in company:
            company['source'] = self.source_name
        
        if 'lead_score' not in company:
            company['lead_score'] = self.calculate_lead_score(company)
            
        return company