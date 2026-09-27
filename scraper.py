import cloudscraper
from bs4 import BeautifulSoup
import re
import datetime

# Danh sách các link dự phòng nếu trang chính bị sập
BASE_URLS = [
    "https://khandai1.link", 
    "https://khandai2.link", 
    "https://khandai3.link"
]
M3U_FILE = "khandai.m3u"

def get_matches():
    m3u_lines = ["#EXTM3U\n\n"]
    match_links = set()
    
    # Khởi tạo công cụ vượt tường lửa Cloudflare
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome', 
            'platform': 'windows', 
            'desktop': True
        }
    )
    
    working_url = None
    
    # 1. Tìm trang chủ nào đang hoạt động và lấy link trận đấu
    for url in BASE_URLS:
        print(f"Đang thử kết nối trang chủ: {url}...")
        try:
            res = scraper.get(url, timeout=15)
            if res.status_code == 200:
                working_url = url
                print("✅ Kết nối thành công!")
                
                soup = BeautifulSoup(res.text, 'html.parser')
                # Tìm mọi thẻ link có chứa chữ 'truc-tiep'
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '/truc-tiep/' in href:
                        full_link = href if href.startswith("http") else f"{working_url.rstrip('/')}/{href.lstrip('/')}"
                        match_links.add(full_link)
                break # Tìm được web sống thì dừng thử các link khác
        except Exception as e:
            print(f"❌ Không thể truy cập {url}: {e}")
            
    if not match_links:
        print("⚠️ Không tìm thấy link trận đấu nào! Ghi file rỗng để tránh lỗi GitHub Actions.")
        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.writelines(m3u_lines)
        return

    print(f"🔎 Đã gom được {len(match_links)} link trận đấu. Bắt đầu chui vào từng link...")
    
    # 2. Bóc tách chi tiết từng trận đấu
    for link in match_links:
        print(f"\nĐang quét: {link}")
        try:
            res = scraper.get(link, timeout=15)
            if res.status_code != 200:
                print("❌ Lỗi tải trang chi tiết.")
                continue
                
            html = res.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Bóc tách tên trận đấu
            title_text = soup.title.text if soup.title else "Trận đấu đang cập nhật"
            match_name = title_text.replace("Trực tiếp", "").replace("Khán Đài TV", "").replace("|", "").strip()
            
            # Bóc tách Logo từ thẻ meta
            logo_url = "https://khandai1.link/media/teams/logos/default.png"
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                logo_url = og_image['content']
                
            # Lưới lọc Regex tóm link m3u8
            m3u8_url = None
            m3u8_match = re.search(r'(https?://[^"\'\s<>]+?\.m3u8[^"\'\s<>]*)', html)
            
            if m3u8_match:
                m3u8_url = m3u8_match.group(1).replace('\\/', '/')
            else:
                # Tìm thử trong iframe dự phòng
                iframe = soup.find('iframe')
                if iframe and 'src' in iframe.attrs and 'm3u8' in iframe['src']:
                    m3u8_url = iframe['src']
                    
            # Ghi chuẩn M3U
            if m3u8_url:
                print(f"✅ ĐÃ CHỘP ĐƯỢC LINK: {m3u8_url.split('?')[0]}...")
                extinf = f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , 🟢 {match_name} [hls]\n'
                vlcopt = f'#EXTVLCOPT:http-referrer={working_url}/\n'
                stream = f'{m3u8_url}\n\n'
                m3u_lines.extend([extinf, vlcopt, stream])
            else:
                print("❌ Trận này chưa có luồng phát hoặc bị mã hóa JS.")
                
        except Exception as e:
            print(f"❌ Lỗi khi quét {link}: {e}")
            
    # 3. Lưu vào file M3U
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    print(f"\n🎉 XONG! Đã lưu file {M3U_FILE} lúc {datetime.datetime.now()}")

if __name__ == "__main__":
    get_matches()
    
