"""
NC 다이노스 보도자료 자동 작성 시스템 (v3.5)
메일/메시지 → 바로 초안 생성 지원
"""
import streamlit as st
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config_manager as cm
from generator import generate, get_category_fields, call_groq
from docx_writer import save_docx

st.set_page_config(page_title="NC 다이노스 보도자료 시스템", page_icon="⚾", layout="wide")

st.markdown("""
<style>
.main-title{font-size:1.6rem;font-weight:700;color:#003087;margin-bottom:0.2rem}
.sub-title{font-size:0.9rem;color:#666;margin-bottom:1.5rem}
.ref-box{background:#f0f4ff;border-left:4px solid #003087;padding:0.6rem 1rem;border-radius:4px;margin-bottom:0.5rem;font-size:0.85rem}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.8rem;font-weight:600;margin-right:6px}
.b-마케팅{background:#e8f4fd;color:#0070c0}
.b-사회공헌{background:#e8f8e8;color:#107010}
.b-선수단{background:#fff0e0;color:#c07000}
.b-위기관리{background:#fde8e8;color:#c00000}
.crisis-alert{background:#fde8e8;border-left:4px solid #c00000;padding:0.7rem 1rem;border-radius:4px;margin-bottom:1rem;font-size:0.9rem}
.mode-card{border:2px solid #dee2e6;border-radius:8px;padding:1rem;cursor:pointer;text-align:center}
.mode-active{border-color:#003087;background:#f0f4ff}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⚾ NC 다이노스 보도자료 자동 작성 시스템</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">실제 보도자료를 학습한 AI가 구단 문체로 초안을 생성합니다</div>', unsafe_allow_html=True)
st.divider()

# ── API 키 확인 (OpenRouter 또는 Groq) ───────────────────────────────────────────
api_key = os.environ.get("OPENROUTER_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
if not api_key:
    st.error("❌ API 키가 설정되지 않았습니다. .env 파일에 OPENROUTER_API_KEY를 입력하세요.")
    st.stop()

# ── 세션 초기화 ───────────────────────────────────────────
for key, default in [
    ("draft", ""), ("references", []),
    ("auto_category", None), ("input_values", {}),
    ("mode", "mail"),  # mail 또는 form
]:
    if key not in st.session_state:
        st.session_state[key] = default

cfg = cm.load()
# get_category_fields()는 카테고리명을 받아 해당 카테고리 정보 반환
# app.py에서는 전체 dict가 필요하므로 모든 카테고리를 한 번에 가져옴
all_category_fields = {cat: get_category_fields(cat) for cat in cfg.get("categories", [])}
non_crisis_categories = [c for c in cfg["categories"] if c != "위기관리"]

# ── 작성 모드 선택 ────────────────────────────────────────
col_m1, col_m2 = st.columns(2)
with col_m1:
    if st.button("📧 메일·메시지로 바로 생성", use_container_width=True,
                 type="primary" if st.session_state["mode"] == "mail" else "secondary"):
        st.session_state["mode"] = "mail"
        st.session_state["draft"] = ""
        st.session_state["references"] = []
        st.rerun()
with col_m2:
    if st.button("📋 항목 직접 입력", use_container_width=True,
                 type="primary" if st.session_state["mode"] == "form" else "secondary"):
        st.session_state["mode"] = "form"
        st.session_state["draft"] = ""
        st.session_state["references"] = []
        st.rerun()

st.divider()

# ══════════════════════════════════════════════════════════
# 모드 1: 메일·메시지 → 바로 초안 생성
# ══════════════════════════════════════════════════════════
if st.session_state["mode"] == "mail":
    col_left, col_right = st.columns([1, 1.3], gap="large")

    with col_left:
        st.subheader("📧 메일·메시지 입력")
        st.caption("받은 내용을 그대로 붙여넣으면 AI가 분석해서 보도자료를 바로 작성합니다.")

        mail_text = st.text_area(
            "내용 붙여넣기",
            height=300,
            placeholder="예)\n2026년 5월 8일(금) vs 삼성\n5월 8일~10일 3연전 홍보 및 굿네이버스 데이\n[5월 8일(금) 세이프 플레이 DAY]\n- 외부 프로모션, 김해서부소장서 안전 교육 부스\n- 승리기원 시구/시타",
            label_visibility="collapsed"
        )

        category_hint = st.selectbox(
            "카테고리 힌트 (선택사항)",
            ["AI가 자동 판단"] + non_crisis_categories,
            help="카테고리를 미리 지정하면 더 정확한 초안이 생성됩니다."
        )

        generate_btn = st.button(
            "✨ 보도자료 초안 바로 생성",
            type="primary",
            use_container_width=True,
            disabled=not mail_text.strip()
        )

    with col_right:
        st.subheader("📄 생성된 초안")

        if generate_btn and mail_text.strip():
            with st.spinner("🤖 AI가 분석 후 보도자료를 작성 중입니다..."):
                try:
                    # 카테고리 힌트 처리
                    cat_instruction = ""
                    if category_hint != "AI가 자동 판단":
                        cat_instruction = f"\n카테고리는 반드시 '{category_hint}'로 작성하세요."

                    # 참고 보도자료 검색
                    from vector_store import search
                    refs = search(mail_text[:200], top_k=3)
                    st.session_state["references"] = refs

                    ref_text = ""
                    for i, r in enumerate(refs, 1):
                        ref_text += f"\n\n[참고 보도자료 {i}: {r['title']}]\n{r['text'][:600]}"

                    common_inst = cfg.get("prompt_instructions", {}).get("공통", "")

                    prompt = f"""당신은 NC 다이노스 구단의 공식 보도자료 작성 전문가입니다.

아래 참고 보도자료들의 문체, 구조, 톤앤매너를 분석하고 동일한 스타일로 새 보도자료를 작성하세요.

## 참고 보도자료{ref_text}

## 입력된 내용 (메일/메시지/기획안)
{mail_text}

## 작성 지침
{common_inst}{cat_instruction}

## 구조 및 문체 규칙
1. **구조**: 제목 → 부제목(선택) → 본문 → 인용문 → 마무리 순서로 작성하세요.
   - 본문은 행사 개요 → 주요 행사 내용(시간 순서) → 의미/효과 순으로 전개하세요.
   - 각 문단은 하나의 핵심 내용만 담고, 2~4문장으로 구성하세요.

2. **인용문 처리**:
   - 인용문은 본문 내용을 단순 반복하지 말고, 의미·감사·기대·포부 등 감성적 메시지를 담으세요.
   - 같은 인물의 인용문이 2개 이상일 경우 내용이 겹치지 않도록 각각 다른 메시지를 전달하세요.
   - 형식: 이름 직책은 "○○○ NC 다이노스 ○○"으로 표기하세요.

3. **문체**:
   - 첫 문장은 행사명과 핵심 내용을 간결하게 소개하세요 (80자 이내).
   - 수동태보다 능동태를 사용하세요.
   - 단조로운 나열식 문장(~했다. ~했다. ~했다.) 대신 문장 구조를 다양하게 변화시키세요.
   - 숫자와 구체적 사실(인원, 금액, 날짜 등)을 적극 활용해 생동감을 더하세요.

확인이 필요한 정보는 [확인 필요: ○○]로 표시하세요.
보도자료만 출력하고 다른 설명은 하지 마세요."""

                    draft = call_groq(prompt)
                    st.session_state["draft"] = draft
                    st.rerun()

                except Exception as e:
                    st.error(f"생성 오류: {e}")

        # 참고 보도자료 표시
        if st.session_state.get("references"):
            st.markdown("**📎 참고한 보도자료**")
            for ref in st.session_state["references"]:
                bc = f"b-{ref['category']}"
                st.markdown(
                    f'<div class="ref-box"><span class="badge {bc}">{ref["category"]}</span>'
                    f'{ref["title"]} <span style="color:#999;font-size:0.8rem;">(유사도: {ref["score"]:.0%})</span></div>',
                    unsafe_allow_html=True)

        current_draft = st.session_state.get("draft", "")
        edited_draft = st.text_area(
            "초안 편집 (직접 수정 가능)",
            value=current_draft,
            height=480,
            placeholder="왼쪽에 메일·메시지 내용을 붙여넣고 버튼을 누르세요."
        )

        col_save, col_reset = st.columns([2, 1])
        with col_save:
            if st.button("💾 Word 파일로 저장", use_container_width=True, disabled=not edited_draft.strip()):
                with st.spinner("Word 파일 생성 중..."):
                    try:
                        title_line = next((l.strip() for l in edited_draft.splitlines() if l.strip()), "보도자료")
                        cat = st.session_state.get("auto_category") or "마케팅"
                        filepath = save_docx(title_line, edited_draft, cat)
                        with open(filepath, "rb") as f:
                            st.download_button(label="📥 다운로드", data=f,
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True)
                    except Exception as e:
                        st.error(f"저장 오류: {e}")
        with col_reset:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state["draft"] = ""
                st.session_state["references"] = []
                st.rerun()

# ══════════════════════════════════════════════════════════
# 모드 2: 항목 직접 입력
# ══════════════════════════════════════════════════════════
else:
    col_left, col_right = st.columns([1, 1.3], gap="large")

    with col_left:
        st.subheader("📋 보도자료 정보 입력")

        auto_cat = st.session_state.get("auto_category") or non_crisis_categories[0]
        auto_cat_idx = non_crisis_categories.index(auto_cat) if auto_cat in non_crisis_categories else 0
        input_values = st.session_state.get("input_values", {})

        category = st.radio("카테고리 선택", options=non_crisis_categories,
                            index=auto_cat_idx, horizontal=True)
        st.markdown(
            '<div style="font-size:0.8rem;color:#c00000;margin-top:-8px;margin-bottom:8px">'
            '🚨 위기관리는 사이드바 → Crisis Management 페이지를 이용하세요</div>',
            unsafe_allow_html=True
        )
        st.markdown("---")

        cat_info = all_category_fields.get(category, {})
        fields = cat_info.get("fields", [])
        sub_categories = cat_info.get("sub_categories", [])

        # 세부 카테고리 선택
        sub_category = ""
        if sub_categories:
            sub_category = st.selectbox("세부 카테고리", sub_categories)

        inputs = {}
        textarea_keys = {"event_detail", "response", "contract_detail", "extra",
                         "player_record", "activity_detail", "amount_or_items"}

        for field_label in fields:
            field_key = field_label.replace(" ", "_").replace("·", "_").replace("*", "").strip()
            val = input_values.get(field_key, "")
            if field_key in textarea_keys or len(field_label) > 6:
                inputs[field_key] = st.text_area(field_label, value=val, height=80,
                    placeholder="내용을 입력하세요")
            else:
                inputs[field_key] = st.text_input(field_label, value=val,
                    placeholder="내용을 입력하세요")

        generate_btn = st.button("✨ 보도자료 초안 생성", type="primary", use_container_width=True)

    with col_right:
        st.subheader("📄 생성된 초안")

        if generate_btn:
            with st.spinner("🤖 AI가 보도자료 초안을 작성 중입니다..."):
                try:
                    # 입력값을 하나의 텍스트로 합쳐서 generate() 호출
                    content_lines = []
                    for k, v in inputs.items():
                        if v.strip():
                            content_lines.append(f"{k}: {v}")
                    content = "\n".join(content_lines)

                    from vector_store import search
                    refs = search(content[:200], top_k=3)
                    st.session_state["references"] = refs

                    style_rules = cfg.get("style_rules", [])
                    common_inst = cfg.get("prompt_instructions", {}).get("공통", "")

                    draft = generate(
                        content=content,
                        category=category,
                        sub_category=sub_category,
                        year="2026",
                        reference_texts=refs,
                        style_rules=style_rules,
                        custom_guidelines=common_inst,
                        config=cfg,
                    )
                    st.session_state["draft"] = draft
                    st.session_state["input_values"] = {}
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 오류: {e}")

        if st.session_state.get("references"):
            st.markdown("**📎 참고한 보도자료**")
            for ref in st.session_state["references"]:
                bc = f"b-{ref['category']}"
                st.markdown(
                    f'<div class="ref-box"><span class="badge {bc}">{ref["category"]}</span>'
                    f'{ref["title"]} <span style="color:#999;font-size:0.8rem;">(유사도: {ref["score"]:.0%})</span></div>',
                    unsafe_allow_html=True)

        current_draft = st.session_state.get("draft", "")
        edited_draft = st.text_area(
            "초안 편집 (직접 수정 가능)",
            value=current_draft,
            height=480,
            placeholder="왼쪽에서 정보를 입력하고 '초안 생성' 버튼을 누르세요."
        )

        col_save, col_reset = st.columns([2, 1])
        with col_save:
            if st.button("💾 Word 파일로 저장", use_container_width=True, disabled=not edited_draft.strip()):
                with st.spinner("Word 파일 생성 중..."):
                    try:
                        title_line = next((l.strip() for l in edited_draft.splitlines() if l.strip()), "보도자료")
                        filepath = save_docx(title_line, edited_draft, category)
                        with open(filepath, "rb") as f:
                            st.download_button(label="📥 다운로드", data=f,
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True)
                    except Exception as e:
                        st.error(f"저장 오류: {e}")
        with col_reset:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state["draft"] = ""
                st.session_state["references"] = []
                st.session_state["input_values"] = {}
                st.rerun()

st.divider()
st.markdown("""<div style="font-size:0.8rem;color:#888;text-align:center;">
⚠️ AI 생성 초안은 반드시 검토 후 사용 &nbsp;|&nbsp;
[확인 필요: ○○] 항목은 실제 정보로 교체 &nbsp;|&nbsp;
🚨 위기관리는 사이드바 Crisis Management 페이지 이용
</div>""", unsafe_allow_html=True)
