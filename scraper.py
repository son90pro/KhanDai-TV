import os
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from playwright.sync_api import sync_playwright

WORKER_DOMAIN = "chuoi-chien-iptv.sonnguyen90pro.workers.dev"
DOMAINS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandaitv.com",
    "https://khandai.tv",
    "https://khandaitv.net"
]
OUTPUT_FILE = "playlist.m3u"
GROUP_NAME = "Khán Đài TV"
GAVANG_LOGO = "https://i.postimg.cc/6pt402sd/logo-gavangtv.jpg"

# Từ điển cờ TẤT CẢ quốc gia & vùng lãnh thổ trên thế giới (Tiếng Anh & Tiếng Việt)
COUNTRY_FLAGS = {
    # Châu Á & Đông Nam Á
    "vietnam": "vn", "việt nam": "vn", "philippines": "ph", "thailand": "th", "thái lan": "th",
    "pakistan": "pk", "indonesia": "id", "malaysia": "my", "singapore": "sg", "myanmar": "mm",
    "cambodia": "kh", "laos": "la", "japan": "jp", "nhật bản": "jp", "south korea": "kr", "hàn quốc": "kr",
    "korea": "kr", "china": "cn", "trung quốc": "cn", "india": "in", "ấn độ": "in", "uzbekistan": "uz",
    "iraq": "iq", "iran": "ir", "saudi arabia": "sa", "ả rập xê út": "sa", "qatar": "qa", "uae": "ae",
    "australia": "au", "úc": "au", "jordan": "jo", "bahrain": "bh", "syria": "sy", "omman": "om",
    "palestine": "ps", "lebanon": "lb", "kuwait": "kw", "yemen": "ye", "kyrgyzstan": "kg", "tajikistan": "tj",
    "timor-leste": "tl", "timor leste": "tl", "hong kong": "hk", "brunei": "bn",

    # Châu Âu
    "slovenia": "si", "scotland": "gb-sct", "england": "gb-eng", "anh": "gb-eng", "wales": "gb-wls",
    "northern ireland": "gb-nir", "spain": "es", "tây ban nha": "es", "france": "fr", "pháp": "fr",
    "germany": "de", "đức": "de", "italy": "it", "ý": "it", "netherlands": "nl", "hà lan": "nl",
    "portugal": "pt", "bồ đào nha": "pt", "belgium": "be", "bỉ": "be", "croatia": "hr", "denmark": "dk",
    "đan mạch": "dk", "sweden": "se", "thụy điển": "se", "norway": "no", "nau uy": "no", "switzerland": "ch",
    "thụy sĩ": "ch", "austria": "at", "áo": "at", "poland": "pl", "ba lan": "pl", "ukraine": "ua",
    "czech": "cz", "séc": "cz", "serbia": "rs", "turkey": "tr", "thổ nhĩ kỳ": "tr", "russia": "ru", "nga": "ru",
    "greece": "gr", "hy lạp": "gr", "romania": "ro", "hungary": "hu", "slovakia": "sk", "finland": "fi",
    " phần lan": "fi", "ireland": "ie", "iceland": "is", "albania": "al", "bosnia": "ba", "macedonia": "mk",
    "georgia": "ge", "armenia": "am", "azerbaijan": "az", "cyprus": "cy", "estonia": "ee", "latvia": "lv",
    "lithuania": "lt", "luxembourg": "lu", "malta": "mt", "moldova": "md", "montenegro": "me", "san marino": "sm",

    # Châu Phi
    "south africa": "za", "nam phi": "za", "guinea": "gn", "equatorial guinea": "gq", "kenya": "ke",
    "eritrea": "er", "egypt": "eg", "ai cập": "eg", "morocco": "ma", "ma rốc": "ma", "senegal": "sn",
    "algeria": "dz", "nigeria": "ng", "cameroon": "cm", "ghana": "gh", "ivory coast": "ci", "bờ biển ngà": "ci",
    "tunisia": "tn", "mali": "ml", "burkina faso": "bf", "congo": "cg", "dr congo": "cd", "zambia": "zm",
    "gabon": "ga", "angola": "ao", "uganda": "ug", "mozambique": "mz", "madagascar": "mg", "sudan": "sd",

    # Bắc, Trung Mỹ & CONCACAF
    "usa": "us", "mỹ": "us", "mexico": "mx", "canada": "ca", "costa rica": "cr", "panama": "pa",
    "jamaica": "jm", "honduras": "hn", "el salvador": "sv", "guatemala": "gt", "haiti": "ht",
    "trinidad": "tt", "martinique": "mq", "curacao": "cw", "barbados": "bb", "saint lucia": "lc",

    # Nam Mỹ
    "brazil": "br", "argentina": "ar", "uruguay": "uy", "colombia": "co", "chile": "cl",
    "peru": "pe", "ecuador": "ec", "paraguay": "py", "venezuela": "ve", "bolivia": "bo"
}

def get_team_logo_url(teams_str: str, img_src: str = "") -> str:
    """Tự động lấy Cờ quốc gia từ tên đội hoặc từ thẻ img gốc của trang"""
    if img_src and img_src.startswith("http"):
        return img_src
        
    t_lower = teams_str.lower()
    for country_name, code in COUNTRY_FLAGS.items():
        pattern = r'\b' + re.escape(country_name) + r'\b'
        if re.search(pattern, t_lower):
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

        # Trích xuất từ text nếu URL slug không thành công
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

    url_luc_4 = re.search(r'luc[-_]?(2[0-3]|[0-1]\d)(\d{2})', url, re.IGNORECASE)
    if url_luc_4:
        return f"{url_luc_4.group(1).zfill(2)}:{url_luc_4.group(2)}"

    return "00:00"

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
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            timezone_id="Asia/Ho_Chi_Minh",
            locale="vi-VN"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        raw_matches = []
        base_domain_used = DOMAINS[0]

        # Thử lần lượt các Domain dự phòng
        for domain in DOMAINS:
            try:
                print(f"[*] Đang kết nối tới: {domain}")
                page.goto(domain, timeout=35000, wait_until="domcontentloaded")
                time.sleep(3)

                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 600)")
                    time.sleep(0.3)

                # Trích xuất tất cả các ô trận đấu
                raw_matches = page.evaluate('''() => {
                    const matches = [];
                    const links = Array.from(document.querySelectorAll('a[href*="/truc-tiep/"], a[href*="/match/"], a[href*="/live/"], a[href*="/xem/"], a[href*="/room/"], a[href*="/phong/"], a[href*="/truc-tiep-bong-da/"], a[href*="/xem-bong-da/"]'));
                    const seenUrls = new Set();

                    links.forEach(link => {
                        const href = link.getAttribute('href');
                        if (!href) return;

                        const fullUrl = href.startsWith('http') ? href : window.location.origin + href;
                        if (seenUrls.has(fullUrl)) return;
                        seenUrls.add(fullUrl);

                        let card = link;
                        let parent = link.parentElement;
                        while (parent && parent.tagName !== 'BODY') {
                            if (parent.querySelectorAll('a').length === 1) {
                                card = parent;
                                parent = parent.parentElement;
                            } else {
                                break;
                            }
                        }

                        const imgEl = card ? card.querySelector('img') : link.querySelector('img');
                        let imgSrc = '';
                        if (imgEl) {
                            imgSrc = imgEl.getAttribute('src') || imgEl.getAttribute('data-src') || '';
                        }

                        matches.push({
                            url: fullUrl,
                            fullText: card ? card.innerText || '' : link.innerText || '',
                            imgSrc: imgSrc
                        });
                    });

                    return matches;
                }''')

                if raw_matches:
                    print(f"[✅] Lấy thành công {len(raw_matches)} trận từ {domain}")
                    base_domain_used = domain
                    break
            except Exception as e:
                print(f"[❌] Lỗi kết nối {domain}: {e}")

        page.close()

        # Bóc tách và định dạng chuẩn giao diện mẫu
        for item in raw_matches:
            text, url, img_src = item['fullText'], item['url'], item['imgSrc']
            if not text: continue

            extracted_time = parse_time_robust(url, text)
            match_date = parse_date_info(url, text, today_str)

            # Lấy thông tin Bình luận viên
            clean_blv = ""
            blv_match = re.search(r'((?:Gà|BLV|Caster)\s+[A-Za-zÀ-ỹ0-9\s\+]+)', text, re.IGNORECASE)
            if blv_match:
                raw_blv = blv_match.group(1).strip()
                raw_blv = re.split(r'(?:hls|flv|live|trực tiếp|\d{1,2}:\d{2}|hiệp|cúp|league)', raw_blv, flags=re.IGNORECASE)[0].strip()
                clean_blv = re.sub(r'^(BLV|Caster)\s*[:\-]?\s*', '', raw_blv, flags=re.IGNORECASE).strip()

            teams_str = parse_teams_from_url(url, text)
            logo = get_team_logo_url(teams_str, img_src)

            blv_suffix = f" ({clean_blv.title()})" if clean_blv else ""
            
            # Tiêu đề hiển thị chuẩn định dạng mẫu: HH:MM DD/MM ⚽ Đội 1 vs Đội 2 (BLV) [hls]
            full_title = f"{extracted_time} {match_date} ⚽ {teams_str}{blv_suffix} [hls]".strip()

            final_matches.append({
                "title": full_title,
                "logo": logo,
                "url": url
            })

        browser.close()

    # Xuất danh sách file M3U Playlist
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
            print("[⚠️] Không thể cào dữ liệu. Xuất thông báo mặc định.")
            f.write(f'#EXTINF:-1 group-title="{GROUP_NAME}",Đang cập nhật danh sách trận đấu...\n')
            f.write('https://0.0.0.0/offline.m3u8\n')

    print(f"[*] Đã hoàn tất! Xuất {len(final_matches)} trận đấu vào {OUTPUT_FILE}")

if __name__ == "__main__":
    run_scraper()
    
