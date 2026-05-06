"""
플랫폼 순찰기 - 뉴스 담당 (API 키 불필요)
역할: 네이버 뉴스 / Google 뉴스 RSS 수집
"""
import requests
import json
from datetime import datetime
from xml.etree import ElementTree as ET
import urllib.parse

class NewsMonitor:

    def search_naver_news(self, query):
        """네이버 뉴스 RSS 검색 (API 키 불필요)"""
        encoded = urllib.parse.quote(query)
        url = f"https://news.naver.com/search/searcher.nhn?query={encoded}&sm=tab_opt&sort=1&photo=0&field=0&pd=0&ds=&de=&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so:dd,p:all,a:all&is_sug_officeid=0"
        headers = {"User-Agent": "Mozilla/5.0"}
        results = []
        try:
            # 네이버 뉴스 검색 (RSS)
            rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
            r = requests.get(rss_url, headers=headers, timeout=10)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:10]:
                title    = item.findtext("title", "")
                link     = item.findtext("link", "")
                pubdate  = item.findtext("pubDate", "")
                desc     = item.findtext("description", "")[:300]
                source   = item.findtext("source", "")
                results.append({
                    "platform": "뉴스",
                    "type": "기사",
                    "title": title,
                    "description": desc,
                    "url": link,
                    "author": source,
                    "published_at": pubdate,
                    "found_at": datetime.now().isoformat(),
                    "query": query
                })
            print(f"[뉴스] '{query}' 검색 결과: {len(results)}건")
        except Exception as e:
            print(f"[뉴스] 검색 오류 ({query}): {e}")
        return results

    def scan_all(self, keywords):
        """모든 키워드 뉴스 스캔"""
        all_results = []
        all_kw = (
            keywords.get("main_keywords", []) +
            keywords.get("case_keywords", [])
        )
        seen = set()
        for kw in all_kw:
            for item in self.search_naver_news(kw):
                if item["url"] not in seen:
                    seen.add(item["url"])
                    all_results.append(item)
        return all_results
