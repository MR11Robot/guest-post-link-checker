from enum import Enum

class ScrapeMethod(Enum):
    REQUESTS = "requests"
    CHROME = "chrome"
    
class NetworkAccessMethod(Enum):
    PROXY = "proxy"
    DIRECT = "direct"