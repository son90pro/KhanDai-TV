import time
import re
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH CƠ BẢN ---
DOMAINS = [
    "https://khandai1.link/",
    "https://khandai2.link/",
    "https://khandai3.link/"
]
REFERER_URL = "https://khandai1.link/"
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
DEFAULT_LOGO = "https://flagcdn.com/w320/un.png"
DEFAULT_BLV = "Khán Đài TV"
KNOWN_BLVS = ["PHÁO THỦ", "ENZO", "KỀN KỀN", "CHIM NHỎ", "LÝ LINH LỰC", "LÝ LÊN LỬA", "NHÀ ĐÀI"]

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
    junk_keywords = ["nhà cái", "fb88", "cược", "trang chủ", "quảng cáo", "gmail.com", "top nhà cái", "lịch thi đấu", "sv368"]
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
        print(f"  [->] Đang bóc tách luồng: {match_url}")
        page.goto(match_url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(3) # Cho player tải m3u8

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

        # Tìm các nút server (FHD, HD, SD...)
        server_buttons = page.query_selector_all('button, div, a')
        valid_buttons = []
        for btn in server_buttons:
            try:
                txt = btn.inner_text().strip()
                if txt in ["FHD", "HD", "SD", "HD1", "HD2", "GEO", "Full HD"]:
                    if txt not in [b[0] for b in valid_buttons]:
                        valid_buttons.append((txt, btn))
            except:
                pass

        if valid_buttons:
            for label, btn in valid_buttons:
                before_len = len(m3u8_history)
                try:
                    btn.click()
                    time.sleep(1.2)
                    if len(m3u8_history) > before_len:
                        captured_streams.append((label, m3u8_history[-1]))
                    elif m3u8_history:
                        captured_streams.append((label, m3u8_history[-1]))
                except Exception:
                    pass
        else:
            if m3u8_history:
                captured_streams.append(("hls", m3u8_history[-1]))

        if not captured_streams and m3u8_history:
            captured_streams.append(("hls", m3u8_history[-1]))

        page.close()
    except Exception as e:
        print(f"  [!] Lỗi cào trang chi tiết: {e}")
        try:
            page.close()
        except:
            pass

    return teams_title, blv_name, match_time, match_date, captured_streams

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    all_extracted_matches = {}

    print(f"[*] Khởi tạo công cụ cào dữ liệu Khán Đài TV...")

    try:
        with sync_playwright() as p:
            # Tắt headless để tránh bị Cloudflare block ẩn
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
                timezone_id="Asia/Ho_Chi_Minh",
                locale="vi-VN"
            )

            connected = False
            for base_url in DOMAINS:
                print(f"[*] Đang thử kết nối: {base_url}")
                try:
                    page = context.new_page()
                    page.goto(base_url, timeout=30000, wait_until="networkidle")
                    time.sleep(3)

                    # Cuộn trang để load hết danh sách trận đấu
                    for _ in range(5):
                        page.evaluate("window.scrollBy(0, 1000)")
                        time.sleep(0.5)

                    extracted = page.evaluate('''() => {
                        const results = [];
                        // Quét tất cả thẻ a và các card trận đấu
                        const elements = document.querySelectorAll('a[href], div[class*="match"], div[class*="card"]');

                        elements.forEach(el => {
                            let href = el.getAttribute('href') || el.getAttribute('data-href') || '';
                            if (!href) {
                                const parentA = el.closest('a');
                                if (parentA) href = parentA.getAttribute('href') || '';
                            }
                            if (!href || href === '#' || href.startswith('javascript:')) return;

                            const fullUrl = href.startswith('http') ? href : window.location.origin + href;
                            const text = el.innerText || '';
                            if (!text || text.length < 5) return;

                            let logoUrl = '';
                            const img = el.querySelector('img');
                            if (img) logoUrl = img.getAttribute('src') || img.getAttribute('data-src') || '';

                            results.push({
                                url: fullUrl,
                                rawText: text,
                                logo: logoUrl
                            });
                        });
                        return results;
                    }''')

                    for item in extracted:
                        all_extracted_matches[item['url']] = item

                    page.close()

                    if len(all_extracted_matches) > 0:
                        print(f"[+] Kết nối thành công! Đã quét thấy {len(all_extracted_matches)} mục trận đấu.")
                        connected = True
                        break
                except Exception as err:
                    print(f"[!] Không thể cào {base_url}: {err}")

            if not connected or not all_extracted_matches:
                print("[!] KHÔNG TÌM THẤY TRẬN ĐẤU NÀO! Kiểm tra lại kết nối mạng hoặc trang web đang đổi cấu trúc.")

            parsed_items = []
            raw_matches = list(all_extracted_matches.values())

            if raw_matches:
                print(f"\n[*] Đang tiến hành bóc tách chi tiết từng trận...")
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
                            # Định dạng giao diện chuẩn IPTV mẫu
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

    # Ghi xuất kết quả ra file playlist.m3u
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
    
