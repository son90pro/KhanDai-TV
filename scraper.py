import re
import base64
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

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

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
}

# Biểu tượng môn thể thao
SPORT_ICONS = {
    "bóng đá": "⚽", "bóng chuyền": "🏐", "bóng rổ": "🏀", "bóng bàn": "🏓",
    "billiards": "🎱", "bida": "🎱", "tennis": "🎾", "cầu lông": "🏸"
}

# Danh sách BLV
KNOWN_BLVS = [
    "Chim Nhỏ", "Tày", "Tay", "Lee Sin", "Pháo Thủ", "Kền Kền", "Tiểu Mây", "Enzo",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka"
]

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "thailand": "th", "thái lan": "th",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es",
    "france": "fr", "pháp": "fr", "germany": "de", "đức": "de",
    "italy": "it", "ý": "it", "japan": "jp", "nhật bản": "jp", "korea": "kr", "hàn quốc": "kr"
}

def clean_slug(url):
    match = re.search(r'/(?:truc-tiep|match|live|room|xem)/([^/?#]+)', url)
    if not match: return "", ""
    slug = match.group(1).lower()
    if '-vs-' not in slug: return "", ""
    
    parts = slug.split('-vs-')
    blv = ""
    for b in KNOWN_BLVS:
        b_slug = b.lower().replace(' ', '-')
        if b_slug in slug:
            blv = b
            break
            
    t1 = parts[0].replace('blv-', '').replace('ga-', '').replace('-', ' ').title()
    t2 = re.sub(r'-(?:luc|ngay|\d+h).*$', '', parts[1]).replace('-', ' ').title()
    return f"{t1} vs {t2}", blv

def get_flag(team_name):
    t_low = team_name.lower()
    for name, code in COUNTRY_FLAGS.items():
        if name in t_low:
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_FLAG

def extract_m3u8_from_html(html_content, base_url):
    """Trích xuất link m3u8 từ mã nguồn HTML hoặc JS"""
    # 1. Tìm trực tiếp đuôi .m3u8
    m3u8_links = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html_content)
    for link in m3u8_links:
        if "blob:" not in link:
            return link
            
    # 2. Tìm link bị mã hóa Base64 (phổ biến ở các trang trực tiếp)
    b64_list = re.findall(r'aHR0cD[a-zA-Z0-9+/=]+', html_content)
    for b64 in b64_list:
        try:
            decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
            if ".m3u8" in decoded:
                return decoded
        except:
            continue

    # 3. Tìm iframe chứa luồng phát
    iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    for iframe in iframes:
        if not iframe.startswith('http'):
            iframe = "https:" + iframe if iframe.startswith('//') else base_url + iframe
        try:
            iframe_res = requests.get(iframe, headers=HEADERS, timeout=8)
            links = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', iframe_res.text)
            if links:
                return links[0]
        except:
            pass
            
    return ""

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    
    matches = []
    active_domain = DOMAINS[0]

    for domain in DOMAINS:
        print(f"[*] Đang tải dữ liệu từ: {domain}")
        try:
            res = requests.get(domain, headers=HEADERS, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                seen = set()
                for a in links:
                    href = a['href']
                    if not re.search(r'/(truc-tiep|match|live|room|xem)/', href):
                        continue
                    
                    full_url = href if href.startswith('http') else domain.rstrip('/') + '/' + href.lstrip('/')
                    if full_url in seen: continue
                    seen.add(full_url)

                    teams, blv = clean_slug(full_url)
                    text = a.get_text(strip=True)
                    if not teams:
                        if "VS" in text.upper(): teams = text
                        else: continue

                    # Bỏ qua các link rác
                    if any(jk in teams.lower() for jk in ["bxh", "nhà cái", "tin tức", "lịch thi đấu"]):
                        continue

                    blv_str = f" ({blv})" if blv else ""
                    sport_icon = "⚽"
                    title = f"🟢 19:30 {today_str} {sport_icon} {teams}{blv_str} [hls]"
                    logo = get_flag(teams)

                    matches.append({
                        "title": title,
                        "logo": logo,
                        "url": full_url
                    })
                
                if matches:
                    active_domain = domain
                    print(f"[+] Tìm thấy {len(matches)} trận đấu!")
                    break
        except Exception as e:
            print(f"[!] Lỗi kết nối {domain}: {e}")

    parsed_items = []
    
    print(f"[*] Đang bóc tách luồng m3u8 cực nhanh...")
    for item in matches:
        match_url = item["url"]
        title = item["title"]
        try:
            # Tải trang trận đấu
            page_res = requests.get(match_url, headers=HEADERS, timeout=10)
            m3u8_url = extract_m3u8_from_html(page_res.text, active_domain)
            
            # Nếu tìm thấy m3u8 thì dùng, không thì dùng link gốc (Để đảm bảo luôn có data)
            final_play_url = m3u8_url if m3u8_url else match_url
            
            parsed_items.append({
                "title": title,
                "logo": item["logo"],
                "play_url": final_play_url
            })
            print(f"[✓] Xử lý xong: {title}")
        except Exception as e:
            print(f"[x] Lỗi khi bóc tách {title}: {e}")

    # Ghi file M3U
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        
        # Kênh dự phòng: Đảm bảo file KHÔNG BAO GIỜ RỖNG 9 BYTES
        if not parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{DEFAULT_FLAG}" group-title="Hệ Thống", [!] Đang cập nhật trận đấu mới hoặc web bảo trì\n')
            f.write(f'{active_domain}\n\n')
        else:
            for item in parsed_items:
                play_url = item["play_url"]
                # Thêm Header Pipe (|) để xem mượt trên IPTV
                if ".m3u8" in play_url and "|" not in play_url:
                    stream_entry = f"{play_url}|User-Agent={USER_AGENT}&Referer={active_domain}/"
                else:
                    stream_entry = play_url

                f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}" http-user-agent="{USER_AGENT}" http-referrer="{active_domain}/", {item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                f.write(f'#EXTVLCOPT:http-referrer={active_domain}/\n')
                f.write(f'{stream_entry}\n\n')

    print(f"[*] Hoàn thành! Đã xuất file {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
