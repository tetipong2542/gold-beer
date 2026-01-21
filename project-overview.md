# 📋 Gold Price API & WordPress Plugin - Project Overview

## 🎯 Project Overview
ระบบ API ราคาทองไทย พร้อม WordPress Plugin สำหรับแสดงราคาทอง

**Repository:** https://github.com/tetipong2542/gold-beer.git

**Working Directory:** `/Users/pond-dev/Documents/gold-wp/`

---

## ✅ สิ่งที่ทำแล้ว

### 1. Flask API (Backend)
- **Files:** `app.py`, `scraper.py`, `templates/index.html`
- แก้ไข scraper ให้ดึงข้อมูลถูกต้อง:
  - `today_change`: +1,950 (สีเขียว ▲)
  - `price_change`: -150 (สีแดง ▼)
  - `change_count`: 45
  - `update_date`: "21 มกราคม 2569"
  - `update_time`: "เวลา 16:40 น."
- Deploy บน Railway: `https://gold-beer-production.up.railway.app`

### 2. WordPress Plugin
- **Location:** `/Users/pond-dev/Documents/gold-wp/wordpress-plugin/gold-price-display/`
- **Files:**
  - `gold-price-display.php` - Plugin หลัก
  - `style.css` - CSS แยกสำหรับ customization
  - `readme.txt` - คู่มือ

**Plugin Metadata:**
- Name: TH Gold Price
- Author: Pond Dev.
- Author URI: https://line.me/ti/p/pond_che

**Features ที่สร้างแล้ว:**
- Shortcode `[gold_price]` พร้อม parameters:
  - `type="bar|ornament|change|full"`
  - `show="header,footer"` - เพิ่ม header/footer ให้ bar/ornament
  - `hide="gpd-header,gpd-footer,gpd-datetime"` - ซ่อนส่วนต่างๆ
- เวลา header แสดงเวลาปัจจุบัน (Asia/Bangkok)
- Error handling ที่ดี พร้อม debug info

---

## 📁 Project Structure

```
/Users/pond-dev/Documents/gold-wp/
├── app.py                    # Flask API server
├── scraper.py                # Gold price scraper
├── requirements.txt          # Python dependencies
├── templates/index.html      # Dashboard
├── README.md                 # Project documentation
├── project-overview.md       # This file
├── .gitignore
└── wordpress-plugin/         # ไม่รวมใน git
    ├── gold-price-display.zip  # Plugin zip (6.3KB)
    └── gold-price-display/
        ├── gold-price-display.php
        ├── style.css
        └── readme.txt
```

---

## 🔄 สิ่งที่ต้องทำต่อ (Next Steps)

### Calculator Shortcode
1. **สร้าง Calculator Shortcode** ใน `gold-price-display.php`:
   - Function `render_calculator()`
   - Register shortcode `[gold_calculator]`

2. **เพิ่ม Dark-Gold Luxury CSS** ใน `style.css`:
   - สี dark background (#1a1a2e, #16162a)
   - สี gold accent (#FFD700, #B8860B)
   - Gradient, shadows, rounded corners
   - Input fields, buttons styled

3. **Calculator Features:**
   - เลือกประเภท: ทองแท่ง / ทองรูปพรรณ
   - เลือก: ซื้อ / ขาย
   - ใส่น้ำหนัก: บาท / สลึง / กรัม
   - แสดงราคารวมแบบ real-time

4. **อัปเดต zip file** และ README

---

## 🎨 Design Reference (Dark-Gold Luxury)

```css
:root {
    --gpd-dark: #1a1a2e;
    --gpd-darker: #16162a;
    --gpd-gold: #FFD700;
    --gpd-gold-dark: #B8860B;
    --gpd-card-bg: rgba(255, 255, 255, 0.05);
    --gpd-border-gold: rgba(255, 215, 0, 0.2);
}
```

---

## 💡 Useful Commands

```bash
# Test scraper
cd /Users/pond-dev/Documents/gold-wp && source venv/bin/activate && python scraper.py

# Update plugin zip
cd /Users/pond-dev/Documents/gold-wp/wordpress-plugin && rm -f gold-price-display.zip && zip -r gold-price-display.zip gold-price-display/

# Push to GitHub
cd /Users/pond-dev/Documents/gold-wp && git add . && git commit -m "message" && git push
```

---

## 🔗 Important URLs

| Resource | URL |
|----------|-----|
| GitHub | https://github.com/tetipong2542/gold-beer |
| API (Railway) | https://gold-beer-production.up.railway.app |
| API Endpoint | https://gold-beer-production.up.railway.app/api/gold/current |
| Contact | https://line.me/ti/p/pond_che |

---

## 📊 API Response Format

```json
{
  "status": "success",
  "data": {
    "bar": {
      "buy": "47,100",
      "sell": "47,000"
    },
    "ornament": {
      "buy": "47,576.40",
      "sell": "46,500"
    },
    "today_change": "+1,950",
    "price_change": "-150",
    "change_count": 45,
    "update_date": "21 มกราคม 2569",
    "update_time": "เวลา 16:40 น."
  }
}
```

---

## 📝 Shortcode Usage

### Basic Usage
```
[gold_price]                    <!-- แสดงทั้งหมด -->
[gold_price type="bar"]         <!-- เฉพาะทองแท่ง -->
[gold_price type="ornament"]    <!-- เฉพาะทองรูปพรรณ -->
[gold_price type="change"]      <!-- เฉพาะการเปลี่ยนแปลง -->
```

### Advanced Options
```
[gold_price type="bar" show="header,footer"]
[gold_price hide="gpd-header,gpd-datetime"]
```

---

## 👨‍💻 Author

**Pond Dev.**
- LINE: https://line.me/ti/p/pond_che

---

*Last Updated: January 21, 2026*
