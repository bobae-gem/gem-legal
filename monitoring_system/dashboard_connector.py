"""
모니터링 → raw_monitoring.json 연결
역할: 수집·분석된 항목을 raw_monitoring.json에 저장
      (상황실 직접 전달 X — 분류실을 거쳐야 함)

올바른 흐름:
  main.py 수집
    ↓
  raw_monitoring.json  ← 여기에 씀
    ↓
  모니터링 센터 (모니터링.html) 에서 확인
    ↓
  분류실 (분류실.html) 에서 분류
    ↓
  needs_dashboard_alert → dashboard_pending.json
  needs_evidence        → 증거보존.html
"""
import json, os
from datetime import datetime

MONITORING_PATH = os.path.join(os.path.dirname(__file__), '..', 'raw_monitoring.json')

class DashboardConnector:
    def __init__(self, pending_path=None):
        # pending_path는 이제 사용 안 함 — raw_monitoring으로 대체
        self.monitoring_path = os.path.normpath(MONITORING_PATH)

    def _load(self):
        try:
            with open(self.monitoring_path, encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"items": []}

    def _save(self, data):
        with open(self.monitoring_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def push_to_pending(self, post: dict, classification: dict, risk: dict, spread: dict) -> bool:
        """
        수집 항목을 raw_monitoring.json에 저장.
        상황실 직접 전달 안 함 — 분류실 거쳐야 함.
        """
        data = self._load()
        items = data.get("items", [])
        url = post.get("url", "")

        # 중복 체크
        if any(i.get("url") == url and url for i in items):
            return False

        now = datetime.now()
        ts = f"{now.year}. {now.month}. {now.day}. {now.strftime('%H:%M')}"

        item = {
            "id": f"mon_{now.strftime('%Y%m%d%H%M%S')}_{abs(hash(url)) % 9999:04d}",
            "platform":    post.get("platform", "?"),
            "ptype":       post.get("type", ""),
            "title":       (post.get("title", "") or "")[:120],
            "author":      post.get("channel") or post.get("author", ""),
            "kw":          post.get("query", ""),
            "url":         url,
            "body":        (post.get("description", "") or "")[:500],
            "postdate":    post.get("published_at", ""),
            "founddate":   ts,
            "views":       post.get("views", ""),
            "likes":       post.get("likes", ""),
            "comments":    post.get("comments", ""),
            "risk":        risk.get("risk_level", "mid"),
            "risk_score":  risk.get("risk_score", 0),
            "vtypes":      classification.get("types", []),
            "confidence":  classification.get("confidence", 0),
            "confidence_reasons": classification.get("reasons", []),
            "capStatus":   "need" if risk.get("risk_level") in ("urgent","high") else "no",
            "is_spreading": spread.get("is_spreading", False),
            "auto_detected": True,
            "class_status": "unclassified",   # 분류실에서 분류 전
            "date":        ts
        }

        items.insert(0, item)
        # 최대 500건 유지
        data["items"] = items[:500]
        data["last_updated"] = now.isoformat()
        self._save(data)
        print(f"[모니터링] 저장: {item['title'][:50]} (위험도: {item['risk']})")
        return True
