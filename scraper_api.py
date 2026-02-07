"""
Gold Price Scraper using GoldTraders API
No Cloudflare bypass needed - direct API access
With auto-fallback to scraper.py when API data is stale
"""
import requests
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

GOLD_API_URL = "https://static-gold.tothanate.workers.dev/api/gold"
GOLD_SCRAPE_URL = "https://xn--42cah7d0cxcvbbb9x.com/"

SOURCE_API = "api"
SOURCE_SCRAPER = "scraper"
SOURCE_AUTO = "auto"

STALE_THRESHOLD_MINUTES = 30  # If data older than this, fallback to scraper


def scrape_gold_prices_api() -> dict:
    """
    Scrape gold prices from GoldTraders API
    
    Returns:
        dict: Contains gold_bar, gold_ornament prices with metadata
    """
    result = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "gold_bar": {"buy": None, "sell": None},
        "gold_ornament": {"buy": None, "sell": None},
        "update_time": None,
        "update_date": None,
        "price_change": {"amount": 0, "direction": "unchanged"},
        "today_change": {"amount": 0, "direction": "unchanged"},
        "change_count": 0,
        "source": GOLD_API_URL,
        "error": None
    }
    
    try:
        response = requests.get(GOLD_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract current prices
        current = data.get("current_prices", {})
        gold_bar = current.get("gold_bar", {})
        gold_ornament = current.get("gold_ornament", {})
        
        result["gold_bar"] = {
            "buy": float(gold_bar.get("buy", 0)),
            "sell": float(gold_bar.get("sell", 0))
        }
        
        result["gold_ornament"] = {
            "buy": float(gold_ornament.get("buy", 0)),
            "sell": float(gold_ornament.get("sell", 0))
        }
        
        # Price change
        change_amount = abs(gold_bar.get("change", 0))
        change_direction = "down" if gold_bar.get("change", 0) < 0 else "up" if gold_bar.get("change", 0) > 0 else "unchanged"
        
        result["price_change"] = {
            "amount": change_amount,
            "direction": change_direction
        }
        
        result["today_change"] = {
            "amount": change_amount,
            "direction": change_direction
        }
        
        # Metadata
        metadata = data.get("metadata", {})
        result["update_date"] = metadata.get("publish_date")
        result["update_time"] = metadata.get("last_updated")
        
        # Extract change count from update_info (e.g., "ประกาศวันที่ 03/02/2569 เวลา 10:54 น. (ครั้งที่ 19)")
        update_info = metadata.get("update_info", "")
        import re
        count_match = re.search(r'ครั้งที่\s*(\d+)', update_info)
        result["change_count"] = int(count_match.group(1)) if count_match else 0
        
        result["success"] = True
        logger.info(f"Successfully fetched from API: Bar={result['gold_bar']}")
        
    except requests.RequestException as e:
        result["error"] = f"API request failed: {str(e)}"
        logger.error(f"API error: {e}")
    except Exception as e:
        result["error"] = f"Parsing failed: {str(e)}"
        logger.error(f"Parsing error: {e}")
    
    return result


def is_data_stale(update_time_str: str) -> bool:
    """Check if update_time is older than STALE_THRESHOLD_MINUTES"""
    if not update_time_str:
        return True
    
    try:
        time_match = re.search(r'(\d{1,2}):(\d{2})', update_time_str)
        if not time_match:
            return True
        
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        now = datetime.now()
        update_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if update_time > now:
            update_time -= timedelta(days=1)
        
        return (now - update_time) > timedelta(minutes=STALE_THRESHOLD_MINUTES)
    except Exception:
        return True


def fetch_from_scraper() -> dict:
    """Fetch gold prices using Playwright scraper (fallback)"""
    try:
        from scraper import scrape_gold_prices
        logger.info("Falling back to Playwright scraper...")
        result = scrape_gold_prices()
        if result.get("success"):
            result["source"] = GOLD_SCRAPE_URL
            result["source_type"] = SOURCE_SCRAPER
        return result
    except ImportError as e:
        logger.error(f"Cannot import scraper: {e}")
        return {"success": False, "error": "Scraper module not available"}
    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        return {"success": False, "error": str(e)}


def fetch_gold_prices(source_mode: str = SOURCE_AUTO) -> dict:
    """
    Fetch gold prices with configurable source mode.
    
    Args:
        source_mode: 'api', 'scraper', or 'auto' (fallback if stale)
    """
    if source_mode == SOURCE_SCRAPER:
        return fetch_from_scraper()
    
    result = scrape_gold_prices_api()
    result["source_type"] = SOURCE_API
    
    if source_mode == SOURCE_AUTO and result.get("success"):
        if is_data_stale(result.get("update_time") or ""):
            logger.warning(f"API data is stale (update_time: {result.get('update_time')}), trying scraper...")
            scraper_result = fetch_from_scraper()
            if scraper_result.get("success"):
                return scraper_result
            logger.warning("Scraper failed, using stale API data")
    
    return result


if __name__ == "__main__":
    # Test the API scraper
    import json
    result = scrape_gold_prices_api()
    print(json.dumps(result, ensure_ascii=False, indent=2))
