import time
import re
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH HỆ THỐNG ---
WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
BASE_URL = "https://khandai1.link"
OUTPUT_FILE = "khandai.m3u"
GROUP_NAME = "Khán Đài TV"

# Từ điển cờ TẤT CẢ quốc gia & vùng lãnh thổ trên thế giới (Tiếng Anh & Tiếng Việt)
COUNTRY_FLAGS = {
    # Châu Á & Đông Nam Á
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "korea": "kr", "china": "cn", "trung quốc": "cn", "india": "in", "ấn độ": "in", "uzbekistan": "uz",
    "iraq": "iq", "iran": "ir", "saudi arabia": "sa", "ả rập xê út": "sa", "qatar": "qa", "uae": "ae",
    "australia": "au", "úc": "au", "jordan": "jo", "bahrain": "bh", "syria": "sy", "omman": "om",
    "palestine": "ps", "lebanon": "lb", "kuwait": "kw", "yemen": "ye", "kyrgyzstan": "kg", "tajikistan": "tj",

    # Châu Âu
    "slovenia": "si", "scotland": "gb-sct", "england": "gb-eng", "anh": "gb-eng", "wales": "gb-wls",
    "northern ireland": "gb-nir", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl",
    "portugal": "pt", "bồ đào nha": "pt", "belgium": "be", "bỉ": "be", "croatia": "hr", "denmark": "dk",
    "đan mạch": "dk", "sweden": "se", "thụy điển": "se", "norway": "no", "nau uy": "no", "switzerland": "ch",
    "thụy sĩ": "ch", "austria": "at", "áo": "at", "poland": "pl", "ba lan": "pl", "ukraine": "ua",
    "czech": "cz", "séc": "cz", "serbia": "rs", "turkey": "tr", "thổ nhĩ kỳ": "tr", "russia": "ru", "nga": "ru",
    "greece": "gr", "hy lạp": "gr", "romania": "ro", "hungary": "hu", "slovakia": "sk", "finland": "fi",
    "ireland": "ie", "iceland": "is", "albania": "al", "bosnia": "ba", "macedonia": "mk",
    "georgia": "ge", "armenia": "am", "azerbaijan": "az", "cyprus": "cy", "estonia": "ee", "latvia": "lv",
    "lithuania": "lt", "luxembourg": "lu", "malta": "mt", "moldova": "md", "montenegro": "me", "kosovo": "xk",

    # Châu Phi & Bắc, Nam Mỹ
    "south africa": "za", "nam phi": "za", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma",
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "brazil": "br", "argentina": "ar", "uruguay": "uy"
}

def get_team_logo_url(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country_name) + r'\b'
        if re.search(pattern, t_lower):
            return f"https://flagcdn.com/w320/{code}.png"

    clean_title = re.sub(r'\b(vs|v|nữ|women|u23|u21|u19|u17)\b', '', teams_str, flags=re.IGNORECASE)
    words = [w[0].upper() for w in clean_title.split() if w[0].isalnum()]
    initials = "".join(words[:3]) if words else "KD"
    return f"https://ui-avatars.com/api/?name={initials}&background=random&color=fff&size=256&bold=true&length=3"

def detect_sport_icon(text: str) -> str:
    t_low = text.lower()
    if any(k in t_low for k in ["volleyball", "bóng chuyền", "volley"]): return "🏐"
    if any(k in t_low for k in ["basketball", "bóng rổ", "nba"]): return "🏀"
    if any(k in t_low for k in ["tennis", "quần vợt"]): return "🎾"
    if any(k in t_low for k in ["badminton", "cầu lông"]): return "🏸"
    return "⚽"

def clean_word(w: str) -> str:
    w_low = w.lower()
    if w_low in ['nu', 'nữ', 'women']: return 'Nữ'
    if w_low in ['nam', 'men']: return 'Nam'
    if w_low in ['u23', 'u21', 'u20', 'u19', 'u18', 'u17']: return w.upper()
    return w.capitalize()

def parse_teams_from_text_or_url(url: str, text: str) -> str:
    try:
        match = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|tran|stream)[^/]*/([^/?#]+)', url)
        slug = match.group(1) if match else next((p for p in url.split('/') if '-vs-' in p), "")
            
        if slug and '-vs-' in slug:
            parts = slug.split('-vs-')
            if len(parts) == 2:
                t1 = " ".join([clean_word(w) for w in parts[0].split('-') if w])
                t2 = " ".join([clean_word(w) for w in parts[1].split('-') if w])
                t1 = re.sub(r'^(blv|caster)-[a-z0-9]+-', '', t1, flags=re.IGNORECASE)
                t2 = re.sub(r'-\d+.*$', '', t2, flags=re.IGNORECASE)
                if t1 and t2:
                    return f"{t1} vs {t2}"
    except Exception:
        pass

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        if ' vs ' in line.lower() or ' - ' in line:
            clean_l = re.sub(r'\d{1,2}:\d{2}', '', line)
            clean_l = re.sub(r'\d{1,2}/\d{1,2}', '', clean_l)
            clean_l = re.sub(r'\((?:BLV|Caster)?[^\)]+\)', '', clean_l)
            if ' vs ' in clean_l.lower():
                pts = re.split(r'\s+vs\s+', clean_l, flags=re.IGNORECASE)
                if len(pts) == 2:
                    return f"{pts[0].strip()} vs {pts[1].strip()}"

    return "Trận đấu Trực Tiếp"

def parse_time_and_date(url: str, text: str, default_date: str):
    extracted_time = "00:00"
    extracted_date = default_date

    t_match = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', text, re.IGNORECASE)
    if t_match:
        extracted_time = f"{t_match.group(1).zfill(2)}:{t_match.group(2)}"
    else:
        url_t = re.search(r'luc[-_]?(2[0-3]|[0-1]\d)(\d{2})', url, re.IGNORECASE)
        if url_t:
            extracted_time = f"{url_t.group(1).zfill(2)}:{url_t.group(2)}"

    d_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', text)
    if d_match:
        extracted_date = f"{d_match.group(1).zfill(2)}/{d_match.group(2).zfill(2)}"
    else:
        url_d = re.search(r'ngay-(\d{1,2})[-_](\d{1,2})', url, re.IGNORECASE)
        if url_d:
            extracted_date = f"{url_d.group(1).zfill(2)}/{url_d.group(2).zfill(2)}"

    return extracted_time, extracted_date

def parse_datetime_obj(date_str: str, time_str: str, vn_tz) -> datetime:
    now = datetime.now(vn_tz)
    try:
        d, m = map(int, date_str.split('/'))
        h, mins = map(int, time_str.split(':'))
        yr = now.year
        if now.month == 12 and m == 1: yr += 1
        elif now.month == 1 and m == 12: yr -= 1
        return datetime(yr, m, d, h, mins, tzinfo=vn_tz)
    except Exception:
        return datetime(2099, 1, 1, 0, 0, tzinfo=vn_tz)

def get_match_details(context, match_url):
    page = context.new_page()
    m3u8_found = []

    def handle_net(req_or_res):
        u = req_or_res.url
        if ".m3u8" in u and "blob:" not in u and u not in m3u8_found:
            m3u8_found.append(u)

    page.on("request", handle_net)
    page.on("response", handle_net)
    
    match_info = {"m3u8_url": "", "is_live": False}

    try:
        page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)
        
        for selector in ['.play-btn', '.btn-play', '#player', 'iframe', 'video', '.player-wrapper', 'button']:
            try:
                page.click(selector, timeout=500)
                time.sleep(0.3)
            except Exception:
                pass

        for _ in range(4):
            if m3u8_found: break
            time.sleep(0.5)

        if not m3u8_found:
            for frame in page.frames:
                try:
                    content = frame.content()
                    urls = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', content)
                    for u in urls:
                        if "blob:" not in u and u not in m3u8_found:
                            m3u8_found.append(u)
                except Exception:
                    pass

        match_info["m3u8_url"] = m3u8_found[0] if m3u8_found else ""

        live_check = page.evaluate('''() => {
            const fullBody = document.body.innerText || '';
            return /(hiệp 1|hiệp 2|hiệp phụ|h1|h2|đang đá|đang diễn ra|live|\\d+['’])/i.test(fullBody);
        }''')

        match_info["is_live"] = live_check or bool(match_info["m3u8_url"])

    except Exception:
        pass
    finally:
        page.close()

    return match_info

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    final_matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )
        
        # Bypass cờ phát hiện automation
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        try:
            print(f"[*] Đang truy cập Khán Đài TV: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")

            # --- KHẮC PHỦC LỖI CLOUDFLARE ---
            print("[*] Đang kiểm tra xác thực Cloudflare...")
            for i in range(15):
                title = page.title()
                if "Just a moment" not in title and "Cloudflare" not in title and "Attention Required" not in title:
                    print(f"[+] Đã vượt qua Cloudflare thành công! Trang hiện tại: {title}")
                    break
                print(f"[-] Đang chờ Cloudflare giải mã... ({i+1}/15s)")
                time.sleep(1)

            time.sleep(3)

            # Cuộn trang để kích hoạt Lazy Load
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.5)

            # QUÉT TOÀN DIỆN CẢ DỮ LIỆU NGẦM VÀ THẺ HTML
            raw_matches = page.evaluate('''() => {
                const matches = [];
                const seenUrls = new Set();

                // 1. Thử cào từ dữ liệu Next.js JSON ngầm (nếu có)
                const nextDataEl = document.getElementById('__NEXT_DATA__');
                if (nextDataEl) {
                    try {
                        const jData = JSON.parse(nextDataEl.innerText);
                        const strData = JSON.stringify(jData);
                        const urlMatches = strData.match(/\\\\?\/[a-zA-Z0-9_-]+-vs-[a-zA-Z0-9_-]+/g);
                        if (urlMatches) {
                            urlMatches.forEach(u => {
                                const cleanU = u.replace(/\\\\/g, '');
                                const fullUrl = window.location.origin + cleanU;
                                if (!seenUrls.has(fullUrl)) {
                                    seenUrls.add(fullUrl);
                                    matches.push({ url: fullUrl, fullText: cleanU });
                                }
                            });
                        }
                    } catch(e) {}
                }

                // 2. Cào từ tất cả các thẻ <a> trên trang
                const links = Array.from(document.querySelectorAll('a[href]'));
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href || href === '#' || href.startsWith('javascript:')) return;

                    let fullUrl = href;
                    try {
                        fullUrl = new URL(href, window.location.origin).href;
                    } catch(e) { return; }

                    if (fullUrl === window.location.origin || fullUrl === window.location.origin + '/') return;
                    if (seenUrls.has(fullUrl)) return;

                    // Nhận diện thẻ là trận đấu
                    const card = link.closest('.match-item, .card, .item, li, tr') || link;
                    const cardText = card ? card.innerText || '' : link.innerText || '';

                    const isMatch = href.includes('-vs-') || 
                                    /truc-tiep|match|live|xem|room|phong|tran|stream|bong-da/i.test(href) ||
                                    /vs|vị/i.test(cardText);

                    if (isMatch) {
                        seenUrls.add(fullUrl);
                        matches.push({
                            url: fullUrl,
                            fullText: cardText
                        });
                    }
                });

                return matches;
            }''')

            page.close()
            print(f"[*] Quét thành công! Tìm thấy {len(raw_matches)} trận đấu!")

            parsed_items = []
            for idx, item in enumerate(raw_matches, 1):
                text, url = item['fullText'], item['url']
                print(f"[{idx}/{len(raw_matches)}] Đang bóc tách: {url}")

                details = get_match_details(context, url)
                extracted_time, match_date = parse_time_and_date(url, text, today_str)

                is_currently_live = details['is_live'] or any(k in text.lower() for k in ["hiệp 1", "hiệp 2", "đang đá", "đang diễn ra", "live"])

                blv_name = ""
                blv_match = re.search(r'\((?:BLV|Caster)?\s*([^\)]+)\)', text, re.IGNORECASE)
                if blv_match:
                    blv_name = blv_match.group(1).strip()
                else:
                    blv_search = re.search(r'(?:BLV|Caster)\s+([A-Za-zÀ-ỹ0-9\s]+)', text, re.IGNORECASE)
                    if blv_search:
                        blv_name = blv_search.group(1).strip()

                teams_str = parse_teams_from_text_or_url(url, text)
                sport_icon = detect_sport_icon(text + " " + url)
                logo = get_team_logo_url(teams_str)

                # Định dạng tiêu đề mẫu: 🟢 20:00 27/09 ⚽ Lithuania vs Azerbaijan (Kền Kền) [hls]
                live_prefix = "🟢 " if is_currently_live else ""
                blv_suffix = f" ({blv_name.title()})" if blv_name else ""
                
                full_title = f"{live_prefix}{extracted_time} {match_date} {sport_icon} {teams_str}{blv_suffix} [hls]".strip()
                dt_obj = parse_datetime_obj(match_date, extracted_time, vn_tz)

                parsed_items.append({
                    "title": full_title,
                    "logo": logo,
                    "url": url,
                    "m3u8_url": details['m3u8_url'],
                    "is_live": is_currently_live,
                    "dt": dt_obj
                })

            parsed_items.sort(key=lambda x: (x['dt'].date(), not x['is_live'], x['dt'].time()))

            seen_urls = set()
            title_tracker = {}

            for p_item in parsed_items:
                if p_item['url'] in seen_urls: continue
                seen_urls.add(p_item['url'])

                raw_title = p_item['title']
                if raw_title in title_tracker:
                    title_tracker[raw_title] += 1
                    p_item['title'] = f"{raw_title} (SV{title_tracker[raw_title]})"
                else:
                    title_tracker[raw_title] = 1

                final_matches.append(p_item)

        except Exception as e:
            print(f"[!] Lỗi nghiêm trọng: {e}")
        finally:
            browser.close()

    # --- XUẤT FILE M3U PLAYLIST ---
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U tvg-shift="0"\n\n')

        for item in final_matches:
            logo_attr = f'tvg-logo="{item["logo"]}"'
            
            if item.get('m3u8_url'):
                stream_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}"
            else:
                stream_url = f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"
            
            f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\n')
            f.write(f'#EXTVLCOPT:http-referrer={BASE_URL}/\n')
            f.write(f'{stream_url}\n\n')

    print(f"[HOÀN THÀNH] Đã ghi thành công {len(final_matches)} trận đấu vào file {OUTPUT_FILE}!")

if __name__ == "__main__":
    run_scraper()
    
