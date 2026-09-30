import requests

url = "https://khandai1.link/api/matches/?ordering=smart&page_size=30"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    matches = data.get("results", [])
    
    print(f"=== TỔNG SỐ TRẬN ĐẤU: {len(matches)} ===\n")
    
    for match in matches:
        home = match.get("home_team_name")
        away = match.get("away_team_name")
        league = match.get("tournament_name")
        start = match.get("start_time")
        
        print(f"⚽ [{league}] {home} VS {away}")
        print(f"🕒 Thời gian: {start}")
        
        # Lấy link stream từ danh sách bình luận viên
        commentators = match.get("commentators", [])
        if commentators:
            for blv in commentators:
                blv_name = blv.get("name")
                stream_link = blv.get("stream_url")
                print(f" 🎙️ BLV: {blv_name} | 🔗 Link m3u8: {stream_link}")
        else:
            print(" ⚠️ Chưa có link stream/BLV")
            
        print("-" * 60)
else:
    print(f"Lỗi lấy dữ liệu: {response.status_code}")
    
