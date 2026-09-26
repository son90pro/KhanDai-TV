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

def get_real_m3u8(context, match_url):
    """
    Truy cập trực tiếp vào trang xem trận đấu và chặn gói tin mạng (Network Sniffing)
    để tìm đường link .m3u8 thực sự đang được ẩn giấu.
    """
    page = context.new_page()
    found_m3u8 = None

    # Hàm lắng nghe mọi request mạng phát ra từ trang
    def handle_request(request):
        nonlocal found_m3u8
        url_lower = request.url.lower()
        if ".m3u8" in url_lower and not found_m3u8:
            # Loại trừ các file m3u8 quảng cáo nếu có
            if "ads" not in url_lower:
                found_m3u8 = request.url

    page.on("request", handle_request)

    try:
        page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        # Đợi 4 giây để video player load và gửi request lấy file m3u8
        page.wait_for_timeout(4000) 
        
        # Fallback: Nếu không bắt được qua request, thử tìm trong source HTML
        if not found_m3u8:
            content = page.content()
            # Tìm pattern link m3u8 trong chuỗi JSON/JS
            match = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', content)
            if match:
                found_m3u8 = match.group(1).replace('\\', '')
                
    except Exception as e:
        print(f"[!] Bỏ qua do lỗi tải trang {match_url}: {e}")
    finally:
        page.close()

    return found_m3u8

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    raw_matches = []
    working_domain = DOMAINS[0]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768}
        )

        # 1. Lấy danh sách link trận đấu từ Trang Chủ
        for base_url in DOMAINS:
            print(f"[*] Đang cào danh sách trận đấu từ: {base_url}")
            try:
                page = context.new_page()
                page.goto(base_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(2)
                
                extracted = page.evaluate('''() => {
                    const results = [];
                    const seenUrls = new Set();
                    const links = document.querySelectorAll('a[href*="truc-tiep"], a[href*="match"], a[href*="live"]');
                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href) return;
                        const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                        if (seenUrls.has(fullUrl)) return;
                        seenUrls.add(fullUrl);
                        results.push({ url: fullUrl, text: link.innerText || '' });
                    });
                    return results;
                }''')
                page.close()

                if extracted:
                    raw_matches = extracted
                    working_domain = base_url
                    print(f"[+] Tìm thấy {len(raw_matches)} link có khả năng phát live.")
                    break
            except Exception as e:
                print(f"[!] Tên miền {base_url} lỗi: {e}")

        parsed_items = []
        seen_keys = set()

        # 2. Xử lý và Bóc tách M3U8 thật cho từng trận
        for item in raw_matches:
            url = item['url']
            card_text = item['text']
            
            # Xử lý thông tin cơ bản
            blv = parse_blv(url) or parse_blv(card_text)
            blv_name = f" ({blv})" if blv else " (Khán Đài TV)"
            
            teams = "Trận đấu Trực Tiếp"
            vs_m = re.search(r'([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)\s+vs\s+([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)', card_text, re.I)
            if vs_m:
                teams = f"{vs_m.group(1).strip().title()} vs {vs_m.group(2).strip().title()}"
            else:
                slug_m = re.search(r'/truc-tiep/(.*?)(?:-vs-|-luc|-ngay|$)', url)
                if slug_m:
                    teams = slug_m.group(1).replace('-', ' ').title()

            match_time = "20:00"
            time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[h:](\d{2})\b', card_text + " " + url)
            if time_m: match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

            dedup_key = f"{teams}_{match_time}"
            if dedup_key in seen_keys: continue
            
            # CHỈ LẤY LINK M3U8 NẾU TRẬN ĐẤU ĐANG/SẮP DIỄN RA
            print(f"[*] Đang bắt luồng video thật cho: {teams}...")
            real_m3u8 = get_real_m3u8(context, url)
            
            if not real_m3u8:
                print(f"  -> Chưa có luồng (có thể trận đấu chưa diễn ra)")
                continue # Bỏ qua kênh nếu chưa có m3u8 thật để tránh rác m3u

            seen_keys.add(dedup_key)
            status_dot = "🟢 "
            sport_icon = "⚽"
            logo = get_match_logo(teams)
            full_title = f"{status_dot}{match_time} {today_str} {sport_icon} {teams}{blv_name} [FHD] [hls]"

            parsed_items.append({
                "title": full_title,
                "logo": logo,
                "stream_url": real_m3u8,
                "match_url": url
            })

        browser.close()

    # 3. GHI FILE PLAYLIST.M3U (Bổ sung Header trực tiếp vào URL cho TiviMate)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            
            # Cú pháp vàng cho TiviMate/OTT Navigator: Ép Referer trực tiếp vào đuôi stream
            stream_with_headers = f"{item['stream_url']}|Referer={working_domain}/&User-Agent={USER_AGENT}"
            f.write(f'{stream_with_headers}\n\n')

    print(f"[*] Hoàn tất! Đã xuất {len(parsed_items)} kênh đang live thật sự vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
