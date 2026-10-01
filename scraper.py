import cloudscraper
import json
from datetime import datetime

API_URL = "https://khandai1.link/api/matches/?ordering=smart&page_size=100"
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
            date_part, time_part = iso_str.split("T")
            y, m, d = date_part.split("-")
            hh, mm = time_part.split(":")[:2]
            return f"{hh}:{mm} {d}/{m}"
        except Exception:
            return ""

def detect_sport_and_icon(match):
    """
    Quét toàn bộ dữ liệu JSON của trận đấu để phân loại môn thể thao và gán icon chính xác.
    """
    # Chuyển toàn bộ object match thành chuỗi chữ thường để tìm kiếm từ khóa rộng rãi
    match_str = json.dumps(match, ensure_ascii=False).lower()

    # 1. BÓNG CHUYỀN
    if any(k in match_str for k in ["bóng chuyền", "bong chuyen", "volleyball", "vnl", "v.league"]):
        return "Bóng Chuyền", "🏐"
    
    # 2. BÓNG RỔ
    if any(k in match_str for k in ["bóng rổ", "bong ro", "basketball", "nba", "vba", "euroleague"]):
        return "Bóng Rổ", "🏀"

    # 3. QUẦN VỢT / TENNIS
    if any(k in match_str for k in ["quần vợt", "quan vot", "tennis", "atp", "wta", "wimbledon", "us open", "roland garros"]):
        return "Quần Vợt", "🎾"

    # 4. CẦU LÔNG
    if any(k in match_str for k in ["cầu lông", "cau long", "badminton", "bwf"]):
        return "Cầu Lông", "🏸"

    # 5. BÓNG BÀN
    if any(k in match_str for k in ["bóng bàn", "bong ban", "table tennis", "ittf"]):
        return "Bóng Bàn", "🏓"

    # 6. E-SPORTS
    if any(k in match_str for k in ["esports", "e-sports", "lien minh", "liên minh", "lol", "dota", "csgo", "cs2", "valorant", "tốc chiến"]):
        return "E-Sports", "🎮"

    # Mặc định là BÓNG ĐÁ
    return "Bóng Đá", "⚽"

def fetch_all_matches(scraper):
    """Lấy toàn bộ danh sách trận đấu qua tất cả các trang API"""
    matches = []
    current_url = API_URL

    while current_url:
        try:
            response = scraper.get(current_url, headers=headers, timeout=20)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                results = data.get("results", [])
                matches.extend(results)
                current_url = data.get("next")
            elif isinstance(data, list):
                matches.extend(data)
                break
            else:
                break
        except Exception as e:
            print(f"Lỗi khi tải dữ liệu từ {current_url}: {e}")
            break

    return matches

def main():
    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        matches = fetch_all_matches(scraper)
        print(f"Lấy thành công tổng cộng {len(matches)} trận đấu từ API.")

        m3u_content = ["#EXTM3U"]

        for match in matches:
            home = match.get("home_team_name", "Home")
            away = match.get("away_team_name", "Away")
            
            # Phân loại môn thể thao & biểu tượng chính xác
            group_category, icon = detect_sport_and_icon(match)

            # Logo đội bóng / giải đấu
            logo_path = match.get("home_team_logo") or match.get("tournament_icon_url") or ""
            logo_url = f"{DOMAIN}{logo_path}" if logo_path.startswith("/") else logo_path

            # Thời gian thi đấu
            raw_start = match.get("start_time", "")
            time_formatted = format_start_time(raw_start)
            time_tag = f"{time_formatted} " if time_formatted else ""

            # Danh sách Bình luận viên & Luồng phát
            commentators = match.get("commentators", [])

            if commentators:
                for blv in commentators:
                    blv_name = blv.get("name", "Kênh Live")
                    stream_url = blv.get("stream_url", "")
                    backup_url = blv.get("backup_stream_url", "")

                    # Luồng chính (FHD)
                    if stream_url:
                        title_fhd = f"{time_tag}{icon} {home} vs {away} ({blv_name}) [FHD]"
                        m3u_content.append(f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_category}", {title_fhd}')
                        m3u_content.append(stream_url)

                    # Luồng dự phòng (HD)
                    if backup_url:
                        title_hd = f"{time_tag}{icon} {home} vs {away} ({blv_name}) [HD]"
                        m3u_content.append(f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_category}", {title_hd}')
                        m3u_content.append(backup_url)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

        print(f"Cập nhật thành công! Đã ghi {len(m3u_content)//2} luồng phát vào {OUTPUT_FILE}")

    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
        exit(1)

if __name__ == "__main__":
    main()
    
