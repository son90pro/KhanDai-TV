import time
import re
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# Danh sách tên miền dự phòng của Khán Đài TV
DOMAINS = [
    "https://khandai1.link",
    "https://khandai.link",
    "https://khandai.tv"
]

OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
GAVANG_LOGO = "https://i.postimg.cc/6pt402sd/logo-gavangtv.jpg"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Biểu tượng môn thể thao
SPORT_ICONS = {
    "bóng đá": "⚽",
    "bóng chuyền": "🏐",
    "bóng rổ": "🏀",
    "bóng bàn": "🏓",
    "billiards": "🎱",
    "bida": "🎱",
    "tennis": "🎾",
    "cầu lông": "🏸"
}

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
    "phần lan": "fi", "ireland": "ie", "iceland": "is", "albania": "al", "bosnia": "ba", "macedonia": "mk",
    "georgia": "ge", "armenia": "am", "azerbaijan": "az", "cyprus": "cy", "estonia": "ee", "latvia": "lv",
    "lithuania": "lt", "luxembourg": "lu", "malta": "mt", "moldova": "md", "montenegro": "me", "san marino": "sm",
    "bulgaria": "bg",

    # Châu Phi
    "south africa": "za", "nam phi": "za", "guinea": "gn", "equatorial guinea": "gq", "kenya": "ke",
    "eritrea": "er", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma", "senegal": "sn",
    "algeria": "dz", "nigeria": "ng", "cameroon": "cm", "ghana": "gh", "ivory coast": "ci", "bờ biển ngà": "ci",
    "tunisia": "tn", "mali": "ml", "burkina faso": "bf", "congo": "cg", "dr congo": "cd", "zambia": "zm",
    "gabon": "ga", "angola": "ao", "uganda": "ug", "mozambique": "mz", "madagascar": "mg", "sudan": "sd",

    # Bắc, Trung Mỹ
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa",
    "jamaica": "jm", "honduras": "hn", "el salvador": "sv", "guatemala": "gt", "haiti": "ht",

    # Nam Mỹ
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl",
    "peru": "pe", "ecuador": "ec", "paraguay": "py", "venezuela": "ve", "bolivia": "bo"
}

def get_team_logo_url(teams_str: str, raw_team1_logo: str = "") -> str:
    """Tự động khớp Cờ quốc gia hoặc lấy ảnh Đội 1 từ web"""
    if raw_team1_logo and raw_team1_logo.startswith("http") and "logo" not in raw_team1_logo.lower() and "default" not in raw_team1_logo.lower():
        return raw_team1_logo

    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country_name) + r'\b'
        if re.search(pattern, t_lower):
            return f"https://flagcdn.com/w320/{code}.png"

    return GAVANG_LOGO

def clean_word(w: str) -> str:
    w_low = w.lower()
    if w_low in ['nu', 'nữ', 'women']: return 'Nữ'
    if w_low in ['nam', 'men']: return 'Nam'
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

    return "20:00"

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
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )

        for base_url in DOMAINS:
            print(f"[*] Đang thử kết nối tới: {base_url}")
            try:
                page = context.new_page()
                page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2.5)

                for _ in range(4):
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(0.4)

                extracted = page.evaluate('''() => {
                    const matches = [];
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    const seenUrls = new Set();

                    links.forEach(link => {
                        const href = link.getAttribute('href') || '';
                        if (!href) return;
                        
                        const isMatchUrl = /(truc-tiep|match|live|room|xem|phong|link|stream|bong-da)/i.test(href);
                        if (!isMatchUrl) return;

                        const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                        if (seenUrls.has(fullUrl) || fullUrl.endsWith('#') || fullUrl === window.location.origin + '/') return;
                        seenUrls.add(fullUrl);

                        let card = link;
                        let parent = link.parentElement;
                        while (parent && parent.tagName !== 'BODY') {
                            if (parent.innerText && parent.innerText.length > 15 && parent.innerText.length < 600) {
                                card = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }

                        const fullText = card ? (card.innerText || '') : (link.innerText || '');
                        const textLower = fullText.toLowerCase();

                        // Xác định môn thể thao
                        let sport = "bóng đá";
                        if (textLower.includes('bóng chuyền') || textLower.includes('volleyball')) sport = "bóng chuyền";
                        else if (textLower.includes('bóng rổ') || textLower.includes('basketball')) sport = "bóng rổ";
                        else if (textLower.includes('billiards') || textLower.includes('bida') || textLower.includes('pool')) sport = "billiards";
                        else if (textLower.includes('bóng bàn') || textLower.includes('table tennis')) sport = "bóng bàn";
                        else if (textLower.includes('tennis') || textLower.includes('quần vợt')) sport = "tennis";

                        // Lấy logo Đội 1
                        let team1Logo = '';
                        const imgs = card.querySelectorAll('img');
                        imgs.forEach(img => {
                            if (!team1Logo) {
                                const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                                if (src && !src.includes('avatar') && !src.includes('icon') && !src.includes('banner') && !src.includes('logo')) {
                                    team1Logo = src.startsWith('//') ? 'https:' + src : (src.startsWith('http') ? src : window.location.origin + src);
                                }
                            }
                        });

                        matches.push({
                            url: fullUrl,
                            fullText: fullText,
                            sport: sport,
                            team1Logo: team1Logo
                        });
                    });

                    return matches;
                }''')

                page.close()
                if extracted and len(extracted) > 0:
                    raw_matches = extracted
                    working_domain = base_url
                    print(f"[+] Lấy thành công {len(raw_matches)} trận từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Lỗi kết nối {base_url}: {e}")

        browser.close()

    parsed_items = []
    seen_urls = set()

    for item in raw_matches:
        url = item['url']
        if url in seen_urls: continue
        seen_urls.add(url)

        text = item['fullText']
        extracted_time = parse_time_robust(url, text)
        match_date = parse_date_info(url, text, today_str)

        is_currently_live = any(k in text.lower() for k in ["hiệp 1", "hiệp 2", "đang đá", "đang diễn ra", "live"])

        # Bóc tách tên BLV
        clean_blv = ""
        blv_match = re.search(r'((?:Gà|BLV|Caster)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
        if blv_match:
            raw_blv = blv_match.group(1).strip()
            raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league|cược)', raw_blv, flags=re.IGNORECASE)[0].strip()
            clean_blv = raw_blv
        
        clean_blv = re.sub(r'^(BLV|Caster|Gà)\s*[:\-]?\s*', '', clean_blv, flags=re.IGNORECASE).strip()
        clean_blv = re.sub(r'\s*(Cược|F888|SV368).*$', '', clean_blv, flags=re.IGNORECASE).strip()

        # Bóc tách tên 2 đội bóng
        teams_str = parse_teams_from_url(url)
        if not teams_str:
            match_vs = re.search(r'([A-Za-zÀ-ỹ0-9\s\.]{2,25})\s+vs\s+([A-Za-zÀ-ỹ0-9\s\.]{2,25})', text, re.I)
            if match_vs:
                teams_str = f"{match_vs.group(1).strip()} vs {match_vs.group(2).strip()}"

        if not teams_str:
            teams_str = "Trận đấu Trực Tiếp"

        sport_icon = SPORT_ICONS.get(item['sport'], "⚽")
        logo = get_team_logo_url(teams_str, item['team1Logo'])
        blv_suffix = f" ({clean_blv.title()})" if clean_blv else ""
        status_dot = "🟢 " if is_currently_live else ""

        # Tiêu đề chuẩn hình mẫu (1845.jpg): 🟢 16:00 26/09 ⚽ Pakistan vs Thái Lan (Chim Nhỏ) [hls]
        full_title = f"{status_dot}{extracted_time} {match_date} {sport_icon} {teams_str}{blv_suffix} [hls]"

        parsed_items.append({
            "title": full_title,
            "logo": logo,
            "url": url,
            "is_live": is_currently_live
        })

    # Ghi file Playlist M3U cho TiviMate
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}" , {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'{item["url"]}\n\n')

    print(f"[*] Xuất thành công {len(parsed_items)} trận vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
