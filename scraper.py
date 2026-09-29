import time
import re
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH CƠ BẢN ---
DOMAINS = [
    "https://khandai1.link/",
    "https://khandai2.link/",
    "https://khandai3.link/",
    "https://khandaitv.com/"
]
REFERER_URL = "https://khandai1.link/"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
DEFAULT_LOGO = "https://flagcdn.com/w320/un.png"
DEFAULT_BLV = "Khán Đài TV"

KNOWN_BLVS = [
    "PHÁO THỦ", "ENZO", "KỀN KỀN", "CHIM NHỎ", "LÝ LINH LỰC", 
    "LÝ LÊN LỬA", "NHÀ ĐÀI", "GẤU BÉO", "RỒNG ĐEN", "KHÁN ĐÀI"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "thailand": "th", "thái lan": "th",
    "indonesia": "id", "malaysia": "my", "philippines": "ph", "singapore": "sg",
    "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "china": "cn", "trung quốc": "cn", "england": "gb-eng", "anh": "gb-eng",
    "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "portugal": "pt",
    "bồ đào nha": "pt", "netherlands": "nl", "hà lan": "nl", "brazil": "br",
    "argentina": "ar", "usa": "us", "mỹ": "us", "ethiopia": "et", "senegal": "sn",
    "finland": "fi", "belarus": "by", "moldova": "md", "faroe islands": "fo",
    "saudi arabia": "sa", "iraq": "iq", "scotland": "gb-sct", "switzerland": "ch",
    "slovenia": "si", "north macedonia": "mk"
}

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[\r\n\t]+', ' ', str(text))
    return re.sub(r'\s+', ' ', clean).strip()

def is_ad_or_junk(text: str) -> bool:
    if not text:
        return True
    junk_keywords = [
        "nhà cái", "fb88", "cược", "trang chủ", "quảng cáo", "gmail.com", 
        "top nhà cái", "lịch thi đấu", "sv368", "bảng xếp hạng", "tin tức", "khuyến mãi"
    ]
    t_lower = text.lower()
    return any(k in t_lower for k in junk_keywords)

def clean_teams_title(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'vào lúc\s*\d{1,2}[:h]\d{2}', '', text, flags=re.I)
    text = re.sub(r',?\s*ngày\s*\d{1,2}[/-]\d{1,2}', '', text, flags=re.I)
    text = re.sub(r'\b\d{1,2}[:h]\d{2}\b', '', text)
    text = re.sub(r'\b\d{1,2}[/-]\d{1,2}\b', '', text)
    
    noise_patterns = [
        r'trực tiếp', r'phát trực tiếp', r'xem trực tiếp', r'xem bóng đá', r'phát',
        r'theo bạn thì trận này đội nào sẽ thắng\??', r'chủ nhà', r'hòa', r'đội khách',
        r'lý linh lực', r'lý lên lửa', r'nhà đài'
    ]
    for pat in noise_patterns:
        text = re.sub(pat, '', text, flags=re.I)

    text = re.sub(r'^\s*vs\s+|\s+vs\s*$', '', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()

def get_sport_icon(text: str) -> str:
    txt = text.lower()
    if "bóng chuyền" in txt or "volleyball" in txt:
        return "🏐"
    elif "bóng rổ" in txt or "basketball" in txt:
        return "🏀"
    elif "tennis" in txt or "quần vợt" in txt:
        return "🎾"
    elif "cầu lông" in txt or "badminton" in txt:
        return "🏸"
    return "⚽"

def get_team_logo(teams_str: str, raw_card_logo: str = "") -> str:
    if raw_card_logo and raw_card_logo.startswith("http") and not any(x in raw_card_logo for x in ["fire.svg", "default", "logo.png"]):
        return raw_card_logo
    clean_str = teams_str.lower()
    for country_key, code in COUNTRY_FLAGS.items():
        if country_key in clean_str:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def extract_blv_from_text(text: str) -> str:
    if not text:
        return ""
    text_upper = text.upper()
    for b in KNOWN_BLVS:
        if b in text_upper and b != "NHÀ ĐÀI":
            return b.title()
    m = re.search(r'(?:🎧|BLV|CASTER)\s*([A-ZÀ-Ỹ0-9\s]{2,15})', text_upper)
    if m:
        candidate = m.group(1).strip()
        if "NHÀ ĐÀI" not in candidate:
            return candidate.title()
    return ""

def scrape_match_detail(context, match_url: str, card_blv: str = ""):
    page = context.new_page()
    captured_streams = []
    m3u8_history = []

    def handle_request(req):
        url = req.url
        if ".m3u8" in url.lower() and url not in m3u8_history:
            m3u8_history.append(url)

    page.on("request", handle_request)

    teams_title = ""
    blv_name = card_blv
    match_time = ""
    match_date = ""

    try:
        print(f"  [->] Đang bắt luồng: {match_url}")
        page.goto(match_url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(2)

        detail_data = page.evaluate('''() => {
            let t1 = '', t2 = '', blv = '', timeStr = '', dateStr = '';
            const bodyText = document.body.innerText || '';

            const teamNodes = document.querySelectorAll('.team-name, .team_name, [class*="team"] .name, .club-name, .team1, .team2');
            if (teamNodes.length >= 2) {
                t1 = teamNodes[0].innerText || '';
                t2 = teamNodes[1].innerText || '';
            }

            const timeMatch = bodyText.match(/(\\d{1,2}:\\d{2})\\s*[-/]?\\s*(\\d{1,2}[/-]\\d{1,2})/);
            if (timeMatch) {
                timeStr = timeMatch[1];
                dateStr = timeMatch[2].replace('-', '/');
            }

            const blvNodes = document.querySelectorAll('[class*="blv"], [class*="caster"], .author, .speaker');
            for (let node of blvNodes) {
                if (node.innerText) {
                    blv = node.innerText.trim();
                    break;
                }
            }
            return { team1: t1, team2: t2, blv: blv, time: timeStr, date: dateStr };
        }''')

        t1 = clean_teams_title(detail_data['team1'])
        t2 = clean_teams_title(detail_data['team2'])
        if t1 and t2 and t1.lower() != t2.lower():
            teams_title = f"{t1} vs {t2}"

        if not blv_name and detail_data['blv']:
            blv_name = extract_blv_from_text(detail_data['blv'])

        match_time = sanitize_text(detail_data['time'])
        match_date = sanitize_text(detail_data['date'])

        # Tìm các nút chọn Server/Chất lượng luồng
        server_buttons = page.query_selector_all('button, div.server, a.btn')
        for btn in server_buttons:
            try:
                txt = btn.inner_text().strip()
                if txt in ["FHD", "HD", "SD", "HD1", "HD2", "GEO", "Full HD"]:
                    btn.click()
                    time.sleep(1)
            except:
                pass

        if m3u8_history:
            for i, stream in enumerate(m3u8_history):
                tag = "hls" if i == 0 else f"hd{i+1}"
                captured_streams.append((tag, stream))

        page.close()
    except Exception as e:
        print(f"  [!] Lỗi bóc tách chi tiết: {e}")
        try:
            page.close()
        except:
            pass

    return teams_title, blv_name, match_time, match_date, captured_streams

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    all_extracted_matches = {}
    parsed_items = []

    print(f"[*] Khởi tạo cào dữ liệu Khán Đài TV...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",  # Chống crash RAM trên GitHub Actions
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
                timezone_id="Asia/Ho_Chi_Minh",
                locale="vi-VN"
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)

            for base_url in DOMAINS:
                print(f"[*] Đang kết nối: {base_url}")
                try:
                    page = context.new_page()
                    page.goto(base_url, timeout=30000, wait_until="domcontentloaded")
                    time.sleep(3)

                    # Cuộn trang nhẹ để render lazy-load
                    page.evaluate("window.scrollBy(0, 500)")
                    time.sleep(1)

                    # Tối ưu DOM Query: Chỉ quét thẻ <a> chứa liên kết trận đấu
                    extracted = page.evaluate('''() => {
                        const results = [];
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        const seen = new Set();

                        for (let a of links) {
                            let href = a.getAttribute('href') || '';
                            if (!href || href.startsWith('#') || href.startsWith('javascript:')) continue;
                            if (href.includes('.css') || href.includes('.js') || href.includes('.png') || href.includes('.jpg')) continue;

                            const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                            
                            // Bỏ qua các trang danh mục cố định
                            if (['/lich-thi-dau', '/bang-xep-hang', '/tin-tuc', '/nha-cai', '/khuyen-mai'].some(k => fullUrl.includes(k))) continue;
                            if (seen.has(fullUrl)) continue;

                            let text = (a.innerText || '').trim();
                            let card = a.closest('.match-item, .item, .box, .card, li, div');
                            let cardText = card ? (card.innerText || '').trim() : text;

                            if (cardText.length < 5) continue;

                            let logoUrl = '';
                            let img = card ? card.querySelector('img') : a.querySelector('img');
                            if (img) logoUrl = img.getAttribute('src') || img.getAttribute('data-src') || '';

                            seen.add(fullUrl);
                            results.push({
                                url: fullUrl,
                                rawText: cardText,
                                logo: logoUrl
                            });
                        }
                        return results;
                    }''')

                    for item in extracted:
                        all_extracted_matches[item['url']] = item

                    page.close()

                    if len(all_extracted_matches) > 0:
                        print(f"[+] Tìm thấy {len(all_extracted_matches)} đường dẫn trận đấu từ {base_url}")
                        break
                except Exception as err:
                    print(f"[!] Không thể cào {base_url}: {err}")

            raw_matches = list(all_extracted_matches.values())

            if raw_matches:
                print(f"\n[*] Đang xử lý danh sách trận đấu...")
                for item in raw_matches:
                    match_url = item['url']
                    card_text = sanitize_text(item['rawText'])
                    
                    if is_ad_or_junk(card_text):
                        continue

                    sport_icon = get_sport_icon(card_text)
                    card_blv = extract_blv_from_text(card_text)
                    teams_from_page, blv_from_page, time_from_page, date_from_page, streams = scrape_match_detail(context, match_url, card_blv)

                    teams_title = teams_from_page
                    if not teams_title:
                        match_vs = re.search(r'([A-Za-zÀ-ỹ0-9\s\.]{2,25})\s+vs\s+([A-Za-zÀ-ỹ0-9\s\.]{2,25})', card_text, re.I)
                        if match_vs:
                            teams_title = f"{clean_teams_title(match_vs.group(1))} vs {clean_teams_title(match_vs.group(2))}"
                        else:
                            teams_title = clean_teams_title(card_text)

                    teams_title = clean_teams_title(teams_title)
                    if is_ad_or_junk(teams_title) or len(teams_title) < 3:
                        continue

                    blv_final = blv_from_page if blv_from_page else (card_blv if card_blv else DEFAULT_BLV)

                    extracted_time = time_from_page
                    if not extracted_time:
                        time_m = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', card_text)
                        extracted_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}" if time_m else "20:00"

                    match_date = date_from_page
                    if not match_date:
                        date_m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', card_text)
                        match_date = f"{date_m.group(1).zfill(2)}/{date_m.group(2).zfill(2)}" if date_m else today_str

                    card_logo = get_team_logo(teams_title, item['logo'])

                    try:
                        d, m = map(int, match_date.split('/'))
                        h, mins = map(int, extracted_time.split(':'))
                        curr_year = datetime.now(vn_tz).year
                        dt_obj = datetime(curr_year, m, d, h, mins, tzinfo=vn_tz)
                    except Exception:
                        dt_obj = datetime(2099, 1, 1, 0, 0, tzinfo=vn_tz)

                    if streams:
                        for server_label, stream_url in streams:
                            qual_tag = server_label.lower() if server_label.lower() in ["fhd", "hd", "sd"] else "hls"
                            # Cấu trúc tiêu chuẩn như ảnh mẫu: 20:00 29/09 ⚽ Ethiopia vs Senegal (Enzo) [hls]
                            full_title = f"{extracted_time} {match_date} {sport_icon} {teams_title} ({blv_final}) [{qual_tag}]"

                            parsed_items.append({
                                "title": full_title,
                                "logo": card_logo,
                                "stream_url": stream_url,
                                "dt": dt_obj,
                                "match_url": f"{match_url}#{server_label}"
                            })

            browser.close()

    except Exception as e:
        print(f"[!] Lỗi hệ thống Playwright: {e}")

    # Sắp xếp theo thời gian và ghi ra file playlist.m3u
    parsed_items.sort(key=lambda x: x['dt'])
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        seen_urls = set()
        count = 0
        for item in parsed_items:
            if item['match_url'] in seen_urls:
                continue
            seen_urls.add(item['match_url'])

            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={REFERER_URL}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'#EXTVLCOPT:http-origin={REFERER_URL}\n')
            f.write(f'{item["stream_url"]}\n\n')
            count += 1

    print(f"\n[✔] HOÀN TẤT! Đã tạo file '{OUTPUT_FILE}' thành công với {count} kênh IPTV.")

if __name__ == "__main__":
    run_scraper()
    
