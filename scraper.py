import os
import re
from playwright.sync_api import sync_playwright

# Danh sách các domain dự phòng của Khán Đài TV
DOMAINS = [
    "https://khandai1.link/",
    "https://khandai2.link/",
    "https://khandai3.link/",
    "https://khandaitv.com/",
    "https://khandai.tv/",
    "https://khandaitv.net/"
]

# Giả lập User-Agent của Chrome thực tế
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def run_scraper():
    print("[*] Bắt đầu cào dữ liệu Khán Đài TV...")
    channels = []
    
    with sync_playwright() as p:
        # Khởi tạo Chromium với chế độ ẩn danh và bypass phát hiện bot
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        page = context.new_page()

        # Áp dụng script qua mặt kiểm tra webdriver
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for url in DOMAINS:
            print(f"[*] Thử kết nối: {url}")
            try:
                # Chờ DOM load xong (tránh kẹt quảng cáo)
                response = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                
                if response and response.status == 200:
                    print(f"[+] Kết nối thành công tới {url}")
                    page.wait_for_timeout(3000) # Đợi JS render danh sách kênh
                    
                    # --- Bắt đầu bóc tách link stream / danh sách kênh ---
                    # Tìm tất cả các thẻ chứa link xem hoặc kênh
                    elements = page.query_selector_all("a[href*='play'], a[href*='xem'], div.match-item, div.channel-item")
                    
                    for el in elements:
                        title = el.inner_text().strip()
                        link = el.get_attribute("href")
                        if title and link:
                            # Làm sạch tiêu đề (xóa xuống dòng)
                            clean_title = re.sub(r'\s+', ' ', title)
                            channels.append((clean_title, link))
                    
                    if channels:
                        print(f"[✅] Tìm thấy {len(channels)} kênh/trận đấu!")
                        break
                    else:
                        print("[!] Trang truy cập được nhưng không tìm thấy danh sách kênh.")
            except Exception as e:
                print(f"[❌] Lỗi kết nối {url}: {e}")

        browser.close()

    # --- Xuất dữ liệu ra file playlist.m3u ---
    m3u_content = ["#EXTM3U"]
    
    if channels:
        for title, link in channels:
            m3u_content.append(f'#EXTINF:-1 group-title="Khán Đài TV",{title}')
            m3u_content.append(link)
    else:
        # Tạo sẵn thông báo nếu không cào được dữ liệu
        print("[⚠️] Không cào được dữ liệu mới. Khởi tạo file M3U mặc định.")
        m3u_content.append('#EXTINF:-1 group-title="Thông báo",Không tìm thấy nguồn phát Khán Đài TV')
        m3u_content.append('https://0.0.0.0/offline.m3u8')

    # Ghi file playlist.m3u
    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_content) + "\n")
        
    print("[💾] Đã ghi file playlist.m3u hoàn tất!")

if __name__ == "__main__":
    run_scraper()
    
