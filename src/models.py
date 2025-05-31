import json

from typing import List, Optional, Tuple, Dict, Any, Union

class Article:
    """Represents an article with a link to check for hyperlinks"""
    def __init__(self, link: str):
        self.link = link
        self.is_hyper_link_found = False


class Website:
    """Represents a website to scrape for hyperlinks"""
    def __init__(self, name: str, domain: str, spreadsheet_id, row_range: str, 
                 link_location: int, app_link: str | None = None, aliases=None):
        self.name = name
        self.domain = domain
        self.table = name
        self.app_link = app_link
        self.row_range = row_range
        self.spreadsheet_id = spreadsheet_id
        self.link_location = link_location
        self.aliases = json.loads(aliases) if aliases else []
        self.articles: List[Article] = []


class NoHrefArticle:
    """Represents an article that didn't have hyperlinks in initial check"""
    def __init__(self, link: str, website: Website):
        self.link = link
        self.website = website


class FailedToRetrieveArticle:
    """Represents an article that failed to retrieve hyperlinks"""
    def __init__(self, link: str, website: Website):
        self.link = link
        self.website = website