"""
증거보존기 — "삭제 전에 저장하는 직원"
역할: 발견된 게시물을 evidence_storage/에 즉시 저장
"""
import json, os
from datetime import datetime

class EvidenceManager:
    def __init__(self, storage_path="evidence_storage"):
        self.storage_path = storage_path
        for folder in ["youtube","community","news","instagram","shorts"]:
            os.makedirs(os.path.join(storage_path, folder), exist_ok=True)

    def _get_folder(self, platform):
        mapping = {
            "유튜브": "youtube",
            "커뮤니티": "community",
            "뉴스": "news",
            "인스타그램": "instagram",
            "틱톡": "shorts",
        }
        return mapping.get(platform, "community")

    def save(self, post: dict, classification: dict, risk: dict, spread: dict) -> str:
        """
        증거 저장 — 파일명: YYYYMMDD_HHMMSS_platform.json
        반환: 저장된 파일 경로
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self._get_folder(post.get("platform",""))
        filename = f"{ts}_{folder}_{abs(hash(post.get('url',''))%9999):04d}.json"
        filepath = os.path.join(self.storage_path, folder, filename)

        evidence = {
            "saved_at":       datetime.now().isoformat(),
            "platform":       post.get("platform"),
            "type":           post.get("type"),
            "title":          post.get("title"),
            "author":         post.get("channel") or post.get("author"),
            "url":            post.get("url"),
            "published_at":   post.get("published_at"),
            "found_at":       post.get("found_at"),
            "content": {
                "description": post.get("description",""),
                "body":        post.get("body","")
            },
            "stats": {
                "views":    post.get("views",0),
                "likes":    post.get("likes",0),
                "comments": post.get("comments",0)
            },
            "analysis": {
                "classification": classification,
                "risk":           risk,
                "spread":         spread
            },
            "legal_note": "공개 게시물에서 수집됨. 비공개 정보 미포함."
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(evidence, f, ensure_ascii=False, indent=2)

        print(f"[증거보존] 저장: {filepath}")
        return filepath

    def list_evidence(self, platform=None, days=7):
        """저장된 증거 목록 조회"""
        results = []
        folders = [self._get_folder(platform)] if platform else ["youtube","community","news","instagram","shorts"]
        for folder in folders:
            path = os.path.join(self.storage_path, folder)
            if not os.path.exists(path):
                continue
            for fname in sorted(os.listdir(path), reverse=True)[:50]:
                if fname.endswith(".json"):
                    fpath = os.path.join(path, fname)
                    try:
                        with open(fpath, encoding="utf-8") as f:
                            data = json.load(f)
                        results.append(data)
                    except:
                        pass
        return results
