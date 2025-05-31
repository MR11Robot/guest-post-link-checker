import os
import threading
import time
import json
import schedule
import traceback

from datetime import datetime
from collections import OrderedDict
from flask import Flask, jsonify, request, send_file, Response

from src.status import bot_status
from src.database import DatabaseManager
from src.services import BotWorker, WebsiteManager
from src.logger import logger

app = Flask(__name__)



# Flask routes
@app.route('/status/', methods=['GET'])
def get_bot_status():
    status_data: OrderedDict[str, int | str] = OrderedDict([
        ("status", bot_status.is_running),
        ("started_at", bot_status.started_at),
        ("current_website_name", bot_status.current_website_name),
        ("current_website_number", bot_status.current_website_number),
        ("total_articles_in_website", bot_status.total_articles_in_website),
        ("current_link_number", bot_status.current_link_number),
    ])
    
    if not bot_status.is_running:
        status_data["finished_at"] = bot_status.finished_at

    return Response(json.dumps(status_data), mimetype="application/json")

@app.route('/start/', methods=['POST'])
def start_bot():      
    if bot_status.is_running:
        logger.info("User attempted to start bot while it is already running.")
        return jsonify({"message": "Bot is already running"}), 400
        
    logger.info("User started bot manually.")
    threading.Thread(target=run_bot, daemon=True).start()
    return jsonify({"message": "Bot started successfully"}), 200

@app.route('/stop/', methods=['POST'])
def stop_bot():
    if not bot_status.is_running:
        logger.info("User attempted to stop bot while it is not running.")
        return jsonify({"message": "Bot is already stopped"}), 400
    
    bot_status.is_running = False
    
    now = datetime.now()
    bot_status.finished_at = now.strftime("%Y/%m/%d %I:%M:%S %p")
    logger.info("Bot stopped successfully.")
    return jsonify({"message": "Bot stopped successfully"}), 200

@app.route('/download/<filename>/', methods=['GET'])
def download_excel(filename):
    file_path = f"output/{filename}.xlsx"
    if not os.path.exists(file_path):
        logger.error(f"File {file_path} not found for download.")
        return jsonify({"error": "File not found"}), 404
    logger.info(f"User requested download of file: {file_path}")
    return send_file(file_path, as_attachment=True)

@app.route('/websites/', methods=['GET'])
def get_websites_list():
    website_manager = WebsiteManager()
    websites = website_manager.load_websites()
    websites_data = [{
        "name": website.name,
        "domain": website.domain,
        "spreadsheet_id": website.spreadsheet_id,
        "row_range": website.row_range,
        "app_link": website.app_link,
        "link_location": website.link_location,
        "aliases": website.aliases
    } for website in websites]
    return jsonify({"websites": websites_data})

@app.route('/add_website/', methods=['POST'])
def add_website():
    data = request.get_json()
    required_fields = ["name", "domain", "spreadsheet_id", "row_range", "link_location"]
    
    if not all(field in data for field in required_fields):
        logger.error("Missing required fields in request data for adding website.")
        return jsonify({"error": "Missing required fields"}), 400
    
    db_manager = DatabaseManager()
    db_manager.add_website(data)
    logger.info(f"Website {data['name']} added successfully.")
    
    return jsonify({"message": f"Website {data['name']} added successfully"}), 201

@app.route('/delete_website/<name>/', methods=['DELETE'])
def delete_website(name):
    db_manager = DatabaseManager()
    success = db_manager.delete_website(name)
    
    if success:
        return jsonify({"message": f"Website {name} deleted successfully"}), 200
    else:
        return jsonify({"error": f"Website {name} not found"}), 404

@app.route('/update_website/<name>/', methods=['PUT'])
def update_website(name):
    data = request.get_json()
    required_fields = ["name", "domain", "spreadsheet_id", "row_range", "app_link", "link_location"]
    
    if not all(field in data for field in required_fields):
        logger.error("Missing required fields in request data for updating website.")
        return jsonify({"error": "Missing required fields"}), 400
    
    db_manager = DatabaseManager()
    db_manager.update_website(name, data)
    logger.info(f"Website {name} updated successfully.")
    
    return jsonify({"message": f"Website {name} updated successfully"}), 200

# Helper functions
def run_bot():    
    if bot_status.is_running:
        logger.warning("Another bot instance is already running")
        return

    try:
        # Set started_at time when bot starts
        now = datetime.now()
        bot_status.started_at = now.strftime("%Y/%m/%d %I:%M:%S %p")
        bot_status.is_running = True
        
        bot = BotWorker()
        bot.run()
        
    except Exception as e:
        logger.error(f"Bot error: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        now = datetime.now()
        bot_status.finished_at = now.strftime("%Y/%m/%d %I:%M:%S %p")
        bot_status.is_running = False
        bot_status.current_website_name = ''
        bot_status.current_website_number = 0
        bot_status.total_articles_in_website = 0
        bot_status.current_link_number = 0

def start_scheduled_bot():
    if bot_status.is_running:
        logger.info("Bot is already running, skipping scheduled run.")
        return
        
    logger.info("Starting scheduled bot...")
    run_bot()

def run_scheduler():
    # Start scheduler thread
    schedule.every().day.at("20:00").do(start_scheduled_bot)
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Run Flask app
    app.run(debug=True, port=5001, use_reloader=False)