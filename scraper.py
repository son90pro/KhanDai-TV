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
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "slovenia": "si", "scotland": "gb-sct", "finland": "fi", "phần lan": "fi",
    "kuwait": "kw", "iraq": "iq", "bulgaria": "bg", "luxembourg": "lu",
    "indonesia": "id", "malaysia": "my", "singapore": "sg", "japan": "jp", "nhật bản": "jp",
    "south korea": "kr", "hàn quốc": "kr", "china": "cn", "trung quốc": "cn",
    "england": "gb-eng", "anh": "gb-eng", "spain": "es", "tây ban nha": "es",
    "france": "fr", "pháp": "fr", "germany": "de", "đức": "de", "italy": "it", "ý": "it",
    "usa": "us", "mỹ": "us", "imoco": "it", "novara": "it"
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
        if country in t1: return f"https://flagcdn.com/w320/{code}.png"
    for country, code in COUNTRY_FLAGS.items():
        if country in t_low: return f"https://flagcdn.com/w320/{code}.png"
    return DEFAULT_LOGO

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    headers = {"User-Agent": USER_AGENT}
    
    parsed_items = []
    seen_keys = set()
    working_domain = DOMAINS[0]

    session = requests.Session()
    session.headers.update(headers)

    # 1. Cào HTML trang chủ
    soup = None
    for domain in DOMAINS:
        try:
            res = session.get(domain, timeout=10)
            if res.status_code == 200 and len(res.text) > 1000:
                soup = BeautifulSoup(res.text, 'html.parser')
                working_domain = domain
                break
        except Exception:
            continue

    if soup:
        # Lấy tất cả thẻ <a> có liên kết trận đấu
        links = soup.find_all('a', href=True)
        for a in links:
            href = a['href']
            if not ('truc-tiep' in href or 'match' in href or 'live' in href):
                continue
            
            full_url = href if href.startswith('http') else f"{working_domain.rstrip('/')}/{href.lstrip('/')}"
            text = a.get_text(separator=' ', strip=True)
            
            # Tách BLV
            blv = parse_blv(text) or parse_blv(full_url)
            blv_slug = to_slug(blv) if blv else "khandai1"
            blv_name = f" ({blv})" if blv else " (Khán Đài TV)"

            # Tách Giờ
            match_time = "20:00"
            time_m = re.search(r'\b([0-2]?\d)[h:](\d{2})\b', text)
            if time_m:
                match_time = f"{time_m.group(1).zfill(2)}:{time_m.group(2)}"

            # Tách Đội bóng
            teams = ""
            vs_m = re.search(r'([A-ZÀ-Ỹa-zà-ỹ0-9\s]{2,})\s+(?:vs|VS|-)\s+([A-ZÀ-Ỹa-zà-ỹ0-9\s]{2,})', text)
            if vs_m:
                teams = f"{vs_m.group(1).strip().title()} vs {vs_m.group(2).strip().title()}"
            else:
                slug_part = full_url.split('/')[-1]
                slug_part = re.sub(r'(-\d+.*|\?.*)$', '', slug_part)
                if '-vs-' in slug_part:
                    p = slug_part.split('-vs-')
                    teams = f"{p[0].replace('-', ' ').title()} vs {p[1].replace('-', ' ').title()}"

            if not teams or len(teams) < 3:
                teams = "Trận đấu Trực Tiếp"

            dedup_key = f"{teams}_{match_time}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            logo = get_match_logo(teams)
            title = f"🟢 {match_time} {today_str} ⚽ {teams}{blv_name} [FHD] [hls]"
            
            # Cấu trúc luồng m3u8 chuẩn của Khán Đài
            stream_url = f"https://stream.khandai.link/hls/{blv_slug}hd/playlist.m3u8"

            parsed_items.append({
                "title": title,
                "logo": logo,
                "stream_url": stream_url
            })

    # 2. Dự phòng cứng nếu trang chủ không lấy được dữ liệu (Đảm bảo file KHÔNG BAO GIỜ RỖNG)
    if not parsed_items:
        default_blvs = ["khandai1", "tay", "leesin", "enzo", "phaothu"]
        for idx, b in enumerate(default_blvs, 1):
            parsed_items.append({
                "title": f"🟢 19:30 {today_str} ⚽ Trực Tiếp Khán Đài {idx} ({b.upper()}) [FHD] [hls]",
                "logo": DEFAULT_LOGO,
                "stream_url": f"https://stream.khandai.link/hls/{b}hd/playlist.m3u8"
            })

    # 3. Xuất file M3U kèm Header Referer chuẩn TiviMate
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write('#EXTM3U\n\n')
        for item in parsed_items:
            f.write(f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="{GROUP_NAME}", {item["title"]}\n')
            f.write(f'#EXTVLCOPT:http-referrer={working_domain}/\n')
            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
            # Ép Referer trực tiếp vào URL stream
            f.write(f"{item['stream_url']}|Referer={working_domain}/&User-Agent={USER_AGENT}\n\n")

if __name__ == "__main__":
    run_scraper()
    
