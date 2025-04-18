#!/usr/bin/env python3
# exporters/csv_exporter.py - CSV export functionality for LeadFinder

import os
import csv
import datetime
from typing import List, Dict, Any

from config import OUTPUT_DIR, logger
from database import Database

class CSVExporter:
    """Handles exporting data to CSV format"""
    
    def __init__(self, db: Database, output_dir: str = OUTPUT_DIR):
        self.db = db
        self.output_dir = output_dir
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
    
    def export(self, companies: List[Dict[str, Any]], filename: str = None) -> str:
        """Export companies to CSV file"""
        if not companies:
            logger.warning("No companies to export")
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
            
            logger.info(f"Exported {len(companies)} companies to CSV: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None
    
    def export_outreach_emails(self, companies: List[Dict[str, Any]], emails: List[str], filename: str = None) -> str:
        """Export outreach emails to a text file"""
        if not companies or not emails or len(companies) != len(emails):
            logger.warning("Invalid data for outreach email export")
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
            
            logger.info(f"Exported {len(emails)} outreach emails to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting outreach emails: {e}")
            return None