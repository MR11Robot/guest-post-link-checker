import sqlite3
import pandas as pd
import json
import os

from typing import List

from .models import Website
from .constants import ScrapeMethod, NetworkAccessMethod
from .logger import logger

class DatabaseManager:
    """Handles all database operations"""
    def __init__(self, database_path="data.db"):
        self.database = database_path
        
    def execute_query(self, query, params=(), fetch=False, commit=True):
        """Execute a database query with proper connection handling"""
        conn = None
        result = None
        try:
            conn = sqlite3.connect(self.database)
            cur = conn.cursor()
            cur.execute(query, params)
            
            if fetch:
                result = cur.fetchall()
            if commit:
                conn.commit()
                
            return result
        except Exception as e:
            logger.critical(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
                
    def create_websites_table(self):
        """Create the main websites table if it doesn't exist"""
        create_query = """CREATE TABLE IF NOT EXISTS websites (
            name TEXT, 
            domain TEXT, 
            spreadsheet_id TEXT, 
            row_range TEXT, 
            app_link TEXT,
            link_location INTEGER,
            aliases TEXT DEFAULT '[]'
        )"""
        self.execute_query(create_query)
        
    def create_website_data_table(self, table_name):
        """Create a table for storing website data"""
        create_query = f"""CREATE TABLE IF NOT EXISTS `{table_name}` (
            article_link TEXT,
            word TEXT,
            hyper_link TEXT,
            link_type TEXT,
            last_check TEXT,
            scrape_method TEXT,
            network_access_method TEXT
        )"""
        self.execute_query(create_query)
        
    def get_websites(self) -> List[Website]:
        """Retrieve all websites from the database"""
        select_query = "SELECT * FROM websites"
        rows = self.execute_query(select_query, fetch=True)
        
        websites = []
        if rows:     
            for row in rows:
                name, domain, spreadsheet_id, row_range, app_link, link_location, aliases = row
                websites.append(Website(
                    name=name,
                    domain=domain,
                    spreadsheet_id=spreadsheet_id,
                    row_range=row_range,
                    app_link=app_link,
                    link_location=link_location,
                    aliases=aliases
                ))
            return websites
        else:
            logger.warning("No websites found in the database.")
            raise ValueError("No websites found in the database.")
    
    def delete_website_data(self, table_name):
        """Delete all data from a website's table"""
        # Check if table exists
        check_query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        table_exists = self.execute_query(check_query, (table_name,), fetch=True)
        
        if table_exists:
            delete_query = f"DELETE FROM `{table_name}`"
            self.execute_query(delete_query)
            logger.info(f"All old data deleted from {table_name} table.")
        else:
            logger.info(f"{table_name} table does not exist.")
            
    def add_website(self, website_data):
        """Add a new website to the database"""
        aliases = json.dumps(website_data.get("aliases", []))
        
        insert_query = """
            INSERT INTO websites (name, domain, spreadsheet_id, row_range, app_link, link_location, aliases)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_query(insert_query, (
            website_data["name"], 
            website_data["domain"], 
            website_data["spreadsheet_id"], 
            website_data["row_range"],
            website_data["app_link"], 
            website_data["link_location"], 
            aliases
        ))
        
    def update_website(self, old_name, website_data):
        """Update an existing website in the database"""
        aliases = json.dumps(website_data.get("aliases", []))
        
        update_query = """
            UPDATE websites 
            SET name = ?, domain = ?, spreadsheet_id = ?, row_range = ?, 
                app_link = ?, link_location = ?, aliases = ?
            WHERE name = ?
        """
        self.execute_query(update_query, (
            website_data["name"], 
            website_data["domain"], 
            website_data["spreadsheet_id"], 
            website_data["row_range"],
            website_data["app_link"], 
            website_data["link_location"], 
            aliases, 
            old_name
        ))
        
    def delete_website(self, name):
        """Delete a website from the database"""
        # Check if the website exists
        check_query = "SELECT 1 FROM websites WHERE name = ?"
        exists = self.execute_query(check_query, (name,), fetch=True)
        
        if not exists:
            return False
            
        # Delete the website
        delete_query = "DELETE FROM websites WHERE name = ?"
        self.execute_query(delete_query, (name,))
        
        # Drop its data table
        drop_query = f"DROP TABLE IF EXISTS `{name}`"
        self.execute_query(drop_query)
        
        return True
        
    def insert_hyperlink_data(self, table_name, article_link, word, hyper_link, link_type, now, scrape_method: ScrapeMethod, network_access_method: NetworkAccessMethod):
        """Insert hyperlink data into a website's table"""
        insert_query = f"""
            INSERT INTO `{table_name}` (article_link, word, hyper_link, link_type, last_check, scrape_method, network_access_method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self.execute_query(insert_query, (article_link, word, hyper_link, link_type, now, scrape_method.value, network_access_method.value))
        logger.info(f"Inserted hyperlink data into {table_name} for article {article_link} with word {word}.")
        
    def export_to_excel(self, table_name):
        """Export a table to Excel"""
        conn = None
        try:
            conn = sqlite3.connect(self.database)
            df = pd.read_sql_query(f"SELECT * FROM `{table_name}`", conn)
            
            # Create output directory if it doesn't exist
            os.makedirs("output", exist_ok=True)
            
            excel_file = f"output/{table_name}.xlsx"
            df.to_excel(excel_file, index=False)
            return True
        except Exception as e:
            logger.critical(f"Error exporting to Excel: {e}")
            return False
        finally:
            if conn:
                conn.close()

