import time
import re
import base64
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

SPORT_ICONS = {
    "bóng đá": "⚽", "bóng chuyền": "🏐", "bóng rổ": "🏀", "bóng bàn": "🏓",
    "billiards": "🎱", "bida": "🎱", "tennis": "🎾", "cầu lông": "🏸"
}

KNOWN_BLVS = [
    "Chim Nhỏ", "Tày", "Tay", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây", "Enzo",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "indonesia": "id", "malaysia": "my", "singapore": "sg", "japan": "jp", "nhật bản": "jp",
    "south korea": "kr", "hàn quốc": "kr", "china": "cn", "trung quốc": "cn", "england": "gb-eng",
    "anh": "gb-eng", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "usa": "us", "mỹ": "us",
    "slovenia": "si", "scotland": "gb-sct", "finland": "fi", "phần lan": "fi", "kuwait": "kw", "iraq": "iq"
}

CLUB_FLAGS = {
    "imoco": "it", "novara": "it", "milano": "it", "scandicci": "it",
    "arsenal": "gb-eng", "manchester": "gb-eng", "real madrid": "es", "barcelona": "es"
}

def extract_from_url_slug(url: str):
    match_slug = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream)/([^/?#]+)', url)
    if not match_slug: return "", ""
    slug = match_slug.group(1).lower()
    if '-vs-' not in slug: return "", ""

    parts = slug.split('-vs-')
    blv_found = ""

    for b in KNOWN_BLVS:
        if b.lower().replace(' ', '-') in slug:
            blv_found = b
            break

    left = re.sub(r'^(?:blv|caster|ga)[-_]+', '', parts[0])
    right = re.sub(r'-(?:luc|ngay|time|\d{2}h\d{2}|\d{3,12}).*$', '', parts[1])

    t1 = " ".join([w.capitalize() for w in left.split('-') if w and not w.isdigit()])
    t2 = " ".join([w.capitalize() for w in right.split('-') if w and not w.isdigit()])

    if t1 and t2:
        return f"{t1} vs {t2}", blv_found
    return "", blv_found

def get_team_logo(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for country, code in COUNTRY_FLAGS.items():
        if country in t_lower:
            return f"https://flagcdn.com/w320/{code}.png"
    for club, code in CLUB_FLAGS.items():
        if club in t_lower:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_FLAG

def fetch_m3u8_stream(context, match_url: str, base_domain: str) -> str:
    """Tự động tương tác và bóc tách luồng m3u8 thực sự từ player"""
    m3u8_url = ""
    page = context.new_page()

    def handle_request(request):
        nonlocal m3u8_url
        u = request.url
        if ".m3u8" in u and "blob:" not in u and not m3u8_url:
            m3u8_url = u

    page.on("request", handle_request)

    try:
        page.goto(match_url, timeout=20000, wait_until="domcontentloaded")
        time.sleep(2)

        # Thử click vào vùng phát video để kích hoạt load stream m3u8
        try:
            page.click('body', timeout=2000)
        except:
            pass
        time.sleep(2)

        # 1. Bắt m3u8 từ HTML / Javascript
        if not m3u8_url:
            content = page.content()
            matches = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', content)
            for u in matches:
                if "blob:" not in u:
                    m3u8_url = u
                    break

        # 2. Giải mã Base64 trong mã nguồn
        if not m3u8_url:
            b64_matches = re.findall(r'aHR0cD[a-zA-Z0-9+/=]+', page.content())
            for b64 in b64_matches:
                try:
                    decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
                    if ".m3u8" in decoded:
                        m3u8_url = decoded
                        break
                except:
                    continue

        # 3. Quét tất cả Iframe con
        if not m3u8_url:
            for frame in page.frames:
                try:
                    c = frame.content()
                    m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', c)
                    for u in m:
                        if "blob:" not in u:
                            m3u8_url = u
                            break
                except Exception:
                    pass
    except Exception as e:
        print(f"[!] Lỗi Playwright tại {match_url}: {e}")
    finally:
        page.close()

    # 4. Dự phòng bằng Request trực tiếp nếu Playwright bị kẹt
    if not m3u8_url:
        try:
            res = requests.get(match_url, headers={"User-Agent": USER_AGENT, "Referer": f"{base_domain}/"}, timeout=8)
            m = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', res.text)
            if m:
                m3u8_url = m[0]
        except:
            pass

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
                time.sleep(3)

                for _ in range(5):
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
                    print(f"[+] Lấy thành công {len(raw_matches)} link trận đấu từ {base_url}")
                    break
            except Exception as e:
                print(f"[!] Kết nối thất bại {base_url}: {e}")

        parsed_items = []
        seen_keys = set()

        print(f"[*] Đang bóc tách luồng m3u8...")
        for item in raw_matches:
            url = item['url']
            teams_title, blv_name = extract_from_url_slug(url)

            if not teams_title:
                continue

            dedup_key = f"{teams_title}_{blv_name}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            blv_suffix = f" ({blv_name})" if blv_name else ""
            sport_icon = "🏐" if "imoco" in teams_title.lower() or "novara" in teams_title.lower() else "⚽"
            status_dot = "🟢"

            # Đóng gói tiêu đề theo đúng mẫu ở Hình 2
            full_title = f"{status_dot} 19:30 {today_str} {sport_icon} {teams_title}{blv_suffix} [hls]"
            logo = get_team_logo(teams_title)

            # Lấy luồng m3u8
            m3u8_stream_url = fetch_m3u8_stream(context, url, working_domain)

            # Nếu lấy được m3u8 thì dùng m3u8, nếu chưa bắt được thì dùng tạm link match làm fallback
            final_play_url = m3u8_stream_url if (m3u8_stream_url and ".m3u8" in m3u8_stream_url) else url

            parsed_items.append({
                "title": full_title,
                "logo": logo,
                "play_url": final_play_url
            })
            print(f"[✓] Đã thêm trận: {teams_title}")

        browser.close()

    # Ghi file M3U tương thích 100% với TiviMate / OTT Navigator
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        
        if not parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{DEFAULT_FLAG}" group-title="Hệ Thống", [!] Đang cập nhật luồng trực tiếp mới\n')
            f.write(f'{working_domain}\n\n')
        else:
            for item in parsed_items:
                play_url = item["play_url"]
                
                # Cú pháp đính kèm Header Pipe để vượt rào chắn 403 Forbidden
                if ".m3u8" in play_url:
                    stream_entry = f"{play_url}|User-Agent={USER_AGENT}&Referer={working_domain}/"
                else:
                    stream_entry = play_url

                f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
                f.write(f'{stream_entry}\n\n')

    print(f"[*] Xuất thành công {len(parsed_items)} trận đấu vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
