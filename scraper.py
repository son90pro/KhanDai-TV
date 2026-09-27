from playwright.sync_api import sync_playwright
import datetime
import time

BASE_URL = "https://khandai1.link"
M3U_FILE = "khandai.m3u"

def get_matches():
    m3u_lines = ["#EXTM3U\n\n"]
    
    with sync_playwright() as p:
        # Mở Chrome vô hình
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"Đang mở trang chủ {BASE_URL}...")
        try:
            page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000) # Đợi 5 giây cho web load xong dữ liệu
            
            # Cuộn xuống cuối để web hiển thị hết các trận đấu
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        except Exception as e:
            print("Lỗi tải trang chủ:", e)
            browser.close()
            return
            
        # Tìm mọi thẻ link có chữ 'truc-tiep'
        hrefs = page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links.map(a => a.href).filter(href => href.includes('/truc-tiep/'));
        }""")
        
        # Loại bỏ các link bị trùng lặp
        match_links = list(set(hrefs))
        print(f"🔎 Tìm thấy {len(match_links)} link trận đấu.")
        
        for link in match_links:
            print(f"\nĐang vào phòng: {link}")
            
            match_name = "Trận đấu đang cập nhật"
            logo_url = "https://khandai1.link/media/teams/logos/default.png"
            m3u8_url = None
            
            # Tính năng "Nghe Lén Mạng": Nếu thấy mạng tải file m3u8 -> Lấy ngay
            def handle_request(request):
                nonlocal m3u8_url
                if ".m3u8" in request.url and not m3u8_url:
                    m3u8_url = request.url

            page.on("request", handle_request)
            
            try:
                page.goto(link, timeout=25000, wait_until="domcontentloaded")
                # Đợi player tải m3u8 (chờ 6 giây)
                page.wait_for_timeout(6000)
                
                # Bóc tách tên trận đấu từ tiêu đề
                title_text = page.title()
                if title_text:
                    match_name = title_text.replace("Trực tiếp", "").replace("Khán Đài TV", "").replace("|", "").strip()
                
                # Bóc tách Logo (từ hình ảnh chia sẻ mạng xã hội)
                logo = page.evaluate("""() => {
                    const meta = document.querySelector('meta[property="og:image"]');
                    return meta ? meta.content : null;
                }""")
                if logo:
                    logo_url = logo
                    
            except Exception as e:
                print(f"Lỗi khi vào phòng: {e}")
            
            page.remove_listener("request", handle_request)
            
            # Xuất dữ liệu ra chuẩn m3u như yêu cầu
            if m3u8_url:
                print(f"✅ ĐÃ CHỘP ĐƯỢC LINK: {m3u8_url.split('?')[0]}...")
                extinf = f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV" , 🟢 {match_name} [hls]\n'
                vlcopt = f'#EXTVLCOPT:http-referrer={BASE_URL}/\n'
                stream = f'{m3u8_url}\n\n'
                m3u_lines.extend([extinf, vlcopt, stream])
            else:
                print("❌ Trận này chưa có luồng phát hoặc bị mã hóa.")
        
        browser.close()
        
    # Ghi đè vào file khandai.m3u
    with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
    print(f"\n🎉 XONG! File đã tạo thành công lúc {datetime.datetime.now()}")

if __name__ == "__main__":
    get_matches()
    
