# logger.py
import logging
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests

from .settings import Settings


logger = logging.getLogger("my_project_logger")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fh = logging.FileHandler("project.log")
    fh.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y/%m/%d %H:%M:%S'
    )

    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

scrapeops_logger = ScrapeOpsRequests(
    scrapeops_api_key=Settings.PROXY_API, 
    spider_name='GuestPostSpider',
    job_name='Job1',
    )
