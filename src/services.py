import googleapiclient.errors
import os
import gzip
import time
import undetected_chromedriver as uc
import traceback
import requests as requests_normal


from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from io import BytesIO
from datetime import date
from urllib.parse import urlparse, ParseResultBytes, ParseResult
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests





from .database import DatabaseManager
from .models import NoHrefArticle, Website, Article, FailedToRetrieveArticle
from .status import bot_status
from .settings import Settings
from .constants import ScrapeMethod, NetworkAccessMethod
from .logger import logger, scrapeops_logger

requests = scrapeops_logger.RequestsWrapper() 


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
                # Create the table if it doesn't exist
                self.db_manager.create_website_data_table(website.table)
        else:
            raise Warning("No websites data found in the database while clearing data.")
    @staticmethod
    def is_valid_url(string):
        """Check if a string is a valid URL"""
        result: ParseResult | ParseResultBytes = urlparse(string)
        return bool(result.scheme and result.netloc)
    
    def load_websites_data_from_spreadsheets(self, max_retries=5, initial_delay=1):
        """Load website article links from Google Sheets"""
        retries = 0
        delay = initial_delay
        
        while retries < max_retries:
            try:
                # Setup Google Sheets API
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
                        if row:  # Check if row is not empty
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
                return True  # Exit the function if successful
                
            except googleapiclient.errors.HttpError as e:
                if e.resp.status == 503:
                    logger.error(f"Google Sheets API is unavailable. Retrying ({retries + 1}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    retries += 1
                else:
                    logger.error(f"Google Sheets API error: {e}")
                    raise
                    
        logger.error("Max retries reached. Unable to load websites data.")
        return False


class WebScraper:
    """Handles the scraping operations"""
    def __init__(self, database_manager: DatabaseManager, proxy_api):
        self.db_manager = database_manager
        self.proxy_api = proxy_api
        
    def try_parse_html(self, html_content):
        """Parse HTML content with error handling"""
        try:
            # Check if content is gzipped
            if isinstance(html_content, bytes) and html_content.startswith(b'\x1f\x8b'):
                html_content = gzip.GzipFile(fileobj=BytesIO(html_content)).read()
                
            # Convert bytes to text
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='replace')
                
            return BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            return None
    
    def request_page(self, article: Article):
        ua = UserAgent()
        headers = {'User-Agent': ua.random}

        # Try direct request first
        try:
            response = requests_normal.get(article.link, headers=headers, timeout=5)
            if response.ok:
                html_content = response.content
                soup = self.try_parse_html(html_content)
                if soup:
                    return soup, response.status_code, NetworkAccessMethod.DIRECT
                else:
                    raise Exception("Failed to parse HTML content.")
            else:
                raise Exception(f"Request failed with status code {response.status_code}")

        except Exception as e:
            logger.error(f"Error in direct request: {e}")
            logger.info("Retrying request via ScrapeOps proxy...")

            # Configure ScrapeOps proxy request
            try:
                # Use the ScrapeOps URL format
                scrapeops_url = "https://proxy.scrapeops.io/v1/"
                
                scrapeops_params = {
                    'api_key': self.proxy_api,  # Make sure this is set
                    'url': article.link,
                    'optimize_request': 'true',
                }
                
                scrapeops_headers = {
                    'User-Agent': ua.random
                }

                # Use requests_normal instead of the wrapped requests for ScrapeOps
                scrapeops_response = requests_normal.get(
                    url=scrapeops_url,
                    params=scrapeops_params,
                    headers=scrapeops_headers,
                    timeout=30
                )

                if scrapeops_response.ok:
                    html_content = scrapeops_response.content
                    soup = self.try_parse_html(html_content)
                    if soup:
                        return soup, scrapeops_response.status_code, NetworkAccessMethod.PROXY
                    else:
                        logger.error("Failed to parse proxy response HTML")
                        raise Exception("Failed to parse proxy response HTML")
                else:
                    logger.error(f"Proxy request failed with status code: {scrapeops_response.status_code}")
                    logger.error(f"Proxy response content: {scrapeops_response.text[:500]}")
                    raise Exception(f"Proxy request failed with status code: {scrapeops_response.status_code}")

            except Exception as proxy_error:
                logger.error(f"Error during ScrapeOps proxy request: {proxy_error}")
                logger.error(f"Traceback: {traceback.format_exc()}")

        return None, 0, NetworkAccessMethod.PROXY
    def get_page_with_chromedriver(self, url, driver: uc.Chrome):
        """Get a page using undetected chromedriver"""
        try:
            retries = 3
            while retries != 0:
                retries -= 1
                
                logger.info(f"Navigating to {url} with undetected ChromeDriver. attemp number: {retries + 1}")

                driver.get(url)
                
                time.sleep(3)
                
                html_content = driver.page_source
                soup = self.try_parse_html(html_content)
                
                # Check for Cloudflare protection
                if "Access denied" in html_content:
                    logger.info("Access Denied")
                    return None, "Access Denied"
                elif "Just a moment..." in html_content:
                    logger.info("Cloudflare detected, waiting...")
                    time.sleep(20)
                    html_content = driver.page_source
                    soup = self.try_parse_html(html_content)
                    
                    if "Just a moment..." in html_content:
                        if retries == 0:
                            logger.error("Failed to bypass Cloudflare protection after retries")
                            return None, "Cloudflare Protection Failed"
                        else:
                            continue  # Retry if still protected
                else:
                    return soup, None
            
            return None, "Max retries reached"
            
        except Exception as e:
            err_msg = str(e)
            default_error_msg = "Failed to retrieve the page"
            if "ERR_NAME_NOT_RESOLVED" in err_msg:
                return None, default_error_msg
            elif "ERR_CONNECTION_REFUSED" in err_msg:
                return None, default_error_msg                
            elif "ERR_CONNECTION_TIMED_OUT" in err_msg:
                return None, default_error_msg
            elif "ERR_SSL_PROTOCOL_ERROR" in err_msg:
                return None, default_error_msg
            elif "ERR_CONNECTION_CLOSED" in err_msg:
                return None, default_error_msg
            elif "ERR_SSL_UNRECOGNIZED_NAME_ALERT" in err_msg:
                return None, default_error_msg
            else:
                logger.critical(f"Error in get_page_with_chromedriver: {err_msg}")
                return None, f"WebDriver Error: {err_msg}"
    
    def check_for_hyperlinks(self, soup: BeautifulSoup, website: Website, article_link, scrape_method: ScrapeMethod, network_access_method: NetworkAccessMethod):
        """Check for hyperlinks in the soup and store in database"""
        hyper_links_found_count = 0
        hyper_links_found: list[str] = []
        words_found: list[str] = []

        # Prepare list of website identifiers to look for
        all_names = [website.domain] + website.aliases
        if website.app_link:
            all_names.append(website.app_link)
        
        # Find all links
        for link in soup.find_all('a'):
            href = link.get('href')
            rel = link.get('rel')
            
            # Determine if the link is followed or not
            if rel is None or "nofollow" not in rel:
                rel = "follow"
            else:
                rel = "nofollow"
            
            # Check if the link contains any of our target domains
            if href:
                for name in all_names:
                    if name in href:
                        hyper_links_found.append(href)
                        
                        link_text = str(link.text).replace("\n", " ").strip()
                        words_found.append(link_text)
                        
                        now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                        logger.info(f"Found {link_text} <|====|> Link Type: {rel} <|====|> Date: {now} <|====|> Hyper_link: {href}")
                        
                        # Insert to database
                        self.db_manager.insert_hyperlink_data(
                            website.table, article_link, link_text, href, rel, now, scrape_method, network_access_method
                        )
                        hyper_links_found_count += 1
                        break
        
        # If no hyperlinks were found, log that
        if hyper_links_found_count == 0:
            logger.info(f"No hyperlinks found for: {article_link}")
            return False
        
        logger.debug(f"Total hyperlinks found: {hyper_links_found_count} for {article_link}")
        for i, link in enumerate(hyper_links_found):
            logger.debug(f"{i + 1}. {link}")
            
        logger.debug(f"Total words found: {len(words_found)} for {article_link}")
        for i, word in enumerate(words_found):
            logger.debug(f"{i + 1}. {word}")
        
        logger.info(f"Hyperlinks found: {hyper_links_found_count}")
        print("===============================================")
        return True
    
    def handle_failed_request(self, website: Website, article_link, response_code, scrape_method: ScrapeMethod, network_access_method: NetworkAccessMethod):
        """Handle a failed request by logging to database"""
        now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
        
        if response_code == 403:
            error_msg = "403 Client Error: Forbidden for URL"
        else:
            error_msg = "Failed to retrieve the page"
            
        self.db_manager.insert_hyperlink_data(
            website.table, article_link, error_msg, error_msg, error_msg, now, scrape_method, network_access_method
        )


class BotWorker:
    """Manages the scraping bot's workflow"""
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.website_manager = WebsiteManager()
        self.scraper = WebScraper(self.db_manager, Settings.PROXY_API)
        
    def run(self):
        """Main bot execution logic"""
       
        
        try:
            logger.info("The bot has started. (run method in BotWorker class)")
            
            # Initialize
            self.website_manager.prepare_bot()
            self.website_manager.load_websites()
            self.website_manager.clear_website_data()
            success = self.website_manager.load_websites_data_from_spreadsheets()
            
            if not success:
                logger.error("Failed to load website data from spreadsheets.")
                return
            
            # Process each website
            for i, website in enumerate(self.website_manager.websites):
                if not bot_status.is_running:
                    logger.info("Bot stop requested.")
                    break
                
                # Update status
                bot_status.current_website_name = website.name
                bot_status.current_website_number = i + 1
                bot_status.total_articles_in_website = len(website.articles)
                self.website_manager.no_href_articles = []  # Clear previous no_href_articles
                self.website_manager.failed_to_retrieve_articles = []  # Clear previous failed articles
                
                
                # Process each article
                for j, article in enumerate(website.articles):
                    if not bot_status.is_running:
                        break
                        
                    bot_status.current_link_number = j + 1
                    logger.info(f"Processing {bot_status.current_link_number}/{bot_status.total_articles_in_website}: {article.link}")
                    
                    # Get the page
                    soup, response_code, network_access_method = self.scraper.request_page(article)
                    
                    if soup:
                        logger.info("Request successful")
                        has_hyperlinks = self.scraper.check_for_hyperlinks(soup, website, article.link, ScrapeMethod.REQUESTS, network_access_method)
                        if not has_hyperlinks:
                            self.website_manager.no_href_articles.append(
                                NoHrefArticle(link=article.link, website=website)
                            )
                    else:
                        logger.info(f"Request failed with code: {response_code}")
                        self.website_manager.failed_to_retrieve_articles.append(
                            FailedToRetrieveArticle(link=article.link, website=website)
                        )
                
                # Process articles with no hyperlinks using Chrome
                if self.website_manager.no_href_articles or self.website_manager.failed_to_retrieve_articles:
                    # Prepare driver
                    options = uc.ChromeOptions()
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    
                    driver = uc.Chrome(options=options)
                    logger.info(f"Processing {len(self.website_manager.no_href_articles) + len(self.website_manager.failed_to_retrieve_articles)} articles with Chrome")
                    bot_status.current_website_name = f"{website.name} (Chrome)"
                    bot_status.total_articles_in_website = len(self.website_manager.no_href_articles) + len(self.website_manager.failed_to_retrieve_articles)
                    if len(self.website_manager.no_href_articles) > 0:
                        for j, no_href_article in enumerate(self.website_manager.no_href_articles):
                            if not bot_status.is_running:
                                break
                                
                            bot_status.current_link_number = j + 1
                            logger.info(f"Chrome processing {bot_status.current_link_number}/{bot_status.total_articles_in_website}: {no_href_article.link}")
                            
                            soup, error = self.scraper.get_page_with_chromedriver(no_href_article.link, driver)
                            
                            if soup and not error:
                                if not self.scraper.check_for_hyperlinks(soup, website, no_href_article.link, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT):
                                    # Insert to database as no links found
                                    now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                                    error_msg = "No links found"
                                    self.db_manager.insert_hyperlink_data(
                                        website.table, no_href_article.link, error_msg, error_msg, error_msg, now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                                    )
                            else:
                                now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                                error_msg = error or "Failed with Chrome"
                                self.db_manager.insert_hyperlink_data(
                                    website.table, no_href_article.link, error_msg, error_msg, error_msg, now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                                )
                    if len(self.website_manager.failed_to_retrieve_articles) > 0:     
                        for n, ftr_article in enumerate(self.website_manager.failed_to_retrieve_articles):
                            if not bot_status.is_running:
                                break
                                
                            bot_status.current_link_number = n + 1
                            logger.info(f"Chrome processing {bot_status.current_link_number}/{bot_status.total_articles_in_website}: {ftr_article.link}")
                            
                            soup, error = self.scraper.get_page_with_chromedriver(ftr_article.link, driver)
                            
                            if soup and not error:
                                if not self.scraper.check_for_hyperlinks(soup, website, ftr_article.link, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT):
                                    # Insert to database as no links found
                                    now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                                    error_msg = "No links found"
                                    self.db_manager.insert_hyperlink_data(
                                        website.table, ftr_article.link, error_msg, error_msg, error_msg, now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                                    )
                            else:
                                now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                                error_msg = error or "Failed with Chrome"
                                self.db_manager.insert_hyperlink_data(
                                    website.table, ftr_article.link, error_msg, error_msg, error_msg, now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                                )

                    driver.quit()
                # Export results
                logger.info(f"Exporting data for {website.name}")
                self.db_manager.export_to_excel(website.table)
            
            logger.info("================|<> Process Done <>|=================")
            
        except Exception as e:
            logger.critical(f"Bot execution error: {e}")
        finally:
            bot_status.is_running = False
