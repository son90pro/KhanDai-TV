import requests
import re
from bs4 import BeautifulSoup
import datetime

# Trang chủ cần quét
BASE_URL = "https://khandai1.link"
M3U_FILE = "khandai.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Referer": "https://khandai1.link/"
}

def get_match_links():
    """Vào trang chủ và gom tất cả các link dẫn đến trang trực tiếp"""
    try:
        print(f"Đang tải trang chủ: {BASE_URL}")
        res = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        links = []
        # Quét tất cả thẻ <a> có chứa đường dẫn
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Lọc lấy các link chứa từ khóa 'truc-tiep'
            if 'truc-tiep' in href:
                # Xử lý nếu web dùng link tương đối (vd: /truc-tiep/abc)
                full_link = href if href.startswith("http") else f"{BASE_URL.rstrip('/')}/{href.lstrip('/')}"
                if full_link not in links:
                    links.append(full_link)
        return links
    except Exception as e:
        print(f"Lỗi lấy link trang chủ: {e}")
        return []

def get_match_details(match_url):
    """Vào từng trận đấu để lấy Logo, Tiêu đề và Link m3u8 ẩn"""
    try:
        print(f"Đang bóc tách: {match_url}")
        res = requests.get(match_url, headers=HEADERS, timeout=15)
        html = res.text
        soup = BeautifulSoup(html, 'html.parser')

        # 1. Lấy Tên trận đấu từ thẻ <title> hoặc <h1>
        title = soup.title.text.strip() if soup.title else "Trận đấu không xác định"
        title = title.replace("Trực tiếp", "").replace("Khán Đài TV", "").replace("|", "").strip()
        match_name = f"🟢 {title} [hls]" # Tạo form tên giống danh sách cũ
        
        # 2. Lấy Logo trận đấu (Thường nằm ở thẻ meta og:image để share FB)
        logo_url = ""
        og_image = soup.find('meta', property='og:image')
        if og_image:
            logo_url = og_image.get('content', '')

        # 3. Lưới lọc Regex: Tìm mọi chuỗi giống định dạng link m3u8 trong source code
        # Định dạng này sẽ tóm gọn các link như phaohoa.live/index.m3u8?expire=...
        m3u8_link = ""
        m3u8_match = re.search(r'(https?://[^"\'\s<>]+?\.m3u8[^"\'\s<>]*)', html)
        
        if m3u8_match:
            # Sửa lỗi thoát ký tự slash nếu link bị nén trong Javascript
            m3u8_link = m3u8_match.group(1).replace('\\/', '/')
        else:
             # Nếu không thấy, tìm thử trong iframe dự phòng
             iframe = soup.find('iframe')
             if iframe and 'src' in iframe.attrs and 'm3u8' in iframe['src']:
                 m3u8_link = iframe['src']

        # Chỉ trả về dữ liệu nếu tìm thấy link m3u8
        if m3u8_link:
            return {
                "name": match_name,
                "logo": logo_url,
                "stream": m3u8_link,
                "referrer": match_url
            }
        else:
            print(" -> Không tìm thấy link m3u8 (Khả năng trận đấu chưa phát hoặc mã hóa JS)")
            return None
            
    except Exception as e:
        print(f"Lỗi tại {match_url}: {e}")
        return None

def generate_playlist():
    m3u_content = ["#EXTM3U\n\n"]
    
    links = get_match_links()
    print(f"🔎 Tìm thấy {len(links)} link trực tiếp. Bắt đầu rà quét...")
    
    # Duyệt qua từng trận đấu
    for url in links:
        match = get_match_details(url)
        if match:
            # Ghi theo đúng cấu trúc anh Sơn yêu cầu
            extinf = f'#EXTINF:-1 tvg-logo="{match["logo"]}" group-title="Khán Đài TV" , {match["name"]}\n'
            vlcopt = f'#EXTVLCOPT:http-referrer={match["referrer"]}\n'
            stream = f'{match["stream"]}\n\n'
            
            m3u_content.extend([extinf, vlcopt, stream])

    # Lưu kết quả
    with open(M3U_FILE, "w", encoding="utf-8") as file:
        file.writelines(m3u_content)
        
    print(f"✅ Đã lưu thành công danh sách vào {M3U_FILE} lúc {datetime.datetime.now()}")

if __name__ == "__main__":
    generate_playlist()
    
