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

# Danh sách BLV Khán Đài TV chuẩn
KNOWN_BLVS = [
    "Chim Nhỏ", "Tây", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây",
    "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát"
]

# Từ điển Cờ Quốc Gia & Vùng lãnh thổ
COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "viet nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th", "thai lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "nhat ban": "jp", "south korea": "kr", "hàn quốc": "kr",
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
    "bulgaria": "bg", "south africa": "za", "nam phi": "za", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma",
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa", "jamaica": "jm",
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl", "peru": "pe", "ecuador": "ec"
}

# Các từ khóa rác tuyệt đối không làm tên đội
JUNK_EXACT = [
    "bóng đá", "bóng chuyền", "bóng rổ", "billiards", "bida", "bóng bàn", "tennis", "cầu lông",
    "cược f888", "cược sv368", "cược fb88", "cược", "f888", "sv368", "fb88",
    "sắp diễn ra", "đang diễn ra", "hiệp 1", "hiệp 2", "hoàn tất", "kết thúc", "vs", "trực tiếp"
]

def clean_team_word(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r'^\d+[\.\s]*', '', name)
    return name.strip()

def parse_card_lines(lines, url: str):
    """Bóc tách thông tin chính xác từng dòng của thẻ trận đấu"""
    extracted_time = ""
    extracted_date = ""
    blv_found = ""
    sport_found = "⚽"
    candidates = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        line_low = line_clean.lower()

        # 1. Lấy Giờ thi đấu
        if not extracted_time:
            time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', line_clean)
            if time_m:
                extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

        # 2. Lấy Ngày thi đấu
        if not extracted_date:
            date_m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})\b', line_clean)
            if date_m:
                extracted_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}"

        # 3. Lấy tên BLV
        if not blv_found:
            for b in KNOWN_BLVS:
                if b.lower() == line_low or b.lower() in line_low:
                    blv_found = b
                    break

        # 4. Nhận diện môn thể thao
        for sp, icon in SPORT_ICONS.items():
            if sp in line_low:
                sport_found = icon
                break

        # 5. Lọc bỏ các dòng rác
        if any(junk == line_low or junk in line_low for junk in JUNK_EXACT):
            continue
        if re.search(r'\d{1,2}[:h/]\d{2}', line_clean):
            continue
        if blv_found and blv_found.lower() in line_low:
            continue

        if len(line_clean) >= 2 and len(line_clean) <= 35:
            candidates.append(line_clean)

    # Trích xuất Tên 2 Đội từ danh sách ứng viên còn lại
    teams_title = ""
    if len(candidates) >= 2:
        # Nếu có dòng tên giải đấu ở đầu, lấy 2 dòng cuối cùng
        t1 = clean_team_word(candidates[-2])
        t2 = clean_team_word(candidates[-1])
        if t1 and t2 and t1.lower() != t2.lower():
            teams_title = f"{t1} vs {t2}"

    # Nếu trích xuất dòng thất bại, giải mã từ URL Slug
    if not teams_title:
        match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong)/([^/?#]+)', url)
        if match_slug and '-vs-' in match_slug.group(1):
            parts = match_slug.group(1).split('-vs-')
            left = re.sub(r'^(?:blv|caster|ga)[-_]+[a-z0-9-_]+?[-_]+', '', parts[0], flags=re.I)
            left = re.sub(r'^(?:blv|caster|ga)[-_]*', '', left, flags=re.I)
            right = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,12}).*$', '', parts[1], flags=re.I)

            t1_words = [w.capitalize() for w in left.split('-') if w and not w.isdigit()]
            t2_words = [w.capitalize() for w in right.split('-') if w and not w.isdigit()]

            t1_str = " ".join(t1_words).strip()
            t2_str = " ".join(t2_words).strip()

            t1_str = re.sub(r'\bViet Nam\b', 'Việt Nam', t1_str, flags=re.I)
            t1_str = re.sub(r'\bThai Lan\b', 'Thái Lan', t1_str, flags=re.I)
            t2_str = re.sub(r'\bViet Nam\b', 'Việt Nam', t2_str, flags=re.I)
            t2_str = re.sub(r'\bThai Lan\b', 'Thái Lan', t2_str, flags=re.I)

            if t1_str and t2_str:
                teams_title = f"{t1_str} vs {t2_str}"

    if not teams_title:
        teams_title = "Trận đấu Trực Tiếp"

    return extracted_time, extracted_date, sport_found, teams_title, blv_found

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
                page.goto(base_url, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(0.4)

                extracted = page.evaluate('''() => {
                    const results = [];
                    const seenUrls = new Set();
                    const links = Array.from(document.querySelectorAll('a[href]'));

                    links.forEach(link => {
                        const href = link.getAttribute('href') || '';
                        if (!href || href === '/' || href.startsWith('#')) return;
                        if (!/(truc-tiep|match|live|room|xem|phong|stream|bong-da)/i.test(href)) return;

                        const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                        if (seenUrls.has(fullUrl)) return;

                        let container = link;
                        let parent = link.parentElement;
                        while (parent && parent.tagName !== 'BODY') {
                            if (parent.innerText && parent.innerText.length > 20 && parent.innerText.length < 600) {
                                container = parent;
                                break;
                            }
                            parent = parent.parentElement;
                        }

                        const text = container ? (container.innerText || '') : (link.innerText || '');
                        const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);

                        if (lines.length > 0) {
                            seenUrls.add(fullUrl);
                            results.push({
                                url: fullUrl,
                                lines: lines,
                                rawText: text
                            });
                        }
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
                print(f"[!] Thất bại tại {base_url}: {e}")

        browser.close()

    parsed_items = []
    seen_urls = set()

    for item in raw_matches:
        url = item['url']
        if url in seen_urls: continue
        seen_urls.add(url)

        lines = item['lines']
        raw_text = item['rawText']

        extracted_time, extracted_date, sport_icon, teams_title, blv_name = parse_card_lines(lines, url)

        if not extracted_time:
            extracted_time = "19:30"
        if not extracted_date:
            extracted_date = today_str

        is_currently_live = any(k in raw_text.lower() for k in ["đang diễn ra", "đang đá", "hiệp 1", "hiệp 2", "live"])
        status_dot = "🟢 " if is_currently_live else ""
        blv_suffix = f" ({blv_name})" if blv_name else ""

        # Tiêu đề kênh chuẩn 100% hình mẫu: 🟢 16:00 26/09 ⚽ Pakistan vs Thái Lan (Chim Nhỏ) [hls]
        full_title = f"{status_dot}{extracted_time} {extracted_date} {sport_icon} {teams_title}{blv_suffix} [hls]"
        logo = get_team_logo(teams_title)

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
    
