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
    "france": "fr", "pháp": "fr", "germany": "de", "đức": "de", "italy": "it", "ý": "it", "usa": "us", "mỹ": "us"
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

def get_stream_url(context, match_url, blv_slug, base_url):
    # Cố gắng quét nhanh link trong HTML (Chống kẹt cứng Playwright)
    try:
        page = context.new_page()
        page.goto(match_url, timeout=8000, wait_until="domcontentloaded")
        content = page.content()
        page.close()
        match = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', content)
        if match:
            return match.group(1).replace('\\', '')
    except Exception:
        pass
    
    # NẾU THẤT BẠI (BỊ CHẶN), DÙNG LINK DỰ ĐOÁN CHỨ KHÔNG BỎ QUA TRẬN ĐẤU
    slug = blv_slug if blv_slug else "khandai1"
    return f"https://stream.khandai.link/hls/{slug}hd/playlist.m3u8"

def build_emergency_channels(domain):
    vn_tz = timezone(timedelta(hours=7))
    now_str = datetime.now(vn_tz).strftime("%H:%M %d/%m")
    return [
        {
            "title": f"🟢 {now_str} ⚽ Kênh Khán Đài 1 Dự Phòng [FHD] [hls]",
            "logo": DEFAULT_LOGO,
            "stream_url": f"https://stream.khandai.link/hls/khandai1hd/playlist.m3u8"
        },
        {
            "title": f"🟢 {now_str} ⚽ Kênh Khán Đài 2 Dự Phòng [FHD] [hls]",
            "logo": DEFAULT_LOGO,
            "stream_url": f"https://stream.khandai.link/hls/khandai2hd/playlist.m3u8"
        }
    ]

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    raw_matches = []
    working_domain = DOMAINS[0]
    parsed_items = []
    seen_keys = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(user_agent=USER_AGENT)

            # 1. Cào danh sách từ Trang chủ
            for base_url in DOMAINS:
                try:
                    page = context.new_page()
                    page.goto(base_url, timeout=15000, wait_until="domcontentloaded")
                    time.sleep(3)
                    raw_matches = page.evaluate('''() => {
                        const results = [];
                        const seenUrls = new Set();
                        document.querySelectorAll('a[href*="truc-tiep"], a[href*="match"]').forEach(link => {
                            const href = link.getAttribute('href');
                            if (!href) return;
                            const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                            if (!seenUrls.has(fullUrl)) {
                                seenUrls.add(fullUrl);
                                results.push({ url: fullUrl, text: link.innerText || '' });
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

            # 2. Tạo Playlist
            for item in raw_matches:
                url = item['url']
                card_text = item['text']
                
                blv = parse_blv(url) or parse_blv(card_text)
                blv_slug = to_slug(blv) if blv else ""
                blv_name = f" ({blv})" if blv else " (Khán Đài TV)"
                
                teams = "Trận đấu Trực Tiếp"
                vs_m = re.search(r'([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)\s+vs\s+([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)', card_text, re.I)
                if vs_m:
                    teams = f"{vs_m.group(1).strip().title()} vs {vs_m.group(2).strip().title()}"
                
                match_time = "20:00"
                time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[h:](\d{2})\b', card_text + " " + url)
                if time_m: match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

                dedup_key = f"{teams}_{match_time}"
                if dedup_key in seen_keys: continue
                seen_keys.add(dedup_key)

                stream_url = get_stream_url(context, url, blv_slug, working_domain)
                logo = get_match_logo(teams)
                
                parsed_items.append({
                    "title": f"🟢 {match_time} {today_str} ⚽ {teams}{blv_name} [FHD] [hls]",
                    "logo": logo,
                    "stream_url": stream_url
                })

            browser.close()
            
    except Exception as e:
        print(f"Lỗi hệ thống: {e}")

    # 3. KÍCH HOẠT DỰ PHÒNG NẾU FILE CÓ NGUY CƠ BỊ RỖNG
    if not parsed_items:
        parsed_items = build_emergency_channels(working_domain)

    # 4. ÉP HEADER VÀO M3U CHO TIVIMATE
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            
            # Cú pháp vàng: Nối Referer trực tiếp vào URL
            stream_with_headers = f"{item['stream_url']}|Referer={working_domain}/&User-Agent={USER_AGENT}"
            f.write(f'{stream_with_headers}\n\n')

if __name__ == "__main__":
    run_scraper()
    
