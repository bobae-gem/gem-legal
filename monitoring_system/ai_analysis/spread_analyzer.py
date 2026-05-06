"""
확산 분석기
역할: 게시물이 여러 플랫폼에 퍼지고 있는지 분석
"""
import json, os
from datetime import datetime, timedelta

class SpreadAnalyzer:
    def __init__(self, evidence_path="evidence_storage"):
        self.evidence_path = evidence_path

    def analyze(self, post: dict, all_results: list) -> dict:
        """
        확산 위험 분석
        반환: {
            "is_spreading": bool,
            "spread_count": int,
            "platforms": [...],
            "spread_speed": "빠름"|"보통"|"느림",
            "notes": [...]
        }
        """
        title_words = set(post.get("title","").split())
        platforms = set()
        same_content_count = 0
        notes = []

        # 같은 내용이 여러 플랫폼에 있는지 확인
        for r in all_results:
            if r.get("url") == post.get("url"):
                continue
            r_words = set(r.get("title","").split())
            # 제목 유사도 (50% 이상 겹치면 동일 콘텐츠로 판단)
            if len(title_words) > 0:
                overlap = len(title_words & r_words) / len(title_words)
                if overlap >= 0.5:
                    same_content_count += 1
                    platforms.add(r.get("platform",""))

        # 조회수 급증 여부
        views = post.get("views", 0)
        pub_time = post.get("published_at", "")
        spread_speed = "느림"
        if isinstance(views, int):
            if views > 100000:
                spread_speed = "바이럴"
                notes.append(f"10만 조회 달성 — 즉시 대응 필요")
            elif views > 50000:
                spread_speed = "빠름"
                notes.append(f"5만 조회 — 확산 중")
            elif views > 10000:
                spread_speed = "보통"

        # 렉카 여부
        channel = post.get("channel", post.get("author","")).lower()
        if any(k in channel for k in ["렉카","폭로","논란"]):
            notes.append("렉카 채널 확산 — 수익형 콘텐츠")
            same_content_count += 1

        # 쇼츠/클립 여부
        if post.get("type") in ["쇼츠/릴스", "쇼츠"]:
            notes.append("쇼츠/릴스 — 빠른 알고리즘 확산 가능")
            spread_speed = "빠름" if spread_speed == "느림" else spread_speed

        is_spreading = same_content_count >= 2 or spread_speed in ["빠름","바이럴"]

        return {
            "is_spreading": is_spreading,
            "spread_count": same_content_count,
            "platforms": list(platforms),
            "spread_speed": spread_speed,
            "notes": notes
        }
