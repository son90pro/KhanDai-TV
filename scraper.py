import requests
from bs4 import BeautifulSoup
import re

BASE_URL = 'https://khandai1.link'

def get_sport_icon(sport_name):
    """Phân loại Icon theo môn thể thao, ưu tiên bóng đá"""
    sport_name = str(sport_name).lower()
    if 'bóng chuyền' in sport_name or 'volleyball' in sport_name: return '🏐'
    elif 'bóng rổ' in sport_name or 'basketball' in sport_name: return '🏀'
    elif 'bóng bàn' in sport_name or 'table tennis' in sport_name: return '🏓'
    elif 'cầu lông' in sport_name or 'badminton' in sport_name: return '🏸'
    elif 'bi a' in sport_name or 'billiards' in sport_name: return '🎱'
    else: return '⚽'

def get_m3u8_from_detail(detail_url, headers):
    """Vào trang chi tiết trận đấu để cào link stream .m3u8"""
    try:
        res = requests.get(detail_url, headers=headers, timeout=12)
        if res.status_code == 200:
            # Dùng Regex quét toàn bộ HTML trang chi tiết tìm link .m3u8
            m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\']*)', res.text)
            if m3u8_matches:
                return m3u8_matches[0].replace('\\/', '/')
    except Exception as e:
        print(f"Lỗi lấy luồng từ {detail_url}: {e}")
    return None

def scrape_khandai():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': BASE_URL
    }
    
    m3u_content = "#EXTM3U\n\n"
    
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Nhận diện thẻ khung trận đấu dựa theo class thực tế anh cung cấp
        cards = soup.find_all('div', class_=lambda c: c and 'rounded-[22px]' in c)
        if not cards:
            cards = soup.find_all('div', attrs={'data-v-dea1422f': True})
            
        print(f"Tìm thấy {len(cards)} trận đấu trên trang chủ.")

        for card in cards:
            try:
                # 1. Lấy đường link chi tiết trận đấu (/truc-tiep/...)
                detail_a = card.find_parent('a', href=re.compile(r'/truc-tiep/')) or card.find('a', href=re.compile(r'/truc-tiep/'))
                if not detail_a:
                    continue
                
                detail_href = detail_a['href']
                detail_url = detail_href if detail_href.startswith('http') else BASE_URL + detail_href

                # 2. Bóc tách Thời gian & Ngày tháng (VD: 13:00 - 30-09)
                time_date_el = card.find('div', class_=re.compile(r'justify-self-start'))
                time_str, date_str = "", ""
                if time_date_el:
                    raw_td = time_date_el.text.strip()
                    if '-' in raw_td:
                        parts = raw_td.split('-')
                        time_str = parts[0].strip()
                        date_str = "/".join([p.strip() for p in parts[1:]]) # Chuyển 30-09 thành 30/09
                    else:
                        time_str = raw_td

                # 3. Môn thể thao
                sport_el = card.find('span', class_='truncate')
                sport_name = sport_el.text.strip() if sport_el else "Bóng đá"
                sport_icon = get_sport_icon(sport_name)

                # 4. Tên 2 đội bóng
                team_names = [el.text.strip() for el in card.find_all('div', class_=re.compile(r'mt-2 truncate'))]
                team1 = team_names[0] if len(team_names) > 0 else "Đội 1"
                team2 = team_names[1] if len(team_names) > 1 else "Đội 2"

                # 5. Logo đội bóng (Ưu tiên lấy logo đội 1)
                logo_url = ""
                for img in card.find_all('img'):
                    src = img.get('src', '')
                    if '/teams/' in src or '/team/' in src:
                        logo_url = src if src.startswith('http') else BASE_URL + src
                        break

                # 6. Tên Bình luận viên (BLV)
                blv_span = card.find('span', class_=re.compile(r'text-\[11px\] font-black leading-none text-white'))
                commentator = blv_span.text.strip() if blv_span else "BLV"

                # 7. Cào link stream m3u8 từ trang chi tiết
                print(f"Đang bóc tách luồng: {team1} vs {team2} ({commentator})")
                stream_url = get_m3u8_from_detail(detail_url, headers)

                if stream_url:
                    # Ghi đúng định dạng M3U chuẩn Khán Đài TV
                    m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , {sport_icon} {time_str} {date_str} {team1} vs {team2} ({commentator}) [hls]\n'
                    m3u_content += f'#EXTVLCOPT:http-referrer={BASE_URL}/\n'
                    m3u_content += f'{stream_url}\n\n'

            except Exception as e:
                print(f"Lỗi khi xử lý 1 trận đấu: {e}")
                continue

    except Exception as e:
        print(f"Lỗi kết nối trang chủ: {e}")

    # Ghi ra file khandai.m3u
    with open('khandai.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print("Đã cập nhật xong file khandai.m3u!")

if __name__ == "__main__":
    scrape_khandai()
    
