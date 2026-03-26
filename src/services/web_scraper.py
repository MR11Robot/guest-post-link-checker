import gzip
import time
import traceback
import requests as requests_normal
import undetected_chromedriver as uc

from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from io import BytesIO

from ..database import DatabaseManager
from ..models import Website, Article
from ..constants import ScrapeMethod, NetworkAccessMethod
from ..logger import logger, scrapeops_logger

requests = scrapeops_logger.RequestsWrapper()


class WebScraper:
    """Handles the scraping operations"""
    def __init__(self, database_manager: DatabaseManager, proxy_api):
        self.db_manager = database_manager
        self.proxy_api = proxy_api

    def try_parse_html(self, html_content):
        """Parse HTML content with error handling"""
        try:
            if isinstance(html_content, bytes) and html_content.startswith(b'\x1f\x8b'):
                html_content = gzip.GzipFile(fileobj=BytesIO(html_content)).read()

            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='replace')

            return BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            return None

    def request_page(self, article: Article):
        """Try to get a page via direct request, then fallback to ScrapeOps proxy"""
        ua = UserAgent()
        headers = {'User-Agent': ua.random}

        try:
            response = requests_normal.get(article.link, headers=headers, timeout=5)
            if response.ok:
                soup = self.try_parse_html(response.content)
                if soup:
                    return soup, response.status_code, NetworkAccessMethod.DIRECT
                raise Exception("Failed to parse HTML content.")
            else:
                raise Exception(f"Request failed with status code {response.status_code}")

        except Exception as e:
            logger.error(f"Error in direct request: {e}")
            logger.info("Retrying request via ScrapeOps proxy...")

            try:
                scrapeops_response = requests_normal.get(
                    url="https://proxy.scrapeops.io/v1/",
                    params={
                        'api_key': self.proxy_api,
                        'url': article.link,
                        'optimize_request': 'true',
                    },
                    headers={'User-Agent': ua.random},
                    timeout=30
                )

                if scrapeops_response.ok:
                    soup = self.try_parse_html(scrapeops_response.content)
                    if soup:
                        return soup, scrapeops_response.status_code, NetworkAccessMethod.PROXY
                    raise Exception("Failed to parse proxy response HTML")
                else:
                    logger.error(f"Proxy request failed with status code: {scrapeops_response.status_code}")
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
                logger.info(f"Navigating to {url} with undetected ChromeDriver. attempt number: {retries + 1}")

                driver.get(url)
                time.sleep(3)

                html_content = driver.page_source
                soup = self.try_parse_html(html_content)

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
                            continue
                else:
                    return soup, None

            return None, "Max retries reached"

        except Exception as e:
            err_msg = str(e)
            default_error_msg = "Failed to retrieve the page"
            known_errors = [
                "ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_REFUSED",
                "ERR_CONNECTION_TIMED_OUT", "ERR_SSL_PROTOCOL_ERROR",
                "ERR_CONNECTION_CLOSED", "ERR_SSL_UNRECOGNIZED_NAME_ALERT"
            ]
            if any(err in err_msg for err in known_errors):
                return None, default_error_msg
            else:
                logger.critical(f"Error in get_page_with_chromedriver: {err_msg}")
                return None, f"WebDriver Error: {err_msg}"

    def check_for_hyperlinks(self, soup: BeautifulSoup, website: Website, article_link, scrape_method: ScrapeMethod, network_access_method: NetworkAccessMethod):
        """Check for hyperlinks in the soup and store in database"""
        hyper_links_found_count = 0
        hyper_links_found: list[str] = []
        words_found: list[str] = []

        all_names = [website.domain] + website.aliases
        if website.app_link:
            all_names.append(website.app_link)

        for link in soup.find_all('a'):
            href = link.get('href')
            rel = link.get('rel')

            rel = "nofollow" if rel and "nofollow" in rel else "follow"

            if href:
                for name in all_names:
                    if name in href:
                        hyper_links_found.append(href)
                        link_text = str(link.text).replace("\n", " ").strip()
                        words_found.append(link_text)

                        now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
                        logger.info(f"Found {link_text} <|====|> Link Type: {rel} <|====|> Date: {now} <|====|> Hyper_link: {href}")

                        self.db_manager.insert_hyperlink_data(
                            website.table, article_link, link_text, href, rel, now, scrape_method, network_access_method
                        )
                        hyper_links_found_count += 1
                        break

        if hyper_links_found_count == 0:
            logger.info(f"No hyperlinks found for: {article_link}")
            return False

        logger.info(f"Hyperlinks found: {hyper_links_found_count}")
        print("===============================================")
        return True

    def handle_failed_request(self, website: Website, article_link, response_code, scrape_method: ScrapeMethod, network_access_method: NetworkAccessMethod):
        """Handle a failed request by logging to database"""
        now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")
        error_msg = "403 Client Error: Forbidden for URL" if response_code == 403 else "Failed to retrieve the page"
        self.db_manager.insert_hyperlink_data(
            website.table, article_link, error_msg, error_msg, error_msg, now, scrape_method, network_access_method
        )