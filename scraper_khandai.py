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
    "austria": "at", "kosovo": "xk", "denmark": "dk", "wales": "gb-wls", "serbia": "rs", "ireland": "ie"
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
    print(f"[*] Đang tải: {target_url}")
    scraper = create_cf_scraper()
    try:
        res = scraper.get(target_url, timeout=12)
        if res.status_code == 200 and len(res.text) > 500 and "Just a moment" not in res.text:
            return res.text
    except Exception as e:
        print(f"  -> Lỗi kết nối direct: {e}")

    proxy_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(target_url, safe='')}"
    try:
        res = requests.get(proxy_url, timeout=12)
        if res.status_code == 200 and len(res.text) > 500:
            return res.text
    except Exception as e:
        print(f"  -> Lỗi qua Worker: {e}")

    return ""

def get_team_logo_url(teams_str: str) -> str:
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        if re.search(r'\b' + re.escape(country_name) + r'\b', t_lower):
            return f"https://flagcdn.com/w320/{code}.png"

    clean_title = re.sub(r'\b(vs|v|nữ|women|u23|u21|u19|u17)\b', '', teams_str, flags=re.IGNORECASE)
    words = [w[0].upper() for w in clean_title.split() if w and w[0].isalnum()]
    initials = "".join(words[:3]) if words else "KD"
    return f"https://ui-avatars.com/api/?name={initials}&background=random&color=fff&size=256&bold=true&length=3"

def detect_sport_icon(text: str) -> str:
    t_low = text.lower()
    if any(k in t_low for k in ["bóng chuyền", "volleyball"]): return "🏐"
    if any(k in t_low for k in ["bóng rổ", "basketball"]): return "🏀"
    if any(k in t_low for k in ["quần vợt", "tennis"]): return "🎾"
    if any(k in t_low for k in ["cầu lông", "badminton"]): return "🏸"
    return "⚽"

def clean_match_title(title_raw: str) -> str:
    # Lọc bỏ ID số ngẫu nhiên ở cuối URL/Tiêu đề
    clean = re.sub(r'\d{6,}$', '', title_raw).strip()
    clean = re.sub(r'\d{1,2}\s+\d{1,2}\s+\d{4}', '', clean).strip()
    clean = re.sub(r'\s+', ' ', clean)
    return clean

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
            print(f"[+] KẾT NỐI THÀNH CÔNG VỚI: {domain}")
            break

    if not html_content:
        print("[!] Không thể truy cập trang web. Dừng tiến trình.")
        sys.exit(1)

    soup = BeautifulSoup(html_content, 'html.parser')
    matches_data = []
    seen_urls = set()

    # Phân tích NextJS JSON data nếu có
    next_data_tag = soup.find('script', id='__NEXT_DATA__')
    if next_data_tag and next_data_tag.string:
        try:
            data = json.loads(next_data_tag.string)
            page_props = data.get('props', {}).get('pageProps', {})
            match_list = page_props.get('matches', []) or page_props.get('data', []) or page_props.get('liveMatches', [])
            
            for item in match_list:
                if isinstance(item, dict):
                    slug = item.get('slug', '') or item.get('id', '')
                    match_url = urljoin(working_domain, f"/truc-tiep/{slug}" if not str(slug).startswith('http') else str(slug))
                    
                    if match_url in seen_urls: continue
                    seen_urls.add(match_url)

                    home = item.get('homeTeam', {}).get('name', '') or item.get('home_name', '')
                    away = item.get('awayTeam', {}).get('name', '') or item.get('away_name', '')
                    teams = f"{home} vs {away}" if home and away else item.get('title', 'Trận đấu Trực Tiếp')
                    
                    blv = item.get('commentator', '') or item.get('blv', '') or item.get('caster', '')
                    
                    matches_data.append({
                        "url": match_url,
                        "teams": clean_match_title(teams),
                        "blv": str(blv).strip(),
                        "sport": item.get('sport', ''),
                        "time": item.get('time', '00:00'),
                        "date": item.get('date', today_str)
                    })
        except Exception as e:
            print(f"[-] Lỗi bóc JSON: {e}")

    # Nếu không parse được JSON, tự động bóc HTML DOM
    if not matches_data:
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/truc-tiep/' in href or '-vs-' in href:
                full_url = urljoin(working_domain, href)
                if full_url in seen_urls or full_url == working_domain + '/': continue
                seen_urls.add(full_url)

                text = a.get_text(separator=' ', strip=True)
                if a.parent: text += " " + a.parent.get_text(separator=' ', strip=True)

                # Tìm BLV
                blv_match = re.search(r'(?:BLV|Caster|Kênh)\s*([A-Za-z0-9_À-ỹ]+)', text, re.IGNORECASE)
                blv_name = blv_match.group(1) if blv_match else ""

                # Tìm thời gian
                time_match = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', text)
                time_str = f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else "00:00"

                # Trích xuất tên hai đội từ slug URL để làm sạch tên
                teams_name = "Trận đấu Trực Tiếp"
                slug_match = re.search(r'/([^/?#]+-vs-[^/?#]+)', href)
                if slug_match:
                    raw_slug = slug_match.group(1)
                    # Loại bỏ ID chuỗi số rác phía cuối slug
                    raw_slug = re.sub(r'-\d+$', '', raw_slug)
                    parts = raw_slug.split('-vs-')
                    if len(parts) == 2:
                        t1 = ' '.join(parts[0].split('-')).title()
                        t2 = ' '.join(parts[1].split('-')).title()
                        teams_name = f"{t1} vs {t2}"

                matches_data.append({
                    "url": full_url,
                    "teams": clean_match_title(teams_name),
                    "blv": blv_name,
                    "sport": text,
                    "time": time_str,
                    "date": today_str
                })

    print(f"[*] Đã lọc được {len(matches_data)} trận đấu. Bắt đầu lấy link luồng phát trực tiếp...")
    
    final_matches = []
    for item in matches_data:
        sub_html = fetch_page(item['url'])
        m3u8_url = ""
        
        if sub_html:
            # Tìm link HLS m3u8 trong mã nguồn trang chi tiết
            m3u8_matches = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', sub_html)
            if m3u8_matches:
                m3u8_url = m3u8_matches[0]
            
            # Cập nhật tên BLV nếu phát hiện thêm trong trang chi tiết
            if not item['blv']:
                blv_in_page = re.search(r'(?:BLV|Caster)\s*([A-Za-z0-9_À-ỹ]+)', sub_html, re.IGNORECASE)
                if blv_in_page:
                    item['blv'] = blv_in_page.group(1)

        is_live = bool(m3u8_url)
        live_prefix = "🟢 " if is_live else "⚪ "
        blv_suffix = f" (BLV {item['blv'].title()})" if item['blv'] else ""
        
        full_title = f"{live_prefix}{item['time']} {item['date']} {detect_sport_icon(item['sport'])} {item['teams']}{blv_suffix}"

        final_matches.append({
            "title": full_title,
            "logo": get_team_logo_url(item['teams']),
            "url": item['url'],
            "m3u8_url": m3u8_url
        })

    print(f"[*] Đang ghi {len(final_matches)} kênh vào file {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U tvg-shift="0"\n\n')
        for item in final_matches:
            # Ưu tiên phát qua link M3U8 trực tiếp nếu bóc tách được
            if item['m3u8_url']:
                stream_url = f"https://{WORKER_DOMAIN}/proxy?url={quote(item['m3u8_url'], safe='')}"
            else:
                stream_url = f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"

            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}",{item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'{stream_url}\n\n')

    print("[THÀNH CÔNG] Đã cập nhật xong file M3U chuẩn!")

if __name__ == "__main__":
    run_scraper()
    
