"""
플랫폼 순찰기 - 커뮤니티 담당
역할: 공개 커뮤니티 게시물 검색 수집 (공개 범위만)
"""
import requests
from datetime import datetime
import urllib.parse

class CommunityMonitor:

    def search_dcinside(self, query):
        """디시인사이드 갤러리 검색 (공개 검색)"""
        encoded = urllib.parse.quote(query)
        url = f"https://search.naver.com/search.naver?where=web&query=site:dcinside.com+{encoded}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        results = []
        try:
            r = requests.get(url, headers=headers, timeout=10)
            # 실제 파싱은 제한적 — 검색 결과 확인용
            if query.lower() in r.text.lower():
                results.append({
                    "platform": "커뮤니티",
                    "type": "게시글",
                    "title": f"[디시인사이드] '{query}' 언급 감지",
                    "description": "수동 확인 필요 — 디시인사이드에서 키워드 발견됨",
                    "url": f"https://search.naver.com/search.naver?query=site:dcinside.com+{encoded}",
                    "author": "unknown",
                    "published_at": datetime.now().isoformat(),
                    "found_at": datetime.now().isoformat(),
                    "query": query,
                    "manual_check_needed": True
                })
        except Exception as e:
            print(f"[커뮤니티] 디시 검색 오류: {e}")
        return results

    def search_theqoo(self, query):
        """더쿠 검색 (Google 검색 경유)"""
        encoded = urllib.parse.quote(f"site:theqoo.net {query}")
        url = f"https://www.google.com/search?q={encoded}&hl=ko"
        headers = {"User-Agent": "Mozilla/5.0"}
        results = []
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if "theqoo" in r.text.lower() and query in r.text:
                results.append({
                    "platform": "커뮤니티",
                    "type": "게시글",
                    "title": f"[더쿠] '{query}' 언급 감지",
                    "description": "수동 확인 필요 — 더쿠에서 키워드 발견됨",
                    "url": f"https://www.google.com/search?q=site:theqoo.net+{urllib.parse.quote(query)}",
                    "author": "unknown",
                    "published_at": datetime.now().isoformat(),
                    "found_at": datetime.now().isoformat(),
                    "query": query,
                    "manual_check_needed": True
                })
        except Exception as e:
            print(f"[커뮤니티] 더쿠 검색 오류: {e}")
        return results

    def scan_all(self, keywords):
        """모든 키워드 커뮤니티 스캔"""
        all_results = []
        main_kw = keywords.get("main_keywords", [])[:3]  # 주요 키워드만 (과부하 방지)
        for kw in main_kw:
            all_results.extend(self.search_dcinside(kw))
            all_results.extend(self.search_theqoo(kw))
        return all_results
