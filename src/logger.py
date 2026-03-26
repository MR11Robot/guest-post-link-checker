# logger.py
import logging
import sys
import io
from scrapeops_python_requests.scrapeops_requests import ScrapeOpsRequests

from .settings import Settings

# Force UTF-8 encoding for stdout (fix Windows console issue)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logger = logging.getLogger("my_project_logger")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # Console Handler (UTF-8 safe)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    # File Handler (UTF-8 safe)
    fh = logging.FileHandler("project.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y/%m/%d %H:%M:%S'
    )

    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

# ScrapeOps logger
scrapeops_logger = ScrapeOpsRequests(
    scrapeops_api_key=Settings.PROXY_API,
    spider_name='GuestPostSpider',
    job_name='Job1',
)