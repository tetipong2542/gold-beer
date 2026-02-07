"""
Gold Price Scraper from GoldTraders.or.th (Official GTA Website)
Simple requests-based scraper - no Cloudflare bypass needed
"""
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

GOLD_SCRAPE_URL = "https://classic.goldtraders.or.th/"


def scrape_gold_prices() -> dict:
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
        "source": GOLD_SCRAPE_URL,
        "error": None
    }
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        response = requests.get(GOLD_SCRAPE_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        bar_sell = soup.find("span", id="DetailPlace_uc_goldprices1_lblBLSell")
        bar_buy = soup.find("span", id="DetailPlace_uc_goldprices1_lblBLBuy")
        orn_sell = soup.find("span", id="DetailPlace_uc_goldprices1_lblOMSell")
        orn_buy = soup.find("span", id="DetailPlace_uc_goldprices1_lblOMBuy")
        
        def parse_price(element):
            if not element:
                return None
            text = element.get_text(strip=True).replace(",", "")
            try:
                return float(text)
            except ValueError:
                return None
        
        result["gold_bar"]["sell"] = parse_price(bar_sell)
        result["gold_bar"]["buy"] = parse_price(bar_buy)
        result["gold_ornament"]["sell"] = parse_price(orn_sell)
        result["gold_ornament"]["buy"] = parse_price(orn_buy)
        
        as_time = soup.find("span", id="DetailPlace_uc_goldprices1_lblAsTime")
        if as_time:
            time_text = as_time.get_text(strip=True)
            result["update_time"] = time_text
            
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', time_text)
            if date_match:
                result["update_date"] = date_match.group(1)
            
            count_match = re.search(r'ครั้งที่\s*(\d+)', time_text)
            if count_match:
                result["change_count"] = int(count_match.group(1))
        
        if result["gold_bar"]["sell"] and result["gold_bar"]["buy"]:
            result["success"] = True
            logger.info(f"Scraped from GoldTraders: Bar sell={result['gold_bar']['sell']}")
        else:
            result["error"] = "Could not parse gold prices"
            
    except requests.RequestException as e:
        result["error"] = f"Request failed: {str(e)}"
        logger.error(f"Scraper error: {e}")
    except Exception as e:
        result["error"] = f"Parsing failed: {str(e)}"
        logger.error(f"Parsing error: {e}")
    
    return result


if __name__ == "__main__":
    import json
    result = scrape_gold_prices()
    print(json.dumps(result, ensure_ascii=False, indent=2))
