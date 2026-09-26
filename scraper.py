import time
import re
import base64
import json
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
    return DEFAULT_FLAG

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

    status_dot = "🟢" if any(k in card_text.lower() for k in ["đang diễn ra", "live", "h1", "h2"]) else "🟡"
    return match_time, match_date, sport_icon, teams, blv, status_dot

def fetch_m3u8_stream(context, match_url: str, base_domain: str) -> str:
    """Trích xuất chính xác luồng .m3u8 trực tiếp từ trình phát"""
    m3u8_url = ""
    page = context.new_page()

    def handle_route(route):
        nonlocal m3u8_url
        req_url = route.request.url
        if ".m3u8" in req_url and "blob:" not in req_url and not m3u8_url:
            m3u8_url = req_url
        route.continue_()

    page.route("**/*", handle_route)

    try:
        page.goto(match_url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

        # 1. Kích hoạt phát video trên trang web
        page.evaluate('''() => {
            const v = document.querySelector('video');
            if (v) { v.muted = true; v.play().catch(()=>{}); }
            const btns = Array.from(document.querySelectorAll('button, div, a'));
            btns.forEach(b => {
                if (b.innerText && (b.innerText.includes('Play') || b.innerText.includes('Xem'))) {
                    try { b.click(); } catch(e){}
                }
            });
        }''')
        page.wait_for_timeout(2000)

        # 2. Truy vấn trực tiếp biến cấu hình Player trong JavaScript (JWPlayer, Clappr, Hls.js)
        if not m3u8_url:
            m3u8_from_js = page.evaluate('''() => {
                let found = '';
                try {
                    if (window.jwplayer && typeof window.jwplayer === 'function') {
                        const playlist = window.jwplayer().getPlaylist();
                        if (playlist && playlist[0] && playlist[0].file) return playlist[0].file;
                    }
                } catch(e){}
                try {
                    if (window.player && window.player.src) return window.player.src;
                } catch(e){}
                
                // Lấy từ thẻ video src
                const videos = Array.from(document.querySelectorAll('video'));
                for (let v of videos) {
                    if (v.src && v.src.includes('.m3u8')) return v.src;
                    const sources = Array.from(v.querySelectorAll('source'));
                    for (let s of sources) {
                        if (s.src && s.src.includes('.m3u8')) return s.src;
                    }
                }
                return '';
            }''')
            if m3u8_from_js and "blob:" not in m3u8_from_js:
                m3u8_url = m3u8_from_js

        # 3. Quét kiểm tra tất cả các khung nhúng (Iframes)
        if not m3u8_url:
            for frame in page.frames:
                try:
                    frame_url = frame.evaluate('''() => {
                        const v = document.querySelector('video');
                        if (v && v.src && v.src.includes('.m3u8')) return v.src;
                        const s = document.querySelector('source');
                        if (s && s.src && s.src.includes('.m3u8')) return s.src;
                        return '';
                    }''')
                    if frame_url and "blob:" not in frame_url:
                        m3u8_url = frame_url
                        break
                except:
                    pass

        # 4. Quét regex nén HTML & Base64
        if not m3u8_url:
            html = page.content()
            m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
            if m:
                for match_item in m:
                    if "blob:" not in match_item:
                        m3u8_url = match_item
                        break

    except Exception as e:
        print(f"[!] Lỗi truy cập link {match_url}: {e}")
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
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security"
            ]
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
                    print(f"[+] Đã tìm thấy {len(raw_matches)} trận đấu từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Lỗi kết nối {base_url}: {e}")

        parsed_items = []
        seen_keys = set()

        print(f"[*] Đang bóc tách đường dẫn trực tiếp (.m3u8)...")
        for item in raw_matches:
            url = item['url']
            card_text = item['text']

            match_time, match_date, sport_icon, teams, blv, status_dot = parse_card_details(url, card_text, today_str)

            dedup_key = f"{teams}_{blv}_{url}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            blv_suffix = f" ({blv})" if blv else ""
            full_title = f"{status_dot} {match_time} {match_date} {sport_icon} {teams}{blv_suffix} [hls]"
            logo = get_match_logo(teams)

            m3u8_stream_url = fetch_m3u8_stream(context, url, working_domain)

            # CHỈ THÊM VÀO PLAYLIST NẾU LẤY ĐƯỢC LINK LUỒNG .M3U8 CHUẨN
            if m3u8_stream_url and ".m3u8" in m3u8_stream_url:
                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "play_url": m3u8_stream_url
                })
                print(f"[✓] Thành công lấy stream: {full_title}")
            else:
                print(f"[X] Bỏ qua (Chưa có luồng live m3u8): {teams}{blv_suffix}")

        browser.close()

    # Ghi file M3U chuẩn định dạng quốc tế IPTV
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        if not parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{DEFAULT_FLAG}" group-title="Hệ Thống", [!] Đang cập nhật luồng phát mới\n')
            f.write(f'{working_domain}\n\n')
        else:
            for item in parsed_items:
                play_url = item["play_url"]
                headers_json = json.dumps({"User-Agent": USER_AGENT, "Referer": f"{working_domain}/"})

                f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
                f.write(f'#EXTHTTP:{headers_json}\n')
                # Giữ link URL hoàn toàn sạch sẽ, không gắn thêm ký tự pipe |
                f.write(f'{play_url}\n\n')

    print(f"[*] Hoàn tất! Đã xuất {len(parsed_items)} kênh phát trực tiếp vào file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
