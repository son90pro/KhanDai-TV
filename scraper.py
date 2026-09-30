import requests

URL = "https://khandai1.link/api/matches/?ordering=smart&page_size=50"
OUTPUT_FILE = "playlist.m3u"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

def main():
    try:
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        matches = data.get("results", [])

        m3u_content = ["#EXTM3U"]

        for match in matches:
            home = match.get("home_team_name", "Home")
            away = match.get("away_team_name", "Away")
            tournament = match.get("tournament_name", "Trực Tiếp Bóng Đá")
            commentators = match.get("commentators", [])

            if commentators:
                for blv in commentators:
                    blv_name = blv.get("name", "Kênh Live")
                    stream_url = blv.get("stream_url", "")
                    
                    if stream_url:
                        title = f"{home} vs {away} (BLV {blv_name})"
                        m3u_content.append(f'#EXTINF:-1 group-title="{tournament}", {title}')
                        m3u_content.append(stream_url)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(m3u_content))

        print(f"Cập nhật thành công {len(m3u_content)//2} luồng phát vào {OUTPUT_FILE}")

    except Exception as e:
        print(f"Lỗi trong quá trình cào dữ liệu: {e}")
        exit(1)

if __name__ == "__main__":
    main()
    
