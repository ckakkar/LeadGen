#!/usr/bin/env python3
# utils/console.py - Console display utilities for LeadFinder

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from typing import List, Dict, Any

console = Console()

def display_welcome(version: str, ai_enabled: bool):
    """Display welcome message"""
    console.print(Panel.fit(
        f"[bold green]LeadFinder v{version}[/bold green]\n\n"
        "[bold]Real Lead Generation Tool for LogicLamp Technologies[/bold]\n\n"
        f"[{'green' if ai_enabled else 'red'}]AI Features: {'Enabled' if ai_enabled else 'Disabled'}[/]\n\n"
        "Type [cyan]leadfinder help[/cyan] for available commands.",
        title="Welcome to LeadFinder",
        border_style="green"
    ))

def display_dashboard(stats: Dict[str, Any], ai_enabled: bool):
    """Display dashboard with statistics"""
    ai_status = "[green]Enabled[/green]" if ai_enabled else "[red]Disabled[/red]"
    
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

def display_table(title: str, data: List[Dict[str, Any]], columns: List[str] = None, max_width: int = None):
    """Display a table of data"""
    if not data:
        console.print("[yellow]No data available.[/yellow]")
        return
    
    # If columns not specified, use all keys from first item
    if not columns:
        columns = list(data[0].keys())
    
    # Create table
    table = Table(title=title)
    
    # Special formatting for certain columns
    style_map = {
        "id": "dim",
        "name": "bold",
        "lead_score": "bold cyan",
        "ai_analysis": lambda val: "green" if val else ""
    }
    
    # Add columns
    for col in columns:
        # Get the style for this column
        if col in style_map:
            style = style_map[col]
            if callable(style):
                # For columns like ai_analysis where we need to check the value
                style = ""
        else:
            style = None
            
        # Add column to table
        table.add_column(col.replace('_', ' ').title(), style=style)
    
    # Add rows
    for item in data:
        row = []
        for col in columns:
            value = item.get(col, '')
            
            # Format specific columns
            if col == 'lead_score':
                row.append(f"{value}")
            elif col == 'ai_analysis':
                row.append("✓" if value else "")
            elif col == 'category' and value and len(str(value)) > 30:
                row.append(f"{str(value)[:27]}...")
            else:
                row.append(str(value))
        
        table.add_row(*row)
    
    console.print(table)

def create_progress(description: str, total: int):
    """Create and return a progress bar"""
    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    )
    task = progress.add_task(description, total=total)
    return progress, task

def display_error(message: str):
    """Display error message"""
    console.print(f"[bold red]Error:[/bold red] {message}")

def display_warning(message: str):
    """Display warning message"""
    console.print(f"[yellow]{message}[/yellow]")

def display_success(message: str):
    """Display success message"""
    console.print(f"[green]✓[/green] {message}")

def display_info(message: str):
    """Display information message"""
    console.print(message)