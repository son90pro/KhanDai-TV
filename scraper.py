from playwright.sync_api import sync_playwright
import datetime
import time
import re

# Danh sách tên miền Khán Đài TV
BASE_URLS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandaia2.me"
]
M3U_FILE = "khandai.m3u"

def get_matches():
    m3u_lines = ["#EXTM3U\n\n"]
    
    with sync_playwright() as p:
        # Khởi chạy Chromium giả dạng trình duyệt thật
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        page = context.new_page()
        
        working_url = None
        match_links = []
        
        # 1. Kết nối trang chủ
        for url in BASE_URLS:
            print(f"🔄 Đang thử truy cập: {url}")
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                
                title = page.title()
                print(f"📌 Tiêu đề nhận được: {title}")
                
                # Kiểm tra xem có bị dính Cloudflare không
                if "Just a moment" in title or "Access denied" in title:
                    print("⚠️ Trang web bị Cloudflare chặn IP server!")
                    continue
                    
                # Lấy tất cả link trận đấu
                hrefs = page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.map(a => a.href).filter(href => href && href.includes('/truc-tiep/'));
                }""")
                
                match_links = list(set(hrefs))
                if match_links:
                    working_url = url
                    print(f"✅ Tìm thấy {len(match_links)} trận đấu trên {url}")
                    break
            except Exception as e:
                print(f"❌ Lỗi truy cập {url}: {e}")
                
        if not match_links:
            print("❌ KHÔNG LẤY ĐƯỢC LINK TRẬN ĐẤU NÀO! (Có thể do web đổi giao diện hoặc chặn IP US).")
            browser.close()
            with open(M3U_FILE, "w", encoding="utf-8") as f:
                f.writelines(m3u_lines)
            return

        # 2. Bắt luồng m3u8 trong từng trận
        for link in match_links:
            print(f"\n⚽ Đang vào phòng trận đấu: {link}")
            
            match_name = "Trận đấu Khán Đài TV"
            logo_url = f"{working_url}/media/teams/logos/default.png"
            m3u8_url = None
            
            # Hàm lắng nghe luồng mạng chộp link .m3u8
            def capture_m3u8(response):
                nonlocal m3u8_url
                res_url = response.url
                if ".m3u8" in res_url and not m3u8_url:
                    # Loại bỏ các file segment / ts
                    if "index.m3u8" in res_url or "playlist.m3u8" in res_url or ".m3u8?" in res_url or res_url.endswith(".m3u8"):
                        m3u8_url = res_url
                        print(f"  🎯 BẮT ĐƯỢC LINK STREAM: {m3u8_url}")

            page.on("response", capture_m3u8)
            
            try:
                page.goto(link, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000) # Chờ 5 giây cho player nạp m3u8
                
                # Bóc tách tên trận
                title_text = page.title()
                if title_text:
                    match_name = title_text.replace("Trực tiếp", "").replace("Khán Đài TV", "").replace("|", "").strip()
                
                # Bóc tách Logo
                logo = page.evaluate("""() => {
                    const meta = document.querySelector('meta[property="og:image"]');
                    return meta ? meta.content : null;
                }""")
                if logo:
                    logo_url = logo
                    
            except Exception as e:
                print(f"❌ Lỗi khi tải trang trận đấu: {e}")
                
            page.remove_listener("response", capture_m3u8)
            
            # Ghi vào M3U
            if m3u8_url:
                extinf = f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , 🟢 {match_name} [hls]\n'
                vlcopt = f'#EXTVLCOPT:http-referrer={working_url}/\n'
                stream = f'{m3u8_url}\n\n'
                m3u_lines.extend([extinf, vlcopt, stream])
            else:
                print("  ❌ Không thấy luồng m3u8 phát ra từ player.")
                
        browser.close()

    # 3. Ghi file
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
        
    print(f"\n🎉 Hoàn thành lúc {datetime.datetime.now()}! Tổng số kênh chộp được: {len(m3u_lines)//4}")

if __name__ == "__main__":
    get_matches()
    
