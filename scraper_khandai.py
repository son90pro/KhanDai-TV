import sys
import time
import re
import json
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urljoin

# Tự động cài đặt cloudscraper nếu chưa có
try:
    import cloudscraper
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
    import cloudscraper

import requests
from bs4 import BeautifulSoup

# --- CẤU HÌNH HỆ THỐNG ---
WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
OUTPUT_FILE = "khandai.m3u"
GROUP_NAME = "Khán Đài TV"

DOMAINS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandai3.link",
    "https://khandai.org",
    "https://khandai.vip"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "china": "cn", "trung quốc": "cn", "india": "in", "ấn độ": "in", "australia": "au", "úc": "au",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl",
    "portugal": "pt", "bồ đào nha": "pt", "usa": "us", "mỹ": "us", "brazil": "br", "argentina": "ar",
    "lithuania": "lt", "azerbaijan": "az", "austria": "at", "kosovo": "xk"
}

def create_cf_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def fetch_page(target_url: str) -> str:
    print(f"[*] Đang kết nối tới: {target_url}")
    scraper = create_cf_scraper()

    try:
        res = scraper.get(target_url, timeout=15)
        print(f"  -> Cloudscraper Status: {res.status_code}")
        if res.status_code == 200 and len(res.text) > 1000 and "Just a moment" not in res.text:
            return res.text
    except Exception as e:
        print(f"  -> Cloudscraper lỗi: {e}")

    proxy_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(target_url, safe='')}"
    print(f"[*] Đang kết nối qua Worker Proxy...")
    try:
        res = requests.get(proxy_url, timeout=15)
        print(f"  -> Worker Proxy Status: {res.status_code}")
        if res.status_code == 200 and len(res.text) > 1000:
            return res.text
    except Exception as e:
        print(f"  -> Worker Proxy lỗi: {e}")

    return ""

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
    if any(k in t_low for k in ["bóng chuyền", "volleyball"]): return "🏐"
    if any(k in t_low for k in ["bóng rổ", "basketball"]): return "🏀"
    if any(k in t_low for k in ["quần vợt", "tennis"]): return "🎾"
    if any(k in t_low for k in ["cầu lông", "badminton"]): return "🏸"
    return "⚽"

def parse_time_and_date(text: str, default_date: str):
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
    
    html_content = ""
    working_domain = ""

    print("=== BẮT ĐẦU QUÉT DỮ LIỆU KHÁN ĐÀI TV ===")
    for domain in DOMAINS:
        html = fetch_page(domain)
        if html:
            html_content = html
            working_domain = domain
            print(f"[+] VƯỢT CLOUDFLARE THÀNH CÔNG TỪ: {domain}")
            break

    if not html_content:
        print("[!] TẤT CẢ DOMAIN ĐỀU THẤT BẠI. DỪNG TIẾN TRÌNH ĐỂ GIỮ FILE M3U CŨ.")
        sys.exit(1)

    soup = BeautifulSoup(html_content, 'html.parser')
    matches_data = []
    seen_urls = set()

    # 1. Giải mã cấu trúc Next.js JSON (__NEXT_DATA__)
    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    if next_data_tag and next_data_tag.string:
        try:
            data = json.loads(next_data_tag.string)
            page_props = data.get('props', {}).get('pageProps', {})
            match_list = page_props.get('matches', []) or page_props.get('data', []) or page_props.get('liveMatches', [])
            
            for item in match_list:
                if isinstance(item, dict):
                    slug = item.get('slug', '') or item.get('id', '')
                    match_url = urljoin(working_domain, f"/truc-tiep/{slug}" if not slug.startswith('http') else slug)
                    
                    if match_url in seen_urls: continue
                    seen_urls.add(match_url)

                    home = item.get('homeTeam', {}).get('name', '') or item.get('home_name', '')
                    away = item.get('awayTeam', {}).get('name', '') or item.get('away_name', '')
                    teams = f"{home} vs {away}" if home and away else item.get('title', 'Trận đấu Trực Tiếp')
                    
                    blv = item.get('commentator', '') or item.get('blv', '') or item.get('caster', '')
                    status = str(item.get('status', ''))
                    is_live = any(k in status.lower() for k in ['live', '1', '2', 'trực tiếp']) or item.get('isLive', False)
                    
                    matches_data.append({
                        "url": match_url, "teams": teams, "blv": blv,
                        "sport": item.get('sport', ''), "is_live": is_live,
                        "time": item.get('time', '00:00'), "date": item.get('date', today_str)
                    })
        except Exception as e:
            print(f"[-] Lỗi bóc tách JSON: {e}")

    # 2. Bóc tách DOM HTML nếu JSON không có
    if not matches_data:
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/truc-tiep/' in href or '-vs-' in href:
                full_url = urljoin(working_domain, href)
                if full_url in seen_urls or full_url == working_domain + '/': continue
                seen_urls.add(full_url)

                text = a.get_text(separator=' ', strip=True)
                if a.parent: text += " " + a.parent.get_text(separator=' ', strip=True)

                time_str, date_str = parse_time_and_date(text, today_str)
                is_live = any(k in text.lower() for k in ["trực tiếp", "hiệp", "'", "live"])
                
                # Đã sửa lại chuỗi Regex chuẩn
                blv_match = re.search(r'(?:BLV|Caster)\s*([A-Za-z0-9_À-ỹ]+)', text, re.IGNORECASE)
                teams_name = "Trận đấu Trực Tiếp"
                slug_match = re.search(r'/([^/?#]+-vs-[^/?#]+)', href)
                if slug_match:
                    parts = slug_match.group(1).split('-vs-')
                    if len(parts) == 2:
                        teams_name = f"{' '.join(parts[0].split('-')).title()} vs {' '.join(parts[1].split('-')).title()}"

                matches_data.append({
                    "url": full_url, "teams": teams_name,
                    "blv": blv_match.group(1) if blv_match else "",
                    "sport": text, "is_live": is_live,
                    "time": time_str, "date": date_str
                })

    print(f"[*] Tìm thấy {len(matches_data)} trận đấu. Đang tổng hợp kịch bản M3U...")
    
    if not matches_data:
        print("[!] Không tìm thấy danh sách trận đấu. Giữ nguyên M3U hiện tại.")
        sys.exit(1)

    parsed_items = []
    for item in matches_data:
        sub_html = fetch_page(item['url'])
        m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', sub_html) if sub_html else []
        m3u8_url = m3u8_matches[0] if m3u8_matches else ""

        is_currently_live = item['is_live'] or bool(m3u8_url)
        live_prefix = "🟢 " if is_currently_live else ""
        blv_suffix = f" (BLV {item['blv'].title()})" if item['blv'] else ""
        
        full_title = f"{live_prefix}{item['time']} {item['date']} {detect_sport_icon(item['sport'])} {item['teams']}{blv_suffix} [hls]".strip()

        parsed_items.append({
            "title": full_title,
            "logo": get_team_logo_url(item['teams']),
            "url": item['url'],
            "m3u8_url": m3u8_url,
            "is_live": is_currently_live,
            "dt": parse_datetime_obj(item['date'], item['time'], vn_tz)
        })

    parsed_items.sort(key=lambda x: (x['dt'].date(), not x['is_live'], x['dt'].time()))

    final_matches, title_tracker = [], {}
    for p_item in parsed_items:
        raw_title = p_item['title']
        if raw_title in title_tracker:
            title_tracker[raw_title] += 1
            p_item['title'] = f"{raw_title} (SV{title_tracker[raw_title]})"
        else:
            title_tracker[raw_title] = 1
        final_matches.append(p_item)

    print(f"[*] Tiến hành ghi {len(final_matches)} trận vào file {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U tvg-shift="0"\n\n')
        for item in final_matches:
            stream_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}" if item.get('m3u8_url') else f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'{stream_url}\n\n')

    print("[THÀNH CÔNG] File M3U đã được tạo mới đầy đủ danh sách kênh!")

if __name__ == "__main__":
    run_scraper()
    
