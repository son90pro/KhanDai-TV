import time
import re
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH HỆ THỐNG ---
DOMAINS = [
    "https://khandai1.link/",
    "https://khandai2.link/",
    "https://khandai3.link/",
    "https://khandaitv.com/"
]
REFERER_URL = "https://khandai1.link/"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
DEFAULT_LOGO = "https://flagcdn.com/w320/un.png"
DEFAULT_BLV = "Khán Đài TV"

KNOWN_BLVS = [
    "PHÁO THỦ", "ENZO", "KỀN KỀN", "CHIM NHỎ", "LÝ LINH LỰC", 
    "LÝ LÊN LỬA", "NHÀ ĐÀI", "GẤU BÉO", "RỒNG ĐEN", "KHÁN ĐÀI"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "thailand": "th", "thái lan": "th",
    "indonesia": "id", "malaysia": "my", "philippines": "ph", "singapore": "sg",
    "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "china": "cn", "trung quốc": "cn", "england": "gb-eng", "anh": "gb-eng",
    "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "portugal": "pt",
    "bồ đào nha": "pt", "netherlands": "nl", "hà lan": "nl", "brazil": "br",
    "argentina": "ar", "usa": "us", "mỹ": "us", "ethiopia": "et", "senegal": "sn",
    "finland": "fi", "belarus": "by", "moldova": "md", "faroe islands": "fo",
    "saudi arabia": "sa", "iraq": "iq", "scotland": "gb-sct", "switzerland": "ch",
    "slovenia": "si", "north macedonia": "mk"
}

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[\r\n\t]+', ' ', str(text))
    return re.sub(r'\s+', ' ', clean).strip()

def is_junk(text: str) -> bool:
    if not text:
        return True
    junk_words = ["nhà cái", "fb88", "cược", "quảng cáo", "gmail", "bảng xếp hạng", "tin tức", "khuyến mãi", "nạp tiền"]
    t = text.lower()
    return any(w in t for w in junk_words)

def clean_teams(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'vào lúc\s*\d{1,2}[:h]\d{2}', '', text, flags=re.I)
    text = re.sub(r',?\s*ngày\s*\d{1,2}[/-]\d{1,2}', '', text, flags=re.I)
    text = re.sub(r'\b\d{1,2}[:h]\d{2}\b', '', text)
    text = re.sub(r'\b\d{1,2}[/-]\d{1,2}\b', '', text)
    for pat in [r'trực tiếp', r'phát trực tiếp', r'xem trực tiếp', r'chủ nhà', r'đội khách']:
        text = re.sub(pat, '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()

def get_flag_logo(teams_str: str, raw_logo: str = "") -> str:
    if raw_logo and raw_logo.startswith("http") and not any(x in raw_logo for x in ["fire.svg", "default", "logo.png"]):
        return raw_logo
    t_lower = teams_str.lower()
    for country, code in COUNTRY_FLAGS.items():
        if country in t_lower:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def extract_blv(text: str) -> str:
    if not text:
        return DEFAULT_BLV
    t_up = text.upper()
    for b in KNOWN_BLVS:
        if b in t_up and b != "NHÀ ĐÀI":
            return b.title()
    m = re.search(r'(?:BLV|CASTER)\s*([A-ZÀ-Ỹ0-9\s]{2,15})', t_up)
    return m.group(1).strip().title() if m else DEFAULT_BLV

def bypass_cloudflare(page):
    """Tự động chờ Cloudflare verify xong"""
    for _ in range(10):
        content = page.content().lower()
        title = page.title().lower()
        if "just a moment" in title or "cloudflare" in title or "checking your browser" in content:
            print("  [!] Cloudflare phát hiện, đang đợi 3s...")
            time.sleep(3)
        else:
            break

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    parsed_items = []

    print("[*] Bắt đầu cào dữ liệu Khán Đài TV...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )

        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        
        target_page = None
        working_domain = ""

        # 1. Tìm Domain hoạt động
        for domain in DOMAINS:
            print(f"[*] Thử kết nối: {domain}")
            try:
                page = context.new_page()
                page.goto(domain, timeout=25000, wait_until="domcontentloaded")
                bypass_cloudflare(page)
                
                # Kiểm tra xem có lấy được nội dung thật không
                if "Khán Đài" in page.title() or len(page.content()) > 5000:
                    print(f"[✔] Kết nối thành công domain: {domain}")
                    target_page = page
                    working_domain = domain
                    break
                else:
                    page.close()
            except Exception as e:
                print(f"[!] Lỗi kết nối {domain}: {e}")

        if not target_page:
            print("[❌] TẤT CẢ DOMAIN ĐỀU BỊ CHẶN HOẶC LỖI!")
            browser.close()
            return

        # 2. Cuộn trang để tải dữ liệu Javascript
        target_page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(2)

        # 3. Thu thập thẻ chứa liên kết trận đấu
        raw_matches = target_page.evaluate('''() => {
            const matches = [];
            const links = document.querySelectorAll('a');
            links.forEach(a => {
                const href = a.getAttribute('href') || '';
                const text = (a.innerText || '').trim();
                const parentText = a.parentElement ? (a.parentElement.innerText || '') : '';
                
                // Lọc thẻ chứa liên kết xem trực tiếp
                if (href && (href.includes('truc-tiep') || href.includes('xem') || href.includes('-vs-') || href.length > 15)) {
                    if (text.length > 3 || parentText.length > 5) {
                        let img = a.querySelector('img') || (a.parentElement ? a.parentElement.querySelector('img') : null);
                        let logo = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                        matches.append ? matches.push({href, text: parentText || text, logo}) : matches.push({href, text: parentText || text, logo});
                    }
                }
            });
            return matches;
        }''')

        print(f"[+] Tìm thấy {len(raw_matches)} thẻ thông tin sơ bộ.")

        # 4. Bóc tách chi tiết từng trận
        visited_urls = set()
        for match in raw_matches:
            href = match['href']
            full_url = href if href.startswith('http') else working_domain.rstrip('/') + '/' + href.lstrip('/')
            
            if full_url in visited_urls or is_junk(match['text']):
                continue
            visited_urls.add(full_url)

            card_text = sanitize_text(match['text'])
            teams_title = clean_teams(card_text)
            
            if len(teams_title) < 3 or is_junk(teams_title):
                continue

            # Bóc tách Giờ / Ngày / BLV
            time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', card_text)
            extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}" if time_m else "20:00"

            date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', card_text)
            extracted_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}" if date_m else today_str

            blv_name = extract_blv(card_text)
            logo_url = get_flag_logo(teams_title, match['logo'])

            # Bắt luồng m3u8 từ trang chi tiết
            m3u8_url = ""
            try:
                detail_page = context.new_page()
                
                def capture_req(req):
                    nonlocal m3u8_url
                    if ".m3u8" in req.url.lower() and not m3u8_url:
                        m3u8_url = req.url

                detail_page.on("request", capture_req)
                detail_page.goto(full_url, timeout=15000, wait_until="domcontentloaded")
                time.sleep(2.5)
                detail_page.close()
            except Exception:
                pass

            # Nếu không bắt được m3u8 động, dùng link trực tiếp để không bị bỏ sót trận
            stream_final = m3u8_url if m3u8_url else full_url

            # Cấu trúc tiêu chuẩn khớp ảnh mẫu: 20:00 29/09 ⚽ Ethiopia vs Senegal (Enzo) [hls]
            full_title = f"{extracted_time} {extracted_date} ⚽ {teams_title} ({blv_name}) [hls]"

            try:
                d, m = map(int, extracted_date.split('/'))
                h, mins = map(int, extracted_time.split(':'))
                dt_obj = datetime(datetime.now(vn_tz).year, m, d, h, mins, tzinfo=vn_tz)
            except Exception:
                dt_obj = datetime(2099, 1, 1, tzinfo=vn_tz)

            parsed_items.append({
                "title": full_title,
                "logo": logo_url,
                "stream_url": stream_final,
                "dt": dt_obj
            })

        browser.close()

    # 5. Sắp xếp theo giờ và Xuất file playlist.m3u
    parsed_items.sort(key=lambda x: x['dt'])
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        count = 0
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={REFERER_URL}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'{item["stream_url"]}\n\n')
            count += 1

    print(f"\n[✔] HOÀN TẤT! Đã xuất {count} kênh vào file '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    run_scraper()
    
