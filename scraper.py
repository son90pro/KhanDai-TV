import time
import re
import json
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from playwright.sync_api import sync_playwright

WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
BASE_URL = "https://khandai1.link"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
GAVANG_LOGO = "https://i.postimg.cc/6pt402sd/logo-gavangtv.jpg"

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
    " phần lan": "fi", "ireland": "ie", "iceland": "is", "albania": "al", "bosnia": "ba", "macedonia": "mk",
    "georgia": "ge", "armenia": "am", "azerbaijan": "az", "cyprus": "cy", "estonia": "ee", "latvia": "lv",
    "lithuania": "lt", "luxembourg": "lu", "malta": "mt", "moldova": "md", "montenegro": "me", "san marino": "sm",

    # Châu Phi
    "south africa": "za", "nam phi": "za", "guinea": "gn", "equatorial guinea": "gq", "kenya": "ke",
    "eritrea": "er", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma", "senegal": "sn",
    "algeria": "dz", "nigeria": "ng", "cameroon": "cm", "ghana": "gh", "ivory coast": "ci", "bờ biển ngà": "ci",
    "tunisia": "tn", "mali": "ml", "burkina faso": "bf", "congo": "cg", "dr congo": "cd", "zambia": "zm",
    "gabon": "ga", "angola": "ao", "uganda": "ug", "mozambique": "mz", "madagascar": "mg", "sudan": "sd",

    # Bắc, Trung Mỹ & CONCACAF
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa",
    "jamaica": "jm", "honduras": "hn", "el salvador": "sv", "guatemala": "gt", "haiti": "ht",
    "trinidad": "tt", "martinique": "mq", "curacao": "cw", "barbados": "bb", "saint lucia": "lc",

    # Nam Mỹ
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl",
    "peru": "pe", "ecuador": "ec", "paraguay": "py", "venezuela": "ve", "bolivia": "bo"
}

def get_team_logo_url(teams_str: str) -> str:
    """Tự động tìm Cờ quốc gia 100% hoặc sử dụng Logo Gà Vàng TV làm mặc định"""
    t_lower = teams_str.lower()
    
    # 1. Quét tìm cờ Quốc gia xuất hiện trong tên trận đấu
    for country_name, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country_name) + r'\b'
        if re.search(pattern, t_lower):
            return f"https://flagcdn.com/w320/{code}.png"

def clean_word(w: str) -> str:
    w_low = w.lower()
    if w_low in ['nu', 'nữ', 'women']: return 'Women' if w_low == 'women' else 'Nữ'
    if w_low in ['nam', 'men']: return 'Men' if w_low == 'men' else 'Nam'
    if w_low in ['u23', 'u21', 'u20', 'u19', 'u18', 'u17', 'u16', 'u15']: return w.upper()
    if w_low in ['ir', 'uae', 'usa', 'uk', 'fk', 'ad', 'real']: return w.upper() if len(w_low) <= 3 else w.capitalize()
    return w.capitalize()

def parse_teams_from_url(url: str) -> str:
    try:
        match = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream|xem-bong-da|truc-tiep-bong-da)/([^/?#]+)', url)
        slug = match.group(1) if match else next((p for p in url.split('/') if '-vs-' in p), "")
            
        if not slug or '-vs-' not in slug:
            return ""

        parts = slug.split('-vs-')
        if len(parts) != 2:
            return ""

        team1_slug, team2_slug = parts[0], parts[1]

        team1_slug = re.sub(r'^(?:blv-)?(?:ga|caster)-(?:sieu-[a-z0-9]+|[a-z0-9]+)-', '', team1_slug, flags=re.IGNORECASE)
        team1_slug = re.sub(r'^blv-[a-z0-9]+-', '', team1_slug, flags=re.IGNORECASE)
        
        team2_slug = re.sub(r'-luc-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-ngay-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-\d{3,4}$', '', team2_slug, flags=re.IGNORECASE)
        team2_slug = re.sub(r'-[a-z0-9]{8,35}$', '', team2_slug, flags=re.IGNORECASE)

        t1 = " ".join([clean_word(w) for w in team1_slug.split('-') if w])
        t2 = " ".join([clean_word(w) for w in team2_slug.split('-') if w])

        if t1 and t2:
            return f"{t1} vs {t2}"
    except Exception:
        pass
    return ""

def parse_date_info(url: str, text: str, default_date: str) -> str:
    try:
        date_match = re.search(r'ngay-(\d{1,2})[-_](\d{1,2})', url, re.IGNORECASE)
        if date_match:
            return f"{date_match.group(1).zfill(2)}/{date_match.group(2).zfill(2)}"
            
        text_date_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', text)
        if text_date_match:
            return f"{text_date_match.group(1).zfill(2)}/{text_date_match.group(2).zfill(2)}"
    except Exception:
        pass
    return default_date

def parse_time_robust(url: str, text: str) -> str:
    text_time = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', text, re.IGNORECASE)
    if text_time:
        return f"{text_time.group(1).zfill(2)}:{text_time.group(2)}"

    url_luc_4 = re.search(r'luc[-_]?(2[0-3]|[0-1]\d)(\d{2})', url, re.IGNORECASE)
    if url_luc_4:
        return f"{url_luc_4.group(1).zfill(2)}:{url_luc_4.group(2)}"

    return "00:00"

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
    
    match_info = {"time_str": "", "m3u8_url": "", "is_live": False}

    try:
        page.goto(match_url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1.5)
        
        for selector in ['.play-btn', '.btn-play', '#player', 'iframe', 'video', '.player-wrapper', 'button']:
            try:
                page.click(selector, timeout=800)
                time.sleep(0.5)
            except Exception:
                pass

        for _ in range(6):
            if m3u8_found:
                break
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

        details = page.evaluate('''() => {
            let tStr = "";
            let liveState = false;
            const fullBody = document.body.innerText || '';
            if (/(hiệp 1|hiệp 2|hiệp phụ|h1|h2|đang đá|đang diễn ra|\\d+['’])/i.test(fullBody)) {
                liveState = true;
            }
            const timeEls = Array.from(document.querySelectorAll('span, div, p, time, b'));
            for (let el of timeEls) {
                const text = el.innerText ? el.innerText.trim() : '';
                if (/\\d{1,2}[:h]\\d{2}/.test(text) && text.length < 30) {
                    tStr = text;
                    break;
                }
            }
            return { timeStr: tStr, liveState: liveState };
        }''')

        if details['timeStr']: match_info["time_str"] = details['timeStr']
        match_info["is_live"] = details['liveState'] or bool(match_info["m3u8_url"])

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
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )
        page = context.new_page()

        try:
            print(f"[*] Đang tải trang Gà Vàng 33 TV: {BASE_URL}")
            page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
            time.sleep(2)

            for _ in range(4):
                page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.5)

            raw_matches = page.evaluate('''() => {
                const matches = [];
                const links = Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"], a[href*="/xem/"], a[href*="/room/"], a[href*="/phong/"], a[href*="/truc-tiep-bong-da/"], a[href*="/xem-bong-da/"]'));
                const seenUrls = new Set();

                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (!href) return;

                    const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                    if (seenUrls.has(fullUrl)) return;
                    seenUrls.add(fullUrl);

                    let card = link;
                    let parent = link.parentElement;
                    while (parent && parent.tagName !== 'BODY') {
                        if (parent.querySelectorAll('a').length === 1) {
                            card = parent;
                            parent = parent.parentElement;
                        } else {
                            break;
                        }
                    }

                    matches.push({
                        url: fullUrl,
                        fullText: card ? card.innerText || '' : link.innerText || ''
                    });
                });

                return matches;
            }''')

            page.close()
            print(f"[*] Quét được {len(raw_matches)} trận đấu. Đang nhận diện Cờ/Logo hoàn chỉnh...")

            parsed_items = []
            for item in raw_matches:
                text, url = item['fullText'], item['url']
                if not text: continue

                details = get_match_details(context, url)
                raw_time_text = details['time_str'] if details['time_str'] else text
                extracted_time = parse_time_robust(url, raw_time_text)
                match_date = parse_date_info(url, text, today_str)

                is_currently_live = details['is_live'] or any(k in text.lower() for k in ["hiệp 1", "hiệp 2", "đang đá", "đang diễn ra"])

                blv_name = ""
                blv_match = re.search(r'((?:Gà|BLV|Caster)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
                if blv_match:
                    raw_blv = blv_match.group(1).strip()
                    raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
                    blv_name = raw_blv

                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', blv_name, flags=re.IGNORECASE).strip()
                teams_str = parse_teams_from_url(url) or "Trận đấu Trực Tiếp"

                # Khớp Cờ quốc gia tự động / Hoặc gán Logo Gà Vàng TV
                logo = get_team_logo_url(teams_str)
                blv_suffix = f" ({clean_blv.title()})" if clean_blv else ""

                if is_currently_live:
                    full_title = f"[{match_date} - 🔴 LIVE {extracted_time}] {teams_str}{blv_suffix}".strip()
                else:
                    full_title = f"[{match_date} - {extracted_time}] {teams_str}{blv_suffix}".strip()

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
            print(f"[!] Lỗi: {e}")
        finally:
            browser.close()

    # Xuất file M3U Playlist (Khai báo tvg-logo & logo ở thẻ EXTM3U để app nhận diện làm ảnh đại diện)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U tvg-shift="0" tvg-logo="{GAVANG_LOGO}" logo="{GAVANG_LOGO}"\n\n')

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

    print(f"[*] Đã hoàn tất! Xuất {len(final_matches)} trận vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
