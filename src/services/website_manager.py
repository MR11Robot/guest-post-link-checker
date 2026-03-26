import googleapiclient.errors
import time

from datetime import date
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List

from ..utils import is_valid_url
from ..database import DatabaseManager
from ..models import NoHrefArticle, Website, Article, FailedToRetrieveArticle
from ..settings import Settings
from ..logger import logger


class WebsiteManager:
    """Manages website scraping operations"""
    def __init__(self, database="data.db"):
        self.db_manager = DatabaseManager(database)
        self.websites: List[Website] = []
        self.today_date = date.today()
        self.proxy_api = Settings.PROXY_API
        self.no_href_articles: List[NoHrefArticle] = []
        self.failed_to_retrieve_articles: List[FailedToRetrieveArticle] = []

    def prepare_bot(self):
        """Initialize the bot with required database tables"""
        self.db_manager.create_websites_table()

    def load_websites(self) -> List[Website]:
        """Load websites from the database"""
        self.websites = self.db_manager.get_websites()
        return self.websites

    def clear_website_data(self):
        """Clear data from all website tables"""
        if self.websites:
            for website in self.websites:
                self.db_manager.delete_website_data(website.table)
                self.db_manager.create_website_data_table(website.table)
        else:
            raise Warning("No websites data found in the database while clearing data.")


    def load_websites_data_from_spreadsheets(self, max_retries=5, initial_delay=1):
        """Load website article links from Google Sheets"""
        retries = 0
        delay = initial_delay

        while retries < max_retries:
            try:
                SERVICE_ACCOUNT_FILE = 'keys.json'
                SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
                creds = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

                for website in self.websites:
                    service = build('sheets', 'v4', credentials=creds)
                    sheet = service.spreadsheets()
                    result = sheet.values().get(
                        spreadsheetId=website.spreadsheet_id,
                        range=website.row_range
                    ).execute()
                    rows = result.get('values', [])

                    for row in rows:
                        if row:
                            target_index = website.link_location - 1
                            if (len(row) > target_index and
                                str(row[target_index]).strip() and
                                    self.is_valid_url(row[target_index])):
                                website.articles.append(Article(link=row[target_index]))
                                logger.info(f"Valid URL: {row[target_index]}")
                            elif len(row) > target_index:
                                logger.info(f"Invalid URL: {row[target_index]}")
                        else:
                            logger.info(f"Row is empty or does not have enough elements: {row}")

                    logger.info(f"Websites data loaded successfully. {website.name} has {len(website.articles)} articles.")
                return True

            except googleapiclient.errors.HttpError as e:
                if e.resp.status == 503:
                    logger.error(f"Google Sheets API is unavailable. Retrying ({retries + 1}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2
                    retries += 1
                else:
                    logger.error(f"Google Sheets API error: {e}")
                    raise

        logger.error("Max retries reached. Unable to load websites data.")
        return False