"""
플랫폼 순찰기 - 유튜브 담당
역할: 유튜브에서 키워드 관련 영상/댓글 수집
"""
import requests
import json
from datetime import datetime

class YouTubeMonitor:
    def __init__(self, api_key, max_results=10):
        self.api_key = api_key
        self.max_results = max_results
        self.base_url = "https://www.googleapis.com/youtube/v3"

    def search_videos(self, query):
        """유튜브에서 키워드로 영상 검색"""
        if not self.api_key or self.api_key == "YOUR_YOUTUBE_API_KEY":
            print(f"[YouTube] API 키 없음 — {query} 검색 건너뜀")
            return []

        url = f"{self.base_url}/search"
        params = {
            "key": self.api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": self.max_results,
            "order": "date",
            "regionCode": "KR",
            "relevanceLanguage": "ko"
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            items = r.json().get("items", [])
            results = []
            for item in items:
                snippet = item["snippet"]
                video_id = item["id"]["videoId"]
                results.append({
                    "platform": "유튜브",
                    "type": "영상",
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")[:300],
                    "channel": snippet.get("channelTitle", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "found_at": datetime.now().isoformat(),
                    "query": query
                })
            print(f"[YouTube] '{query}' 검색 결과: {len(results)}건")
            return results
        except Exception as e:
            print(f"[YouTube] 검색 오류 ({query}): {e}")
            return []

    def get_video_stats(self, video_id):
        """영상 조회수/좋아요/댓글 수 가져오기"""
        if not self.api_key or self.api_key == "YOUR_YOUTUBE_API_KEY":
            return {}
        url = f"{self.base_url}/videos"
        params = {"key": self.api_key, "id": video_id, "part": "statistics"}
        try:
            r = requests.get(url, params=params, timeout=10)
            stats = r.json().get("items", [{}])[0].get("statistics", {})
            return {
                "views":    int(stats.get("viewCount", 0)),
                "likes":    int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0))
            }
        except:
            return {}

    def scan_all(self, keywords):
        """모든 키워드 스캔"""
        all_results = []
        all_kw = (
            keywords.get("main_keywords", []) +
            keywords.get("related_keywords", []) +
            keywords.get("variant_keywords", []) +
            keywords.get("case_keywords", [])
        )
        for kw in all_kw:
            results = self.search_videos(kw)
            for r in results:
                stats = self.get_video_stats(r.get("video_id", ""))
                r.update(stats)
            all_results.extend(results)

        # 중복 제거 (같은 URL)
        seen = set()
        unique = []
        for r in all_results:
            if r["url"] not in seen:
                seen.add(r["url"])
                unique.append(r)
        return unique
