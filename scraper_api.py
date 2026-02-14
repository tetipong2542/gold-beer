"""
Gold Price Scraper using GoldTraders.or.th Official API
With fallback to classic.goldtraders.or.th HTML scraper
Source: https://www.goldtraders.or.th/api/GoldPrices/details
"""
import requests
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

THAI_TZ = timezone(timedelta(hours=7))

GOLD_API_URL = "https://www.goldtraders.or.th/api/GoldPrices/details"
GOLD_SCRAPE_URL = "https://classic.goldtraders.or.th/"

SOURCE_API = "api"
SOURCE_SCRAPER = "scraper"
SOURCE_AUTO = "auto"


def scrape_gold_prices_api() -> dict:
    result = {
        "success": False,
        "timestamp": datetime.now(THAI_TZ).isoformat(),
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
        response = requests.get(GOLD_API_URL, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        response.raise_for_status()
        api_data = response.json()

        if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
            result["error"] = "GoldTraders API returned empty data"
            return result

        current = api_data[0]

        result["gold_bar"] = {
            "buy": current.get("bL_BuyPrice"),
            "sell": current.get("bL_SellPrice")
        }

        result["gold_ornament"] = {
            "buy": current.get("oM965_BuyPrice"),
            "sell": current.get("oM965_SellPrice")
        }

        price_change = current.get("priceChangeFromPrevRow", 0) or 0
        result["price_change"] = {
            "amount": abs(price_change),
            "direction": "down" if price_change < 0 else "up" if price_change > 0 else "unchanged"
        }

        today_change = current.get("priceChangeFromPrevDayLast", 0) or 0
        result["today_change"] = {
            "amount": abs(today_change),
            "direction": "down" if today_change < 0 else "up" if today_change > 0 else "unchanged"
        }

        as_time = current.get("asTime", "")
        result["update_time"] = as_time
        if as_time:
            result["update_date"] = as_time.split("T")[0]

        result["change_count"] = current.get("seq", 0)

        result["success"] = True
        logger.info(f"Fetched from GoldTraders API: Bar={result['gold_bar']}, change={price_change}, today={today_change}")

    except requests.RequestException as e:
        result["error"] = f"API request failed: {str(e)}"
        logger.error(f"GoldTraders API error: {e}")
    except Exception as e:
        result["error"] = f"Parsing failed: {str(e)}"
        logger.error(f"GoldTraders parsing error: {e}")

    return result


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
    if source_mode == SOURCE_SCRAPER:
        return fetch_from_scraper()

    result = scrape_gold_prices_api()
    result["source_type"] = SOURCE_API

    if source_mode == SOURCE_AUTO and not result.get("success"):
        logger.warning(f"API failed ({result.get('error')}), falling back to scraper...")
        scraper_result = fetch_from_scraper()
        if scraper_result.get("success"):
            return scraper_result
        logger.warning("Scraper also failed, returning API error")

    return result


if __name__ == "__main__":
    import json
    result = scrape_gold_prices_api()
    print(json.dumps(result, ensure_ascii=False, indent=2))
