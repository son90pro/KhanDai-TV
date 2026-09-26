import time
import re
import unicodedata
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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DEFAULT_FLAG = "https://flagcdn.com/w320/un.png"

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

# Danh sách BLV Khán Đài TV nhận diện từ văn bản
KNOWN_BLVS = [
    "Chim Nhỏ", "Tây", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây",
    "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát"
]

# Từ điển cờ TẤT CẢ quốc gia & vùng lãnh thổ trên thế giới
COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "viet nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th", "thai lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "nhat ban": "jp", "south korea": "kr", "hàn quốc": "kr", "han quoc": "kr",
    "korea": "kr", "china": "cn", "trung quốc": "cn", "trung quoc": "cn", "india": "in", "ấn độ": "in", "uzbekistan": "uz",
    "iraq": "iq", "iran": "ir", "saudi arabia": "sa", "ả rập xê út": "sa", "qatar": "qa", "uae": "ae",
    "australia": "au", "úc": "au", "jordan": "jo", "bahrain": "bh", "syria": "sy", "omman": "om",
    "palestine": "ps", "lebanon": "lb", "kuwait": "kw", "yemen": "ye", "kyrgyzstan": "kg", "tajikistan": "tj",
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
    "south africa": "za", "nam phi": "za", "guinea": "gn", "equatorial guinea": "gq", "kenya": "ke",
    "eritrea": "er", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma", "senegal": "sn",
    "algeria": "dz", "nigeria": "ng", "cameroon": "cm", "ghana": "gh", "ivory coast": "ci", "bờ biển ngà": "ci",
    "tunisia": "tn", "mali": "ml", "burkina faso": "bf", "congo": "cg", "dr congo": "cd", "zambia": "zm", "gabon": "ga",
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa", "jamaica": "jm",
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl", "peru": "pe", "ecuador": "ec"
}

def clean_team_name(name: str) -> str:
    """Lọc sạch rác từ tên đội bóng"""
    if not name:
        return ""
    # Loại bỏ thông số ngày giờ, cược, giải đấu
    name = re.sub(r'\b(?:\d{1,2}:\d{2}|\d{1,2}[-/.]\d{1,2}(?:[-/.Post]\d{2,4})?)\b', '', name)
    name = re.sub(r'\b(?:BÓNG ĐÁ|BÓNG CHUYỀN|BÓNG RỔ|BILLIARDS|BÓNG BÀN|TENNIS|CƯỢC|F888|SV368|FB88|SẮP DIỄN RA|ĐANG DIỄN RA|HIỆP 1|HIỆP 2)\b', '', name, flags=re.I)
    for blv in KNOWN_BLVS:
        name = re.sub(r'\b' + re.escape(blv) + r'\b', '', name, flags=re.I)
    name = re.sub(r'^\d+[\.\s]*', '', name)
    return name.strip()

def extract_teams_from_text(text: str):
    """Trích xuất chính xác Tên Đội 1 vs Đội 2 từ văn bản thẻ web"""
    match_vs = re.search(r'([A-Za-zÀ-ỹ0-9\s\.]{2,30})\s+(?:VS|vs|-vs-)\s+([A-Za-zÀ-ỹ0-9\s\.]{2,30})', text)
    if match_vs:
        t1 = clean_team_name(match_vs.group(1))
        t2 = clean_team_name(match_vs.group(2))
        if t1 and t2 and len(t1) > 1 and len(t2) > 1:
            return f"{t1} vs {t2}"
    return ""

def get_team_logo(teams_str: str) -> str:
    """Tự động tìm Cờ Quốc Gia tương ứng"""
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country_name) + r'\b'
        if re.search(pattern, t_lower):
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_FLAG

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
            print(f"[*] Đang kết nối tới: {base_url}")
            try:
                page = context.new_page()
                # Chờ trang nạp hoàn tất hoàn toàn
                page.goto(base_url, timeout=35000, wait_until="networkidle")
                time.sleep(3)

                # Cuộn trang nhiều lần để tải hết danh sách trận đấu
                for _ in range(6):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(0.5)

                extracted = page.evaluate('''() => {
                    const results = [];
                    const seenUrls = new Set();
                    
                    // Tìm tất cả các thẻ liên kết trận đấu
                    const cards = Array.from(document.querySelectorAll('div, a, section, article'));
                    
                    cards.forEach(el => {
                        const txt = el.innerText || '';
                        if (txt.length > 15 && txt.length < 500 && (/VS/i.test(txt) || /\\d{1,2}:\\d{2}/.test(txt))) {
                            let href = '';
                            if (el.tagName === 'A') href = el.getAttribute('href');
                            else {
                                const a = el.querySelector('a[href]');
                                if (a) href = a.getAttribute('href');
                            }
                            
                            if (!href || href === '/' || href.startsWith('#') || href.includes('javascript')) return;
                            
                            const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                            if (seenUrls.has(fullUrl)) return;
                            
                            // Chỉ lấy thẻ nhỏ nhất chứa thông tin trận
                            const childCards = Array.from(el.querySelectorAll('div')).filter(c => /VS/i.test(c.innerText || ''));
                            if (childCards.length > 0) return;

                            seenUrls.add(fullUrl);
                            results.push({ url: fullUrl, text: txt });
                        }
                    });

                    // Dự phòng nếu cách trên không tìm thấy: Lấy tất cả thẻ <a> có link trận
                    if (results.length === 0) {
                        const links = Array.from(document.querySelectorAll('a[href*="truc-tiep"], a[href*="match"], a[href*="live"], a[href*="xem"], a[href*="phong"], a[href*="bong-da"]'));
                        links.forEach(a => {
                            const href = a.getAttribute('href');
                            if (!href) return;
                            const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                            if (seenUrls.has(fullUrl)) return;
                            seenUrls.add(fullUrl);
                            results.push({ url: fullUrl, text: a.innerText || a.parentElement?.innerText || '' });
                        });
                    }

                    return results;
                }''')

                page.close()

                if extracted and len(extracted) > 0:
                    raw_matches = extracted
                    working_domain = base_url
                    print(f"[+] Lấy thành công {len(raw_matches)} trận từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Thất bại tại {base_url}: {e}")

        browser.close()

    parsed_items = []
    seen_urls = set()

    for item in raw_matches:
        url = item['url']
        if url in seen_urls: continue
        seen_urls.add(url)

        text = item['text']

        # 1. Bóc tách Tên 2 Đội
        teams_str = extract_teams_from_text(text)
        if not teams_str:
            # Dự phòng giải mã từ URL Slug
            match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong)/([^/?#]+)', url)
            if match_slug and '-vs-' in match_slug.group(1):
                p = match_slug.group(1).split('-vs-')
                t1 = re.sub(r'^(?:blv|caster|ga)[-_]+[a-z0-9-_]+?[-_]+', '', p[0], flags=re.I)
                t2 = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,10}).*$', '', p[1], flags=re.I)
                t1_clean = " ".join([w.capitalize() for w in t1.split('-') if w and not w.isdigit()])
                t2_clean = " ".join([w.capitalize() for w in t2.split('-') if w and not w.isdigit()])
                if t1_clean and t2_clean:
                    teams_str = f"{t1_clean} vs {t2_clean}"

        if not teams_str:
            teams_str = "Trận đấu Trực Tiếp"

        # 2. Bóc tách tên BLV
        blv_name = ""
        for b in KNOWN_BLVS:
            if b.lower() in text.lower() or b.lower().replace(' ', '-') in url.lower():
                blv_name = b
                break

        # 3. Bóc tách Thời gian & Ngày
        time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', text)
        extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}" if time_m else "19:30"

        date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', text)
        match_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}" if date_m else today_str

        # 4. Icon môn thể thao
        sport_icon = "⚽"
        text_low = text.lower()
        for sport, icon in SPORT_ICONS.items():
            if sport in text_low:
                sport_icon = icon
                break

        is_currently_live = any(k in text_low for k in ["đang diễn ra", "đang đá", "hiệp 1", "hiệp 2", "live"])
        status_dot = "🟢 " if is_currently_live else ""
        blv_suffix = f" ({blv_name})" if blv_name else ""

        # Tiêu đề kênh chuẩn: 🟢 16:00 26/09 ⚽ Pakistan vs Thái Lan (Chim Nhỏ) [hls]
        full_title = f"{status_dot}{extracted_time} {match_date} {sport_icon} {teams_str}{blv_suffix} [hls]"
        logo = get_team_logo(teams_str)

        parsed_items.append({
            "title": full_title,
            "logo": logo,
            "url": url
        })

    # Ghi file M3U Playlist cho TiviMate
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
    
