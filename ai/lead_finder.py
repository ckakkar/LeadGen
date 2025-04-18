#!/usr/bin/env python3
# ai/lead_finder.py - AI lead generation for LeadFinder

import json
import re
import time
from typing import List, Dict, Any
import openai

from config import OPENAI_MODEL, OPENAI_API_KEY, AI_ENABLED, logger
from database import Database
from utils.console import create_progress

class AILeadFinder:
    """Uses OpenAI to proactively find and identify potential leads"""
    
    def __init__(self, db: Database):
        self.db = db
        self.enabled = AI_ENABLED
        
        if self.enabled:
            openai.api_key = OPENAI_API_KEY
    
    def find_potential_leads(self, city: str, state: str, industry: str = None) -> List[Dict[str, Any]]:
        """Use AI to generate potential leads based on city, state, and optional industry"""
        if not self.enabled:
            logger.warning("AI features are disabled")
            return []
        
        try:
            # Check cache first
            cache_key = f"ai_leads_{city}_{state}_{industry or 'all'}"
            cached_leads = self.db.cache_get(cache_key)
            
            if cached_leads:
                logger.info(f"Using cached AI leads for {city}, {state}")
                return cached_leads
            
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
            logger.info(f"Using AI to identify potential leads in {city}, {state}")
            
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
                
                # Cache the results
                self.db.cache_set(cache_key, leads)
                
                return leads
                
            except json.JSONDecodeError as e:
                # If JSON parsing fails, try to extract structured information manually
                logger.warning(f"Could not parse JSON from AI response: {e}")
                
                # Look for numbered list items or business names
                leads = self._extract_leads_from_text(response_text, city, state)
                
                # Store in database
                for company in leads:
                    self.db.insert_company(company)
                
                # Cache the results
                self.db.cache_set(cache_key, leads)
                
                return leads
                
        except Exception as e:
            logger.error(f"Error using AI to find leads: {e}")
            return []
    
    def research_company(self, company_name: str, city: str, state: str) -> Dict[str, Any]:
        """Use AI to research a specific company and generate lead information"""
        if not self.enabled:
            logger.warning("AI features are disabled")
            return {}
        
        try:
            # Check cache first
            cache_key = f"company_research_{company_name}_{city}_{state}"
            cached_research = self.db.cache_get(cache_key)
            
            if cached_research:
                logger.info(f"Using cached AI research for {company_name}")
                return cached_research
            
            # Prepare context for AI
            context = (
                f"Company Name: {company_name}\n"
                f"City: {city}\n"
                f"State: {state}\n"
                f"Research Task: Generate detailed lead information about this company for an energy efficiency solutions provider."
            )
            
            # Ask AI to research the company
            logger.info(f"Using AI to research {company_name}")
            
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
                company_id = self.db.insert_company(company)
                
                # Add ID to company data
                if company_id:
                    company['id'] = company_id
                
                # Cache the results
                self.db.cache_set(cache_key, company)
                
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
                company_id = self.db.insert_company(company)
                
                # Add ID to company data
                if company_id:
                    company['id'] = company_id
                
                # Cache the results
                self.db.cache_set(cache_key, company)
                
                return company
                
        except Exception as e:
            logger.error(f"Error using AI to research company: {e}")
            return {'name': company_name, 'city': city, 'state': state, 'source': 'AI Research Failed'}
    
    def identify_lead_sources(self, city: str, state: str) -> str:
        """Use AI to identify potential lead sources specific to a city"""
        if not self.enabled:
            logger.warning("AI features are disabled")
            return ""
        
        try:
            # Check cache first
            cache_key = f"lead_sources_{city}_{state}"
            cached_sources = self.db.cache_get(cache_key)
            
            if cached_sources:
                logger.info(f"Using cached lead sources for {city}, {state}")
                return cached_sources
            
            # Prepare context for AI
            context = (
                f"City: {city}\n"
                f"State: {state}\n"
                f"Task: Identify specific lead sources (websites, directories, organizations, etc.) "
                f"that would be good for finding potential clients for energy efficiency solutions in this location."
            )
            
            # Ask AI to identify lead sources
            logger.info(f"Using AI to identify lead sources in {city}, {state}")
            
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
            
            result = response.choices[0].message['content']
            
            # Cache the result
            self.db.cache_set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error identifying lead sources: {e}")
            return ""
    
    def analyze_market_potential(self, city: str, state: str) -> str:
        """Use AI to analyze the market potential for energy efficiency solutions in a specific city"""
        if not self.enabled:
            logger.warning("AI features are disabled")
            return ""
        
        try:
            # Check cache first
            cache_key = f"market_analysis_{city}_{state}"
            cached_analysis = self.db.cache_get(cache_key)
            
            if cached_analysis:
                logger.info(f"Using cached market analysis for {city}, {state}")
                return cached_analysis
            
            # Prepare context for AI
            context = (
                f"City: {city}\n"
                f"State: {state}\n"
                f"Task: Analyze the market potential for energy efficiency solutions in this location."
            )
            
            # Ask AI to analyze market potential
            logger.info(f"Using AI to analyze market potential in {city}, {state}")
            
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
            
            result = response.choices[0].message['content']
            
            # Cache the result
            self.db.cache_set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing market potential: {e}")
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
            size = str(company['building_size']).lower()
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
                from datetime import datetime
                current_year = datetime.now().year
                age = current_year - year
                
                if age > 30:
                    score += 20
                elif age > 20:
                    score += 15
                elif age > 10:
                    score += 10
            except (ValueError, TypeError):
                # If not a valid year, check for age-related keywords
                year_text = str(company['year_built']).lower()
                if 'old' in year_text or 'aging' in year_text:
                    score += 15
        
        # Category/industry factor
        if company.get('category'):
            category = str(company['category']).lower()
            
            high_energy_sectors = ['manufacturing', 'industrial', 'factory', 'warehouse', 
                                  'hospital', 'healthcare', 'hotel', 'lodging', 'data center',
                                  'office building', 'school', 'university', 'retail']
            
            for sector in high_energy_sectors:
                if sector in category:
                    score += 15
                    break
        
        # AI analysis content
        if company.get('ai_analysis'):
            analysis = str(company['ai_analysis']).lower()
            
            opportunity_keywords = ['high energy', 'inefficient', 'outdated', 'saving', 'cost reduction',
                                   'upgrade', 'retrofit', 'improvement', 'consumption', 'bill', 'expense']
            
            keyword_count = sum(1 for keyword in opportunity_keywords if keyword in analysis)
            score += min(keyword_count * 3, 15)  # Up to 15 points for keywords
        
        # Contact information
        if company.get('contact_title'):
            decision_maker_roles = ['owner', 'ceo', 'president', 'director', 'manager', 'facility']
            
            for role in decision_maker_roles:
                if role.lower() in str(company.get('contact_title', '')).lower():
                    score += 10
                    break
        
        # Cap score at 100
        return min(score, 100)