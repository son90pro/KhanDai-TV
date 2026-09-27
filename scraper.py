import datetime
import re
import time
from playwright.sync_api import sync_playwright

# Danh sách tên miền Khán Đài TV
BASE_URLS = [
    "https://khandai1.link",
    "https://khandai2.link",
    "https://khandaia2.me",
]
M3U_FILE = "khandai.m3u"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like"
    " Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def get_matches():
  m3u_lines = ["#EXTM3U\n\n"]

  with sync_playwright() as p:
    # 1. Khởi chạy Chromium với cấu hình ẩn danh chống bot
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
    )

    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720},
        locale="vi-VN",
        timezone_id="Asia/Ho_Chi_Minh",
    )

    # Vô hiệu hóa cờ navigator.webdriver
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () =>"
        " undefined});"
    )

    page = context.new_page()
    working_url = None
    match_links = []

    # 2. Truy cập trang chủ & lấy danh sách link trận đấu
    for url in BASE_URLS:
      print(f"🔄 Đang thử truy cập: {url}")
      try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        title = page.title()
        print(f"📌 Tiêu đề nhận được: {title}")

        if "Just a moment" in title or "Access denied" in title:
          print("⚠️ Trang web bị Cloudflare chặn IP!")
          continue

        # Lấy link trận đấu với bộ lọc linh hoạt hơn
        hrefs = page.evaluate("""() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links
                        .map(a => a.href)
                        .filter(href => href && (
                            href.includes('/truc-tiep') || 
                            href.includes('/xem-') || 
                            href.includes('/match/') ||
                            href.includes('/tran-')
                        ));
                }""")

        # Loại bỏ các link trùng lặp hoặc link trang chủ
        unique_links = []
        for h in hrefs:
          if (
              h not in unique_links
              and h.rstrip("/") != url.rstrip("/")
              and not h.endswith("/truc-tiep")
          ):
            unique_links.append(h)

        match_links = unique_links
        if match_links:
          working_url = url
          print(f"✅ Tìm thấy {len(match_links)} trận đấu trên {url}")
          break
      except Exception as e:
        print(f"❌ Lỗi truy cập {url}: {e}")

    page.close()

    if not match_links:
      print(
          "❌ KHÔNG LẤY ĐƯỢC LINK TRẬN ĐẤU NÀO! (Có thể do web đổi giao diện"
          " hoặc chặn IP)."
      )
      browser.close()
      with open(M3U_FILE, "w", encoding="utf-8") as f:
        f.writelines(m3u_lines)
      return

    # 3. Truy cập từng phòng trận đấu để bắt luồng stream .m3u8
    for link in match_links:
      print(f"\n⚽ Đang vào phòng trận đấu: {link}")

      # Mở tab mới cho từng trận đấu
      match_page = context.new_page()

      match_name = "Trận đấu Khán Đài TV"
      logo_url = f"{working_url}/media/teams/logos/default.png"
      m3u8_url = None

      # Hàm lắng nghe network request
      def capture_m3u8(response):
        nonlocal m3u8_url
        res_url = response.url

        # Bắt file .m3u8 và bỏ qua các segment nhỏ (.ts, .m4s)
        if ".m3u8" in res_url and not m3u8_url:
          if not any(ext in res_url for ext in [".ts", ".m4s", ".key"]):
            m3u8_url = res_url
            print(f"  🎯 BẮT ĐƯỢC LINK STREAM: {m3u8_url}")

      match_page.on("response", capture_m3u8)

      try:
        match_page.goto(link, timeout=30000, wait_until="domcontentloaded")
        match_page.wait_for_timeout(3000)

        # Lấy tên trận đấu
        title_text = match_page.title()
        if title_text:
          clean_title = (
              title_text.replace("Trực tiếp", "")
              .replace("Khán Đài TV", "")
              .replace("|", "")
              .replace("-", " ")
              .strip()
          )
          if clean_title:
            match_name = clean_title

        # Lấy Logo trận đấu
        logo = match_page.evaluate("""() => {
                    const meta = document.querySelector('meta[property="og:image"]');
                    return meta ? meta.content : null;
                }""")
        if logo:
          logo_url = logo

        # Kích hoạt Play / Chọn Server nếu Player chưa tự chạy
        if not m3u8_url:
          try:
            match_page.evaluate("""() => {
                            const targets = document.querySelectorAll(
                                'video, iframe, .play-btn, .btn-play, [class*="player"], [class*="server"], [class*="kenh"]'
                            );
                            targets.forEach(el => {
                                try { el.click(); } catch(e) {}
                            });
                        }""")
          except Exception:
            pass

          # Đợi player tải và nạp luồng video
          match_page.wait_for_timeout(5000)

      except Exception as e:
        print(f"❌ Lỗi khi tải trang trận đấu: {e}")

      match_page.close()

      # Ghi vào danh sách M3U nếu bắt được m3u8
      if m3u8_url:
        extinf = (
            f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="Khán Đài TV",'
            f' 🟢 {match_name} [hls]\n'
        )
        vlcopt_ref = f"#EXTVLCOPT:http-referrer={working_url}/\n"
        vlcopt_ua = f"#EXTVLCOPT:http-user-agent={USER_AGENT}\n"
        stream = f"{m3u8_url}\n\n"
        m3u_lines.extend([extinf, vlcopt_ref, vlcopt_ua, stream])
      else:
        print("  ❌ Không thấy luồng m3u8 phát ra từ player.")

    browser.close()

  # 4. Xuất file M3U
  with open(M3U_FILE, "w", encoding="utf-8") as f:
    f.writelines(m3u_lines)

  valid_channels = (len(m3u_lines) - 1) // 5
  print(
      f"\n🎉 Hoàn thành lúc {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}!"
      f" Tổng số kênh chộp được: {valid_channels}"
  )


if __name__ == "__main__":
  get_matches()
    
