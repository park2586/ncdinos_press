"""
generator.py - NC 다이노스 보도자료 생성기
OpenRouter API 사용 (Groq 네트워크 차단 대응)
"""

import os
import re
import json
import requests
from typing import Optional

# OpenRouter 설정
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# 모델 우선순위
MODEL_PRIORITY = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "groq/compound",
    "groq/compound-mini",
    "qwen/qwen3-8b-27b",
    "meta-llama/llama-3.3-70b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]

# 한자 → 한글 변환 맵
HANJA_MAP = {
    "商品": "상품", "選手": "선수", "球團": "구단", "契約": "계약",
    "協約": "협약", "行事": "행사", "後援": "후원", "社會": "사회",
    "貢獻": "공헌", "施設": "시설", "事故": "사고", "危機": "위기",
    "管理": "관리", "選手團": "선수단", "記錄": "기록", "受賞": "수상",
    "入團": "입단", "放出": "방출", "負傷": "부상", "再活": "재활",
    "寄附": "기부", "奉仕": "봉사", "活動": "활동", "支援": "지원",
    "飲酒": "음주", "運轉": "운전", "賭博": "도박", "情報": "정보",
    "保安": "보안",
}

# 카테고리별 필드 정의
CATEGORY_FIELDS = {
    "마케팅": {
        "sub_categories": ["티켓·멤버십", "스폰서·협약", "이벤트·행사", "브랜드·캐치프레이즈", "상품"],
        "fields": ["행사명", "일시", "장소", "대상", "내용", "담당자"],
    },
    "선수단": {
        "sub_categories": ["계약·입단·방출", "부상·재활", "수상·기록", "기타"],
        "fields": ["선수명", "내용", "계약 조건", "입단일", "비고"],
    },
    "사회공헌": {
        "sub_categories": ["기부·후원", "봉사활동", "아마추어 지원"],
        "fields": ["활동명", "일시", "장소", "대상", "내용", "금액"],
    },
    "위기관리": {
        "sub_categories": ["시설 사고", "선수 사건·사고", "음주운전", "도박", "기타"],
        "fields": ["사건 개요", "발생 일시", "관련 인물", "현재 상황", "대응 조치"],
    },
    "구단": {
        "sub_categories": ["정보보안"],
        "fields": ["내용", "일시", "관련 부서", "조치 사항"],
    },
}


def clean_draft(text: str) -> str:
    """후처리: 한자 제거, NC 다이노스는→가"""
    if not text:
        return text
    for hanja, hangul in HANJA_MAP.items():
        text = text.replace(hanja, hangul)
    text = re.sub(r'[一-鿿぀-ゟ゠-ヿ]+', '', text)
    text = re.sub(r'NC 다이노스는\b', 'NC 다이노스가', text, count=1)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def get_api_key() -> str:
    """API 키 반환 (OpenRouter 우선, Groq fallback)"""
    return (
        os.environ.get("OPENROUTER_API_KEY", "")
        or os.environ.get("GROQ_API_KEY", "")
    )


def call_openrouter(prompt: str, system_prompt: str, api_key: str, model: str) -> str:
    """OpenRouter API 호출"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://nc-dinos-press.streamlit.app",
        "X-Title": "NC Dinos Press Release Generator",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    response = requests.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"{model}: {response.status_code} {response.text[:200]}")


# ── app.py 호환 래퍼 함수들 ──────────────────────────────────────

def call_groq(prompt: str, system_prompt: str = "") -> str:
    """app.py 호환용 — OpenRouter로 실제 호출"""
    api_key = get_api_key()
    if not api_key:
        return "오류: API 키가 설정되지 않았습니다."
    last_error = ""
    for model in MODEL_PRIORITY:
        try:
            result = call_openrouter(prompt, system_prompt or "당신은 NC 다이노스 보도자료 작성 전문가입니다.", api_key, model)
            if result and len(result) > 20:
                return result
        except Exception as e:
            last_error = str(e)
    return f"오류: 모든 모델 실패. {last_error}"


def get_category_fields(category: str) -> dict:
    """카테고리별 입력 필드 반환"""
    return CATEGORY_FIELDS.get(category, {"sub_categories": [], "fields": []})


def generate(
    content: str,
    category: str = "",
    sub_category: str = "",
    year: str = "2026",
    reference_texts: list = None,
    style_rules: list = None,
    custom_guidelines: str = "",
    config: dict = None,
) -> str:
    """보도자료 초안 생성 메인 함수"""
    api_key = get_api_key()
    if not api_key:
        return "오류: OPENROUTER_API_KEY 또는 GROQ_API_KEY가 설정되지 않았습니다."

    # 스타일 규칙
    style_text = ""
    if style_rules:
        rules_list = "\n".join([f"- {r}" for r in style_rules[:30]])
        style_text = f"\n\n[NC 다이노스 문체 가이드]\n{rules_list}"

    # 참고 보도자료
    reference_text = ""
    if reference_texts:
        refs = []
        for i, ref in enumerate(reference_texts[:3], 1):
            title = ref.get("title", "")
            text = ref.get("text", "")[:300]
            refs.append(f"[참고 {i}] {title}\n{text}")
        reference_text = "\n\n[참고 보도자료]\n" + "\n\n".join(refs)

    # 카테고리
    cat_text = ""
    if category:
        cat_text = f"\n카테고리: {category}"
        if sub_category:
            cat_text += f" > {sub_category}"

    # config 프롬프트 규칙
    prompt_rules = ""
    if config and "prompt_rules" in config:
        rules = config["prompt_rules"]
        if isinstance(rules, list):
            prompt_rules = "\n".join([f"{i+1}. {r}" for i, r in enumerate(rules)])
        elif isinstance(rules, str):
            prompt_rules = rules
    if custom_guidelines:
        prompt_rules += f"\n{custom_guidelines}"

    default_rules = """1. 3인칭 평서체 문말어미 사용 (~했다, ~이다, ~할 예정이다)
2. 이메일/SNS 말투 금지
3. 선수 닉네임 사용 금지
4. 반드시 (끝)으로 마무리
5. [첨부파일 설명] 섹션 포함
6. 불확실한 정보는 [확인 필요: ○○] 표기
7. 한자 사용 금지
8. 번호 목록이나 불릿 목록 사용 금지 — 산문 단락으로 작성
9. NC 다이노스가 주어일 때 '~는' 대신 '~가' 사용"""

    system_prompt = f"""당신은 NC 다이노스 구단 공식 보도자료 작성 전문가입니다.
아래 규칙을 반드시 준수하여 보도자료를 작성하세요.

[필수 준수 사항]
{prompt_rules if prompt_rules else default_rules}
{style_text}
{reference_text}"""

    user_prompt = f"""다음 내용을 바탕으로 NC 다이노스 공식 보도자료 초안을 작성해주세요.{cat_text}
연도: {year}

[입력 내용]
{content}

보도자료 형식:
- 제목
- 본문 (산문 단락, 목록 형식 사용 금지)
- [첨부파일 설명]
- (끝)"""

    last_error = ""
    for model in MODEL_PRIORITY:
        try:
            result = call_openrouter(user_prompt, system_prompt, api_key, model)
            if result and len(result) > 50:
                return clean_draft(result)
        except Exception as e:
            last_error = str(e)
            continue

    return f"생성 오류: 모든 모델 실패. 마지막 오류: {last_error}"


def generate_press_release(
    content: str,
    category: str = "",
    sub_category: str = "",
    year: str = "2026",
    reference_texts: list = None,
    style_rules: list = None,
    custom_guidelines: str = "",
    config: dict = None,
) -> str:
    """generate()의 별칭 (하위 호환)"""
    return generate(
        content=content,
        category=category,
        sub_category=sub_category,
        year=year,
        reference_texts=reference_texts,
        style_rules=style_rules,
        custom_guidelines=custom_guidelines,
        config=config,
    )


def analyze_mail_for_press_release(mail_content: str, config: dict = None) -> dict:
    """메일/메시지 분석 → 보도자료 항목 추출"""
    api_key = get_api_key()
    if not api_key:
        return {"error": "API 키 없음"}

    system_prompt = "NC 다이노스 홍보팀 보조 AI입니다. 입력된 메일/메시지에서 보도자료 작성에 필요한 정보를 추출하세요. 반드시 JSON 형식으로 응답하세요."
    user_prompt = f"""다음 내용에서 보도자료 작성에 필요한 정보를 추출해 JSON으로 반환하세요:

{mail_content}

반환 형식:
{{
  "title": "보도자료 예상 제목",
  "category": "마케팅/선수단/사회공헌/위기관리 중 하나",
  "sub_category": "세부 카테고리",
  "key_facts": ["핵심 사실1", "핵심 사실2"],
  "who": "주체/인물",
  "what": "무엇을",
  "when": "언제",
  "where": "어디서",
  "why": "왜/목적",
  "how": "어떻게",
  "quotes": ["인용구"],
  "attachments": ["첨부 예상 파일"],
  "missing_info": ["확인 필요 항목"]
}}"""

    for model in MODEL_PRIORITY[:3]:
        try:
            result = call_openrouter(user_prompt, system_prompt, api_key, model)
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            continue
    return {"error": "분석 실패"}


def generate_crisis_statement(
    incident_type: str,
    stage: str,
    facts: str,
    response_actions: str,
    config: dict = None,
) -> str:
    """위기관리 성명서/보도자료 생성"""
    api_key = get_api_key()
    if not api_key:
        return "오류: API 키 없음"

    stage_guide = {
        "initial": "사건 인지 직후 초기 입장문. 사실 확인 중임을 명시, 추가 입장 예고",
        "interim": "수습 진행 중 중간 입장. 현재 조치 사항, 향후 계획 포함",
        "closure": "최종 입장문. 재발 방지 대책, 사과/유감 표명, 마무리",
    }

    system_prompt = f"""NC 다이노스 구단 위기관리 보도자료 작성 전문가입니다.
{stage_guide.get(stage, '')}
- 3인칭 평서체 사용
- 감정적 표현 자제, 사실 중심
- 법적 책임 인정 표현 주의
- (끝)으로 마무리"""

    user_prompt = f"""위기 유형: {incident_type}
대응 단계: {stage}

[확인된 사실]
{facts}

[현재 대응 조치]
{response_actions}

위 내용을 바탕으로 공식 입장문을 작성하세요."""

    for model in MODEL_PRIORITY[:4]:
        try:
            result = call_openrouter(user_prompt, system_prompt, api_key, model)
            if result and len(result) > 50:
                return clean_draft(result)
        except Exception:
            continue
    return "위기관리 성명서 생성 실패"
