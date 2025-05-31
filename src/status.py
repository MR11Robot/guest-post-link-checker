import threading


class BotStatus:
    def __init__(self):
        self.is_running: bool = False
        self.started_at: str = ''
        self.finished_at: str = ''
        self.current_website_name: str = ''
        self.current_website_number: int = 0
        self.total_articles_in_website: int = 0
        self.current_link_number: int = 0
        

bot_status = BotStatus()
