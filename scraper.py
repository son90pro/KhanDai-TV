import cloudscraper
import json
from datetime import datetime
from collections import defaultdict

API_URL = "https://khandai1.link/api/matches/?ordering=smart&page_size=100"
DOMAIN = "https://khandai1.link"
OUTPUT_FILE = "playlist.m3u"

# Danh sách thứ tự ưu tiên hiển thị Tab trên IPTV (Bóng Đá sẽ luôn ở top 1)
SPORT_ORDER = ["Bóng Đá", "Bóng Chuyền", "Bóng Rổ", "Quần Vợt", "Cầu Lông", "Bóng Bàn", "E-Sports"]

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
    """Phân loại môn thể thao và gán biểu tượng tương ứng"""
    match_str = json.dumps(match, ensure_ascii=False).lower()

    if any(k in match_str for k in ["bóng chuyền", "bong chuyen", "volleyball", "vnl", "v.league"]):
        return "Bóng Chuyền", "🏐"
    
    if any(k in match_str for k in ["bóng rổ", "bong ro", "basketball", "nba", "vba", "euroleague"]):
        return "Bóng Rổ", "🏀"

    if any(k in match_str for k in ["quần vợt", "quan vot", "tennis", "atp", "wta", "wimbledon", "us open", "roland garros"]):
        return "Quần Vợt", "🎾"

    if any(k in match_str for k in ["cầu lông", "cau long", "badminton", "bwf"]):
        return "Cầu Lông", "🏸"

    if any(k in match_str for k in ["bóng bàn", "bong ban", "table tennis", "ittf"]):
        return "Bóng Bàn", "🏓"

    if any(k in match_str for k in ["esports", "e-sports", "lien minh", "liên minh", "lol", "dota", "csgo", "cs2", "valorant", "tốc chiến"]):
        return "E-Sports", "🎮"

    return "Bóng Đá", "⚽"

def fetch_all_matches(scraper):
    """Lấy toàn bộ danh sách trận đấu từ API"""
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

        # Dùng dictionary gom nhóm các luồng phát theo danh mục môn thể thao
        grouped_streams = defaultdict(list)

        for match in matches:
            home = match.get("home_team_name", "Home")
            away = match.get("away_team_name", "Away")
            
            group_category, icon = detect_sport_and_icon(match)

            logo_path = match.get("home_team_logo") or match.get("tournament_icon_url") or ""
            logo_url = f"{DOMAIN}{logo_path}" if logo_path.startswith("/") else logo_path

            raw_start = match.get("start_time", "")
            time_formatted = format_start_time(raw_start)
            time_tag = f"{time_formatted} " if time_formatted else ""

            commentators = match.get("commentators", [])

            if commentators:
                for blv in commentators:
                    blv_name = blv.get("name", "Kênh Live")
                    stream_url = blv.get("stream_url", "")
                    backup_url = blv.get("backup_stream_url", "")

                    if stream_url:
                        title_fhd = f"{time_tag}{icon} {home} vs {away} ({blv_name}) [FHD]"
                        grouped_streams[group_category].append(
                            (f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_category}", {title_fhd}', stream_url)
                        )

                    if backup_url:
                        title_hd = f"{time_tag}{icon} {home} vs {away} ({blv_name}) [HD]"
                        grouped_streams[group_category].append(
                            (f'#EXTINF:-1 tvg-logo="{logo_url}" group-title="{group_category}", {title_hd}', backup_url)
                        )

        # Ghi nội dung M3U theo thứ tự ưu tiên
        m3u_content = ["#EXTM3U"]
        
        # 1. Ghi các nhóm theo thứ tự ưu tiên trong SPORT_ORDER (Bóng Đá -> Bóng Chuyền -> ...)
        for sport in SPORT_ORDER:
            if sport in grouped_streams:
                for extinf, url in grouped_streams[sport]:
                    m3u_content.append(extinf)
                    m3u_content.append(url)

        # 2. Ghi các nhóm phát sinh thêm (nếu có môn mới ngoài danh sách)
        for sport, items in grouped_streams.items():
            if sport not in SPORT_ORDER:
                for extinf, url in items:
                    m3u_content.append(extinf)
                    m3u_content.append(url)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

        print(f"Cập nhật thành công! Đã ghi {len(m3u_content)//2} luồng phát vào {OUTPUT_FILE} theo đúng thứ tự ưu tiên.")

    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
        exit(1)

if __name__ == "__main__":
    main()
    
