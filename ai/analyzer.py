#!/usr/bin/env python3
# ai/analyzer.py - AI analysis functionality for LeadFinder

import re
import time
from typing import List, Dict, Any
import openai

from config import OPENAI_MODEL, OPENAI_API_KEY, AI_ENABLED, BATCH_SIZE, logger
from database import Database
from utils.console import create_progress

class AIAnalyzer:
    """Uses OpenAI to analyze and enhance lead data"""
    
    def __init__(self, db: Database):
        self.db = db
        self.enabled = AI_ENABLED
        
        if self.enabled:
            openai.api_key = OPENAI_API_KEY
    
    def analyze_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a company to identify energy efficiency opportunities"""
        if not self.enabled:
            return company
        
        try:
            # Check cache first
            cache_key = f"ai_analysis_{company.get('id', '')}_{company.get('name')}_{company.get('city')}"
            cached_analysis = self.db.cache_get(cache_key)
            
            if cached_analysis:
                logger.info(f"Using cached AI analysis for {company.get('name')}")
                
                # Update the company with cached analysis
                if isinstance(cached_analysis, dict):
                    # If cache contains the full updated company
                    for key, value in cached_analysis.items():
                        company[key] = value
                    return company
                elif isinstance(cached_analysis, str):
                    # If cache contains just the analysis text
                    company['ai_analysis'] = cached_analysis
                    return company
                
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
            
            # Cache the analysis
            self.db.cache_set(cache_key, {'ai_analysis': ai_analysis, 'lead_score': company.get('lead_score')})
            
            return company
            
        except Exception as e:
            logger.error(f"Error in AI company analysis: {e}")
            return company
    
    def analyze_companies_batch(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze a batch of companies"""
        if not self.enabled or not companies:
            return companies
        
        results = []
        
        # Create progress display
        progress, task = create_progress(f"Analyzing companies with AI...", len(companies))
        
        with progress:
            for i, company in enumerate(companies):
                # Add a small delay between API calls to avoid rate limits
                if i > 0:
                    time.sleep(0.5)
                
                # Analyze company
                analyzed_company = self.analyze_company(company)
                results.append(analyzed_company)
                
                # Update progress
                progress.update(task, advance=1)
                
                # Process in smaller batches to reduce memory usage
                if i > 0 and i % BATCH_SIZE == 0:
                    logger.info(f"Analyzed {i}/{len(companies)} companies")
        
        return results
    
    def generate_outreach_email(self, company: Dict[str, Any]) -> str:
        """Generate personalized outreach email for a company"""
        if not self.enabled:
            return "AI features are disabled. Configure your OpenAI API key to use this feature."
        
        try:
            # Check cache first
            cache_key = f"outreach_email_{company.get('id', '')}_{company.get('name')}_{company.get('city')}"
            cached_email = self.db.cache_get(cache_key)
            
            if cached_email:
                logger.info(f"Using cached outreach email for {company.get('name')}")
                return cached_email
            
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
            
            email = response.choices[0].message['content']
            
            # Cache the email
            self.db.cache_set(cache_key, email)
            
            return email
            
        except Exception as e:
            logger.error(f"Error generating outreach email: {e}")
            return f"Error generating email: {str(e)}"
    
    def generate_outreach_emails_batch(self, companies: List[Dict[str, Any]]) -> List[str]:
        """Generate outreach emails for a batch of companies"""
        if not self.enabled or not companies:
            return ["AI features are disabled"] * len(companies)
        
        emails = []
        
        # Create progress display
        progress, task = create_progress(f"Generating outreach emails...", len(companies))
        
        with progress:
            for i, company in enumerate(companies):
                # Add a small delay between API calls to avoid rate limits
                if i > 0:
                    time.sleep(0.5)
                
                # Generate email
                email = self.generate_outreach_email(company)
                emails.append(email)
                
                # Update progress
                progress.update(task, advance=1)
        
        return emails