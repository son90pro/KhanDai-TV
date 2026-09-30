import re
import os
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
DOMAINS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandaitv.com",
    "https://khandai.tv",
    "https://khandaitv.net",
    "https://khandai1.com"
]
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
GAVANG_LOGO = "https://i.postimg.cc/6pt402sd/logo-gavangtv.jpg"

COUNTRY_FLAGS = {
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "korea": "kr", "china": "cn", "trung quốc": "cn", "india": "in", "ấn độ": "in", "uzbekistan": "uz",
    "iraq": "iq", "iran": "ir", "saudi arabia": "sa", "ả rập xê út": "sa", "qatar": "qa", "uae": "ae",
    "australia": "au", "úc": "au", "jordan": "jo", "bahrain": "bh", "syria": "sy", "omman": "om",
    "palestine": "ps", "lebanon": "lb", "kuwait": "kw", "yemen": "ye", "kyrgyzstan": "kg", "tajikistan": "tj",
    "timor-leste": "tl", "timor leste": "tl", "hong kong": "hk", "brunei": "bn",
    "slovenia": "si", "scotland": "gb-sct", "england": "gb-eng", "anh": "gb-eng", "wales": "gb-wls",
    "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr", "germany": "de", "đức": "de",
    "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl", "portugal": "pt", "bồ đào nha": "pt",
    "belgium": "be", "bỉ": "be", "croatia": "hr", "denmark": "dk", "đan mạch": "dk", "sweden": "se",
    "norway": "no", "switzerland": "ch", "austria": "at", "poland": "pl", "ba lan": "pl", "ukraine": "ua",
    "czech": "cz", "serbia": "rs", "turkey": "tr", "thổ nhĩ kỳ": "tr", "russia": "ru", "nga": "ru",
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
}

def get_team_logo_url(teams_str: str, img_src: str = "") -> str:
    if img_src and img_src.startswith("http"):
        return img_src
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        if re.search(r'\b' + re.escape(country_name) + r'\b', t_lower):
            return f"https://flagcdn.com/w320/{code}.png"
    return GAVANG_LOGO

def clean_word(w: str) -> str:
    w_low = w.lower()
    if w_low in ['nu', 'nữ', 'women']: return 'Women' if w_low == 'women' else 'Nữ'
    if w_low in ['nam', 'men']: return 'Men' if w_low == 'men' else 'Nam'
    if w_low in ['u23', 'u21', 'u20', 'u19', 'u18', 'u17', 'u16', 'u15']: return w.upper()
    if w_low in ['ir', 'uae', 'usa', 'uk', 'fk', 'ad', 'real', 'as']: return w.upper() if len(w_low) <= 3 else w.capitalize()
    return w.capitalize()

def parse_teams_from_url(url: str, raw_text: str = "") -> str:
    try:
        match = re.search(r'/(?:truc-tiep|match|live|room|xem|phong|link|stream|xem-bong-da|truc-tiep-bong-da)/([^/?#]+)', url)
        slug = match.group(1) if match else next((p for p in url.split('/') if '-vs-' in p), "")
            
        if slug and '-vs-' in slug:
            parts = slug.split('-vs-')
            if len(parts) == 2:
                team1_slug, team2_slug = parts[0], parts[1]
                team1_slug = re.sub(r'^(?:blv-)?(?:ga|caster)-(?:sieu-[a-z0-9]+|[a-z0-9]+)-', '', team1_slug, flags=re.IGNORECASE)
                team1_slug = re.sub(r'^blv-[a-z0-9]+-', '', team1_slug, flags=re.IGNORECASE)
                team2_slug = re.sub(r'-luc-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
                team2_slug = re.sub(r'-ngay-\d+.*$', '', team2_slug, flags=re.IGNORECASE)
                team2_slug = re.sub(r'-\d{3,4}$', '', team2_slug, flags=re.IGNORECASE)

                t1 = " ".join([clean_word(w) for w in team1_slug.split('-') if w])
                t2 = " ".join([clean_word(w) for w in team2_slug.split('-') if w])

                if t1 and t2:
                    return f"{t1} vs {t2}"

        if " vs " in raw_text.lower():
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            for line in lines:
                if " vs " in line.lower():
                    return line
    except Exception:
        pass
    return "Trận đấu Trực Tiếp"

def parse_date_info(url: str, text: str, default_date: str) -> str:
    try:
        date_match = re.search(r'ngay-(\d{1,2})[-_](\d{1,2})', url, re.IGNORECASE)
        if date_match:
            return f"{date_match.group(1).zfill(2)}/{date_match.group(2).zfill(2)}"
        text_date_match = re.search(r'\b(\d{1,2})[/.-](\d{1,2})\b', text)
        if text_date_match:
            return f"{text_date_match.group(1).zfill(2)}/{text_date_match.group(2).zfill(2)}"
    except Exception:
        pass
    return default_date

def parse_time_robust(url: str, text: str) -> str:
    text_time = re.search(r'\b(2[0-3]|[0-1]?\d)[:h](\d{2})\b', text, re.IGNORECASE)
    if text_time:
        return f"{text_time.group(1).zfill(2)}:{text_time.group(2)}"
    url_luc = re.search(r'luc[-_]?(2[0-3]|[0-1]\d)(\d{2})', url, re.IGNORECASE)
    if url_luc:
        return f"{url_luc.group(1).zfill(2)}:{url_luc.group(2)}"
    return "00:00"

def run_scraper():
    vn_tz = timezone(timedelta(hours=7))
    today_str = datetime.now(vn_tz).strftime("%d/%m")
    final_matches = []
    raw_matches = []
    base_domain_used = DOMAINS[0]

    # Duyệt nhanh qua các Domain bằng HTTP GET (Timeout 5 giây)
    for domain in DOMAINS:
        try:
            print(f"[*] Đang cào dữ liệu từ: {domain}")
            res = requests.get(domain, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                seen_urls = set()

                # Tìm tất cả thẻ <a> dẫn tới các trận đấu
                links = soup.find_all('a', href=True)
                for a in links:
                    href = a['href']
                    if any(key in href for key in ['/truc-tiep/', '/match/', '/live/', '/xem/', '/room/', '/phong/', '/truc-tiep-bong-da/', '/xem-bong-da/']):
                        full_url = urljoin(domain, href)
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)

                        # Tìm thẻ chứa thông tin trận đấu
                        card = a.find_parent(class_=re.compile(r'(item|match|card|box)', re.I)) or a
                        card_text = card.get_text(separator=" ", strip=True)

                        img_tag = card.find('img') or a.find('img')
                        img_src = ""
                        if img_tag:
                            img_src = img_tag.get('src') or img_tag.get('data-src') or ""

                        raw_matches.append({
                            'url': full_url,
                            'fullText': card_text,
                            'imgSrc': img_src
                        })

                if raw_matches:
                    print(f"[✅] Lấy thành công {len(raw_matches)} trận từ {domain}")
                    base_domain_used = domain
                    break
        except Exception as e:
            print(f"[❌] Không thể kết nối {domain}: {e}")

    # Bóc tách và định dạng danh sách trận đấu
    for item in raw_matches:
        text, url, img_src = item['fullText'], item['url'], item['imgSrc']
        if not text: continue

        extracted_time = parse_time_robust(url, text)
        match_date = parse_date_info(url, text, today_str)

        clean_blv = ""
        blv_match = re.search(r'((?:Gà|BLV|Caster)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
        if blv_match:
            raw_blv = blv_match.group(1).strip()
            raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
            clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', raw_blv, flags=re.IGNORECASE).strip()

        teams_str = parse_teams_from_url(url, text)
        logo = get_team_logo_url(teams_str, img_src)

        blv_suffix = f" ({clean_blv.title()})" if clean_blv else ""
        full_title = f"{extracted_time} {match_date} ⚽ {teams_str}{blv_suffix} [hls]".strip()

        final_matches.append({
            "title": full_title,
            "logo": logo,
            "url": url
        })

    # Xuất file M3U
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U tvg-shift="0" tvg-logo="{GAVANG_LOGO}" logo="{GAVANG_LOGO}"\n\n')

        if final_matches:
            for item in final_matches:
                logo_attr = f'tvg-logo="{item["logo"]}"'
                stream_url = f"https://{WORKER_DOMAIN}/live?url={quote(item['url'], safe='')}"
                
                f.write(f'#EXTINF:-1 {logo_attr} group-title="{GROUP_NAME}",{item["title"]}\n')
                f.write(f'#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\n')
                f.write(f'#EXTVLCOPT:http-referrer={base_domain_used}/\n')
                f.write(f'{stream_url}\n\n')
        else:
            print("[⚠️] Không lấy được trận nào. Tạo mục chờ...")
            f.write(f'#EXTINF:-1 group-title="{GROUP_NAME}",Đang cập nhật danh sách trận đấu...\n')
            f.write('https://0.0.0.0/offline.m3u8\n')

    print(f"[*] Đã hoàn thành trong vài giây! Xuất {len(final_matches)} trận đấu vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
