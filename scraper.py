import re
import unicodedata
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

DOMAINS = [
    "https://khandai1.link",
    "https://khandai.link",
    "https://khandai.tv"
]

OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
DEFAULT_LOGO = "https://flagcdn.com/w320/un.png"

KNOWN_BLVS = [
    "Tày", "Lee Sin", "Pháo Thủ", "Enzo", "Kền Kền", "Chim Nhỏ", "Tiểu Mây",
    "KaKa", "Giga", "Sư Tử", "Voi Con", "Gà Rừng", "Hắc Cáo", "Lão Đại", "Táo Quân",
    "Bắp Cày", "Rồng Vàng", "Cú Mèo", "Sóc Nâu", "Khỉ Vàng", "Cá Chép",
    "Trâu Chiến", "Đèn Mờ", "Khám Phá", "Tên Sát", "Batman", "Spider", "Suka"
]

COUNTRY_FLAGS = {
    "viet nam": "vn", "vietnam": "vn", "việt nam": "vn", 
    "philippines": "ph", "thailand": "th", "thai lan": "th", "thái lan": "th",
    "slovenia": "si", "scotland": "gb-sct", "finland": "fi", "phan lan": "fi", "phần lan": "fi",
    "kuwait": "kw", "iraq": "iq", "bulgaria": "bg", "luxembourg": "lu",
    "indonesia": "id", "malaysia": "my", "singapore": "sg", "japan": "jp", "nhat ban": "jp", "nhật bản": "jp",
    "south korea": "kr", "han quoc": "kr", "hàn quốc": "kr", "china": "cn", "trung quoc": "cn", "trung quốc": "cn",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tay ban nha": "es", "tây ban nha": "es",
    "france": "fr", "phap": "fr", "pháp": "fr", "germany": "de", "duc": "de", "đức": "de", 
    "italy": "it", "y": "it", "ý": "it", "usa": "us", "my": "us", "mỹ": "us"
}

def to_slug(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.lower().replace('đ', 'd')
    return re.sub(r'[^a-z0-9]', '', text)

def parse_blv(text: str) -> str:
    if not text: return ""
    text_low = text.lower()
    for b in KNOWN_BLVS:
        if b.lower() in text_low or to_slug(b) in text_low:
            return b
    return ""

def get_match_logo(teams_str: str) -> str:
    t_low = teams_str.lower()
    parts = re.split(r'\s+vs\s+', t_low, flags=re.IGNORECASE)
    t1 = parts[0] if len(parts) > 0 else t_low
    
    for country, code in COUNTRY_FLAGS.items():
        if country in t1: 
            return f"https://flagcdn.com/w320/{code}.png"
    for country, code in COUNTRY_FLAGS.items():
        if country in t_low: 
            return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def extract_teams_from_url(url: str) -> str:
    slug = url.split('/')[-1]
    slug = re.sub(r'(\?.*|#.*)$', '', slug)
    
    if '-vs-' in slug:
        parts = slug.split('-vs-')
        team1 = parts[0].replace('-', ' ').title()
        team2 = parts[1].replace('-', ' ').title()
        return f"{team1} vs {team2}"
    elif slug:
        return slug.replace('-', ' ').title()
    return "Trận đấu Trực Tiếp"

def resolve_m3u8_link(session, match_url, base_domain):
    """
    Truy cập sâu vào trang trận đấu để lấy link stream .m3u8
    """
    try:
        res = session.get(match_url, timeout=8)
        if res.status_code == 200:
            html = res.text
            
            # 1. Tìm m3u8 trực tiếp trong nguồn JS
            m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            for url in m3u8_matches:
                url_clean = url.replace('\\', '')
                if "advertisement" not in url_clean and "qc" not in url_clean:
                    return url_clean

            # 2. Tìm trong iframe nhúng player
            iframe_m = re.search(r'iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if iframe_m:
                iframe_url = iframe_m.group(1)
                if not iframe_url.startswith('http'):
                    iframe_url = f"{base_domain.rstrip('/')}/{iframe_url.lstrip('/')}"
                
                res_iframe = session.get(iframe_url, headers={"Referer": match_url}, timeout=6)
                if res_iframe.status_code == 200:
                    m3u8_in_iframe = re.findall(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', res_iframe.text)
                    for url in m3u8_in_iframe:
                        url_clean = url.replace('\\', '')
                        if "advertisement" not in url_clean:
                            return url_clean
    except Exception:
        pass

    # Dự phòng dạng luồng HLS chuẩn của hệ thống Khán Đài
    slug = match_url.split('/')[-1]
    return f"https://stream.khandai.link/hls/{slug}/playlist.m3u8"

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    })

    parsed_items = []
    seen_keys = set()
    working_domain = DOMAINS[0]

    soup = None
    for domain in DOMAINS:
        try:
            res = session.get(domain, timeout=10)
            if res.status_code == 200 and len(res.text) > 500:
                soup = BeautifulSoup(res.text, 'html.parser')
                working_domain = domain
                print(f"[+] Kết nối thành công: {domain}")
                break
        except Exception:
            continue

    if soup:
        for a in soup.find_all('a', href=True):
            href = a['href']
            if not ('truc-tiep' in href or 'match' in href):
                continue

            full_url = href if href.startswith('http') else f"{working_domain.rstrip('/')}/{href.lstrip('/')}"
            text = a.get_text(separator=' ', strip=True)

            teams = extract_teams_from_url(full_url)
            
            match_time = "19:30"
            time_m = re.search(r'\b([0-2]?\d)[h:](\d{2})\b', text)
            if time_m:
                match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

            blv = parse_blv(text) or parse_blv(full_url)
            blv_name = f" ({blv})" if blv else " (Khán Đài TV)"

            dedup_key = f"{teams}_{match_time}_{blv}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            logo = get_match_logo(teams)
            title = f"🟢 {match_time} {today_str} ⚽ {teams}{blv_name} [FHD] [hls]"
            
            # Lấy luồng m3u8
            stream_url = resolve_m3u8_link(session, full_url, working_domain)

            parsed_items.append({
                "title": title,
                "logo": logo,
                "stream_url": stream_url,
                "page_url": full_url
            })

    # Nếu không lấy được trang chủ, dùng danh sách dự phòng trận HOT
    if not parsed_items:
        hot_matches = [
            ("Viet Nam vs Philippines", "19:30", "Tay", "viet-nam-vs-philippines"),
            ("Slovenia vs Scotland", "20:00", "Phao Thu", "slovenia-vs-scotland"),
            ("Imoco vs Novara", "20:30", "Enzo", "imoco-vs-novara"),
            ("Phan Lan vs Slovenia", "22:00", "Tay", "phan-lan-vs-slovenia")
        ]
        for teams, m_time, blv, slug in hot_matches:
            parsed_items.append({
                "title": f"🟢 {m_time} {today_str} ⚽ {teams} ({blv}) [FHD] [hls]",
                "logo": get_match_logo(teams),
                "stream_url": f"https://stream.khandai.link/hls/{slug}/playlist.m3u8",
                "page_url": f"{working_domain}/truc-tiep/{slug}"
            })

    # Xuất file playlist.m3u với bộ Header tối ưu vượt tường rào TiviMate
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            # Khai báo Header toàn cục cho từng kênh
            f.write(f'#EXTVLCOPT:http-referrer={item["page_url"]}\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            f.write(f'#EXTHTTP:{{"Referer":"{item["page_url"]}","Origin":"{working_domain}","User-Agent":"{USER_AGENT}"}}\n')
            # Nối tham số Referer & Origin vào trực tiếp URL
            f.write(f"{item['stream_url']}|Referer={item['page_url']}&Origin={working_domain}&User-Agent={USER_AGENT}\n\n")

    print(f"[*] Đã xuất {len(parsed_items)} trận đấu vào file {OUTPUT_FILE}.")

if __name__ == "__main__":
    run_scraper()
    
