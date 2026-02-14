# Gold Price API & WordPress Plugin - Project Overview

## Project Overview
ระบบ API ราคาทองไทย ดึงข้อมูลจากสมาคมค้าทองคำ พร้อม WordPress Plugin สำหรับแสดงราคาทอง

**Repository:** https://github.com/tetipong2542/gold-beer.git

**Working Directory:** `/Users/pond-dev/Documents/gold-wp/`

**Production URL:** https://gold-beer-production.up.railway.app

---

## Architecture

### Data Sources (priority order)
1. **RakaTong API** (`rakatong.com/api/homepage.php`) — Primary source, provides `barChange`, `barChangeToday`, `annouce` (change count)
2. **GoldTraders Scraper** (`classic.goldtraders.or.th`) — Fallback when API fails or data is stale (>30 min)
3. **Playwright Scraper** (`scraper.py`) — Legacy, uses `xn--42cah7d0cxcvbbb9x.com`

### Source Selection (`SOURCE_AUTO` mode)
- Try RakaTong API first
- If API fails → fallback to GoldTraders scraper
- If API data is stale (update_time > 30 min old) → fallback to GoldTraders scraper

### Price Change Logic
- `price_change` — การเปลี่ยนแปลงล่าสุดในรอบนี้ (ได้จาก `barChange` ของ API)
- `today_change` — การเปลี่ยนแปลงรวมวันนี้ (ได้จาก `barChangeToday` ของ API)
- ใช้ค่าจาก API เป็นหลัก, fallback คำนวณจาก history เฉพาะเมื่อ API ไม่มีค่า

### Adaptive Refresh
- Base interval: 120s
- Off-hours (weekday 18:00-08:00, weekend): interval x10
- Unchanged x5+: interval x3, unchanged x10+: interval x5
- Quiet Hours: หยุดดึงข้อมูลตามช่วงเวลาที่กำหนด

---

## Project Structure

```
/Users/pond-dev/Documents/gold-wp/
├── app.py                      # Flask API server (routes, scheduler, adaptive refresh)
├── scraper_api.py              # RakaTong API scraper + auto-fallback logic
├── scraper_goldtraders.py      # GoldTraders.or.th HTML scraper (fallback)
├── scraper.py                  # Legacy Playwright scraper
├── requirements.txt            # Python dependencies
├── railway.json                # Railway deployment config (projectId)
├── gold_price_history.json     # Runtime data (gitignored)
├── templates/
│   └── index.html              # Dashboard UI (auto-refresh, settings, API docs)
├── README.md                   # Public documentation
├── project-overview.md         # This file
├── .gitignore
└── wordpress-plugin/           # WordPress plugins (gitignored)
    ├── gold-price-display/
    │   ├── gold-price-display.php    # Main plugin (shortcodes, API integration)
    │   ├── style.css                 # Dark-Gold Luxury theme
    │   ├── style-light.css           # Light theme variant
    │   ├── calculation.md            # Calculator logic docs
    │   └── readme.txt
    ├── gold-price-display.zip        # Plugin distribution zip
    └── gold-checkout-qt/             # Gold checkout/quotation plugin
        ├── gold-checkout-qt.php
        ├── includes/
        │   ├── class-gcq-cart.php
        │   ├── class-gcq-customer.php
        │   └── class-gcq-qt-generator.php
        ├── assets/
        │   ├── css/gcq-style.css
        │   └── js/gcq-cart.js, gcq-bridge.js, gcq-customer-popup.js
        └── templates/quotation.html
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API info |
| GET | `/dashboard` | Dashboard UI |
| GET | `/api/gold/current` | ราคาทองปัจจุบัน |
| GET | `/api/gold/bar` | ทองแท่ง |
| GET | `/api/gold/ornament` | ทองรูปพรรณ |
| GET | `/api/gold/history?limit=60` | ราคาย้อนหลัง |
| GET | `/api/gold/history/today` | ราคาย้อนหลังวันนี้ |
| GET | `/api/gold/summary` | สถิติ (สูงสุด/ต่ำสุด/เฉลี่ย) |
| GET | `/api/health` | Health check |
| GET | `/api/settings` | อ่านค่า settings |
| POST | `/api/gold/refresh` | Force refresh (rate limit: 30s) |
| POST | `/api/settings` | อัปเดต settings |

### API Response Format (`/api/gold/current`)

```json
{
  "success": true,
  "timestamp": "2026-02-14T09:43:00",
  "gold_bar": { "buy": 74000.00, "sell": 74200.00 },
  "gold_ornament": { "buy": 72525.44, "sell": 75000.00 },
  "price_change": { "amount": 100, "direction": "up" },
  "today_change": { "amount": 600, "direction": "up" },
  "change_count": 4,
  "update_time": "09:43",
  "update_date": "14/02/2569",
  "source_type": "api"
}
```

---

## Settings (configurable via API/Dashboard)

| Setting | Default | Description |
|---------|---------|-------------|
| `adaptive_enabled` | true | Adaptive refresh rate |
| `base_interval` | 120 | Base refresh interval (60-600s) |
| `wp_api_enabled` | true | WordPress Plugin API on/off |
| `gold_source_mode` | "auto" | "api", "scraper", or "auto" |
| `quiet_hours.enabled` | true | หยุดดึงข้อมูลนอกเวลาตลาด |
| `quiet_hours.weekday` | 18:00-08:00 | ช่วงหยุดวันจันทร์-ศุกร์ |
| `quiet_hours.weekend` | 18:00-08:00 | ช่วงหยุดวันเสาร์-อาทิตย์ |

---

## WordPress Plugins

### Gold Price Display
- **Shortcode:** `[gold_price]`
  - `type="bar|ornament|change|full"`
  - `show="header,footer"`
  - `hide="gpd-header,gpd-footer,gpd-datetime,gpd-change-row,gpd-card,gpd-grid"`

### Gold Checkout QT
- ระบบตะกร้าสินค้าทองคำ พร้อมใบเสนอราคา

---

## Deployment

- **Platform:** Railway
- **Project:** rare-analysis
- **Service:** gold-beer
- **Deploy command:** `railway up`

---

## Bug Fixes Log

### 2026-02-14: price_change/today_change ไม่แสดงบน Dashboard
- **สาเหตุ:** `calculate_price_changes()` ทับค่า `price_change` และ `today_change` ที่ API ส่งมาถูกต้องแล้ว
- **แก้ไข:** ใช้ค่าจาก API เป็นหลัก, fallback คำนวณจาก history เฉพาะเมื่อ API ไม่มี amount

### 2026-02-14: Quiet Hours บล็อก initial fetch ตอน server startup
- **สาเหตุ:** `fetch_gold_prices_job()` เช็ค quiet hours ทุกครั้ง รวมถึงตอน init ทำให้ server เริ่มนอกเวลาทำการไม่มีข้อมูล
- **แก้ไข:** เพิ่ม parameter `force=True` เพื่อ bypass quiet hours check ตอน initial fetch

---

## Useful Commands

```bash
# Test API scraper
python scraper_api.py

# Test GoldTraders scraper
python scraper_goldtraders.py

# Run server locally
python app.py

# Deploy to Railway
railway up

# Update plugin zip
cd wordpress-plugin && rm -f gold-price-display.zip && zip -r gold-price-display.zip gold-price-display/
```

---

## Important URLs

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/tetipong2542/gold-beer |
| Production (Railway) | https://gold-beer-production.up.railway.app |
| Dashboard | https://gold-beer-production.up.railway.app/dashboard |
| API Endpoint | https://gold-beer-production.up.railway.app/api/gold/current |
| Contact | https://line.me/ti/p/pond_che |

---

## Author

**Pond Dev.**
- LINE: https://line.me/ti/p/pond_che

---

*Last Updated: February 15, 2026*
