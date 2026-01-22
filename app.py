"""
Gold Price API - Flask Application
Provides REST API endpoints for Thai gold prices with auto-refresh every 1 minute
"""
import os
import json
from datetime import datetime, timedelta
from collections import deque
from threading import Lock
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scraper import scrape_gold_prices
import logging
import atexit
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Data storage with thread-safety
data_lock = Lock()
current_price = {}
price_history = deque(maxlen=1440)  # Store 24 hours of data (1 per minute)

# Configuration
FETCH_INTERVAL_MINUTES = 1
HISTORY_FILE = "gold_price_history.json"

# Adaptive refresh settings
adaptive_settings = {
    "adaptive_enabled": False,
    "base_interval": 120,  # Base interval in seconds
    "unchanged_count": 0,  # Count of consecutive unchanged prices
    "last_change_count": None,  # Last change_count from source
    "current_interval": 120,  # Current active interval
}

# WordPress API settings
wp_api_settings = {
    "enabled": True,  # Enable/disable WP API access
}


def load_history():
    """Load price history from file on startup"""
    global price_history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                price_history = deque(data, maxlen=1440)
                logger.info(f"Loaded {len(price_history)} historical records")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")


def save_history():
    """Save price history to file"""
    try:
        with data_lock:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(price_history), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


def fetch_gold_prices():
    """Fetch and store gold prices with smart caching"""
    global current_price, adaptive_settings
    
    logger.info("Fetching gold prices...")
    result = scrape_gold_prices()
    
    with data_lock:
        if result.get("success"):
            new_change_count = result.get("change_count")
            last_change_count = adaptive_settings["last_change_count"]
            
            # Check if price actually changed (compare change_count from source)
            price_changed = (last_change_count is None or new_change_count != last_change_count)
            
            if price_changed:
                # Price changed - reset unchanged counter
                adaptive_settings["unchanged_count"] = 0
                adaptive_settings["last_change_count"] = new_change_count
                
                # Add to history only when price changes
                history_entry = {
                    "timestamp": result["timestamp"],
                    "gold_bar": result["gold_bar"],
                    "gold_ornament": result["gold_ornament"],
                    "price_change": result["price_change"],
                    "update_time": result["update_time"],
                    "change_count": new_change_count
                }
                price_history.append(history_entry)
                logger.info(f"📈 Price changed! Bar: {result['gold_bar']['sell']}, Count: {new_change_count}")
            else:
                # Price unchanged - increment counter
                adaptive_settings["unchanged_count"] += 1
                logger.info(f"⏸️ Price unchanged (x{adaptive_settings['unchanged_count']})")
            
            # Always update current_price for display
            current_price = result
            
            # Adaptive interval adjustment
            if adaptive_settings["adaptive_enabled"]:
                adjust_refresh_interval()
        else:
            logger.warning(f"Failed to fetch prices: {result.get('error')}")
    
    # Save history periodically (every 10 changes)
    if len(price_history) % 10 == 0:
        save_history()


def adjust_refresh_interval():
    """Adjust refresh interval based on price activity"""
    global adaptive_settings

    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    base = adaptive_settings["base_interval"]
    unchanged = adaptive_settings["unchanged_count"]
    
    # Weekend or outside trading hours (before 9AM or after 5PM)
    is_off_hours = weekday >= 5 or hour < 9 or hour >= 17
    
    if is_off_hours:
        # Outside trading hours: use longer intervals
        new_interval = base * 5  # 5x base interval
    elif unchanged >= 10:
        # 10+ unchanged: double the interval (max 5x)
        new_interval = min(base * 2, base * 5)
    elif unchanged >= 5:
        # 5-9 unchanged: 1.5x interval
        new_interval = int(base * 1.5)
    else:
        # Active trading: use base interval
        new_interval = base
    
    if new_interval != adaptive_settings["current_interval"]:
        adaptive_settings["current_interval"] = new_interval
        logger.info(f"🔄 Adaptive interval: {new_interval}s (unchanged: {unchanged}, off_hours: {is_off_hours})")


# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=fetch_gold_prices,
    trigger=IntervalTrigger(minutes=FETCH_INTERVAL_MINUTES),
    id='gold_price_fetch',
    name='Fetch gold prices every minute',
    replace_existing=True
)


def init_app():
    """Initialize app data and scheduler - called on startup"""
    global current_price
    
    # Load historical data
    load_history()
    
    # Start scheduler if not already running
    if not scheduler.running:
        scheduler.start()
        logger.info(f"⏰ Scheduler started - fetching every {FETCH_INTERVAL_MINUTES} minute(s)")
    
    # Fetch initial data IMMEDIATELY if no data available
    with data_lock:
        need_fetch = not current_price
    
    if need_fetch:
        logger.info("📥 Fetching initial gold prices...")
        fetch_gold_prices()
        logger.info("✅ Initial gold prices loaded!")


# Initialize on module load (works with both flask run and python app.py)
init_app()


# ============== API ENDPOINTS ==============

@app.route('/')
def index():
    """API information endpoint"""
    return jsonify({
        "name": "Thai Gold Price API DEV Thai",
        "version": "1.0.0",
    })


@app.route('/dashboard')
def dashboard():
    """Render the Thai dashboard UI page"""
    return render_template('index.html')


@app.route('/api/gold/current')
def get_current_price():
    """Get current gold prices"""
    with data_lock:
        if not wp_api_settings["enabled"]:
            return jsonify({
                "success": False,
                "error": "API_DISABLED",
                "message": "Update! โปรดติดต่อ Developer"
            }), 503
        
        if not current_price:
            return jsonify({
                "success": False,
                "error": "No data available yet. Please wait for first fetch.",
                "message": "Data is being fetched, try again in a moment."
            }), 503
        return jsonify(current_price)


@app.route('/api/gold/bar')
def get_gold_bar():
    """Get gold bar prices only"""
    with data_lock:
        if not current_price:
            return jsonify({"success": False, "error": "No data available"}), 503
        return jsonify({
            "success": True,
            "timestamp": current_price.get("timestamp"),
            "update_time": current_price.get("update_time"),
            "gold_bar": current_price.get("gold_bar"),
            "price_change": current_price.get("price_change"),
            "today_change": current_price.get("today_change"),
            "change_count": current_price.get("change_count")
        })


@app.route('/api/gold/ornament')
def get_gold_ornament():
    """Get gold ornament prices only"""
    with data_lock:
        if not current_price:
            return jsonify({"success": False, "error": "No data available"}), 503
        return jsonify({
            "success": True,
            "timestamp": current_price.get("timestamp"),
            "update_time": current_price.get("update_time"),
            "gold_ornament": current_price.get("gold_ornament"),
            "price_change": current_price.get("price_change"),
            "today_change": current_price.get("today_change"),
            "change_count": current_price.get("change_count")
        })


@app.route('/api/gold/history')
def get_history():
    """
    Get price history
    Query params:
        - limit: Number of records (default: 60, max: 1440)
        - offset: Starting offset (default: 0)
    """
    limit = min(int(request.args.get('limit', 60)), 1440)
    offset = int(request.args.get('offset', 0))
    
    with data_lock:
        history_list = list(price_history)
        # Return newest first
        history_list.reverse()
        total = len(history_list)
        paginated = history_list[offset:offset + limit]
        
        return jsonify({
            "success": True,
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": paginated
        })


@app.route('/api/gold/history/today')
def get_history_today():
    """Get today's price history only"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    with data_lock:
        history_list = [h for h in price_history if h.get('timestamp', '').startswith(today)]
        # Return newest first
        history_list.reverse()
        
        return jsonify({
            "success": True,
            "date": today,
            "total": len(history_list),
            "data": history_list,
            "today_change": current_price.get("today_change") if current_price else None
        })


@app.route('/api/gold/refresh', methods=['POST'])
def refresh_prices():
    """Force refresh gold prices (with rate limiting)"""
    with data_lock:
        last_update = current_price.get("timestamp")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update)
                if datetime.now() - last_time < timedelta(seconds=30):
                    return jsonify({
                        "success": False,
                        "error": "Rate limited. Please wait at least 30 seconds between refreshes.",
                        "data": current_price
                    }), 429
            except (ValueError, TypeError):
                pass
    
    fetch_gold_prices()
    with data_lock:
        return jsonify({
            "success": True,
            "message": "Prices refreshed",
            "data": current_price
        })


@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    with data_lock:
        has_data = bool(current_price)
        last_update = current_price.get("timestamp") if current_price else None
    
    return jsonify({
        "status": "healthy",
        "has_data": has_data,
        "last_update": last_update,
        "history_count": len(price_history),
        "scheduler_running": scheduler.running
    })


@app.route('/api/gold/summary')
def get_summary():
    """Get price summary with statistics"""
    with data_lock:
        if not current_price or len(price_history) == 0:
            return jsonify({"success": False, "error": "No data available"}), 503
        
        history_list = list(price_history)
        
        # Calculate statistics
        bar_prices = [h["gold_bar"]["sell"] for h in history_list if h["gold_bar"]["sell"]]
        orn_prices = [h["gold_ornament"]["sell"] for h in history_list if h["gold_ornament"]["sell"]]
        
        summary = {
            "success": True,
            "current": current_price,
            "statistics": {
                "records_count": len(history_list),
                "gold_bar": {
                    "high": max(bar_prices) if bar_prices else None,
                    "low": min(bar_prices) if bar_prices else None,
                    "average": round(sum(bar_prices) / len(bar_prices), 2) if bar_prices else None
                },
                "gold_ornament": {
                    "high": max(orn_prices) if orn_prices else None,
                    "low": min(orn_prices) if orn_prices else None,
                    "average": round(sum(orn_prices) / len(orn_prices), 2) if orn_prices else None
                }
            }
        }
        return jsonify(summary)


@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current adaptive refresh settings"""
    with data_lock:
        return jsonify({
            "success": True,
            "settings": {
                "adaptive_enabled": adaptive_settings["adaptive_enabled"],
                "base_interval": adaptive_settings["base_interval"],
                "current_interval": adaptive_settings["current_interval"],
                "unchanged_count": adaptive_settings["unchanged_count"],
                "wp_api_enabled": wp_api_settings["enabled"]
            }
        })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update adaptive refresh settings"""
    global adaptive_settings, wp_api_settings
    
    data = request.get_json() or {}
    
    with data_lock:
        if "adaptive_enabled" in data:
            adaptive_settings["adaptive_enabled"] = bool(data["adaptive_enabled"])
            logger.info(f"🔧 Adaptive mode: {'enabled' if adaptive_settings['adaptive_enabled'] else 'disabled'}")
        
        if "base_interval" in data:
            interval = int(data["base_interval"])
            if 60 <= interval <= 500:
                adaptive_settings["base_interval"] = interval
                adaptive_settings["current_interval"] = interval
                logger.info(f"🔧 Base interval: {interval}s")
            else:
                return jsonify({"success": False, "error": "Interval must be 60-500 seconds"}), 400
        
        if "wp_api_enabled" in data:
            wp_api_settings["enabled"] = bool(data["wp_api_enabled"])
            logger.info(f"🔧 WP API: {'enabled' if wp_api_settings['enabled'] else 'disabled'}")
        
        return jsonify({
            "success": True,
            "message": "Settings updated",
            "settings": {
                "adaptive_enabled": adaptive_settings["adaptive_enabled"],
                "base_interval": adaptive_settings["base_interval"],
                "current_interval": adaptive_settings["current_interval"],
                "wp_api_enabled": wp_api_settings["enabled"]
            }
        })


# Cleanup on shutdown
def cleanup():
    """Cleanup function called on app shutdown"""
    try:
        if scheduler.running:
            logger.info("Shutting down scheduler...")
            scheduler.shutdown(wait=False)
        save_history()
        logger.info("Cleanup complete")
    except Exception as e:
        logger.warning(f"Cleanup warning: {e}")


atexit.register(cleanup)


if __name__ == '__main__':
    # Run Flask app
    # Default to port 8000 to avoid conflict with macOS AirPlay on port 5000
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get('PORT', 8000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        use_reloader=False  # Disable reloader to avoid duplicate scheduler
    )
