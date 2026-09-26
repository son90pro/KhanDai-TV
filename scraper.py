import time
import re
import unicodedata
import json
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

# Bảng ánh xạ Server CDN trực tiếp theo từng BLV
CASTER_STREAM_MAP = {
    "tay": "https://stream.khandai.link/hls/tayhd/playlist.m3u8",
    "leesin": "https://stream.khandai.link/hls/leesinhd/playlist.m3u8",
    "phaothu": "https://stream.khandai.link/hls/phaothuhd/playlist.m3u8",
    "enzo": "https://stream.khandai.link/hls/enzohd/playlist.m3u8",
    "kenken": "https://stream.khandai.link/hls/kenkenhd/playlist.m3u8",
    "chimnho": "https://stream.khandai.link/hls/chimnhohd/playlist.m3u8",
    "tieumay": "https://stream.khandai.link/hls/tieumayhd/playlist.m3u8",
    "kaka": "https://stream.khandai.link/hls/kakahd/playlist.m3u8",
    "giga": "https://stream.khandai.link/hls/gigahd/playlist.m3u8",
    "sutu": "https://stream.khandai.link/hls/sutuhd/playlist.m3u8",
    "voicon": "https://stream.khandai.link/hls/voiconhd/playlist.m3u8",
    "garung": "https://stream.khandai.link/hls/garunghd/playlist.m3u8",
    "haccao": "https://stream.khandai.link/hls/haccaohd/playlist.m3u8",
    "laodai": "https://stream.khandai.link/hls/laodaihd/playlist.m3u8",
    "taoquan": "https://stream.khandai.link/hls/taoquanhd/playlist.m3u8",
    "bapcay": "https://stream.khandai.link/hls/bapcayhd/playlist.m3u8",
    "rongvang": "https://stream.khandai.link/hls/rongvanghd/playlist.m3u8",
    "cumeo": "https://stream.khandai.link/hls/cumeohd/playlist.m3u8",
    "socnau": "https://stream.khandai.link/hls/socnauhd/playlist.m3u8",
    "khivang": "https://stream.khandai.link/hls/khivanghd/playlist.m3u8",
    "cachep": "https://stream.khandai.link/hls/cachephd/playlist.m3u8",
    "trauchien": "https://stream.khandai.link/hls/trauchienhd/playlist.m3u8",
    "denmo": "https://stream.khandai.link/hls/denmohd/playlist.m3u8",
    "khampa": "https://stream.khandai.link/hls/khampahd/playlist.m3u8",
    "tensat": "https://stream.khandai.link/hls/tensathd/playlist.m3u8",
    "batman": "https://stream.khandai.link/hls/batmanhd/playlist.m3u8",
    "spider": "https://stream.khandai.link/hls/spiderhd/playlist.m3u8",
    "suka": "https://stream.khandai.link/hls/sukahd/playlist.m3u8"
}

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

SPECIAL_LOGOS = {
    "imoco": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Imoco_Volley_logo.png/220px-Imoco_Volley_logo.png",
    "novara": "https://flagcdn.com/w320/it.png"
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
        b_low = b.lower()
        if b_low in text_low or to_slug(b) in text_low:
            return b
    return ""

def get_match_logo(teams_str: str) -> str:
    t_low = teams_str.lower()
    for club, logo_url in SPECIAL_LOGOS.items():
        if club in t_low:
            return logo_url
    parts = re.split(r'\s+vs\s+', t_low, flags=re.IGNORECASE)
    t1 = parts[0] if len(parts) > 0 else t_low
    for country, code in COUNTRY_FLAGS.items():
        if country in t1:
            return f"https://flagcdn.com/w320/{code}.png"
    for country, code in COUNTRY_FLAGS.items():
        if country in t_low:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def parse_card_details(url: str, card_text: str, default_date: str):
    blv = parse_blv(url) or parse_blv(card_text)
    teams = ""
    match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream)/([^/?#]+)', url)
    if match_slug:
        slug = match_slug.group(1).lower()
        if '-vs-' in slug:
            parts = slug.split('-vs-')
            left = re.sub(r'^(?:blv|caster|ga)[-_]+', '', parts[0])
            right = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,12}|blv.*).*$', '', parts[1])
            for b in KNOWN_BLVS:
                b_slug = to_slug(b)
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

    match_time = "19:30"
    time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[h:](\d{2})\b', card_text + " " + url)
    if time_m:
        match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

    match_date = default_date
    date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', card_text + " " + url)
    if date_m:
        match_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}"

    sport_icon = "⚽"
    if any(k in (teams + card_text).lower() for k in ["imoco", "novara", "bóng chuyền", "volleyball", "volley"]):
        sport_icon = "🏐"
    elif any(k in (teams + card_text).lower() for k in ["bóng rổ", "basketball"]):
        sport_icon = "🏀"

    status_dot = "🟢 " if any(k in card_text.lower() for k in ["đang diễn ra", "live", "h1", "h2"]) else "🟡 "
    return match_time, match_date, sport_icon, teams, blv, status_dot

def build_emergency_channels():
    vn_tz = timezone(timedelta(hours=7))
    now_str = datetime.now(vn_tz).strftime("%H:%M %d/%m")
    items = []
    for blv in KNOWN_BLVS:
        slug = to_slug(blv)
        stream_url = CASTER_STREAM_MAP.get(slug, f"https://stream.khandai.link/hls/{slug}hd/playlist.m3u8")
        title = f"🟢 {now_str} ⚽ Trực Tiếp ({blv}) [FHD] [hls]"
        items.append({
            "title": title,
            "logo": DEFAULT_LOGO,
            "stream_url": stream_url,
            "match_url": f"emergency-{slug}"
        })
    return items

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
            print(f"[*] Đang cào danh sách trận đấu từ: {base_url}")
            try:
                page = context.new_page()
                page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2.5)

                for _ in range(4):
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
                    print(f"[+] Lấy thành công {len(raw_matches)} trận từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Lỗi kết nối {base_url}: {e}")

        parsed_items = []
        seen_keys = set()

        if raw_matches:
            for item in raw_matches:
                url = item['url']
                card_text = item['text']

                match_time, match_date, sport_icon, teams, blv, status_dot = parse_card_details(url, card_text, today_str)

                dedup_key = f"{teams}_{blv}_{url}"
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                blv_name = blv if blv else "Khán Đài TV"
                blv_slug = to_slug(blv_name)
                
                # Ánh xạ link luồng trực tiếp theo tên BLV
                stream_url = CASTER_STREAM_MAP.get(
                    blv_slug, 
                    f"https://stream.khandai.link/hls/{blv_slug}hd/playlist.m3u8"
                )

                blv_suffix = f" ({blv_name})"
                full_title = f"{status_dot}{match_time} {match_date} {sport_icon} {teams}{blv_suffix} [FHD] [hls]"
                logo = get_match_logo(teams)

                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "stream_url": stream_url,
                    "match_url": url
                })

        browser.close()

    # NẾU KHÔNG CÀO ĐƯỢC TRẬN NÀO -> TỰ ĐỘNG BẬT KÊNH KHẨN CẤP ĐỂ TIVIMATE KHÔNG BAO GIỜ BỊ TRỐNG
    if not parsed_items:
        print("[!] Kích hoạt danh sách kênh khẩn cấp khôi phục IPTV!")
        parsed_items = build_emergency_channels()

    # Ghi file M3U chuẩn 100% TiviMate / OTT Navigator
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        seen_urls = set()
        for item in parsed_items:
            if item["match_url"] in seen_urls:
                continue
            seen_urls.add(item["match_url"])

            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'{item["stream_url"]}\n\n')

    print(f"[*] Hoàn tất! Đã xuất {len(parsed_items)} kênh vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
