from enum import Enum

class ScrapeMethod(Enum):
    REQUESTS = "requests"
    UNDETECTED_CHROMEDRIVER = "undetected_chromedriver"
    
class NetworkAccessMethod(Enum):
    PROXY = "proxy"
    DIRECT = "direct"