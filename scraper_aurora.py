import requests
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

THAI_TZ = timezone(timedelta(hours=7))
GOLD_SCRAPE_URL = "https://www.aurora.co.th/price/gold_pricelist"


def scrape_gold_prices() -> dict:
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
        
        tables = soup.find_all('table')
        if not tables:
            result["error"] = "No price tables found"
            return result
        
        today_table = tables[0]
        rows = today_table.find_all('tr')
        
        if len(rows) < 3:
            result["error"] = "Not enough rows in price table"
            return result
        
        latest_row = rows[2]
        cells = latest_row.find_all('td')
        
        if len(cells) < 6:
            result["error"] = f"Expected 6 cells, got {len(cells)}"
            return result
        
        def parse_price(text):
            if not text:
                return None
            text = text.replace(",", "").replace(" ", "")
            try:
                return float(text)
            except ValueError:
                return None
        
        def parse_change(text):
            if not text:
                return {"amount": 0, "direction": "unchanged"}
            text = text.strip()
            match = re.match(r'([+-]?)([0-9,]+)', text)
            if match:
                sign = match.group(1)
                amount = float(match.group(2).replace(",", ""))
                if sign == '+':
                    return {"amount": amount, "direction": "up"}
                elif sign == '-':
                    return {"amount": amount, "direction": "down"}
                elif amount > 0:
                    return {"amount": amount, "direction": "up"}
            return {"amount": 0, "direction": "unchanged"}
        
        time_text = cells[0].get_text(strip=True)
        count_text = cells[1].get_text(strip=True)
        bar_buy = parse_price(cells[2].get_text(strip=True))
        bar_sell = parse_price(cells[3].get_text(strip=True))
        orn_buy = parse_price(cells[4].get_text(strip=True))
        change_text = cells[5].get_text(strip=True)
        
        result["gold_bar"]["buy"] = bar_buy
        result["gold_bar"]["sell"] = bar_sell
        result["gold_ornament"]["buy"] = orn_buy
        
        orn_sell_elem = soup.find('span', class_='aurora-gold-v5__price-value--sale')
        if orn_sell_elem:
            result["gold_ornament"]["sell"] = parse_price(orn_sell_elem.get_text(strip=True))
        else:
            result["gold_ornament"]["sell"] = bar_sell + 800 if bar_sell else None
        
        result["price_change"] = parse_change(change_text)
        
        try:
            result["change_count"] = int(count_text)
        except ValueError:
            result["change_count"] = 0
        
        today = datetime.now(THAI_TZ).strftime('%d/%m/%Y')
        result["update_time"] = f"{today} เวลา {time_text} (ครั้งที่ {result['change_count']})"
        result["update_date"] = today
        
        if len(tables) >= 2:
            summary_table = tables[1]
            summary_rows = summary_table.find_all('tr')
            for row in summary_rows:
                text = row.get_text(strip=True)
                if 'สรุปราคาทองระหว่างวัน' in text:
                    match = re.search(r'([+-]?[0-9,]+)\s*$', text)
                    if match:
                        result["today_change"] = parse_change(match.group(1))
                    break
        
        if result["gold_bar"]["sell"] and result["gold_bar"]["buy"]:
            result["success"] = True
            logger.info(f"Scraped from Aurora: Bar sell={result['gold_bar']['sell']}, change={result['price_change']}")
        else:
            result["error"] = "Could not parse gold prices"
            
    except requests.RequestException as e:
        result["error"] = f"Request failed: {str(e)}"
        logger.error(f"Aurora scraper error: {e}")
    except Exception as e:
        result["error"] = f"Parsing failed: {str(e)}"
        logger.error(f"Aurora parsing error: {e}")
    
    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    result = scrape_gold_prices()
    print(json.dumps(result, ensure_ascii=False, indent=2))
