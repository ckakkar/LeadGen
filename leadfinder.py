#!/usr/bin/env python3
# leadfinder.py - Real Lead Generation Tool for LogicLamp Technologies
# Main entry point for the application

import argparse
import sys
import time
from rich.console import Console
from rich.panel import Panel

# Import configuration
from config import VERSION, AI_ENABLED

# Import modules
from database import Database
from ai.analyzer import AIAnalyzer
from ai.lead_finder import AILeadFinder
from scrapers.yellowpages_scraper import YellowPagesScraper
from scrapers.googlemaps_scraper import GoogleMapsScraper
from exporters.csv_exporter import CSVExporter
from exporters.hubspot_exporter import HubSpotExporter
from utils.console import display_table, display_welcome, display_dashboard

# Initialize console
console = Console()

class LeadFinder:
    """Main application class"""
    
    def __init__(self):
        """Initialize the application"""
        self.db = Database()
        self.csv_exporter = CSVExporter(self.db)
        self.hubspot_exporter = HubSpotExporter(self.db)
        self.ai_analyzer = AIAnalyzer(self.db)
        self.ai_lead_finder = AILeadFinder(self.db)
    
    def show_welcome(self):
        """Show welcome message"""
        display_welcome(VERSION, AI_ENABLED)
    
    def show_dashboard(self):
        """Show dashboard with statistics"""
        stats = self.db.get_stats()
        display_dashboard(stats, AI_ENABLED)
    
    def find_leads(self, city, state, category=None, source="all", count=20, get_details=True):
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
                    companies = scraper.get_business_details_batch(companies)
                
                # Store companies in database
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
                for company in companies:
                    self.db.insert_company(company)
                
                console.print(f"[green]✓[/green] Found {len(companies)} businesses on Google Maps")
                all_companies.extend(companies)
        
        # AI Analysis if enabled and requested
        if AI_ENABLED and get_details:
            console.print(f"[yellow]Analyzing {len(all_companies)} companies with AI...[/yellow]")
            all_companies = self.ai_analyzer.analyze_companies_batch(all_companies)
            
            # Update in database
            for company in all_companies:
                if company.get('id'):
                    self.db.update_company(company['id'], {
                        'ai_analysis': company.get('ai_analysis'),
                        'lead_score': company.get('lead_score')
                    })
        
        # Sort by lead score
        all_companies.sort(key=lambda x: x.get('lead_score', 0), reverse=True)
        
        # Display top results
        if all_companies:
            console.print(f"[green]✓[/green] Found {len(all_companies)} potential leads")
            console.print("\n[bold]Top Leads:[/bold]")
            
            display_table(
                "Top Leads", 
                all_companies[:min(10, len(all_companies))], 
                ["id", "name", "city", "state", "phone", "category", "lead_score"]
            )
        
        return all_companies
    
    def ai_find_leads(self, city, state, industry=None):
        """Use AI to identify potential leads in a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Using AI to find leads in {city}, {state}...[/bold]")
        
        # Find potential leads using AI
        leads = self.ai_lead_finder.find_potential_leads(city, state, industry)
        
        if not leads:
            console.print("[yellow]No leads were generated by AI. Try a different location or industry.[/yellow]")
            return
        
        console.print(f"[green]✓[/green] AI generated {len(leads)} potential leads")
        
        # Display leads
        display_table(
            f"AI-Generated Leads for {city}, {state}", 
            leads, 
            ["id", "name", "category", "building_size", "contact_title", "lead_score"]
        )
        
        # Offer to analyze the market as well
        if console.input("\n[bold]Would you like an AI analysis of the market potential in this area? (y/n):[/bold] ").lower() == 'y':
            self.analyze_market(city, state)
            
        return leads
    
    def research_company(self, name, city, state):
        """Use AI to research a specific company"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Researching {name} in {city}, {state}...[/bold]")
        
        # Research the company
        company = self.ai_lead_finder.research_company(name, city, state)
        
        if not company:
            console.print(f"[yellow]Could not research company: {name}[/yellow]")
            return
        
        # Display company details
        self.view_company(company.get('id', 0))
        
        # Offer to generate outreach email
        if console.input("\n[bold]Generate outreach email? (y/n):[/bold] ").lower() == 'y':
            self.generate_outreach(id=company.get('id', 0))
            
        return company
    
    def identify_sources(self, city, state):
        """Identify lead sources for a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Identifying lead sources for {city}, {state}...[/bold]")
        
        # Get lead sources
        sources = self.ai_lead_finder.identify_lead_sources(city, state)
        
        # Display sources
        console.print(Panel.fit(
            f"{sources}",
            title=f"Lead Sources for {city}, {state}",
            border_style="green"
        ))
    
    def analyze_market(self, city, state):
        """Analyze market potential for a specific city"""
        if not AI_ENABLED:
            console.print("[yellow]AI features are disabled. Configure your OpenAI API key to use this feature.[/yellow]")
            return
        
        console.print(f"[bold]Analyzing market potential in {city}, {state}...[/bold]")
        
        # Get market analysis
        analysis = self.ai_lead_finder.analyze_market_potential(city, state)
        
        # Display analysis
        console.print(Panel.fit(
            f"{analysis}",
            title=f"Market Analysis: {city}, {state}",
            border_style="green"
        ))
    
    def list_companies(self, limit=10, city=None, state=None, category=None, min_score=None):
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
        
        # Display companies
        display_table(
            f"Companies (Total: {total_count})", 
            companies, 
            ["id", "name", "city", "state", "category", "contact_person", "phone", "lead_score", "ai_analysis"]
        )
        
        return companies
    
    def export_leads(self, format_type="csv", city=None, state=None, min_score=50, limit=100):
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
            output_path = self.hubspot_exporter.export(companies)
            export_type = "HubSpot"
        else:
            # Export to standard CSV
            output_path = self.csv_exporter.export(companies)
            export_type = "standard"
        
        if output_path:
            console.print(f"[green]✓[/green] Exported {len(companies)} companies to {export_type} CSV: [cyan]{output_path}[/cyan]")
        else:
            console.print(f"[red]✗[/red] Failed to export companies")
    
    def generate_outreach(self, id=None, count=5, min_score=70, export=False):
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
        
        # Generate emails
        emails = self.ai_analyzer.generate_outreach_emails_batch(companies)
        
        # Display or export emails
        if export:
            output_path = self.csv_exporter.export_outreach_emails(companies, emails)
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
    
    def view_company(self, company_id):
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
            self.find_leads(
                city=args.city,
                state=args.state,
                category=args.category,
                source=args.source,
                count=args.count,
                get_details=args.details
            )
        
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
        
        elif command == "help":
            self.show_help()
        
        else:
            console.print(f"[red]Unknown command: {command}[/red]")
    
    def show_help(self):
        """Show help information"""
        console.print(Panel.fit(
            "[bold]Available Commands:[/bold]\n\n"
            "[bold]Basic Commands:[/bold]\n"
            "  dashboard              - Show dashboard with statistics\n"
            "  list                   - List companies in the database\n"
            "  view ID                - View detailed information about a company\n"
            "  help                   - Show this help message\n\n"
            
            "[bold]Lead Finding:[/bold]\n"
            "  find CITY STATE        - Find leads in specific city using web scraping\n"
            "    --category TEXT      - Business category to search\n"
            "    --source SOURCE      - Data source (yellowpages, googlemaps, or all)\n"
            "    --count NUMBER       - Maximum number of leads to find\n"
            "    --details            - Get detailed information for each lead\n\n"
            
            "[bold]AI Features:[/bold]\n"
            "  ai-find CITY STATE     - Use AI to identify potential leads\n"
            "    --industry TEXT      - Specific industry to focus on\n"
            "  research NAME CITY STATE - Use AI to research a specific company\n"
            "  sources CITY STATE     - Identify lead sources for a specific city\n"
            "  market CITY STATE      - Analyze market potential for a specific city\n"
            "  outreach               - Generate outreach emails for leads\n"
            "    --id ID              - Generate for specific lead ID\n"
            "    --count NUMBER       - Number of emails to generate\n"
            "    --min-score NUMBER   - Minimum lead score\n"
            "    --export             - Export emails to file\n\n"
            
            "[bold]Export:[/bold]\n"
            "  export                 - Export leads to CSV\n"
            "    --format FORMAT      - Export format (csv or hubspot)\n"
            "    --city TEXT          - Filter by city\n"
            "    --state TEXT         - Filter by state\n"
            "    --min-score NUMBER   - Minimum lead score\n"
            "    --limit NUMBER       - Maximum number of leads to export\n",
            title="LeadFinder Help",
            border_style="cyan"
        ))
    
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
    research_parser.add_argument('name', type=str, help='Company name')
    research_parser.add_argument('city', type=str, help='City name')
    research_parser.add_argument('state', type=str, help='State (2-letter code)')
    
    # Identify lead sources command
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
    
    # Add help command
    help_parser = subparsers.add_parser('help', help='Show available commands')
    
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
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()