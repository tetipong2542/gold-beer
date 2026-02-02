"""
Gold Price Scraper Module
Scrapes gold prices from ราคาทองคําวันนี้.com
Uses Playwright to bypass Cloudflare protection
"""
import re
import os
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)

# Target URL (Punycode encoded Thai domain)
GOLD_PRICE_URL = "https://xn--42cah7d0cxcvbbb9x.com/"


class GoldPriceScraper:
    """Scraper class for Thai gold prices using Playwright"""
    
    def __init__(self):
        self.timeout = 30000  # 30 seconds timeout
        
    def _parse_price(self, text: str) -> Optional[float]:
        """Extract numeric price from text"""
        if not text:
            return None
        # Remove commas and non-numeric characters except decimal
        cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    
    def _parse_change(self, text: str) -> dict:
        """Parse price change information"""
        change = {"amount": 0, "direction": "unchanged"}
        if not text:
            return change
            
        text = text.strip()
        if "+" in text or "ขึ้น" in text:
            change["direction"] = "up"
        elif "-" in text or "ลง" in text:
            change["direction"] = "down"
            
        amount = self._parse_price(text)
        if amount:
            change["amount"] = amount
            
        return change
    
    def scrape(self, use_persistent_session: bool = True) -> dict:
        """
        Scrape current gold prices from the website using Playwright
        
        Returns:
            dict: Contains gold_bar, gold_ornament prices with buy/sell,
                  update_time, price_change info, and timestamp
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
            "source": GOLD_PRICE_URL,
            "error": None
        }
        
        try:
            browser = None  # Initialize for cleanup
            with sync_playwright() as p:
                if use_persistent_session:
                    # วิธี #5: Session Reuse (แนะนำ)
                    # ครั้งแรก: headless=False → manual solve Turnstile
                    # ครั้งต่อไป: headless=True → ใช้ session ซ้ำ
                    session_dir = "./cloudflare_session"
                    is_first_run = not os.path.exists(session_dir)
                    
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=session_dir,
                        headless=False if is_first_run else True,  # ครั้งแรกเปิด GUI
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="th-TH",
                        timezone_id="Asia/Bangkok",
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                        ]
                    )
                    
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    if is_first_run:
                        logger.warning("⚠️  FIRST RUN: Please solve Cloudflare Turnstile manually in the browser window")
                        logger.warning("⚠️  After solving, the session will be saved for future use")
                else:
                    # วิธี #1+#2: Stealth mode (fallback)
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--no-sandbox',
                            '--disable-dev-shm-usage',
                        ]
                    )
                    
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        locale="th-TH",
                        timezone_id="Asia/Bangkok",
                    )
                    
                    page = context.new_page()
                    
                    # Apply stealth mode
                    stealth = Stealth()
                    stealth.apply_stealth_sync(page)
                
                # Navigate to URL
                logger.info(f"Loading {GOLD_PRICE_URL}...")
                page.goto(GOLD_PRICE_URL, wait_until="load", timeout=self.timeout)
                
                # Wait a bit for any dynamic content / Cloudflare
                if use_persistent_session:
                    session_dir = "./cloudflare_session"
                    if not os.path.exists(session_dir) or len(os.listdir(session_dir)) == 0:
                        # ครั้งแรก: รอให้ user solve Turnstile
                        logger.info("Waiting 30 seconds for manual Turnstile solve...")
                        page.wait_for_timeout(30000)  # 30 วินาที
                    else:
                        page.wait_for_timeout(3000)
                else:
                    page.wait_for_timeout(3000)
                
                # Wait for Cloudflare challenge to complete (if any)
                # Look for the gold price table to ensure page is fully loaded
                try:
                    page.wait_for_selector('.divgta, table, body', timeout=10000)
                    logger.info("Page loaded successfully")
                except PlaywrightTimeoutError:
                    logger.warning("Timeout waiting for content, trying to parse anyway")
                
                # Take screenshot for debugging (optional)
                # page.screenshot(path="debug_screenshot.png")
                
                # Get page content
                html_content = page.content()
                
                # Debug: Save HTML to file for inspection
                with open('/tmp/gold_page_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info("Saved HTML to /tmp/gold_page_debug.html for debugging")
                
                # Debug: Check if we got Cloudflare challenge page
                if "just a moment" in html_content.lower() or "checking your browser" in html_content.lower():
                    logger.error("Still blocked by Cloudflare challenge page")
                    result["error"] = "Blocked by Cloudflare - challenge page detected"
                    browser.close()
                    return result
                
                # Close browser/context
                if use_persistent_session:
                    context.close()
                elif browser:
                    browser.close()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Method 1: Find by table structure with divgta class
            divgta = soup.find('div', class_='divgta')
            if divgta:
                tables = divgta.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'span', 'em'])
                        row_text = row.get_text()
                        
                        # Check for gold bar (ทองแท่ง)
                        if 'ทองแท่ง' in row_text or 'ทองคำแท่ง' in row_text:
                            prices = [self._parse_price(cell.get_text()) for cell in cells]
                            prices = [p for p in prices if p and p > 10000]
                            if len(prices) >= 2:
                                result["gold_bar"]["buy"] = prices[0]
                                result["gold_bar"]["sell"] = prices[1]
                                
                        # Check for gold ornament (ทองรูปพรรณ)
                        if 'ทองรูปพรรณ' in row_text or 'รูปพรรณ' in row_text:
                            prices = [self._parse_price(cell.get_text()) for cell in cells]
                            prices = [p for p in prices if p and p > 10000]
                            if len(prices) >= 2:
                                result["gold_ornament"]["buy"] = prices[0]
                                result["gold_ornament"]["sell"] = prices[1]
            
            # Method 2: Find by specific class patterns (backup)
            if not result["gold_bar"]["buy"]:
                # Look for span and em elements with prices
                all_spans = soup.find_all('span', class_='span')
                all_ems = soup.find_all('em', class_='em')
                
                gold_bar_found = False
                gold_ornament_found = False
                
                for i, span in enumerate(all_spans):
                    text = span.get_text()
                    if 'ทองแท่ง' in text and not gold_bar_found:
                        # Next two em elements should be prices
                        if i < len(all_ems) - 1:
                            result["gold_bar"]["buy"] = self._parse_price(all_ems[i].get_text())
                            result["gold_bar"]["sell"] = self._parse_price(all_ems[i+1].get_text())
                            gold_bar_found = True
                    elif 'รูปพรรณ' in text and not gold_ornament_found:
                        if i < len(all_ems) - 1:
                            result["gold_ornament"]["buy"] = self._parse_price(all_ems[i].get_text())
                            result["gold_ornament"]["sell"] = self._parse_price(all_ems[i+1].get_text())
                            gold_ornament_found = True
            
            # Method 3: Pattern matching on full text
            if not result["gold_bar"]["buy"]:
                full_text = soup.get_text()
                
                # Pattern for gold bar prices
                bar_pattern = r'ทอง(?:คำ)?แท่ง[^\d]*?([\d,]+)[^\d]*([\d,]+)'
                bar_match = re.search(bar_pattern, full_text)
                if bar_match:
                    result["gold_bar"]["buy"] = self._parse_price(bar_match.group(1))
                    result["gold_bar"]["sell"] = self._parse_price(bar_match.group(2))
                
                # Pattern for gold ornament prices
                orn_pattern = r'ทอง(?:คำ)?รูปพรรณ[^\d]*?([\d,]+)[^\d]*([\d,]+)'
                orn_match = re.search(orn_pattern, full_text)
                if orn_match:
                    result["gold_ornament"]["buy"] = self._parse_price(orn_match.group(1))
                    result["gold_ornament"]["sell"] = self._parse_price(orn_match.group(2))
            
            # Find update time
            time_patterns = [
                r'อัพเดท[^\d]*(\d{1,2}[:/]\d{2})',
                r'ประกาศครั้งที่[^\d]*(\d+)',
                r'(\d{1,2}:\d{2})\s*น\.',
            ]
            
            for pattern in time_patterns:
                time_match = re.search(pattern, soup.get_text())
                if time_match:
                    result["update_time"] = time_match.group(1)
                    break
            
            # Find price change info from the divgta table structure
            # Based on HTML analysis:
            # Row 3: <td class="span bg-span g-u">วันนี้<span>1,950</td> | <td><span class="css-sprite-down"></td> | <td class="em bg-em al-l g-d">-150</td>
            # - today_change: "วันนี้ 1,950" with class g-u (green/up)
            # - price_change: "-150" with class g-d (red/down)
            
            if divgta:
                # Find today's change - look for td with "วันนี้" text and g-u or g-d class
                for td in divgta.find_all('td', class_=re.compile(r'g-[ud]')):
                    text = td.get_text(strip=True)
                    classes = td.get('class') or []
                    
                    if 'วันนี้' in text:
                        # Extract number after วันนี้
                        match = re.search(r'วันนี้[^\d]*([0-9,]+)', text)
                        if match:
                            amount = self._parse_price(match.group(1))
                            if amount:
                                direction = "up" if 'g-u' in classes else "down"
                                result["today_change"] = {"amount": int(amount), "direction": direction}
                    
                    # Find latest price change - element with al-l class and contains just a number (possibly with +/-)
                    elif classes and 'al-l' in classes and 'em' in classes:
                        # This is the latest change cell like "-150" or "+50"
                        match = re.search(r'^([+-]?[0-9,]+)$', text)
                        if match:
                            amount = self._parse_price(text)
                            if amount:
                                direction = "up" if 'g-u' in classes else "down"
                                result["price_change"] = {"amount": int(amount), "direction": direction}
            
            # Find change count (ครั้งที่) - look for number after ครั้งที่
            count_match = re.search(r'ครั้งที่\s*(\d+)', soup.get_text())
            if count_match:
                result["change_count"] = int(count_match.group(1))
            
            if divgta:
                txtd_cells = divgta.find_all('td', class_='txtd')
                for td in txtd_cells:
                    text = td.get_text(strip=True)
                    if re.search(r'\d+\s+\S+\s+\d{4}', text):
                        result["update_date"] = text
                    elif 'เวลา' in text:
                        result["update_time"] = text
            
            # Validate we got actual data
            if result["gold_bar"]["buy"] or result["gold_ornament"]["buy"]:
                result["success"] = True
                logger.info(f"Successfully scraped gold prices: Bar={result['gold_bar']}, Ornament={result['gold_ornament']}")
            else:
                result["error"] = "Could not parse gold prices from page"
                logger.warning("Failed to parse gold prices from page content")
                
        except PlaywrightTimeoutError as e:
            result["error"] = f"Timeout: {str(e)}"
            logger.error(f"Playwright timeout error: {e}")
        except Exception as e:
            result["error"] = f"Scraping failed: {str(e)}"
            logger.error(f"Scraping error: {e}")
            
        return result


def scrape_gold_prices() -> dict:
    """Convenience function to scrape gold prices"""
    scraper = GoldPriceScraper()
    return scraper.scrape()


if __name__ == "__main__":
    # Test the scraper
    result = scrape_gold_prices()
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
