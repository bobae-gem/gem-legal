"""
AI 분류기 — "위험한지 판단하는 변호사"
역할: 수집된 게시물을 8가지 유형으로 분류
"""

# 분류 유형
CLASS_TYPES = [
    "단순 언급",
    "악성 댓글",
    "허위사실 가능성",
    "명예훼손 가능성",
    "모욕 가능성",
    "사생활 침해 가능성",
    "렉카 확산 가능성",
    "법적 대응 검토 필요"
]

# 위험 패턴 사전
RISK_PATTERNS = {
    "허위사실": [
        "피해자가 먼저", "조작", "꾸민", "거짓말", "사기",
        "없는 사실", "날조", "허위", "가짜", "지어낸",
        "사실이래", "그랬대", "했다더라", "썰"
    ],
    "명예훼손": [
        "폭로", "진실", "충격", "실체", "전말", "낱낱이",
        "알아야", "진짜 모습", "실체 공개", "숨긴 진실"
    ],
    "모욕": [
        "쓰레기", "미친", "병신", "X같", "한심",
        "찌질", "역겨", "혐오", "개X", "씹"
    ],
    "렉카": [
        "렉카", "논란정리", "폭로TV", "충격", "경악",
        "난리난", "화제의", "이 영상 봤어?"
    ],
    "사생활": [
        "주소", "집", "가족", "부모", "자녀", "번호",
        "사는 곳", "개인정보", "신상"
    ],
    "확산": [
        "퍼가요", "알려주세요", "공유", "클립", "편집본",
        "짤", "캡처", "대박", "실화냐"
    ]
}


def classify_post(post: dict) -> dict:
    """
    게시물 분류 함수
    반환: {
        "types": ["허위사실 가능성", ...],
        "confidence": 0~100,
        "reasons": ["이유1", ...]
    }
    """
    text = " ".join([
        post.get("title", ""),
        post.get("description", ""),
        post.get("body", "")
    ]).lower()

    detected_types = []
    reasons = []
    confidence_score = 0

    # 렉카 채널 판별
    channel = post.get("channel", post.get("author", "")).lower()
    if any(k in channel for k in ["렉카", "논란", "폭로", "정리tv", "뉴스킹"]):
        detected_types.append("렉카 확산 가능성")
        reasons.append("렉카성 채널명 감지")
        confidence_score += 25

    # 패턴 매칭
    for category, patterns in RISK_PATTERNS.items():
        matched = [p for p in patterns if p.lower() in text]
        if matched:
            if category == "허위사실":
                detected_types.append("허위사실 가능성")
                reasons.append(f"허위사실 패턴: {', '.join(matched[:3])}")
                confidence_score += 30
            elif category == "명예훼손":
                detected_types.append("명예훼손 가능성")
                reasons.append(f"명예훼손 패턴: {', '.join(matched[:3])}")
                confidence_score += 25
            elif category == "모욕":
                detected_types.append("모욕 가능성")
                reasons.append(f"모욕 표현: {', '.join(matched[:3])}")
                confidence_score += 20
            elif category == "렉카":
                if "렉카 확산 가능성" not in detected_types:
                    detected_types.append("렉카 확산 가능성")
                    reasons.append(f"렉카 키워드: {', '.join(matched[:3])}")
                confidence_score += 20
            elif category == "사생활":
                detected_types.append("사생활 침해 가능성")
                reasons.append(f"사생활 정보 언급: {', '.join(matched[:3])}")
                confidence_score += 30
            elif category == "확산":
                reasons.append(f"확산 유도 표현 감지")
                confidence_score += 10

    # 조회수/확산 기반
    views = post.get("views", 0)
    if isinstance(views, int):
        if views > 100000:
            if "렉카 확산 가능성" not in detected_types:
                detected_types.append("렉카 확산 가능성")
            reasons.append(f"조회수 급증: {views:,}회")
            confidence_score += 20
        elif views > 10000:
            reasons.append(f"주목할 만한 조회수: {views:,}회")
            confidence_score += 10

    # 단순 언급 (위험 패턴 없을 때)
    if not detected_types:
        detected_types.append("단순 언급")
        reasons.append("위험 패턴 미감지")
        confidence_score = max(confidence_score, 15)

    # 복합 위험 → 법적 대응 검토
    high_risk = {"허위사실 가능성", "명예훼손 가능성", "렉카 확산 가능성", "사생활 침해 가능성"}
    if len(set(detected_types) & high_risk) >= 2:
        detected_types.append("법적 대응 검토 필요")
        reasons.append("복합 위험 요소 감지")
        confidence_score = min(confidence_score + 15, 100)

    return {
        "types": list(set(detected_types)),
        "confidence": min(confidence_score, 100),
        "reasons": reasons
    }
