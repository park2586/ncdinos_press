"""
TF-IDF 기반 로컬 벡터 스토어
카테고리 우선 + 전체 검색 병행으로 유사도 향상
"""
import os
import pickle
import subprocess
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "tfidf_store.pkl")
UPLOAD_DIR = "/mnt/user-data/uploads"

FILE_CATEGORIES = {
    "NC_다이노스__25시즌_코칭스태프__프런트_워크숍_진행.docx": "선수단",
    "NC__연고지역_중고등학교_야구팀에_의류_선물.docx": "사회공헌",
    "NC_다이노스__FA_김성욱_계약.docx": "선수단",
    "NC_다이노스__케이엔코리아와_킷_스폰서_계약_체결.docx": "마케팅",
    "NC_다이노스_천재환_선수_외_6명__사회공헌을_위한_일일_카페_진행.docx": "사회공헌",
    "NC_다이노스__2025시즌_캐치프레이즈__LIGHT__NOW___공개.docx": "마케팅",
    "NC_다이노스_창원시_창원시설공단__창원NC파크_사고_수습을_위한_합동_대책반_구성_운영.docx": "위기관리",
    "NC_다이노스__NH농협은행과_2024시즌_선수단_팀기록_연계_적립금_기부.docx": "사회공헌",
    "NC_다이노스__2025시즌__민트_멤버십__판매.docx": "마케팅",
    "NC_다이노스__2025_시즌티켓_판매.docx": "마케팅",
}


def extract_text(docx_path: str) -> str:
    """docx 파일에서 텍스트 추출 (python-docx 우선, pandoc 폴백)"""
    try:
        from docx import Document
        doc = Document(docx_path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        if text.strip():
            return text.strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["pandoc", docx_path, "-t", "plain"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def get_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and "자동 생성된 설명" not in line and len(line) > 5:
            return line
    return "제목 없음"


def build_store():
    docs, metas = [], []
    for filename, category in FILE_CATEGORIES.items():
        path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(path):
            continue
        text = extract_text(path)
        if not text:
            continue
        title = get_title(text)
        docs.append(text)
        metas.append({"category": category, "title": title, "filename": filename})
        print(f"[OK] {category:6s} | {title[:45]}")

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=10000)
    matrix = vectorizer.fit_transform(docs)

    store = {"vectorizer": vectorizer, "matrix": matrix, "docs": docs, "metas": metas}
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "wb") as f:
        pickle.dump(store, f)
    print(f"\n✅ {len(docs)}개 저장 완료")
    return store


def load_store():
    if not os.path.exists(DB_PATH):
        return build_store()
    with open(DB_PATH, "rb") as f:
        return pickle.load(f)


def search(query: str, category: str = None, top_k: int = 3):
    """
    유사도 검색 개선:
    - 같은 카테고리 자료 우선 검색
    - 유사도 낮을 경우 전체에서 추가 검색하여 보완
    """
    store = load_store()
    vectorizer = store["vectorizer"]
    matrix = store["matrix"]
    docs = store["docs"]
    metas = store["metas"]

    qvec = vectorizer.transform([query])
    sims = cosine_similarity(qvec, matrix).flatten()

    results = []
    seen = set()

    # 1순위: 같은 카테고리에서 검색
    if category:
        cat_indices = sorted(
            [i for i in range(len(docs)) if metas[i]["category"] == category],
            key=lambda i: sims[i], reverse=True
        )
        for i in cat_indices[:top_k]:
            results.append({
                "score": float(sims[i]),
                "title": metas[i]["title"],
                "category": metas[i]["category"],
                "text": docs[i],
                "filename": metas[i]["filename"],
            })
            seen.add(i)

    # 2순위: 부족하면 전체에서 추가
    if len(results) < top_k:
        all_indices = sorted(range(len(docs)), key=lambda i: sims[i], reverse=True)
        for i in all_indices:
            if i not in seen:
                results.append({
                    "score": float(sims[i]),
                    "title": metas[i]["title"],
                    "category": metas[i]["category"],
                    "text": docs[i],
                    "filename": metas[i]["filename"],
                })
                seen.add(i)
            if len(results) >= top_k:
                break

    # 유사도 순 재정렬
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
