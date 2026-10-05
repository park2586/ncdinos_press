"""
NC 다이노스 문법·스타일 가이드 엑셀 파서
"""
import os
import json
import pandas as pd

STYLE_PATH = os.path.join(os.path.dirname(__file__), "db", "style_guide.json")


def extract_style_from_excel(xlsx_path: str) -> dict:
    xl = pd.ExcelFile(xlsx_path)
    style = {
        "보도자료_작성규칙": [],
        "붙여쓰기": [],
        "띄어쓰기": [],
        "표현수정": [],
        "구장명": [],
        "구단명": [],
        "숫자표기": [],
        "용어순환": [],
        "기타": [],
    }

    # ── 1. 보도자료 가이드 시트 ──────────────────────────
    if "보도자료 가이드" in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name="보도자료 가이드", header=None)
        section = None
        for _, row in df.iterrows():
            vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip() not in ["nan",""]]
            if not vals:
                continue
            if "보도자료 작성 가이드" in vals:
                section = "보도자료"
                continue
            if "이미지 제작 가이드" in vals:
                section = "이미지"
                continue
            if "보도자료 작성/배포 업무" in vals:
                section = None
                continue
            if section == "보도자료":
                # 번호 제외, 규칙+예시 합쳐서 저장
                parts = [v for v in vals if not v.isdigit() and v not in ["보도자료","이미지","예시"]]
                if parts:
                    rule = parts[0]
                    example = parts[1] if len(parts) > 1 else ""
                    if example:
                        style["보도자료_작성규칙"].append(f"{rule} (예: {example})")
                    else:
                        style["보도자료_작성규칙"].append(rule)

    # ── 2. NC 문법(2026, 설명) 시트 — 가장 상세한 정보 ──
    if "NC 문법(2026, 설명)" in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name="NC 문법(2026, 설명)", header=None)
        current_category = ""

        for _, row in df.iterrows():
            vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip() not in ["nan",""]]
            if not vals or vals == ["단어","구분","추가 설명"]:
                continue

            # 카테고리 감지
            if len(vals) >= 1 and vals[0] in ["구장명","구단명","기타"]:
                current_category = vals[0]
                vals = vals[1:]

            if not vals:
                continue

            word = vals[0] if len(vals) > 0 else ""
            rule = vals[1] if len(vals) > 1 else ""
            desc = vals[2] if len(vals) > 2 else ""

            if not word or word in ["//", "NC 다이노스 기사 작성 시 참고사항"]:
                continue

            if current_category == "구장명":
                style["구장명"].append(word)
            elif current_category == "구단명":
                if rule and rule not in ["//"]:
                    style["구단명"].append(f"{word} ({rule})")
                else:
                    style["구단명"].append(word)
            elif current_category == "기타":
                if "붙혀쓰기" in rule or "붙여쓰기" in rule:
                    entry = f"{word}" + (f" — {desc}" if desc and desc != "//" else "")
                    style["붙여쓰기"].append(entry)
                elif "띄어쓰기" in rule:
                    entry = f"{word}" + (f" — {desc}" if desc and desc != "//" else "")
                    style["띄어쓰기"].append(entry)
                elif "표현수정" in rule:
                    entry = f"{word}" + (f" ({desc})" if desc and desc != "//" else "")
                    style["표현수정"].append(entry)

    # ── 3. NC 문법(2026) 시트 — 숫자표기, 용어순환 등 ──
    if "NC 문법(2026)" in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name="NC 문법(2026)", header=None)
        for _, row in df.iterrows():
            vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip() not in ["nan",""]]
            if not vals:
                continue

            first = vals[0]
            rest = vals[1:]

            if "시간/숫자" in first or "숫자 표기" in first:
                for v in rest:
                    if len(v) > 5:
                        style["숫자표기"].append(v)
            elif "용어\n순환" in first or "용어순환" in first or "주중경기" in first:
                for v in vals:
                    if len(v) > 3 and v not in ["용어\n순환"]:
                        style["용어순환"].append(v)
            elif "오전/오후" in first or "낮/밤" in first:
                for v in vals:
                    if len(v) > 3:
                        style["숫자표기"].append(v)
            elif any(x in first for x in ["개막전","전지훈련","데이' 표기"]):
                for v in vals:
                    if len(v) > 3:
                        style["용어순환"].append(v)
            elif "CAMP" in " ".join(vals):
                style["기타"].append(f"캠프 표기: {' '.join(vals)}")

    # 중복 제거
    for k in style:
        style[k] = list(dict.fromkeys([v for v in style[k] if v and v not in ["nan","//"]]))

    return style


def save_style(style: dict):
    os.makedirs(os.path.dirname(STYLE_PATH), exist_ok=True)
    with open(STYLE_PATH, "w", encoding="utf-8") as f:
        json.dump(style, f, ensure_ascii=False, indent=2)


def load_style() -> dict:
    if not os.path.exists(STYLE_PATH):
        return {}
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_style_prompt(style: dict) -> str:
    if not style:
        return ""

    lines = ["\n## NC 다이노스 공식 문법·표기 가이드 (반드시 준수)"]

    if style.get("보도자료_작성규칙"):
        lines.append("\n### 보도자료 작성 규칙")
        for i, rule in enumerate(style["보도자료_작성규칙"], 1):
            lines.append(f"{i}. {rule}")

    if style.get("붙여쓰기"):
        lines.append(f"\n### 붙여쓰기 (반드시 붙여쓸 것)")
        for v in style["붙여쓰기"]:
            lines.append(f"- {v}")

    if style.get("띄어쓰기"):
        lines.append(f"\n### 띄어쓰기 (반드시 띄어쓸 것)")
        for v in style["띄어쓰기"]:
            lines.append(f"- {v}")

    if style.get("표현수정"):
        lines.append(f"\n### 올바른 표현 (괄호 안은 틀린 표현)")
        for v in style["표현수정"]:
            lines.append(f"- {v}")

    if style.get("숫자표기"):
        lines.append(f"\n### 숫자·시간 표기법")
        for v in style["숫자표기"]:
            lines.append(f"- {v}")

    if style.get("용어순환"):
        lines.append(f"\n### 용어 표기 원칙")
        for v in style["용어순환"]:
            lines.append(f"- {v}")

    if style.get("구장명"):
        lines.append(f"\n### 공식 구장명\n{', '.join(style['구장명'])}")

    if style.get("구단명"):
        lines.append(f"\n### 공식 구단명 표기\n{', '.join(style['구단명'])}")

    return "\n".join(lines)
