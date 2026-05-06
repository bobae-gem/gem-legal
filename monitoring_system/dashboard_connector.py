"""
상황실 업데이터 연결 — "대표 상황판 갱신"
역할: 분석 완료된 항목을 dashboard_pending.json에 추가
흐름: 모니터링 → 분류 → 위험도 → [이 파일] → 업데이터.html → 대표 승인 → 상황실
"""
import json, os
from datetime import datetime

class DashboardConnector:
    def __init__(self, pending_path="../dashboard_pending.json"):
        self.pending_path = pending_path

    def _load_pending(self):
        try:
            with open(self.pending_path, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"pending": []}

    def _save_pending(self, data):
        with open(self.pending_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _already_exists(self, pending_items, url):
        """중복 URL 체크"""
        return any(
            p.get("detail","").find(url) >= 0 or p.get("id","").startswith("mon_")
            and url in p.get("detail","")
            for p in pending_items
        )

    def push_to_pending(self, post: dict, classification: dict, risk: dict, spread: dict) -> bool:
        """
        분석된 항목을 pending에 추가
        반환: True(추가됨) / False(중복)
        """
        data = self._load_pending()
        pending = data.get("pending", [])

        url = post.get("url", "")

        # 중복 체크
        for p in pending:
            if url and url in p.get("detail", ""):
                print(f"[Dashboard] 중복 건너뜀: {post.get('title','')[:40]}")
                return False

        now = datetime.now()
        ts = f"{now.year}. {now.month}. {now.day}. {now.strftime('%H:%M')}"

        risk_level = risk.get("risk_level", "mid")
        priority_map = {"urgent":"urgent","high":"high","mid":"mid","low":"low"}

        detail_parts = []
        if post.get("channel") or post.get("author"):
            detail_parts.append(f"채널/작성자: {post.get('channel') or post.get('author')}")
        if post.get("description"):
            detail_parts.append(f"내용: {post.get('description','')[:200]}")
        if url:
            detail_parts.append(f"URL: {url}")
        views = post.get("views")
        if views and isinstance(views, int):
            detail_parts.append(f"조회수: {views:,}회")
        comments = post.get("comments")
        if comments and isinstance(comments, int):
            detail_parts.append(f"댓글: {comments}개")
        if risk.get("risk_factors"):
            detail_parts.append(f"위험 요소: {', '.join(risk['risk_factors'][:4])}")
        if spread.get("notes"):
            detail_parts.append(f"확산: {', '.join(spread['notes'][:2])}")

        # 대응 연결 자동 결정
        connects = self._determine_connects(classification, risk)

        item = {
            "id": f"mon_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(url) % 9999:04d}",
            "category": "alert",
            "priority": priority_map.get(risk_level, "mid"),
            "title": f"[{post.get('platform','?')}·{post.get('type','?')}] {post.get('title','(제목 없음)')[:60]}",
            "detail": "\n".join(detail_parts),
            "sources": [f"{post.get('platform','?')} 자동 수집", f"감지 키워드: {post.get('query','')}"],
            "confidence": classification.get("confidence", 50),
            "confidence_reasons": classification.get("reasons", [])[:4],
            "time": ts,
            "status": "pending",
            "vtypes": classification.get("types", []),
            "connects": connects,
            "risk_score": risk.get("risk_score", 0),
            "is_spreading": spread.get("is_spreading", False),
            "auto_detected": True,
            "raw_url": url
        }

        pending.insert(0, item)
        data["pending"] = pending
        self._save_pending(data)
        print(f"[Dashboard] 추가: {item['title'][:50]} (위험도: {risk_level})")
        return True

    def _determine_connects(self, classification, risk):
        """위험 유형에 따라 자동 연결 팀 결정"""
        connects = []
        types = set(classification.get("types", []))
        level = risk.get("risk_level", "low")

        if "허위사실 가능성" in types or "명예훼손 가능성" in types:
            connects.append("법률전략실")
        if "렉카 확산 가능성" in types or level in ("urgent","high"):
            connects.append("행동위험차단팀")
        if "사생활 침해 가능성" in types:
            connects.append("법률전략실")
        if "법적 대응 검토 필요" in types:
            if "법률전략실" not in connects:
                connects.append("법률전략실")
            connects.append("판사시점분석팀")

        return list(set(connects)) or ["행동위험차단팀"]
