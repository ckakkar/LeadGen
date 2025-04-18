#!/usr/bin/env python3
# exporters/hubspot_exporter.py - HubSpot export functionality for LeadFinder

import os
import csv
import datetime
from typing import List, Dict, Any

from config import OUTPUT_DIR, logger
from database import Database

class HubSpotExporter:
    """Handles exporting data to HubSpot-compatible format"""
    
    def __init__(self, db: Database, output_dir: str = OUTPUT_DIR):
        self.db = db
        self.output_dir = output_dir
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export(self, companies: List[Dict[str, Any]], filename: str = None) -> str:
        """Export companies in HubSpot-compatible CSV format"""
        if not companies:
            logger.warning("No companies to export")
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
            
            logger.info(f"Exported {len(companies)} companies to HubSpot CSV: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting to HubSpot CSV: {e}")
            return None