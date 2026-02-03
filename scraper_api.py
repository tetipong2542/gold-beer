"""
Gold Price Scraper using GoldTraders API
No Cloudflare bypass needed - direct API access
"""
import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# API endpoint (no Cloudflare protection)
GOLD_API_URL = "https://static-gold.tothanate.workers.dev/api/gold"


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


if __name__ == "__main__":
    # Test the API scraper
    import json
    result = scrape_gold_prices_api()
    print(json.dumps(result, ensure_ascii=False, indent=2))
