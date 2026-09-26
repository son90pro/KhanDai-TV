import time
import re
import base64
import requests
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
DEFAULT_FLAG = "https://flagcdn.com/w320/un.png"

KNOWN_BLVS = [
    "Chim Nhỏ", "Tày", "Tay", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây", "Enzo",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka"
]

# Danh sách Cờ Quốc Gia chuẩn FlagCDN (Đã bổ sung đầy đủ)
COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "slovenia": "si", "scotland": "gb-sct", "finland": "fi", "phần lan": "fi",
    "kuwait": "kw", "iraq": "iq", "bulgaria": "bg", "luxembourg": "lu",
    "indonesia": "id", "malaysia": "my", "singapore": "sg", "japan": "jp", "nhật bản": "jp",
    "south korea": "kr", "hàn quốc": "kr", "china": "cn", "trung quốc": "cn",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es",
    "france": "fr", "pháp": "fr", "germany": "de", "đức": "de", "italy": "it", "ý": "it", "usa": "us", "mỹ": "us"
}

# Logo riêng cho các CLB Thể Thao / Bóng Chuyền
SPECIAL_LOGOS = {
    "imoco": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Imoco_Volley_logo.png/220px-Imoco_Volley_logo.png",
    "novara": "https://flagcdn.com/w320/it.png"
}

def parse_blv(text: str) -> str:
    if not text: return ""
    text_low = text.lower()
    for b in KNOWN_BLVS:
        b_low = b.lower()
        if b_low in text_low or b_low.replace(' ', '-') in text_low:
            return b
    return ""

def get_match_logo(teams_str: str) -> str:
    t_low = teams_str.lower()
    
    # 1. Kiểm tra logo CLB đặc biệt
    for club, logo_url in SPECIAL_LOGOS.items():
        if club in t_low:
            return logo_url

    # 2. Ưu tiên lấy cờ của ĐỘI 1 (Chủ nhà / Đội bên trái chữ VS)
    parts = re.split(r'\s+vs\s+', t_low, flags=re.IGNORECASE)
    t1 = parts[0] if len(parts) > 0 else t_low

    for country, code in COUNTRY_FLAGS.items():
        if country in t1:
            return f"https://flagcdn.com/w320/{code}.png"

    # 3. Nếu Đội 1 không khớp thì mới quét toàn bộ chuỗi
    for country, code in COUNTRY_FLAGS.items():
        if country in t_low:
            return f"https://flagcdn.com/w320/{code}.png"

    return DEFAULT_FLAG

def parse_card_details(url: str, card_text: str, default_date: str):
    blv = parse_blv(url) or parse_blv(card_text)
    teams = ""

    # Trích xuất tên 2 đội từ URL
    match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream)/([^/?#]+)', url)
    if match_slug:
        slug = match_slug.group(1).lower()
        if '-vs-' in slug:
            parts = slug.split('-vs-')
            left = re.sub(r'^(?:blv|caster|ga)[-_]+', '', parts[0])
            right = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,12}|blv.*).*$', '', parts[1])

            for b in KNOWN_BLVS:
                b_slug = b.lower().replace(' ', '-')
                left = left.replace(f"-{b_slug}", "").replace(f"{b_slug}-", "")
                right = right.replace(f"-{b_slug}", "").replace(f"{b_slug}-", "")

            t1 = " ".join([w.capitalize() for w in left.split('-') if w and not w.isdigit()])
            t2 = " ".join([w.capitalize() for w in right.split('-') if w and not w.isdigit()])

            t1 = t1.replace("Viet Nam", "Việt Nam").replace("Phan Lan", "Phần Lan")
            t2 = t2.replace("Viet Nam", "Việt Nam").replace("Phan Lan", "Phần Lan")

            if t1 and t2:
                teams = f"{t1} vs {t2}"

    if not teams:
        vs_m = re.search(r'([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)\s+vs\s+([A-ZÀ-Ỹa-zà-ỹ0-9\s]+)', card_text, re.I)
        if vs_m:
            teams = f"{vs_m.group(1).strip().title()} vs {vs_m.group(2).strip().title()}"

    if not teams:
        teams = "Trận đấu Trực Tiếp"

    # Trích xuất Thời gian & Ngày thi đấu
    match_time = "19:30"
    time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[h:](\d{2})\b', card_text + " " + url)
    if time_m:
        match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

    match_date = default_date
    date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', card_text + " " + url)
    if date_m:
        match_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}"

    # Biểu tượng môn thể thao
    sport_icon = "⚽"
    if any(k in (teams + card_text).lower() for k in ["imoco", "novara", "bóng chuyền", "volleyball", "volley"]):
        sport_icon = "🏐"
    elif any(k in (teams + card_text).lower() for k in ["bóng rổ", "basketball"]):
        sport_icon = "🏀"

    status_dot = "🟢" if any(k in card_text.lower() for k in ["đang diễn ra", "live", "h1", "h2"]) else "🟡"

    return match_time, match_date, sport_icon, teams, blv, status_dot

def fetch_m3u8_stream(context, match_url: str, base_domain: str) -> str:
    """Bắt luồng video .m3u8 thực sự thông qua bắt gói tin Network & API"""
    m3u8_url = ""
    page = context.new_page()

    def handle_request(request):
        nonlocal m3u8_url
        u = request.url
        if ".m3u8" in u and "blob:" not in u and not m3u8_url:
            m3u8_url = u

    def handle_response(response):
        nonlocal m3u8_url
        if m3u8_url: return
        u = response.url
        if ".m3u8" in u and "blob:" not in u:
            m3u8_url = u
        elif "json" in response.headers.get("content-type", "") or "api" in u:
            try:
                text = response.text()
                m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', text)
                if m and "blob:" not in m[0]:
                    m3u8_url = m[0]
            except:
                pass

    page.on("request", handle_request)
    page.on("response", handle_response)

    try:
        page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(2)

        # Click kích hoạt trình phát video
        page.evaluate('''() => {
            const el = document.querySelector('video') || document.querySelector('.player') || document.querySelector('iframe');
            if (el) el.click();
        }''')
        time.sleep(2)

        if not m3u8_url:
            content = page.content()
            m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', content)
            for u in m:
                if "blob:" not in u:
                    m3u8_url = u
                    break

        if not m3u8_url:
            for frame in page.frames:
                try:
                    c = frame.content()
                    m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', c)
                    for u in m:
                        if "blob:" not in u:
                            m3u8_url = u
                            break
                except:
                    pass
    except Exception as e:
        print(f"[!] Lỗi khi truy cập {match_url}: {e}")
    finally:
        page.close()

    return m3u8_url

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    raw_matches = []
    working_domain = DOMAINS[0]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )

        for base_url in DOMAINS:
            print(f"[*] Đang quét danh sách từ: {base_url}")
            try:
                page = context.new_page()
                page.goto(base_url, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                for _ in range(6):
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(0.3)

                extracted = page.evaluate('''() => {
                    const results = [];
                    const seenUrls = new Set();
                    const links = Array.from(document.querySelectorAll('a[href]'));

                    links.forEach(link => {
                        const href = link.getAttribute('href') || '';
                        if (!href || href === '/' || href.startsWith('#')) return;
                        if (!/(truc-tiep|match|live|room|xem|phong|stream)/i.test(href)) return;

                        const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                        if (seenUrls.has(fullUrl)) return;

                        seenUrls.add(fullUrl);
                        results.push({ url: fullUrl, text: link.innerText || '' });
                    });
                    return results;
                }''')

                page.close()

                if extracted and len(extracted) > 0:
                    raw_matches = extracted
                    working_domain = base_url
                    print(f"[+] Tìm thấy {len(raw_matches)} link trận đấu từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Thất bại tại {base_url}: {e}")

        parsed_items = []
        seen_keys = set()

        print(f"[*] Đang bóc tách thông tin chi tiết và luồng live video...")
        for item in raw_matches:
            url = item['url']
            card_text = item['text']

            match_time, match_date, sport_icon, teams, blv, status_dot = parse_card_details(url, card_text, today_str)

            # Khóa chống trùng lặp: Bao gồm cả Tên trận + BLV (để giữ lại các trận có 2 BLV khác nhau)
            dedup_key = f"{teams}_{blv}_{url}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            blv_suffix = f" ({blv})" if blv else ""
            full_title = f"{status_dot} {match_time} {match_date} {sport_icon} {teams}{blv_suffix} [hls]"
            logo = get_match_logo(teams)

            m3u8_stream_url = fetch_m3u8_stream(context, url, working_domain)

            # CHỈ LẤY CÁC TRẬN CÓ LUỒNG .M3U8 HỢP LỆ ĐỂ ĐẢM BẢO IPTV PHÁT ĐƯỢC 100%
            if m3u8_stream_url and ".m3u8" in m3u8_stream_url:
                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "play_url": m3u8_stream_url
                })
                print(f"[✓] Đã thêm thành công: {full_title}")

        browser.close()

    # Ghi file M3U xuất ra chuẩn định dạng IPTV
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        if not parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{DEFAULT_FLAG}" group-title="Hệ Thống", [!] Đang cập nhật luồng trực tiếp mới\n')
            f.write(f'{working_domain}\n\n')
        else:
            for item in parsed_items:
                play_url = item["play_url"]
                stream_entry = f"{play_url}|User-Agent={USER_AGENT}&Referer={working_domain}/"

                f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
                f.write(f'{stream_entry}\n\n')

    print(f"[*] Đã xuất xong {len(parsed_items)} trận đấu chuẩn mẫu vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
