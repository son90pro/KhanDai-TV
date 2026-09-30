import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Danh sách tên miền dự phòng của Khán Đài TV
URLS_TO_TRY = [
    'https://khandai1.link',
    'https://khandai.link',
    'https://khandaia2.me'
]

def get_sport_icon(sport_name):
    sport_name = str(sport_name).lower()
    if 'bóng chuyền' in sport_name or 'volleyball' in sport_name: return '🏐'
    elif 'bóng rổ' in sport_name or 'basketball' in sport_name: return '🏀'
    elif 'bóng bàn' in sport_name or 'table tennis' in sport_name: return '🏓'
    elif 'cầu lông' in sport_name or 'badminton' in sport_name: return '🏸'
    elif 'bi a' in sport_name or 'billiards' in sport_name: return '🎱'
    else: return '⚽'

def scrape_khandai():
    m3u_content = "#EXTM3U\n\n"
    total_matches = 0

    with sync_playwright() as p:
        # Khởi tạo Chromium chế độ Stealth chống phát hiện bot
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security'
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800},
            locale='vi-VN',
            timezone_id='Asia/Ho_Chi_Minh'
        )

        # Xóa cờ bot tự động của Playwright
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()

        working_base_url = None
        for target_url in URLS_TO_TRY:
            print(f"--- Đang thử kết nối: {target_url} ---")
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(3000)
                
                title = page.title()
                print(f"Tiêu đề trang: {title}")
                
                if "Just a moment" in title or "Access denied" in title or "Cloudflare" in title:
                    print("⚠️ Trang này bị Cloudflare chặn IP máy chủ GitHub.")
                    continue

                working_base_url = target_url
                break
            except Exception as e:
                print(f"Lỗi khi kết nối {target_url}: {e}")

        if not working_base_url:
            print("❌ Tất cả tên miền đều không kết nối được!")
            browser.close()
            return

        page.wait_for_timeout(4000) # Đợi Vue.js render trận đấu
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Quét khung trận đấu
        cards = soup.find_all('div', class_=lambda c: c and 'rounded-[22px]' in c)
        if not cards:
            cards = soup.find_all('div', attrs={'data-v-dea1422f': True})

        print(f"=> Tìm thấy tổng cộng {len(cards)} trận đấu.")

        for card in cards:
            try:
                detail_a = card.find_parent('a', href=re.compile(r'/truc-tiep/')) or card.find('a', href=re.compile(r'/truc-tiep/'))
                if not detail_a:
                    continue

                detail_href = detail_a['href']
                detail_url = detail_href if detail_href.startswith('http') else working_base_url + detail_href

                # Thời gian & Ngày
                time_date_el = card.find('div', class_=re.compile(r'justify-self-start'))
                time_str, date_str = "", ""
                if time_date_el:
                    raw_td = time_date_el.text.strip()
                    if '-' in raw_td:
                        parts = raw_td.split('-')
                        time_str = parts[0].strip()
                        date_str = "/".join([p.strip() for p in parts[1:]])
                    else:
                        time_str = raw_td

                # Môn thể thao
                sport_el = card.find('span', class_='truncate')
                sport_name = sport_el.text.strip() if sport_el else "Bóng đá"
                sport_icon = get_sport_icon(sport_name)

                # Tên 2 đội
                team_names = [el.text.strip() for el in card.find_all('div', class_=re.compile(r'mt-2 truncate'))]
                team1 = team_names[0] if len(team_names) > 0 else "Đội 1"
                team2 = team_names[1] if len(team_names) > 1 else "Đội 2"

                # Logo
                logo_url = ""
                for img in card.find_all('img'):
                    src = img.get('src', '')
                    if '/teams/' in src or '/team/' in src or '/media' in src:
                        logo_url = src if src.startswith('http') else working_base_url + src
                        break

                # BLV
                blv_span = card.find('span', class_=re.compile(r'text-\[11px\] font-black leading-none text-white'))
                commentator = blv_span.text.strip() if blv_span else "BLV"

                print(f"📌 Bắt luồng: {team1} vs {team2} ({commentator})")

                detail_page = context.new_page()
                stream_url = None

                def handle_request(request):
                    nonlocal stream_url
                    if '.m3u8' in request.url and not stream_url:
                        stream_url = request.url

                detail_page.on("request", handle_request)

                try:
                    detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=25000)
                    detail_page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"Lỗi mở {detail_url}: {e}")

                if not stream_url:
                    detail_html = detail_page.content()
                    m3u8_matches = re.findall(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\']*)', detail_html)
                    if m3u8_matches:
                        stream_url = m3u8_matches[0].replace('\\/', '/')

                detail_page.close()

                if stream_url:
                    total_matches += 1
                    m3u_content += f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , {sport_icon} {time_str} {date_str} {team1} vs {team2} ({commentator}) [hls]\n'
                    m3u_content += f'#EXTVLCOPT:http-referrer={working_base_url}/\n'
                    m3u_content += f'{stream_url}\n\n'

            except Exception as e:
                print(f"Lỗi xử lý 1 trận: {e}")
                continue

        browser.close()

    # Ghi ra file khandai.m3u
    with open('khandai.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)

    print(f"✅ HOÀN TẤT: Đã bóc tách {total_matches} trận đấu vào file khandai.m3u!")

if __name__ == "__main__":
    scrape_khandai()
    
