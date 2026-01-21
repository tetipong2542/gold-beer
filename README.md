# TH Gold Price API 🥇

ระบบ API ราคาทองไทย ดึงข้อมูลจากสมาคมค้าทองคำ อัพเดทอัตโนมัติ

## 📋 Features

- ✅ ดึงราคาทองแท่ง และ ทองรูปพรรณ 96.5%
- ✅ แสดงการเปลี่ยนแปลงล่าสุด (เช่น -150 บาท)
- ✅ แสดงการเปลี่ยนแปลงรวมวันนี้ (เช่น +1,950 บาท)
- ✅ Dashboard สวยงาม พร้อม Auto-refresh
- ✅ REST API สำหรับเชื่อมต่อกับระบบอื่น
- ✅ Cache อัตโนมัติ ลดการเรียก API ซ้ำ

---

## 🚀 การติดตั้ง

### 1. Clone Repository

```bash
git clone https://github.com/tetipong2542/gold-beer.git
cd gold-beer
```

### 2. สร้าง Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# หรือ
venv\Scripts\activate     # Windows
```

### 3. ติดตั้ง Dependencies

```bash
pip install -r requirements.txt
```

### 4. รัน Server

```bash
python app.py
```

Server จะรันที่ `http://localhost:8000`

---

## 🌐 API Endpoints

### ราคาทองปัจจุบัน

```
GET /api/gold/current
```

**Response:**
```json
{
  "success": true,
  "timestamp": "2026-01-21T16:40:00",
  "gold_bar": {
    "buy": 71450.00,
    "sell": 71550.00
  },
  "gold_ornament": {
    "buy": 70024.04,
    "sell": 72350.00
  },
  "price_change": {
    "amount": 150,
    "direction": "down"
  },
  "today_change": {
    "amount": 1950,
    "direction": "up"
  },
  "change_count": 45
}
```

### ราคาทองแท่ง

```
GET /api/gold/bar
```

### ราคาทองรูปพรรณ

```
GET /api/gold/ornament
```

### ราคาย้อนหลัง

```
GET /api/gold/history?limit=60
```

**Parameters:**
- `limit` - จำนวนรายการ (default: 60, max: 1440)
- `offset` - เริ่มจากรายการที่ (default: 0)

### ราคาย้อนหลังวันนี้

```
GET /api/gold/history/today
```

### สถิติราคา

```
GET /api/gold/summary
```

**Response:**
```json
{
  "success": true,
  "statistics": {
    "gold_bar": {
      "high": 71600.00,
      "low": 69650.00,
      "average": 70500.00
    }
  }
}
```

### บังคับ Refresh

```
POST /api/gold/refresh
```

> ⚠️ Rate limit: 30 วินาที

### Health Check

```
GET /api/health
```

---

## 🖥️ Dashboard

เข้าถึง Dashboard ได้ที่:

```
http://localhost:8000/dashboard
```

**Features:**
- แสดงราคาทองแท่ง และ ทองรูปพรรณ
- แสดงการเปลี่ยนแปลงล่าสุด (สีแดง/เขียว)
- แสดงการเปลี่ยนแปลงรวมวันนี้
- Auto-refresh ตามที่ตั้งค่า
- ปุ่ม Manual Refresh

---

## 📝 ตัวอย่างการใช้งาน

### PHP (WordPress)

```php
<?php
$response = wp_remote_get('https://your-api-url.com/api/gold/current');
$gold = json_decode(wp_remote_retrieve_body($response), true);

if ($gold['success']) {
    echo 'ทองแท่ง ขายออก: ' . number_format($gold['gold_bar']['sell']) . ' บาท';
    echo 'วันนี้: ' . ($gold['today_change']['direction'] == 'up' ? '+' : '-') . $gold['today_change']['amount'];
}
?>
```

### JavaScript

```javascript
fetch('https://your-api-url.com/api/gold/current')
  .then(res => res.json())
  .then(data => {
    console.log('ทองแท่ง:', data.gold_bar.sell);
    console.log('วันนี้:', data.today_change.amount, data.today_change.direction);
  });
```

### Python

```python
import requests

response = requests.get('https://your-api-url.com/api/gold/current')
data = response.json()

if data['success']:
    print(f"ทองแท่ง: {data['gold_bar']['sell']:,.2f} บาท")
    print(f"วันนี้: {data['today_change']['direction']} {data['today_change']['amount']}")
```

### cURL

```bash
curl -X GET https://your-api-url.com/api/gold/current
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 8000 | Port ที่ server รัน |
| `FLASK_DEBUG` | false | เปิด Debug mode |

### ตั้งค่า Refresh Interval

แก้ไขใน `app.py`:

```python
FETCH_INTERVAL_MINUTES = 1  # ดึงข้อมูลทุก 1 นาที
```

---

## 🔌 WordPress Plugin

ดาวน์โหลด Plugin สำหรับ WordPress ได้ที่โฟลเดอร์ `wordpress-plugin/`

### วิธีติดตั้ง Plugin

1. ดาวน์โหลด `gold-price-display.zip`
2. ไปที่ WordPress Admin → Plugins → Add New → Upload Plugin
3. เลือกไฟล์ zip แล้วกด Install Now
4. Activate Plugin

### ตั้งค่า API URL

เปิดไฟล์ `gold-price-display.php` แก้ไขบรรทัด:

```php
$GOLD_API_BASE_URL = 'https://your-api-domain.com';
```

### Shortcodes

| Shortcode | Description |
|-----------|-------------|
| `[gold_price]` | แสดงราคาเต็ม (ทองแท่ง + รูปพรรณ) |
| `[gold_price type="bar"]` | แสดงเฉพาะทองแท่ง |
| `[gold_price type="ornament"]` | แสดงเฉพาะทองรูปพรรณ |
| `[gold_price type="change"]` | แสดงเฉพาะการเปลี่ยนแปลง (inline) |

---

## 📁 Project Structure

```
gold-beer/
├── app.py              # Flask API server
├── scraper.py          # Gold price scraper
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Dashboard UI
├── wordpress-plugin/   # WordPress plugin (ไม่รวมใน git)
│   ├── gold-price-display/
│   │   ├── gold-price-display.php
│   │   ├── style.css
│   │   └── readme.txt
│   └── gold-price-display.zip
└── README.md
```

---

## 🛠️ Development

### รัน Development Mode

```bash
FLASK_DEBUG=true python app.py
```

### ทดสอบ Scraper

```bash
python scraper.py
```

---

## 📞 Contact

**Author:** Pond Dev.

**LINE:** [https://line.me/ti/p/pond_che](https://line.me/ti/p/pond_che)

---

## 📄 License

MIT License
