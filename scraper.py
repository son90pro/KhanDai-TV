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
    "LEE SIN", "TÂY", "TIỂU MÂY", "CHIM NHỎ", "KỀN KỀN", "ENZO", 
    "PHÁO THỦ", "LÝ LINH LỰC", "LÝ LÊN LỬA", "NHÀ ĐÀI", "GẤU BÉO", "RỒNG ĐEN"
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
    "slovenia": "si", "north macedonia": "mk", "czech republic": "cz", "croatia": "hr",
    "slovakia": "sk", "kazakhstan": "kz", "timor-leste": "tl", "cambodia": "kh",
    "uzbekistan": "uz", "hong kong": "hk", "brunei": "bn", "malta": "mt",
    "bahrain": "bh", "yemen": "ye", "united arab emirates": "ae", "qatar": "qa"
}

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[\r\n\t]+', ' ', str(text))
    return re.sub(r'\s+', ' ', clean).strip()

def is_junk_or_ad(text: str) -> bool:
    if not text:
        return True
    
    # Chặn chữ Thái Lan
    if re.search(r'[\u0e00-\u0e7f]', text):
        return True
        
    junk_keywords = [
        "nhà cái", "fb88", "cược", "quảng cáo", "gmail", "bảng xếp hạng", 
        "tin tức", "khuyến mãi", "nạp tiền", "thắng", "kèo", "trang chủ", 
        "liên hệ", "uy tín", "tỉ lệ", "đăng ký", "đăng nhập", "chủ nhà", "đội khách"
    ]
    t_lower = text.lower()
    return any(k in t_lower for k in junk_keywords)

def clean_team_names(text: str) -> str:
    if not text:
        return ""
    
    text = re.sub(r'vào lúc\s*\d{1,2}[:h]\d{2}', '', text, flags=re.I)
    text = re.sub(r',?\s*ngày\s*\d{1,2}[/-]\d{1,2}', '', text, flags=re.I)
    text = re.sub(r'\b\d{1,2}[:h]\d{2}\b', '', text)
    text = re.sub(r'\b\d{1,2}[/-]\d{1,2}\b', '', text)
    
    for pat in [r'trực tiếp', r'phát trực tiếp', r'xem trực tiếp', r'xem bóng đá']:
        text = re.sub(pat, '', text, flags=re.I)
        
    for blv in KNOWN_BLVS:
        text = re.sub(rf'\(?{blv}\)?', '', text, flags=re.I)
        
    return re.sub(r'\s+', ' ', text).strip()

def get_best_logo(teams_str: str, raw_logo: str = "") -> str:
    if raw_logo and raw_logo.startswith("http") and not any(x in raw_logo for x in ["default", "logo.png", "fire.svg", "banner"]):
        return raw_logo
        
    t_lower = teams_str.lower()
    for country, code in COUNTRY_FLAGS.items():
        if country in t_lower:
            return f"https://flagcdn.com/w320/{code}.png"
            
    return DEFAULT_LOGO

def extract_blv_name(text: str) -> str:
    if not text:
        return DEFAULT_BLV
    t_upper = text.upper()
    for b in KNOWN_BLVS:
        if b in t_upper and b != "NHÀ ĐÀI":
            return b.title()
    m = re.search(r'(?:BLV|CASTER|\()([A-ZÀ-Ỹ0-9\s]{2,15})(?:\)|$)', t_upper)
    if m:
        candidate = m.group(1).strip()
        if not is_junk_or_ad(candidate):
            return candidate.title()
    return DEFAULT_BLV

def bypass_cloudflare(page):
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

        for domain in DOMAINS:
            print(f"[*] Thử kết nối: {domain}")
            try:
                page = context.new_page()
                page.goto(domain, timeout=30000, wait_until="domcontentloaded")
                bypass_cloudflare(page)
                
                if "Khán Đài" in page.title() or len(page.content()) > 3000:
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

        # Cuộn trang và chờ render JavaScript
        target_page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(3)

        # Sửa lỗi JavaScript .strip() -> .trim() và quét tất cả thẻ liên kết
        raw_matches = target_page.evaluate('''() => {
            const results = [];
            const links = document.querySelectorAll('a');
            
            links.forEach(a => {
                const href = a.getAttribute('href') || '';
                const text = (a.innerText || '').trim();
                
                if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
                if (text.length < 5) return;

                let img = a.querySelector('img');
                let logo = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';

                results.push({
                    href: href,
                    text: text,
                    logo: logo
                });
            });
            return results;
        }''')

        print(f"[+] Thu thập được {len(raw_matches)} liên kết thô.")

        visited_urls = set()
        for match in raw_matches:
            card_text = sanitize_text(match['text'])
            
            if is_junk_or_ad(card_text):
                continue

            href = match['href']
            full_url = href if href.startswith('http') else working_domain.rstrip('/') + '/' + href.lstrip('/')
            
            if full_url in visited_urls:
                continue

            # Lấy thông tin Giờ & Ngày
            time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', card_text)
            extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}" if time_m else "20:00"

            date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', card_text)
            extracted_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}" if date_m else today_str

            # Làm sạch tên đội và hỗ trợ các ký tự phân cách (vs, -, –)
            teams_title = clean_team_names(card_text)
            
            # Tìm cặp đấu A vs B hoặc A - B
            vs_match = re.search(r'([A-Za-zÀ-ỹ0-9\s\.]{2,25})\s*(?:vs|VS|-|–)\s*([A-Za-zÀ-ỹ0-9\s\.]{2,25})', card_text)
            if vs_match:
                teams_title = f"{vs_match.group(1).strip()} vs {vs_match.group(2).strip()}"
            elif len(teams_title) < 5:
                continue

            visited_urls.add(full_url)

            blv_name = extract_blv_name(card_text)
            logo_url = get_best_logo(teams_title, match['logo'])

            # Bắt luồng m3u8 từ trang chi tiết (có timeout ngắn để tránh treo script)
            m3u8_url = ""
            try:
                detail_page = context.new_page()
                def capture_req(req):
                    nonlocal m3u8_url
                    if ".m3u8" in req.url.lower() and not m3u8_url:
                        m3u8_url = req.url

                detail_page.on("request", capture_req)
                detail_page.goto(full_url, timeout=8000, wait_until="domcontentloaded")
                time.sleep(1.5)
                detail_page.close()
            except Exception:
                pass

            stream_final = m3u8_url if m3u8_url else full_url

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

    print(f"\n[✔] HOÀN TẤT! Đã tạo thành công {count} trận đấu vào file '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    run_scraper()
    
