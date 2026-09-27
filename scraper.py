import sys
import time
import re
import json
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urljoin
from playwright.sync_api import sync_playwright

# --- CẤU HÌNH HỆ THỐNG ---
WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
OUTPUT_FILE = "khandai.m3u"
GROUP_NAME = "Khán Đài TV"

# Danh sách tên miền dự phòng của Khán Đài TV
DOMAINS = [
    "https://khandai1.link",
    "https://khandai.tv",
    "https://khandai2.link",
    "https://khandaitv.link"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "china": "cn", "trung quốc": "cn", "india": "in", "ấn độ": "in", "australia": "au", "úc": "au",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl",
    "portugal": "pt", "bồ đào nha": "pt", "usa": "us", "mỹ": "us", "brazil": "br", "argentina": "ar"
}

def get_team_logo_url(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        if re.search(r'\b' + re.escape(country_name) + r'\b', t_lower):
            return f"https://flagcdn.com/w320/{code}.png"

    clean_title = re.sub(r'\b(vs|v|nữ|women|u23|u21|u19|u17)\b', '', teams_str, flags=re.IGNORECASE)
    words = [w[0].upper() for w in clean_title.split() if w[0].isalnum()]
    initials = "".join(words[:3]) if words else "KD"
    return f"https://ui-avatars.com/api/?name={initials}&background=random&color=fff&size=256&bold=true&length=3"

def detect_sport_icon(text: str) -> str:
    t_low = text.lower()
    if any(k in t_low for k in ["volleyball", "bóng chuyền"]): return "🏐"
    if any(k in t_low for k in ["basketball", "bóng rổ"]): return "🏀"
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
    match = re.search(r'/([^/?#]+-vs-[^/?#]+)', url)
    if match:
        slug = match.group(1)
        parts = slug.split('-vs-')
        if len(parts) == 2:
            t1 = " ".join([clean_word(w) for w in parts[0].split('-') if w])
            t2 = " ".join([clean_word(w) for w in parts[1].split('-') if w])
            t1 = re.sub(r'^(blv|caster)-[a-z0-9]+-', '', t1, flags=re.IGNORECASE)
            t2 = re.sub(r'-\d+.*$', '', t2, flags=re.IGNORECASE)
            if t1 and t2:
                return f"{t1} vs {t2}"

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        if ' vs ' in line.lower():
            clean_l = re.sub(r'\d{1,2}:\d{2}', '', line)
            clean_l = re.sub(r'\((?:BLV|Caster)?[^\)]+\)', '', clean_l)
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

    d_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', text)
    if d_match:
        extracted_date = f"{d_match.group(1).zfill(2)}/{d_match.group(2).zfill(2)}"

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
            locale="vi-VN"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

        working_domain = None
        raw_matches = []

        # 1. Thử kết nối qua từng domain
        for domain in DOMAINS:
            try:
                print(f"[*] Đang thử truy cập: {domain}")
                page.goto(domain, timeout=30000, wait_until="domcontentloaded")
                
                # Chờ Cloudflare tự động xác minh (tối đa 15 giây)
                for _ in range(15):
                    title = page.title()
                    if "Just a moment" not in title and "Cloudflare" not in title and "Attention Required" not in title:
                        break
                    time.sleep(1)

                time.sleep(2)
                # Cuộn trang xuống
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(1)

                # Quét danh sách link trận đấu
                matches_data = page.evaluate('''() => {
                    const results = [];
                    const seen = new Set();
                    
                    // Quét Next.js state
                    const nextEl = document.getElementById('__NEXT_DATA__');
                    if (nextEl) {
                        try {
                            const str = nextEl.innerText;
                            const found = str.match(/\\\\?\/[a-zA-Z0-9_-]+-vs-[a-zA-Z0-9_-]+/g) || [];
                            found.forEach(u => {
                                const cleanU = u.replace(/\\\\/g, '');
                                if (!seen.has(cleanU)) {
                                    seen.add(cleanU);
                                    results.push({ url: cleanU, text: cleanU });
                                }
                            });
                        } catch(e) {}
                    }

                    // Quét thẻ <a> HTML
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    links.forEach(a => {
                        const href = a.getAttribute('href');
                        if (!href || href === '#' || href.startsWith('javascript')) return;
                        if (href.includes('-vs-') || /truc-tiep|phong|live|match/i.test(href)) {
                            if (!seen.has(href)) {
                                seen.add(href);
                                results.push({ url: href, text: a.innerText || href });
                            }
                        }
                    });

                    return results;
                }''')

                if matches_data and len(matches_data) > 0:
                    working_domain = domain
                    raw_matches = matches_data
                    print(f"[+] Kết nối thành công tới {domain}! Tìm thấy {len(raw_matches)} trận.")
                    break
            except Exception as e:
                print(f"[-] Không thể kết nối {domain}: {e}")

        if not working_domain or len(raw_matches) == 0:
            print("[!] KHÔNG TÌM THẤY TRẬN ĐẤU NÀO TRÊN TẤT CẢ DOMAIN.")
            browser.close()
            return

        # 2. Bóc tách thông tin từng trận
        parsed_items = []
        for idx, item in enumerate(raw_matches, 1):
            full_url = urljoin(working_domain, item['url'])
            text = item['text']

            # Lấy link m3u8 nếu có
            m3u8_url = ""
            try:
                sub_page = context.new_page()
                m3u8_list = []
                sub_page.on("request", lambda req: m3u8_list.append(req.url) if ".m3u8" in req.url else None)
                sub_page.goto(full_url, timeout=10000, wait_until="domcontentloaded")
                time.sleep(1)
                if m3u8_list:
                    m3u8_url = m3u8_list[0]
                sub_page.close()
            except Exception:
                pass

            extracted_time, match_date = parse_time_and_date(full_url, text, today_str)
            is_currently_live = bool(m3u8_url) or any(k in text.lower() for k in ["hiệp 1", "hiệp 2", "đang đá", "live"])

            blv_name = ""
            blv_match = re.search(r'\((?:BLV|Caster)?\s*([^\)]+)\)', text, re.IGNORECASE)
            if blv_match:
                blv_name = blv_match.group(1).strip()

            teams_str = parse_teams_from_text_or_url(full_url, text)
            sport_icon = detect_sport_icon(text + " " + full_url)
            logo = get_team_logo_url(teams_str)

            live_prefix = "🟢 " if is_currently_live else ""
            blv_suffix = f" ({blv_name.title()})" if blv_name else ""
            
            full_title = f"{live_prefix}{extracted_time} {match_date} {sport_icon} {teams_str}{blv_suffix} [hls]".strip()
            dt_obj = parse_datetime_obj(match_date, extracted_time, vn_tz)

            parsed_items.append({
                "title": full_title,
                "logo": logo,
                "url": full_url,
                "m3u8_url": m3u8_url,
                "is_live": is_currently_live,
                "dt": dt_obj
            })

        parsed_items.sort(key=lambda x: (x['dt'].date(), not x['is_live'], x['dt'].time()))

        title_tracker = {}
        for p_item in parsed_items:
            raw_title = p_item['title']
            if raw_title in title_tracker:
                title_tracker[raw_title] += 1
                p_item['title'] = f"{raw_title} (SV{title_tracker[raw_title]})"
            else:
                title_tracker[raw_title] = 1
            final_matches.append(p_item)

        browser.close()

    # 3. Xuất file M3U
    if final_matches:
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
                f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
                f.write(f'{stream_url}\n\n')

        print(f"[HOÀN THÀNH] Đã ghi thành công {len(final_matches)} trận đấu vào file {OUTPUT_FILE}!")
    else:
        print("[!] Không xuất file vì không lấy được trận đấu nào.")

if __name__ == "__main__":
    try:
        run_scraper()
    except Exception as e:
        print(f"[LỖI CRASH]: {e}")
        traceback.print_exc()
            
