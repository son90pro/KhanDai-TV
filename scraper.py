import requests
from bs4 import BeautifulSoup
import re
import datetime

# Danh sách trang web mục tiêu
URLS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandai3.link"
]

M3U_FILE = "khandai.m3u"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

def fetch_html(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Lỗi truy cập {url}: {e}")
        return None

def parse_matches(html, base_url):
    matches = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # CHÚ Ý: Cần thay đổi 'class-ten-tran-dau' bằng class thực tế khi F12 (Inspect) trang web
    match_elements = soup.find_all('div', class_='class-bao-ngoai-moi-tran-dau') 

    for el in match_elements:
        try:
            # 1. Trích xuất thông tin hiển thị
            time_str = el.find('span', class_='class-thoi-gian').text.strip() # VD: 11:00 27/09
            sport_icon = el.find('span', class_='class-icon-the-thao').text.strip() # 🏐 hoặc ⚽
            teams = el.find('span', class_='class-ten-doi').text.strip() # VD: Hàn Quốc vs Philippines
            commentator = el.find('span', class_='class-blv').text.strip() # VD: Lee Sin
            
            match_name = f"{time_str} {sport_icon} {teams} ({commentator}) [hls]"
            
            # Thêm chấm xanh nếu đang Live
            if el.find('span', class_='class-live-badge'):
                match_name = f"🟢 {match_name}"

            # 2. Trích xuất link Logo
            logo_tag = el.find('img', class_='class-logo-img')
            logo_url = logo_tag['src'] if logo_tag else ""
            if logo_url and not logo_url.startswith("http"):
                logo_url = f"{base_url.rstrip('/')}/{logo_url.lstrip('/')}"

            # 3. Trích xuất link m3u8 
            # Tìm link m3u8 trong data-attribute hoặc dùng regex tìm trong toàn bộ HTML của phần tử
            stream_url = ""
            iframe = el.find('iframe')
            if iframe and 'src' in iframe.attrs:
                # Nếu trang dùng iframe, có thể cần request thêm vào src của iframe để lấy link m3u8
                stream_url = iframe['src']
            else:
                m3u8_search = re.search(r'(https?://[^\s"\'<>]+m3u8[^\s"\'<>]*)', str(el))
                if m3u8_search:
                    stream_url = m3u8_search.group(1)

            if stream_url:
                matches.append({
                    "name": match_name,
                    "logo": logo_url,
                    "stream": stream_url,
                    "referrer": base_url
                })
        except AttributeError:
            continue
            
    return matches

def generate_playlist():
    m3u_content = ["#EXTM3U\n\n"]
    
    for url in URLS:
        print(f"Đang xử lý: {url}")
        html = fetch_html(url)
        if html:
            matches = parse_matches(html, url)
            for match in matches:
                # Cấu trúc chuẩn xác theo yêu cầu
                extinf = f'#EXTINF:-1 tvg-logo="{match["logo"]}" group-title="Khán Đài TV" , {match["name"]}\n'
                vlcopt = f'#EXTVLCOPT:http-referrer={match["referrer"]}\n'
                stream = f'{match["stream"]}\n\n'
                m3u_content.extend([extinf, vlcopt, stream])

    # Ghi đè file m3u
    with open(M3U_FILE, "w", encoding="utf-8") as file:
        file.writelines(m3u_content)
    print(f"Hoàn tất tạo {M3U_FILE} vào lúc {datetime.datetime.now()}")

if __name__ == "__main__":
    generate_playlist()
    
