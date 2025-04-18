#!/usr/bin/env python3
# models/company.py - Company data model for LeadFinder

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class Company:
    """Company data model"""
    
    # Required fields
    name: str
    city: str
    state: str
    
    # Optional fields with defaults
    id: Optional[int] = None
    address: str = ""
    zipcode: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    category: str = ""
    building_size: str = ""
    year_built: str = ""
    description: str = ""
    source: str = ""
    lead_score: int = 50
    ai_analysis: str = ""
    contact_person: str = ""
    contact_title: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    scraped_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Company':
        """Create a Company instance from a dictionary"""
        # Copy the dictionary to avoid modifying the original
        company_data = data.copy()
        
        # Convert scraped_at to datetime if it's a string
        if isinstance(company_data.get('scraped_at'), str):
            try:
                company_data['scraped_at'] = datetime.fromisoformat(company_data['scraped_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                company_data['scraped_at'] = datetime.now()
        
        # Convert lead_score to int if it's a string
        if isinstance(company_data.get('lead_score'), str):
            try:
                company_data['lead_score'] = int(company_data['lead_score'])
            except (ValueError, TypeError):
                company_data['lead_score'] = 50
        
        # Remove any fields that aren't in the class
        valid_fields = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in company_data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Company instance to a dictionary"""
        # Convert datetime to string
        company_dict = self.__dict__.copy()
        if isinstance(company_dict.get('scraped_at'), datetime):
            company_dict['scraped_at'] = company_dict['scraped_at'].isoformat()
        
        return company_dict
    
    def calculate_lead_score(self) -> int:
        """Calculate a lead score based on available information"""
        score = 50  # Base score
        
        # Building age
        if self.year_built:
            try:
                year = int(self.year_built)
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
        
        # Building size
        if self.building_size:
            size_text = self.building_size.lower()
            
            if 'large' in size_text:
                score += 15
            elif 'medium' in size_text:
                score += 10
            elif 'small' in size_text:
                score += 5
        
        # Website available (indicates established business)
        if self.website:
            score += 10
        
        # Contact person available
        if self.contact_person or self.contact_title:
            score += 10
        
        # Email or phone available
        if self.email or self.phone:
            score += 5
        
        # Description available
        if self.description:
            score += 5
        
        # Category/Services
        if self.category:
            category = self.category.lower()
            
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