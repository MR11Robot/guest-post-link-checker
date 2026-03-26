# Guest Post Link Checker 🔍

A scheduled web scraping bot that automatically checks guest post articles for hyperlinks and exports the results to Excel. Built as part of the [django-coupons](https://github.com/MR11Robot/django-coupons) ecosystem.

---

## What It Does

- Reads article URLs from **Google Sheets**
- Scrapes each article looking for hyperlinks to target domains
- Falls back to **ScrapeOps proxy** if direct request fails
- Falls back to **Playwright** (with stealth mode) to bypass Cloudflare protection
- Saves results to **SQLite** and exports to **Excel**
- Runs automatically every day at 8:00 PM via a built-in scheduler
- Exposes a **REST API** to start/stop the bot and manage websites

---

## Project Structure

```
├── app.py                  # Flask app & scheduler
├── src/
│   ├── services/
│   │   ├── bot_worker.py       # Main bot orchestration
│   │   ├── web_scraper.py      # Scraping logic (requests → proxy → Playwright)
│   │   └── website_manager.py  # Google Sheets loader
│   ├── database.py         # SQLite operations & Excel export
│   ├── models.py           # Data models
│   ├── settings.py         # Environment config
│   ├── constants.py        # Enums (ScrapeMethod, NetworkAccessMethod)
│   ├── status.py           # Bot runtime status
│   ├── utils.py            # URL validation helpers
│   └── logger.py           # Logging setup (UTF-8 safe)
└── output/                 # Generated Excel files
```

---

## Requirements

- Python 3.12+
- [Poetry](https://python-poetry.org/)
- A [ScrapeOps](https://scrapeops.io/) API key
- A Google Cloud service account with Sheets API access

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/MR11Robot/guest-post-link-checker.git
cd guest-post-link-checker
```

**2. Install dependencies**
```bash
poetry install
```

**3. Install Playwright browsers**
```bash
poetry run playwright install chromium
```

**4. Configure environment variables**

Create a `.env` file in the root:
```env
PROXY_API_KEY=your_scrapeops_api_key
PROXY_URL=https://proxy.scrapeops.io/v1/
PORT=5001
```

**5. Add Google Sheets credentials**

Place your Google service account JSON file as `keys.json` in the root directory.

---

## Running

```bash
# Default port (from .env or 5001)
poetry run app

# Custom port
poetry run app --port 8080
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status/` | Get current bot status |
| POST | `/start/` | Start the bot manually |
| POST | `/stop/` | Stop the bot |
| GET | `/download/<filename>/` | Download Excel report |
| GET | `/websites/` | List all websites |
| POST | `/add_website/` | Add a new website |
| PUT | `/update_website/<name>/` | Update a website |
| DELETE | `/delete_website/<name>/` | Delete a website |

---

## Part of a Larger System

This bot is one of three automation tools managed by [django-coupons](https://github.com/MR11Robot/django-coupons), a Django dashboard that controls and monitors all bots from a single interface.

---

## License

MIT