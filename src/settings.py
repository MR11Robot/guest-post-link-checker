# settings.py

import os

from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROXY_API = os.getenv('PROXY_API_KEY')
    PROXY_URL = os.getenv('PROXY_URL')
    PORT = int(os.getenv('PORT', 5001))