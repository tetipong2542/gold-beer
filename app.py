"""
Gold Price API - Flask Application
Provides REST API endpoints for Thai gold prices with auto-refresh every 1 minute
"""
import os
import json
from datetime import datetime, timedelta, timezone
from collections import deque
from threading import Lock
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from scraper_api import fetch_gold_prices, SOURCE_API, SOURCE_SCRAPER, SOURCE_AUTO
import logging
import atexit
import sys

THAI_TZ = timezone(timedelta(hours=7))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers to reduce log volume
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Data storage with thread-safety
data_lock = Lock()
current_price = {}
price_history = deque(maxlen=1440)  # Store 24 hours of data (1 per minute)

# Configuration
HISTORY_FILE = "gold_price_history.json"

adaptive_settings = {
    "adaptive_enabled": True,
    "base_interval": 120,
    "unchanged_count": 0,
    "last_change_count": None,
    "current_interval": 120,
}

# WordPress API settings
wp_api_settings = {
    "enabled": True,
}

gold_source_settings = {
    "mode": SOURCE_AUTO,
    "last_source_used": None,
}

quiet_hours_settings = {
    "enabled": True,
    "weekday": {"enabled": True, "start": "18:00", "end": "08:00"},
    "weekend": {"enabled": True, "start": "18:00", "end": "08:00"},
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


def is_quiet_hours() -> bool:
    if not quiet_hours_settings["enabled"]:
        return False
    
    now = datetime.now(THAI_TZ)
    current_time = now.hour * 60 + now.minute
    weekday = now.weekday()
    
    if weekday < 5:
        config = quiet_hours_settings["weekday"]
    else:
        config = quiet_hours_settings["weekend"]
    
    if not config.get("enabled", True):
        return False
    
    start_h, start_m = map(int, config["start"].split(":"))
    end_h, end_m = map(int, config["end"].split(":"))
    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m
    
    if start_mins > end_mins:
        return current_time >= start_mins or current_time < end_mins
    else:
        return start_mins <= current_time < end_mins


def reschedule_fetch_job(interval_seconds: int):
    try:
        scheduler.reschedule_job(
            'gold_price_fetch',
            trigger=IntervalTrigger(seconds=interval_seconds)
        )
    except Exception as e:
        logger.error(f"Failed to reschedule job: {e}")


def calculate_price_changes(new_bar_sell: float) -> dict:
    """Calculate price_change (vs last) and today_change (vs first today) from history"""
    result = {
        "price_change": {"amount": 0, "direction": "unchanged"},
        "today_change": {"amount": 0, "direction": "unchanged"}
    }
    
    if not price_history or new_bar_sell is None:
        return result
    
    history_list = list(price_history)
    
    # price_change: compare with last entry
    if history_list:
        last_entry = history_list[-1]
        last_sell = last_entry.get("gold_bar", {}).get("sell")
        if last_sell and last_sell != new_bar_sell:
            diff = new_bar_sell - last_sell
            result["price_change"] = {
                "amount": abs(diff),
                "direction": "up" if diff > 0 else "down"
            }
    
    # today_change: compare with first entry of today
    today = datetime.now(THAI_TZ).strftime('%Y-%m-%d')
    today_entries = [h for h in history_list if h.get('timestamp', '').startswith(today)]
    
    if today_entries:
        first_today = today_entries[0]
        first_sell = first_today.get("gold_bar", {}).get("sell")
        if first_sell:
            total_diff = new_bar_sell - first_sell
            if total_diff != 0:
                result["today_change"] = {
                    "amount": abs(total_diff),
                    "direction": "up" if total_diff > 0 else "down"
                }
    
    return result


def fetch_gold_prices_job(force=False):
    global current_price, adaptive_settings, gold_source_settings
    
    if not force and is_quiet_hours():
        logger.info("Quiet hours - skipping fetch")
        return
    
    logger.info("Fetching gold prices...")
    result = fetch_gold_prices(gold_source_settings["mode"])
    
    with data_lock:
        if result.get("success"):
            new_bar_sell = result.get("gold_bar", {}).get("sell")
            
            api_price_change = result.get("price_change", {})
            api_today_change = result.get("today_change", {})
            
            if not api_price_change.get("amount") and not api_today_change.get("amount"):
                calculated_changes = calculate_price_changes(new_bar_sell)
                result["price_change"] = calculated_changes["price_change"]
                result["today_change"] = calculated_changes["today_change"]
            
            new_change_count = result.get("change_count")
            last_change_count = adaptive_settings["last_change_count"]
            
            price_changed = (last_change_count is None or new_change_count != last_change_count)
            
            if price_changed:
                adaptive_settings["unchanged_count"] = 0
                adaptive_settings["last_change_count"] = new_change_count
                
                history_entry = {
                    "timestamp": result["timestamp"],
                    "gold_bar": result["gold_bar"],
                    "gold_ornament": result["gold_ornament"],
                    "price_change": result["price_change"],
                    "update_time": result["update_time"],
                    "change_count": new_change_count
                }
                price_history.append(history_entry)
                logger.info(f"Price changed! Bar: {result['gold_bar']['sell']}, Count: {new_change_count}")
            else:
                adaptive_settings["unchanged_count"] += 1
                count = adaptive_settings["unchanged_count"]
                if count in [1, 10, 50, 100] or count % 100 == 0:
                    logger.info(f"Price unchanged (x{count})")
            
            current_price = result
            gold_source_settings["last_source_used"] = result.get("source_type", "unknown")
            
            if adaptive_settings["adaptive_enabled"]:
                adjust_refresh_interval()
        else:
            logger.warning(f"Failed to fetch prices: {result.get('error')}")
    
    if len(price_history) % 10 == 0:
        save_history()


def adjust_refresh_interval():
    global adaptive_settings

    now = datetime.now(THAI_TZ)
    hour = now.hour
    weekday = now.weekday()
    
    base = adaptive_settings["base_interval"]
    unchanged = adaptive_settings["unchanged_count"]
    
    is_off_hours = weekday >= 5 or hour < 9 or hour >= 17
    
    if is_off_hours:
        new_interval = base * 10
    elif unchanged >= 10:
        new_interval = base * 5
    elif unchanged >= 5:
        new_interval = base * 3
    else:
        new_interval = base
    
    if new_interval != adaptive_settings["current_interval"]:
        adaptive_settings["current_interval"] = new_interval
        reschedule_fetch_job(new_interval)
        logger.info(f"Adaptive interval: {new_interval}s (unchanged: {unchanged}, off_hours: {is_off_hours})")


# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=fetch_gold_prices_job,
    trigger=IntervalTrigger(seconds=adaptive_settings["base_interval"]),
    id='gold_price_fetch',
    name='Fetch gold prices',
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
        logger.info(f"Scheduler started - initial interval: {adaptive_settings['base_interval']}s")
    
    # Fetch initial data IMMEDIATELY if no data available
    with data_lock:
        need_fetch = not current_price
    
    if need_fetch:
        logger.info("Fetching initial gold prices...")
        fetch_gold_prices_job(force=True)
        logger.info("Initial gold prices loaded")


# Initialize on module load (works with both flask run and python app.py)
init_app()


# ============== API ENDPOINTS ==============

@app.route('/')
def index():
    """API information endpoint"""
    return jsonify({
        "name": "Thai Gold Price API",
        "version": "2.0.0",
        "data_source": "GOLD",
        "note": "No Cloudflare bypass needed - direct API access via RakaTong"
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
    
    fetch_gold_prices_job(force=True)
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
    with data_lock:
        return jsonify({
            "success": True,
            "settings": {
                "adaptive_enabled": adaptive_settings["adaptive_enabled"],
                "base_interval": adaptive_settings["base_interval"],
                "current_interval": adaptive_settings["current_interval"],
                "unchanged_count": adaptive_settings["unchanged_count"],
                "wp_api_enabled": wp_api_settings["enabled"],
                "gold_source_mode": gold_source_settings["mode"],
                "gold_source_last_used": gold_source_settings["last_source_used"],
                "quiet_hours": quiet_hours_settings,
                "is_quiet_hours_now": is_quiet_hours()
            }
        })


@app.route('/api/settings', methods=['POST'])
def update_settings():
    global adaptive_settings, wp_api_settings, gold_source_settings
    
    data = request.get_json() or {}
    
    with data_lock:
        if "adaptive_enabled" in data:
            adaptive_settings["adaptive_enabled"] = bool(data["adaptive_enabled"])
            logger.info(f"Adaptive mode: {'enabled' if adaptive_settings['adaptive_enabled'] else 'disabled'}")
        
        if "base_interval" in data:
            interval = int(data["base_interval"])
            if 60 <= interval <= 600:
                adaptive_settings["base_interval"] = interval
                adaptive_settings["current_interval"] = interval
                logger.info(f"Base interval: {interval}s")
            else:
                return jsonify({"success": False, "error": "Interval must be 60-600 seconds"}), 400
        
        if "wp_api_enabled" in data:
            wp_api_settings["enabled"] = bool(data["wp_api_enabled"])
            logger.info(f"WP API: {'enabled' if wp_api_settings['enabled'] else 'disabled'}")
        
        if "gold_source_mode" in data:
            mode = data["gold_source_mode"]
            if mode in [SOURCE_API, SOURCE_SCRAPER, SOURCE_AUTO]:
                gold_source_settings["mode"] = mode
                logger.info(f"Gold source mode: {mode}")
            else:
                return jsonify({"success": False, "error": "Invalid source mode"}), 400
        
        if "quiet_hours" in data:
            qh = data["quiet_hours"]
            if "enabled" in qh:
                quiet_hours_settings["enabled"] = bool(qh["enabled"])
            if "weekday" in qh:
                quiet_hours_settings["weekday"] = qh["weekday"]
            if "weekend" in qh:
                quiet_hours_settings["weekend"] = qh["weekend"]
            logger.info(f"Quiet hours: enabled={quiet_hours_settings['enabled']}, weekday={quiet_hours_settings['weekday']}, weekend={quiet_hours_settings['weekend']}")
        
        return jsonify({
            "success": True,
            "message": "Settings updated",
            "settings": {
                "adaptive_enabled": adaptive_settings["adaptive_enabled"],
                "base_interval": adaptive_settings["base_interval"],
                "current_interval": adaptive_settings["current_interval"],
                "wp_api_enabled": wp_api_settings["enabled"],
                "gold_source_mode": gold_source_settings["mode"],
                "gold_source_last_used": gold_source_settings["last_source_used"],
                "quiet_hours": quiet_hours_settings,
                "is_quiet_hours_now": is_quiet_hours()
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
