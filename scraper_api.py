"""
Gold Price Scraper using RakaTong.com API
With auto-fallback to classic.goldtraders.or.th when API data is stale
Source: https://rakatong.com/api/homepage.php
"""
import requests
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

GOLD_API_URL = "https://rakatong.com/api/homepage.php"
GOLD_SCRAPE_URL = "https://classic.goldtraders.or.th/"

SOURCE_API = "api"
SOURCE_SCRAPER = "scraper"
SOURCE_AUTO = "auto"

STALE_THRESHOLD_MINUTES = 30


def _parse_price(value: str) -> float:
    """Parse price string like '72,400.00' to float 72400.00"""
    if not value:
        return 0.0
    return float(str(value).replace(",", ""))


def scrape_gold_prices_api() -> dict:
    """
    Scrape gold prices from RakaTong.com API (homepage.php)
    
    API Response format:
    {
      "success": true,
      "data": {
        "current": {
          "date": "06/02/2569", "time": "09:43", "annouce": "4",
          "barBuy": "72,400.00", "barSell": "72,600.00",
          "ornamentBuy": "70,948.80", "ornamentSell": "73,400.00",
          "barChange": "100", "barChangeToday": "600"
        },
        "today": [...], "statistic": {...}, "last30Days": {...}
      }
    }
    
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
        api_data = response.json()
        
        if not api_data.get("success"):
            result["error"] = "RakaTong API returned success=false"
            return result
        
        data = api_data.get("data", {})
        current = data.get("current", {})
        
        result["gold_bar"] = {
            "buy": _parse_price(current.get("barBuy")),
            "sell": _parse_price(current.get("barSell"))
        }
        
        result["gold_ornament"] = {
            "buy": _parse_price(current.get("ornamentBuy")),
            "sell": _parse_price(current.get("ornamentSell"))
        }
        
        bar_change_str = str(current.get("barChange", "0")).replace(",", "")
        bar_change = float(bar_change_str) if bar_change_str else 0
        change_direction = "down" if bar_change < 0 else "up" if bar_change > 0 else "unchanged"
        
        result["price_change"] = {
            "amount": abs(bar_change),
            "direction": change_direction
        }
        
        today_change_str = str(current.get("barChangeToday", "0")).replace(",", "")
        today_change = float(today_change_str) if today_change_str else 0
        today_direction = "down" if today_change < 0 else "up" if today_change > 0 else "unchanged"
        
        result["today_change"] = {
            "amount": abs(today_change),
            "direction": today_direction
        }
        
        # Metadata
        result["update_date"] = current.get("date")
        result["update_time"] = current.get("time")
        
        annouce = current.get("annouce", "0")
        result["change_count"] = int(annouce) if str(annouce).isdigit() else 0
        
        result["success"] = True
        logger.info(f"Successfully fetched from RakaTong API: Bar={result['gold_bar']}")
        
    except requests.RequestException as e:
        result["error"] = f"API request failed: {str(e)}"
        logger.error(f"RakaTong API error: {e}")
    except Exception as e:
        result["error"] = f"Parsing failed: {str(e)}"
        logger.error(f"RakaTong parsing error: {e}")
    
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
    try:
        from scraper_goldtraders import scrape_gold_prices
        logger.info("Fetching from classic.goldtraders.or.th...")
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
        source_mode: 'api', 'scraper', or 'auto' (fallback if stale or failed)
    """
    if source_mode == SOURCE_SCRAPER:
        return fetch_from_scraper()
    
    result = scrape_gold_prices_api()
    result["source_type"] = SOURCE_API
    
    if source_mode == SOURCE_AUTO:
        if not result.get("success"):
            logger.warning(f"API failed ({result.get('error')}), falling back to scraper...")
            scraper_result = fetch_from_scraper()
            if scraper_result.get("success"):
                return scraper_result
            logger.warning("Scraper also failed, returning API error")
        elif is_data_stale(result.get("update_time") or ""):
            logger.warning(f"API data is stale (update_time: {result.get('update_time')}), trying scraper...")
            api_price_change = result.get("price_change", {})
            api_today_change = result.get("today_change", {})
            scraper_result = fetch_from_scraper()
            if scraper_result.get("success"):
                if not scraper_result.get("price_change", {}).get("amount"):
                    scraper_result["price_change"] = api_price_change
                if not scraper_result.get("today_change", {}).get("amount"):
                    scraper_result["today_change"] = api_today_change
                return scraper_result
            logger.warning("Scraper failed, using stale API data")
    
    return result


if __name__ == "__main__":
    # Test the API scraper
    import json
    result = scrape_gold_prices_api()
    print(json.dumps(result, ensure_ascii=False, indent=2))
