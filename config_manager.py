"""
시스템 설정 관리자
카테고리, 키워드, 프롬프트 등 모든 설정을 config.json에 저장합니다.
"""
import os
import json
from copy import deepcopy

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# ── 기본값 (최초 실행 시 config.json 생성에 사용) ─────────────────
DEFAULT_CONFIG = {
    "version": "1.0.0",
    "categories": ["마케팅", "사회공헌", "선수단", "위기관리"],
    "category_descriptions": {
        "마케팅": "마케팅·이벤트·스폰서 관련 공식 보도자료",
        "사회공헌": "지역사회 공헌·기부·봉사 활동 관련 공식 보도자료",
        "선수단": "선수단 FA계약·입단·방출·수상·훈련 관련 공식 보도자료",
        "위기관리": "사고·위기 상황에 대한 공식 입장 및 대응 보도자료",
    },
    "category_keywords": {
        "마케팅":   ["멤버십", "티켓", "판매", "스폰서", "계약 체결", "캐치프레이즈", "이벤트", "행사", "홍보"],
        "사회공헌": ["기부", "사회공헌", "봉사", "후원", "지원", "나눔", "아마추어", "취약계층"],
        "선수단":   ["FA", "계약", "입단", "방출", "수상", "워크숍", "훈련", "캠프", "코칭", "선수"],
        "위기관리": ["사고", "대책", "합동", "재발방지", "안전", "수습", "입장", "위기", "긴급"],
    },
    "category_fields": {
        "마케팅": [
            ["event_name",   "행사/이벤트명 *"],
            ["event_date",   "일시 *"],
            ["event_place",  "장소"],
            ["event_detail", "주요 내용 (혜택, 프로그램 등) *"],
            ["partner",      "파트너사/협력사"],
            ["quote_person", "코멘트 인물 (이름, 직책)"],
            ["extra",        "추가 참고사항"],
        ],
        "사회공헌": [
            ["activity_name",   "활동명 *"],
            ["activity_date",   "일시 *"],
            ["activity_place",  "장소"],
            ["beneficiary",     "지원 대상/수혜자"],
            ["amount_or_items", "기부금액 또는 물품"],
            ["participants",    "참여 선수 또는 임직원"],
            ["quote_person",    "코멘트 인물 (이름, 직책)"],
            ["extra",           "추가 참고사항"],
        ],
        "선수단": [
            ["news_type",       "보도자료 유형 (FA계약/입단/방출/수상/워크숍 등) *"],
            ["player_name",     "선수명 *"],
            ["player_position", "포지션"],
            ["contract_detail", "계약 내용 (기간, 금액 등)"],
            ["player_record",   "주요 기록/이력"],
            ["quote_person",    "코멘트 인물 (이름, 직책)"],
            ["extra",           "추가 참고사항"],
        ],
        "위기관리": [
            ["incident",     "사고/이슈 개요 *"],
            ["date",         "발생 일시 *"],
            ["response",     "구단 대응 내용 *"],
            ["parties",      "관련 기관/주체"],
            ["quote_person", "공식 발언자 (이름, 직책)"],
            ["extra",        "추가 참고사항"],
        ],
    },
    "prompt_instructions": {
        "공통": (
            "1. 제목은 참고 자료처럼 간결하고 명확하게 (예: \"NC 다이노스, ○○ ○○\")\n"
            "2. 첫 문단에 핵심 내용 (육하원칙) 포함\n"
            "3. 구단 공식 문체 유지 (경어체, ~했다 종결)\n"
            "4. 인물 코멘트는 \"○○은 '...'라고 말했다\" 형식\n"
            "5. 마지막에 반드시 \"(끝)\" 추가\n"
            "6. [첨부파일 설명] 섹션도 간략히 포함\n"
            "7. 실제 공백이나 날짜 등 확인이 필요한 부분은 [확인 필요: ○○]로 표시"
        ),
        "위기관리_추가": "신중하고 책임감 있는 톤 유지, 법적 표현 주의",
    },
    "model": "llama-3.3-70b-versatile",
    "max_tokens": 2000,
    "top_k_references": 2,
}


def load() -> dict:
    """설정 로드. 없으면 기본값으로 생성."""
    if not os.path.exists(CONFIG_PATH):
        save(DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 새 키 누락 시 기본값으로 보완
    for key, val in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = deepcopy(val)
    return cfg


def save(cfg: dict):
    """설정 저장."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def reset():
    """기본값으로 초기화."""
    save(DEFAULT_CONFIG)
    return deepcopy(DEFAULT_CONFIG)


def get_category_fields(cfg: dict) -> dict:
    """category_fields를 generator.py 형식(list of tuple)으로 변환."""
    return {
        cat: [tuple(pair) for pair in pairs]
        for cat, pairs in cfg["category_fields"].items()
    }
