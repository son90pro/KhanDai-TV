import time
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# Tên miền chính và dự phòng của Khán Đài TV
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
    "Chim Nhỏ", "Tày", "Tay", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây", "Enzo",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka",
    "Tiền Đạo", "Hậu Vệ", "Họa Mi", "Bia Hơi", "Thánh Dự", "Thần Tài"
]

# Từ điển Cờ Quốc Gia chuẩn FlagCDN (Không bao giờ bị lỗi ảnh/chặn 403)
COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "viet nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th", "thai lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "nhat ban": "jp", "south korea": "kr", "hàn quốc": "kr",
    "korea": "kr", "china": "cn", "trung quốc": "cn", "trung quoc": "cn", "india": "in", "ấn độ": "in", "uzbekistan": "uz",
    "iraq": "iq", "iran": "ir", "saudi arabia": "sa", "ả rập xê út": "sa", "qatar": "qa", "uae": "ae", "united arab emirates": "ae",
    "australia": "au", "úc": "au", "jordan": "jo", "bahrain": "bh", "syria": "sy", "omman": "om", "oman": "om",
    "palestine": "ps", "lebanon": "lb", "kuwait": "kw", "yemen": "ye", "kyrgyzstan": "kg", "tajikistan": "tj",
    "slovenia": "si", "scotland": "gb-sct", "england": "gb-eng", "anh": "gb-eng", "wales": "gb-wls",
    "northern ireland": "gb-nir", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl",
    "portugal": "pt", "bồ đào nha": "pt", "belgium": "be", "bỉ": "be", "croatia": "hr", "denmark": "dk",
    "đan mạch": "dk", "sweden": "se", "thụy điển": "se", "norway": "no", "nau uy": "no", "switzerland": "ch",
    "thụy sĩ": "ch", "austria": "at", "áo": "at", "poland": "pl", "ba lan": "pl", "ukraine": "ua",
    "czech": "cz", "czech republic": "cz", "séc": "cz", "serbia": "rs", "turkey": "tr", "thổ nhĩ kỳ": "tr", "russia": "ru", "nga": "ru",
    "greece": "gr", "hy lạp": "gr", "romania": "ro", "hungary": "hu", "slovakia": "sk", "finland": "fi",
    "phần lan": "fi", "ireland": "ie", "iceland": "is", "albania": "al", "bosnia": "ba", "macedonia": "mk",
    "north macedonia": "mk", "georgia": "ge", "armenia": "am", "azerbaijan": "az", "cyprus": "cy", "estonia": "ee",
    "latvia": "lv", "lithuania": "lt", "luxembourg": "lu", "bulgaria": "bg", "belarus": "by", "moldova": "md",
    "israel": "il", "kosovo": "xk", "taiwan": "tw", "đài loan": "tw", "hong kong": "hk",
    "south africa": "za", "nam phi": "za", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma",
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa",
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl", "peru": "pe", "ecuador": "ec"
}

CLUB_FLAGS = {
    "imoco": "it", "novara": "it", "milano": "it", "scandicci": "it", "trentino": "it", "lube": "it", "perugia": "it",
    "vakifbank": "tr", "fenerbahce": "tr", "ezzacibasi": "tr",
    "arsenal": "gb-eng", "manchester": "gb-eng", "liverpool": "gb-eng", "chelsea": "gb-eng",
    "real madrid": "es", "barcelona": "es", "bayern": "de", "juventus": "it", "psg": "fr"
}

JUNK_KEYWORDS = [
    "bxh", "lịch thi đấu", "top nhà cái", "nhà cái", "bảng xếp hạng", "tin tức", "hướng dẫn",
    "cược", "f888", "sv368", "fb88", "sắp diễn ra", "đang diễn ra", "hiệp 1", "hiệp 2",
    "bóng đá", "bóng chuyền", "bóng rổ", "billiards", "bida", "bóng bàn", "tennis", "cầu lông", "trực tiếp"
]

def is_blv_name(text: str) -> bool:
    if not text: return False
    t_low = text.strip().lower()
    for b in KNOWN_BLVS:
        if b.lower() == t_low or f"blv {b.lower()}" == t_low or f"caster {b.lower()}" == t_low:
            return True
    return False

def clean_team_name(name: str) -> str:
    if not name: return ""
    name = re.sub(r'^\d+[\.\s]*', '', name)
    for blv in KNOWN_BLVS:
        name = re.sub(r'\b' + re.escape(blv) + r'\b', '', name, flags=re.IGNORECASE)
    for jk in JUNK_KEYWORDS:
        name = re.sub(r'\b' + re.escape(jk) + r'\b', '', name, flags=re.IGNORECASE)
    return name.strip()

def extract_from_url_slug(url: str):
    match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream|xem-bong-da|truc-tiep-bong-da)/([^/?#]+)', url)
    if not match_slug:
        return "", ""

    slug = match_slug.group(1).lower()
    if '-vs-' not in slug:
        return "", ""

    parts = slug.split('-vs-')
    left, right = parts[0], parts[1]

    blv_found = ""

    left_clean = re.sub(r'^(?:blv|caster|ga)[-_]+', '', left)
    for b in KNOWN_BLVS:
        b_slug = b.lower().replace(' ', '-').replace('đ', 'd')
        if left_clean.startswith(b_slug + "-"):
            blv_found = b
            left_clean = left_clean[len(b_slug)+1:]
            break

    right_clean = right
    for b in KNOWN_BLVS:
        b_slug = b.lower().replace(' ', '-').replace('đ', 'd')
        pattern = r'-(?:blv|caster|ga)?[-_]*' + re.escape(b_slug) + r'$'
        if re.search(pattern, right_clean):
            if not blv_found:
                blv_found = b
            right_clean = re.sub(pattern, '', right_clean)
            break

    right_clean = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,12}).*$', '', right_clean)
    right_clean = re.sub(r'-\d{1,2}-\d{1,2}-\d{4}.*$', '', right_clean)

    t1_words = [w.capitalize() for w in left_clean.split('-') if w and not w.isdigit() and not is_blv_name(w)]
    t2_words = [w.capitalize() for w in right_clean.split('-') if w and not w.isdigit() and not is_blv_name(w)]

    t1_str = " ".join(t1_words).strip()
    t2_str = " ".join(t2_words).strip()

    t1_str = re.sub(r'\bViet Nam\b', 'Việt Nam', t1_str, flags=re.I)
    t1_str = re.sub(r'\bThai Lan\b', 'Thái Lan', t1_str, flags=re.I)
    t2_str = re.sub(r'\bViet Nam\b', 'Việt Nam', t2_str, flags=re.I)
    t2_str = re.sub(r'\bThai Lan\b', 'Thái Lan', t2_str, flags=re.I)

    teams = ""
    if t1_str and t2_str and t1_str.lower() != t2_str.lower():
        teams = f"{t1_str} vs {t2_str}"

    return teams, blv_found

def parse_card_lines(lines, url: str):
    extracted_time = ""
    extracted_date = ""
    blv_found = ""
    sport_found = "bóng đá"
    candidates = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        line_low = line_clean.lower()

        if any(jk in line_low for jk in ["bxh", "lịch thi đấu", "top nhà cái", "bảng xếp hạng", "tin tức"]):
            continue

        if not extracted_time:
            time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', line_clean)
            if time_m:
                extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

        if not extracted_date:
            date_m = re.search(r'\b(\d{1,2})[-/.](\d{1,2})\b', line_clean)
            if date_m:
                extracted_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}"

        if not blv_found:
            for b in KNOWN_BLVS:
                if b.lower() == line_low or f"blv {b.lower()}" in line_low or f"caster {b.lower()}" in line_low:
                    blv_found = b
                    break

        if is_blv_name(line_clean):
            continue

        for sp in SPORT_ICONS.keys():
            if sp in line_low:
                sport_found = sp
                break

        if any(junk == line_low or junk in line_low for junk in JUNK_KEYWORDS):
            continue
        if re.search(r'\d{1,2}[:h/]\d{2}', line_clean):
            continue

        if len(line_clean) >= 2 and len(line_clean) <= 35:
            candidates.append(line_clean)

    teams_title = ""
    if len(candidates) >= 2:
        t1 = clean_team_name(candidates[-2])
        t2 = clean_team_name(candidates[-1])
        if t1 and t2 and t1.lower() != t2.lower() and not is_blv_name(t1) and not is_blv_name(t2):
            teams_title = f"{t1} vs {t2}"

    teams_from_slug, blv_from_slug = extract_from_url_slug(url)

    if teams_from_slug:
        teams_title = teams_from_slug
    if not blv_found and blv_from_slug:
        blv_found = blv_from_slug

    if not teams_title:
        teams_title = "Trận đấu Trực Tiếp"

    return extracted_time, extracted_date, sport_found, teams_title, blv_found

def get_team_logo(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for country, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country) + r'\b'
        if re.search(pattern, t_lower):
            return f"https://flagcdn.com/w320/{code}.png"
    for club, code in CLUB_FLAGS.items():
        if club in t_lower:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_FLAG

def fetch_m3u8_stream(context, match_url: str) -> str:
    """Tự động tìm luồng m3u8 phát trực tiếp"""
    m3u8_url = ""
    page = context.new_page()

    def handle_request(request):
        nonlocal m3u8_url
        u = request.url
        if ".m3u8" in u and "blob:" not in u and not m3u8_url:
            m3u8_url = u

    page.on("request", handle_request)

    try:
        page.goto(match_url, timeout=10000, wait_until="domcontentloaded")
        time.sleep(1.5)

        if not m3u8_url:
            content = page.content()
            matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', content)
            for u in matches:
                if "blob:" not in u:
                    m3u8_url = u
                    break

        if not m3u8_url:
            for frame in page.frames:
                try:
                    c = frame.content()
                    m = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', c)
                    for u in m:
                        if "blob:" not in u:
                            m3u8_url = u
                            break
                except Exception:
                    pass
    except Exception:
        pass
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
            print(f"[*] Đang kết nối tới: {base_url}")
            try:
                page = context.new_page()
                page.goto(base_url, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3.5)

                for _ in range(8):
                    page.evaluate("window.scrollBy(0, 1000)")
                    time.sleep(0.4)

                extracted = page.evaluate('''() => {
                    const results = [];
                    const seenUrls = new Set();
                    const links = Array.from(document.querySelectorAll('a[href]'));

                    links.forEach(link => {
                        const href = link.getAttribute('href') || '';
                        if (!href || href === '/' || href.startsWith('#')) return;
                        
                        if (/(bxh|top-nha-cai|lich-thi-dau|tin-tuc|huong-dan)/i.test(href)) return;
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
                        if (text.includes('BXH & LỊCH THI ĐẤU') || text.includes('TOP NHÀ CÁI')) return;

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

        parsed_items = []
        seen_keys = set()

        print(f"[*] Đang bóc tách thông tin và luồng video cho {len(raw_matches)} trận...")
        for item in raw_matches:
            url = item['url']
            lines = item['lines']
            raw_text = item['rawText']

            extracted_time, extracted_date, sport, teams_title, blv_name = parse_card_lines(lines, url)

            if "BXH" in teams_title or "TOP NHÀ CÁI" in teams_title:
                continue

            dedup_key = f"{teams_title}_{blv_name}_{url}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            if not extracted_time:
                extracted_time = "19:30"
            if not extracted_date:
                extracted_date = today_str

            is_currently_live = any(k in raw_text.lower() for k in ["đang diễn ra", "đang đá", "hiệp 1", "hiệp 2", "live"])
            status_dot = "🟢 " if is_currently_live else ""
            blv_suffix = f" ({blv_name})" if blv_name else ""
            sport_icon = SPORT_ICONS.get(sport, "⚽")

            full_title = f"{status_dot}{extracted_time} {extracted_date} {sport_icon} {teams_title}{blv_suffix} [hls]"
            logo = get_team_logo(teams_title)

            # Tìm link .m3u8, nếu chưa có thì giữ URL trang làm dự phòng (LUÔN BẢO ĐẢM CÓ DỮ LIỆU)
            m3u8_stream_url = fetch_m3u8_stream(context, url)
            play_url = m3u8_stream_url if (m3u8_stream_url and ".m3u8" in m3u8_stream_url) else url

            parsed_items.append({
                "title": full_title,
                "logo": logo,
                "play_url": play_url
            })

        browser.close()

    # Ghi file M3U Playlist chuẩn mẫu tham khảo
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}" , {item["title"]} \n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'{item["play_url"]}\n\n')

    print(f"[*] Xuất thành công {len(parsed_items)} trận vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
            
