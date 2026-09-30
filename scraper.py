import cloudscraper
from datetime import datetime

API_URL = "https://khandai1.link/api/matches/?ordering=smart&page_size=50"
DOMAIN = "https://khandai1.link"
OUTPUT_FILE = "playlist.m3u"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://khandai1.link/",
    "Origin": "https://khandai1.link"
}

def format_start_time(iso_str):
    """Chuyển đổi chuỗi thời gian ISO thành định dạng HH:MM DD/MM"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%H:%M %d/%m")
    except Exception:
        try:
            # Parse thủ công nếu môi trường không tương thích ISO format cũ
            date_part, time_part = iso_str.split("T")
            y, m, d = date_part.split("-")
            hh, mm = time_part.split(":")[:2]
            return f"{hh}:{mm} {d}/{m}"
        except Exception:
            return ""

def main():
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        response = scraper.get(API_URL, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        matches = data.get("results", [])

        m3u_content = ["#EXTM3U"]

        for match in matches:
            home = match.get("home_team_name", "Home")
            away = match.get("away_team_name", "Away")
            tournament = match.get("tournament_name", "Trực Tiếp Bóng Đá").strip()
            
            # 1. Xử lý đường dẫn Logo đội bóng / Giải đấu
            logo_path = match.get("home_team_logo") or match.get("tournament_icon_url") or ""
            logo_url = f"{DOMAIN}{logo_path}" if logo_path.startswith("/") else logo_path

            # 2. Xử lý Thời gian thi đấu
            raw_start = match.get("start_time", "")
            time_formatted = format_start_time(raw_start)
            time_tag = f"[{time_formatted}] " if time_formatted else ""

            # 3. Duyệt danh sách Bình luận viên & Luồng phát
            commentators = match.get("commentators", [])

            if commentators:
                for blv in commentators:
                    blv_name = blv.get("name", "Kênh Live")
                    stream_url = blv.get("stream_url", "")
                    backup_url = blv.get("backup_stream_url", "")

                    # Luồng chính mặc định gán nhãn [FHD]
                    if stream_url:
                        title_fhd = f"{time_tag}{home} vs {away} [FHD] (BLV {blv_name})"
                        m3u_content.append(f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{tournament}", {title_fhd}')
                        m3u_content.append(stream_url)

                    # Luồng dự phòng gán nhãn [HD] (nếu nhà mạng/server phụ có)
                    if backup_url:
                        title_hd = f"{time_tag}{home} vs {away} [HD - Dự Phòng] (BLV {blv_name})"
                        m3u_content.append(f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{tournament}", {title_hd}')
                        m3u_content.append(backup_url)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

        print(f"Cập nhật thành công! Đã ghi {len(m3u_content)//2} luồng phát vào {OUTPUT_FILE}")

    except Exception as e:
        print(f"Lỗi cào dữ liệu: {e}")
        exit(1)

if __name__ == "__main__":
    main()
    
