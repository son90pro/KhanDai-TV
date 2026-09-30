import os
import re
import json
import time
from playwright.sync_api import sync_playwright

# Danh sách domain Khán Đài TV
DOMAINS = [
    "https://khandaitv.com",
    "https://khandai.tv",
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandai3.link",
    "https://khandaitv.net"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

def run_scraper():
    print("[*] Bắt đầu cào dữ liệu trận đấu Khán Đài TV...")
    matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )
        
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        
        page = context.new_page()
        # Bypass Cloudflare webdriver check
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for domain in DOMAINS:
            print(f"[*] Kết nối tới domain: {domain}")
            try:
                # Chờ network rảnh rỗi để đảm bảo toàn bộ API/JS đã tải xong
                page.goto(domain, timeout=35000, wait_until="networkidle")
                time.sleep(3)

                # Bóc tách tất cả các thẻ chứa thông tin trận đấu
                elements = page.query_selector_all("a[href*='truc-tiep'], a[href*='xem'], .match-item, .item-match, div[class*='match']")
                
                for el in elements:
                    try:
                        href = el.get_attribute("href") or ""
                        text = el.inner_text().strip()
                        
                        if not href or not text:
                            continue

                        # Lấy ảnh logo/quốc kỳ
                        img = el.query_selector("img")
                        logo = ""
                        if img:
                            logo = img.get_attribute("src") or img.get_attribute("data-src") or ""

                        # Format lại chuỗi hiển thị
                        clean_text = " ".join(text.split())
                        if "vs" in clean_text.lower() or "⚽" in clean_text or "-" in clean_text:
                            if not href.startswith("http"):
                                href = domain.rstrip("/") + "/" + href.lstrip("/")
                            if logo and not logo.startswith("http"):
                                logo = domain.rstrip("/") + "/" + logo.lstrip("/")

                            title = clean_text
                            if "⚽" not in title:
                                title = f"⚽ {title}"
                            if "[hls]" not in title.lower():
                                title = f"{title} [hls]"

                            matches.append({
                                "title": title,
                                "link": href,
                                "logo": logo
                            })
                    except Exception:
                        continue

                # Lọc bỏ các trận đấu bị trùng lặp link
                unique_matches = {m['link']: m for m in matches}.values()
                matches = list(unique_matches)

                if matches:
                    print(f"[✅] Đã cào thành công {len(matches)} trận đấu từ {domain}!")
                    break

            except Exception as e:
                print(f"[❌] Không thể cào từ {domain}: {e}")

        browser.close()

    # --- Xuất danh sách M3U ---
    m3u_lines = ["#EXTM3U"]
    if matches:
        for m in matches:
            logo_attr = f' tvg-logo="{m["logo"]}"' if m["logo"] else ''
            m3u_lines.append(f'#EXTINF:-1{logo_attr} group-title="Khán Đài TV",{m["title"]}')
            m3u_lines.append(m["link"])
    else:
        print("[⚠️] Không thể lấy trận đấu. Ghi file fallback.")
        m3u_lines.append('#EXTINF:-1 group-title="Thông báo",Không tìm thấy nguồn phát Khán Đài TV')
        m3u_lines.append('https://0.0.0.0/offline.m3u8')

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines) + "\n")

    print("[💾] Cập nhật playlist.m3u hoàn tất!")

if __name__ == "__main__":
    run_scraper()
