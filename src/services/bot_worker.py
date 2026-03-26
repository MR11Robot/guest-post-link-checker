import undetected_chromedriver as uc

from datetime import datetime

from ..database import DatabaseManager
from ..models import NoHrefArticle, FailedToRetrieveArticle
from ..status import bot_status
from ..settings import Settings
from ..constants import ScrapeMethod, NetworkAccessMethod
from ..logger import logger
from .website_manager import WebsiteManager
from .web_scraper import WebScraper


class BotWorker:
    """Manages the scraping bot's workflow"""
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.website_manager = WebsiteManager()
        self.scraper = WebScraper(self.db_manager, Settings.PROXY_API)

    def run(self):
        """Main bot execution logic"""
        try:
            logger.info("The bot has started.")

            self.website_manager.prepare_bot()
            self.website_manager.load_websites()
            self.website_manager.clear_website_data()
            success = self.website_manager.load_websites_data_from_spreadsheets()

            if not success:
                logger.error("Failed to load website data from spreadsheets.")
                return

            for i, website in enumerate(self.website_manager.websites):
                if not bot_status.is_running:
                    logger.info("Bot stop requested.")
                    break

                bot_status.current_website_name = website.name
                bot_status.current_website_number = i + 1
                bot_status.total_articles_in_website = len(website.articles)
                self.website_manager.no_href_articles = []
                self.website_manager.failed_to_retrieve_articles = []

                # Phase 1: requests
                for j, article in enumerate(website.articles):
                    if not bot_status.is_running:
                        break

                    bot_status.current_link_number = j + 1
                    logger.info(f"Processing {bot_status.current_link_number}/{bot_status.total_articles_in_website}: {article.link}")

                    soup, response_code, network_access_method = self.scraper.request_page(article)

                    if soup:
                        logger.info("Request successful")
                        has_hyperlinks = self.scraper.check_for_hyperlinks(soup, website, article.link, ScrapeMethod.REQUESTS, network_access_method)
                        if not has_hyperlinks:
                            self.website_manager.no_href_articles.append(NoHrefArticle(link=article.link, website=website))
                    else:
                        logger.info(f"Request failed with code: {response_code}")
                        self.website_manager.failed_to_retrieve_articles.append(FailedToRetrieveArticle(link=article.link, website=website))

                # Phase 2: ChromeDriver fallback
                if self.website_manager.no_href_articles or self.website_manager.failed_to_retrieve_articles:
                    self._process_with_chrome(website)

                logger.info(f"Exporting data for {website.name}")
                self.db_manager.export_to_excel(website.table)

            logger.info("================|<> Process Done <>|=================")

        except Exception as e:
            logger.critical(f"Bot execution error: {e}")
        finally:
            bot_status.is_running = False

    def _process_with_chrome(self, website):
        """Process failed/no-href articles using ChromeDriver"""
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = uc.Chrome(options=options)

        all_pending = self.website_manager.no_href_articles + self.website_manager.failed_to_retrieve_articles
        bot_status.current_website_name = f"{website.name} (Chrome)"
        bot_status.total_articles_in_website = len(all_pending)

        logger.info(f"Processing {len(all_pending)} articles with Chrome")

        try:
            for j, pending_article in enumerate(all_pending):
                if not bot_status.is_running:
                    break

                bot_status.current_link_number = j + 1
                logger.info(f"Chrome processing {bot_status.current_link_number}/{bot_status.total_articles_in_website}: {pending_article.link}")

                soup, error = self.scraper.get_page_with_chromedriver(pending_article.link, driver)
                now = datetime.now().strftime("| %Y-%m-%d | %I:%M:%S %p |")

                if soup and not error:
                    if not self.scraper.check_for_hyperlinks(soup, website, pending_article.link, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT):
                        self.db_manager.insert_hyperlink_data(
                            website.table, pending_article.link, "No links found", "No links found", "No links found",
                            now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                        )
                else:
                    error_msg = error or "Failed with Chrome"
                    self.db_manager.insert_hyperlink_data(
                        website.table, pending_article.link, error_msg, error_msg, error_msg,
                        now, ScrapeMethod.UNDETECTED_CHROMEDRIVER, NetworkAccessMethod.DIRECT
                    )
        finally:
            driver.quit()