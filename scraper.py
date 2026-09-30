import requests
from bs4 import BeautifulSoup
import re

# Trang chủ cần cào dữ liệu
BASE_URL = 'https://khandai1.link'

def get_sport_icon(sport_name):
    sport_name = str(sport_name).lower()
    if 'bóng chuyền' in sport_name or 'volleyball' in sport_name: return '🏐'
    elif 'bóng rổ' in sport_name or 'basketball' in sport_name: return '🏀'
    elif 'bóng bàn' in sport_name or 'table tennis' in sport_name: return '🏓'
    elif 'cầu lông' in sport_name or 'badminton' in sport_name: return '🏸'
    elif 'bi a' in sport_name or 'billiards' in sport_name: return '🎱'
    else: return '⚽' # Ưu tiên bóng đá

def get_m3u8_from_detail(detail_url, headers):
    """Truy cập vào trang chi tiết trận đấu và dùng Regex quét tìm link m3u8"""
    try:
        response = requests.get(detail_url, headers=headers, timeout=15)
        # Regex này sẽ quét toàn bộ HTML để tìm đoạn text có chứa HTTP/HTTPS và kết thúc bằng .m3u8 kèm token
        m3u8_pattern = r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\']*)'
        matches = re.findall(m3u8_pattern, response.text)
        
        if matches:
            # Lấy link m3u8 đầu tiên tìm được. (Replace để loại bỏ dấu gạch chéo ngược nếu nó nằm trong JSON)
            return matches[0].replace('\\/', '/') 
        return None
    except Exception as e:
        print(f"Lỗi khi cào link chi tiết {detail_url}: {e}")
        return None

def scrape_khandai():
    m3u_content = "#EXTM3U\n\n"
    # Giả lập trình duyệt để tránh bị chặn
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Referer': BASE_URL
    }
    
    try:
        # Vào trang chủ cào các thẻ trận đấu
        response = requests.get(BASE_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # BƯỚC 1: Lấy danh sách trận đấu
        # LƯU Ý: Anh Sơn cần F12 (Inspect) trang chủ web để đổi 'match-item-class' thành class thực tế trên web
        matches = soup.find_all('div', class_='match-item-class') 
        
        for match in matches:
            try:
                # Cần sửa lại class tương ứng cho các trường dữ liệu bên dưới
                time_str = match.find('span', class_='time-class').text.strip()
                date_str = match.find('span', class_='date-class').text.strip()
                team1 = match.find('span', class_='team1-class').text.strip()
                team2 = match.find('span', class_='team2-class').text.strip()
                logo_url = match.find('img', class_='logo-class')['src']
                commentator = match.find('span', class_='blv-class').text.strip()
                sport_name = match.find('span', class_='sport-class').text.strip()
                
                # Định dạng URL logo nếu web dùng link tương đối (VD: /media/teams/...)
                if logo_url.startswith('/'):
                    logo_url = BASE_URL + logo_url
                    
                sport_icon = get_sport_icon(sport_name)
                
                # Tìm thẻ <a> chứa link chi tiết trận đấu (link /truc-tiep/...)
                detail_link_tag = match.find('a', href=re.compile(r'/truc-tiep/'))
                if detail_link_tag:
                    detail_path = detail_link_tag['href']
                    if not detail_path.startswith('http'):
                        detail_path = BASE_URL + detail_path
                    
                    print(f"Đang lấy luồng trận: {team1} vs {team2} ...")
                    
                    # BƯỚC 2: Bắt đầu chui vào link chi tiết để lấy M3U8
                    stream_url = get_m3u8_from_detail(detail_path, headers)
                    
                    if stream_url:
                        # Ghi vào M3U chuẩn format Khán Đài TV anh cung cấp
                        m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , {sport_icon} {time_str} {date_str} {team1} vs {team2} ({commentator}) [hls]\n'
                        m3u_content += f'#EXTVLCOPT:http-referrer={BASE_URL}/\n'
                        m3u_content += f'{stream_url}\n\n'
                    else:
                        print(f"Không tìm thấy luồng cho trận {team1} vs {team2}")
                        
            except Exception as e:
                # Nếu có một trận bị lỗi định dạng HTML, bỏ qua và chạy tiếp trận sau
                continue
                
    except Exception as e:
        print(f"Lỗi khi truy cập {BASE_URL}: {e}")

    # Ghi ra file
    with open('khandai.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print("Cập nhật thành công file m3u!")

if __name__ == "__main__":
    scrape_khandai()
    
