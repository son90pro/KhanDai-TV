import time
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

DOMAINS = [
    "https://khandai1.link",
    "https://khandai.link",
    "https://khandai.tv"
]

OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DEFAULT_LOGO = "https://flagcdn.com/w320/un.png"

KNOWN_BLVS = [
    "Tày", "Lee Sin", "Pháo Thủ", "Enzo", "Kền Kền", "Chim Nhỏ", "Tiểu Mây",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "slovenia": "si", "scotland": "gb-sct", "finland": "fi", "phần lan": "fi",
    "kuwait": "kw", "iraq": "iq", "bulgaria": "bg", "luxembourg": "lu",
    "indonesia": "id", "malaysia": "my", "singapore": "sg", "japan": "jp", "nhật bản": "jp",
    "south korea": "kr", "hàn quốc": "kr", "china": "cn", "trung quốc": "cn",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es",
    "france": "fr", "pháp": "fr", "germany": "de", "đức": "de", "italy": "it", "ý": "it", 
    "usa": "us", "mỹ": "us", "imoco": "it", "novara": "it"
}

def to_slug(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.lower().replace('đ', 'd')
    return re.sub(r'[^a-z0-9]', '', text)

def parse_blv(text: str) -> str:
    if not text: return ""
    text_low = text.lower()
    for b in KNOWN_BLVS:
        if b.lower() in text_low or to_slug(b) in text_low:
            return b
    return ""

def get_match_logo(teams_str: str) -> str:
    t_low = teams_str.lower()
    parts = re.split(r'\s+vs\s+', t_low, flags=re.IGNORECASE)
    t1 = parts[0] if len(parts) > 0 else t_low
    for country, code in COUNTRY_FLAGS.items():
        if country in t1: return f"https://flagcdn.com/w320/{code}.png"
    for country, code in COUNTRY_FLAGS.items():
        if country in t_low: return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def parse_match_details(card_text: str, match_url: str, vn_tz):
    # 1. Tách Giờ & Ngày ra trước để tránh dính số ngày (như 09) vào tên đội
    time_match = re.search(r'\b([0-2]?\d)[h:](\d{2})\b', card_text)
    match_time = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "20:00"

    date_match = re.search(r'\b([0-3]?\d/[0-1]?\d)\b', card_text)
    match_date = date_match.group(1) if date_match else datetime.now(vn_tz).strftime("%d/%m")

    # Loại bỏ Giờ và Ngày khỏi chuỗi xử lý tên
    clean_text = card_text
    if time_match: clean_text = clean_text.replace(time_match.group(0), "")
    if date_match: clean_text = clean_text.replace(date_match.group(0), "")

    # 2. Tìm BLV
    blv = parse_blv(clean_text) or parse_blv(match_url)

    # 3. Trích xuất tên Đội bóng (Kết hợp Text & Slug URL)
    teams = ""
    vs_match = re.search(r'([A-ZÀ-Ỹa-zà-ỹ\s]{2,})\s+(?:vs|VS|-)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,})', clean_text)
    if vs_match:
        t1 = vs_match.group(1).strip().title()
        t2 = vs_match.group(2).strip().title()
        teams = f"{t1} vs {t2}"
    else:
        # Lấy từ URL slug nếu card text bị mờ/thiếu
        slug = match_url.split('/')[-1]
        slug = re.sub(r'(-\d{3,4}.*|\?.*)$', '', slug)
        slug = re.sub(r'^(truc-tiep-|live-|watch-)', '', slug)
        if '-vs-' in slug:
            parts = slug.split('-vs-')
            teams = f"{parts[0].replace('-', ' ').title()} vs {parts[1].replace('-', ' ').title()}"
        elif slug:
            teams = slug.replace('-', ' ').title()

    if not teams or len(teams) < 3 or teams.lower() in ['truc tiep', 'live']:
        teams = "Trận đấu Trực Tiếp"

    return match_time, match_date, teams, blv

def capture_m3u8(page, match_url):
    """ Mở trang trận đấu và bắt chính xác đường dẫn .m3u8 đang phát """
    found_m3u8 = None

    def handle_request(request):
        nonlocal found_m3u8
        url = request.url
        if ".m3u8" in url.lower() and not found_m3u8:
            if "advertisement" not in url.lower() and "qc" not in url.lower():
                found_m3u8 = url

    page.on("request", handle_request)
    try:
        page.goto(match_url, timeout=12000, wait_until="domcontentloaded")
        # Đợi tối đa 3.5 giây cho video player tải luồng m3u8
        for _ in range(7):
            if found_m3u8: break
            page.wait_for_timeout(500)
    except Exception as e:
        print(f"[!] Bỏ qua {match_url}: {e}")

    return found_m3u8

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    raw_matches = []
    working_domain = DOMAINS[0]
    parsed_items = []
    seen_keys = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(user_agent=USER_AGENT)

        # Chặn ảnh/font/css để tăng tốc độ tải trang gấp 5 lần
        context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}", lambda route: route.abort())

        # 1. Lấy danh sách trận đấu
        for base_url in DOMAINS:
            try:
                page = context.new_page()
                page.goto(base_url, timeout=15000, wait_until="domcontentloaded")
                time.sleep(2)
                raw_matches = page.evaluate('''() => {
                    const results = [];
                    const seen = new Set();
                    document.querySelectorAll('a[href*="truc-tiep"], a[href*="match"]').forEach(a => {
                        const href = a.getAttribute('href');
                        if (!href) return;
                        const full = href.startsWith('http') ? href : window.location.origin + href;
                        if (!seen.has(full)) {
                            seen.add(full);
                            results.push({ url: full, text: a.innerText || '' });
                        }
                    });
                    return results;
                }''')
                page.close()
                if raw_matches:
                    working_domain = base_url
                    break
            except Exception:
                pass

        # 2. Xử lý chi tiết và Bắt luồng m3u8
        worker_page = context.new_page()
        for item in raw_matches:
            url = item['url']
            card_text = item['text']

            match_time, match_date, teams, blv = parse_match_details(card_text, url, vn_tz)
            blv_name = f" ({blv})" if blv else " (Khán Đài TV)"

            dedup_key = f"{teams}_{match_time}"
            if dedup_key in seen_keys: continue

            # Bắt link video m3u8 thực tế
            real_m3u8 = capture_m3u8(worker_page, url)
            if not real_m3u8:
                continue # Nếu trận chưa phát/không có luồng thật thì bỏ qua

            seen_keys.add(dedup_key)
            logo = get_match_logo(teams)
            full_title = f"🟢 {match_time} {match_date} ⚽ {teams}{blv_name} [FHD] [hls]"

            parsed_items.append({
                "title": full_title,
                "logo": logo,
                "stream_url": real_m3u8
            })

        worker_page.close()
        browser.close()

    # 3. Ghi file M3U chuẩn cho TiviMate
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            # Nối trực tiếp Header Referer vào URL để TiviMate không bị chặn 403
            f.write(f"{item['stream_url']}|Referer={working_domain}/&User-Agent={USER_AGENT}\n\n")

    print(f"[*] Hoàn tất! Đã cập nhật {len(parsed_items)} trận đấu live.")

if __name__ == "__main__":
    run_scraper()
    
