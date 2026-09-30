import os
import re
import time
from playwright.sync_api import sync_playwright

# Danh sách domain dự phòng Khán Đài TV
DOMAINS = [
    "https://khandaitv.com",
    "https://khandai.tv",
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandai3.link",
    "https://khandaitv.net"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def parse_matches(page, base_url):
    """Trích xuất chi tiết từng trận đấu: Thời gian, Đội bóng, BLV, Logo và Link"""
    matches = []
    
    # Đợi thẻ trận đấu hiển thị (thử các class phổ biến của Khán Đài TV)
    selectors = [
        ".match-item", ".item-match", ".card-match", 
        ".match-card", "a[href*='truc-tiep']", "a[href*='xem-phat-song']"
    ]
    
    for selector in selectors:
        items = page.query_selector_all(selector)
        if items:
            print(f"[+] Tìm thấy {len(items)} mục với selector: {selector}")
            for item in items:
                try:
                    # 1. Lấy link xem trận đấu
                    link = item.get_attribute("href") or ""
                    if not link:
                        continue
                    if not link.startswith("http"):
                        link = base_url.rstrip("/") + "/" + link.lstrip("/")

                    # 2. Lấy Logo / Cờ quốc gia
                    img_el = item.query_selector("img")
                    logo_url = ""
                    if img_el:
                        logo_url = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
                        if logo_url and not logo_url.startswith("http"):
                            logo_url = base_url.rstrip("/") + "/" + logo_url.lstrip("/")

                    # 3. Trích xuất text thông tin trận đấu (Thời gian, Đội A vs Đội B, BLV)
                    raw_text = item.inner_text().strip()
                    if not raw_text:
                        continue
                        
                    # Làm sạch khoảng trắng/xuống dòng
                    clean_text = " ".join(raw_text.split())
                    
                    # Định dạng tiêu đề hiển thị chuẩn IPTV
                    if "vs" in clean_text.lower() or "⚽" in clean_text or "-" in clean_text:
                        title = clean_text
                        if "⚽" not in title:
                            title = f"⚽ {title}"
                        if "[hls]" not in title.lower():
                            title = f"{title} [hls]"
                            
                        matches.append({
                            "title": title,
                            "link": link,
                            "logo": logo_url
                        })
                except Exception:
                    continue
            if matches:
                break
    return matches

def run_scraper():
    print("[*] Bắt đầu cào dữ liệu toàn bộ trận đấu Khán Đài TV...")
    all_matches = []

    with sync_playwright() as p:
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
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        
        page = context.new_page()
        # Fake webdriver để vượt qua kiểm tra cơ bản của Cloudflare
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for domain in DOMAINS:
            print(f"[*] Đang kết nối tới: {domain}")
            try:
                res = page.goto(domain, timeout=30000, wait_until="domcontentloaded")
                time.sleep(4) # Chờ Javascript dựng danh sách trận đấu
                
                # Kiểm tra nếu gặp trang chờ Cloudflare
                if "Just a moment" in page.title():
                    print(f"[⚠️] {domain} yêu cầu xác minh Cloudflare, chuyển domain tiếp theo...")
                    continue

                matches = parse_matches(page, domain)
                if matches:
                    print(f"[✅] Cào thành công {len(matches)} trận đấu từ {domain}!")
                    all_matches = matches
                    break
            except Exception as e:
                print(f"[❌] Lỗi khi tải {domain}: {e}")

        browser.close()

    # --- Xuất danh sách ra định dạng file playlist.m3u ---
    m3u_lines = ["#EXTM3U"]
    
    if all_matches:
        for match in all_matches:
            logo_attr = f' tvg-logo="{match["logo"]}"' if match["logo"] else ''
            m3u_lines.append(f'#EXTINF:-1{logo_attr} group-title="Khán Đài TV",{match["title"]}')
            m3u_lines.append(match["link"])
    else:
        print("[⚠️] Không lấy được danh sách trận đấu. Ghi file trống.")
        m3u_lines.append('#EXTINF:-1 group-title="Khán Đài TV",Đang cập nhật lịch thi đấu...')
        m3u_lines.append('https://0.0.0.0/offline.m3u8')

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")

    print(f"[💾] Đã ghi thành công file playlist.m3u với {len(all_matches)} trận đấu!")

if __name__ == "__main__":
    run_scraper()
    
