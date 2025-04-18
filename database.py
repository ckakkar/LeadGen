#!/usr/bin/env python3
# database.py - Database manager for LeadFinder

import sqlite3
import sys
import json
import time
from typing import List, Dict, Any, Optional
from rich.console import Console

from config import DATABASE_PATH, DB_INIT_SQL, logger, CACHE_ENABLED, CACHE_EXPIRY

console = Console()

class Database:
    """Database manager for LeadFinder"""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize the database if it doesn't exist"""
        try:
            # Connect to database (creates it if it doesn't exist)
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            
            # Execute initialization SQL
            cursor = self.conn.cursor()
            cursor.executescript(DB_INIT_SQL)
            self.conn.commit()
            cursor.close()
            
            logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            console.print(f"[bold red]Error initializing database: {e}[/bold red]")
            sys.exit(1)
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def insert_company(self, company_data: Dict[str, Any]) -> int:
        """Insert a company record and return its ID"""
        try:
            cursor = self.conn.cursor()
            
            # Check if company already exists
            query = "SELECT id FROM companies WHERE name = ? AND city = ?"
            cursor.execute(query, (company_data.get('name'), company_data.get('city')))
            existing = cursor.fetchone()
            
            if existing:
                return existing['id']
            
            # Convert dict to SQL parameters
            columns = ', '.join(company_data.keys())
            placeholders = ', '.join(['?' for _ in company_data])
            values = list(company_data.values())
            
            query = f"INSERT INTO companies ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            self.conn.commit()
            
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error inserting company: {e}")
            return None
    
    def update_company(self, company_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a company record"""
        try:
            cursor = self.conn.cursor()
            
            # Prepare update statement
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(company_id)  # Add ID for WHERE clause
            
            query = f"UPDATE companies SET {set_clause} WHERE id = ?"
            cursor.execute(query, values)
            self.conn.commit()
            
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating company: {e}")
            return False
    
    def get_companies(self, limit: int = 100, offset: int = 0, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get companies with optional filtering"""
        try:
            cursor = self.conn.cursor()
            
            query = "SELECT * FROM companies"
            params = []
            
            # Apply filters if provided
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'id':
                        where_clauses.append("id = ?")
                        params.append(value)
                    elif key == 'city':
                        where_clauses.append("city LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'state':
                        where_clauses.append("state = ?")
                        params.append(value)
                    elif key == 'category':
                        where_clauses.append("category LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'min_lead_score':
                        where_clauses.append("lead_score >= ?")
                        params.append(value)
                    elif key == 'name':
                        where_clauses.append("name LIKE ?")
                        params.append(f"%{value}%")
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            query += " ORDER BY lead_score DESC, scraped_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error getting companies: {e}")
            return []
    
    def count_companies(self, filters: Dict[str, Any] = None) -> int:
        """Count companies with optional filtering"""
        try:
            cursor = self.conn.cursor()
            
            query = "SELECT COUNT(*) as count FROM companies"
            params = []
            
            # Apply filters if provided
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if key == 'city':
                        where_clauses.append("city LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'state':
                        where_clauses.append("state = ?")
                        params.append(value)
                    elif key == 'category':
                        where_clauses.append("category LIKE ?")
                        params.append(f"%{value}%")
                    elif key == 'min_lead_score':
                        where_clauses.append("lead_score >= ?")
                        params.append(value)
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
        except sqlite3.Error as e:
            logger.error(f"Error counting companies: {e}")
            return 0
    
    def record_export(self, export_type: str, file_path: str, record_count: int) -> int:
        """Record an export operation"""
        try:
            cursor = self.conn.cursor()
            
            query = "INSERT INTO exports (export_type, file_path, record_count) VALUES (?, ?, ?)"
            cursor.execute(query, (export_type, file_path, record_count))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error recording export: {e}")
            return None
    
    def record_search(self, search_type: str, search_term: str, results_count: int) -> int:
        """Record a search operation"""
        try:
            cursor = self.conn.cursor()
            
            query = "INSERT INTO search_history (search_type, search_term, results_count) VALUES (?, ?, ?)"
            cursor.execute(query, (search_type, search_term, results_count))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error recording search: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            cursor = self.conn.cursor()
            
            stats = {}
            
            # Company stats
            cursor.execute("SELECT COUNT(*) as count FROM companies")
            stats['company_count'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT AVG(lead_score) as avg_score FROM companies")
            stats['avg_lead_score'] = cursor.fetchone()['avg_score'] or 0
            
            # City stats
            cursor.execute("SELECT COUNT(DISTINCT city) as count FROM companies")
            stats['city_count'] = cursor.fetchone()['count']
            
            # Category stats
            cursor.execute("SELECT COUNT(DISTINCT category) as count FROM companies")
            stats['category_count'] = cursor.fetchone()['count']
            
            # Search stats
            cursor.execute("SELECT COUNT(*) as count FROM search_history")
            stats['search_count'] = cursor.fetchone()['count']
            
            # Export stats
            cursor.execute("SELECT COUNT(*) as count FROM exports")
            stats['export_count'] = cursor.fetchone()['count']
            
            # AI analysis stats
            cursor.execute("SELECT COUNT(*) as count FROM companies WHERE ai_analysis IS NOT NULL")
            stats['ai_analyzed_count'] = cursor.fetchone()['count']
            
            return stats
        except sqlite3.Error as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def cache_set(self, key: str, value: Any) -> bool:
        """Set a value in the cache"""
        if not CACHE_ENABLED:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Convert value to JSON string if it's not a string
            if not isinstance(value, str):
                value = json.dumps(value)
                
            # Insert or replace cache entry
            query = "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, datetime('now'))"
            cursor.execute(query, (key, value))
            self.conn.commit()
            
            return True
        except sqlite3.Error as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def cache_get(self, key: str) -> Optional[Any]:
        """Get a value from the cache"""
        if not CACHE_ENABLED:
            return None
            
        try:
            cursor = self.conn.cursor()
            
            # Get cache entry if it exists and hasn't expired
            query = f"""
                SELECT value FROM cache 
                WHERE key = ? 
                AND datetime('now') < datetime(created_at, '+{CACHE_EXPIRY} seconds')
            """
            cursor.execute(query, (key,))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            value = result['value']
            
            # Try to parse JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except sqlite3.Error as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    def cache_clear(self, key: str = None) -> bool:
        """Clear specific or all cache entries"""
        if not CACHE_ENABLED:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            if key:
                # Clear specific cache entry
                query = "DELETE FROM cache WHERE key = ?"
                cursor.execute(query, (key,))
            else:
                # Clear all cache entries
                query = "DELETE FROM cache"
                cursor.execute(query)
                
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error clearing cache: {e}")
            return False