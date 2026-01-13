# app.py
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from Levenshtein import distance as levenshtein_distance

# -----------------------------
# App / configuration
# -----------------------------
app = Flask(__name__)

# Same-origin前提のローカル利用が基本。必要なら環境変数でHOSTを0.0.0.0に。
# /diseases もフロントから叩くのでCORS対象に含める
CORS(
    app,
    resources={
        r"/ask-text": {"origins": [r"http://127\.0\.0\.1:\d+", r"http://localhost:\d+"]},
        r"/diseases": {"origins": [r"http://127\.0\.0\.1:\d+", r"http://localhost:\d+"]},
        r"/health": {"origins": [r"http://127\.0\.0\.1:\d+", r"http://localhost:\d+"]},
    },
)

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CSV_NAME = "感染症の治療期間.csv"
CSV_PATH = Path(os.getenv("ABX_DATA_CSV", str(BASE_DIR / DEFAULT_CSV_NAME)))

TOP_N_CANDIDATES = int(os.getenv("TOP_N_CANDIDATES", "5"))
HOST = os.getenv("HOST", "127.0.0.1")  # 外部アクセス不要なら127.0.0.1推奨
PORT = int(os.getenv("PORT", "5001"))

# 受け入れる列名（表記ゆれ吸収）
ALIASES = {
    "disease": ["疾患/病態", "患者/病名", "病名", "疾患名", "感染症名"],
    "period": ["推奨期間", "治療期間", "推奨治療期間", "期間"],
    "remarks": ["備考", "注記", "コメント", "メモ", "備考欄"],
}

# -----------------------------
# Dataset (lazy load)
# -----------------------------
DISEASE_LIST: List[str] = []
DISEASE_DICT: Dict[str, Dict[str, str]] = {}
RESOLVED_COLS: Tuple[str, str, str] | None = None
DATASET_ERROR: str | None = None


def _normalize_text(s: str) -> str:
    """
    NFKCで正規化（全角/半角などを寄せる）し、空白除去、lower化。
    """
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFKC", s)
    return s.strip().lower()


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    """
    日本語CSVでありがちな文字コードを順に試行。
    """
    encodings = ["utf-8-sig", "utf-8", "cp932", "shift_jis"]
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            return pd.read_csv(path, header=0, encoding=enc)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"CSVの読み込みに失敗: {path} / 最後のエラー: {last_err}")


def _resolve_column(df: pd.DataFrame, logical: str) -> str:
    df.columns = df.columns.astype(str).str.strip()
    for cand in ALIASES[logical]:
        if cand in df.columns:
            return cand
    raise ValueError(
        f"CSVに必要なカラム '{logical}' が見つかりません。"
        f"想定候補={ALIASES[logical]} / 実際のカラム={df.columns.tolist()}"
    )


def _ensure_dataset_loaded() -> None:
    """
    例外でプロセスを落とさないために遅延ロード＋エラー保持。
    """
    global DISEASE_LIST, DISEASE_DICT, RESOLVED_COLS, DATASET_ERROR

    if DISEASE_LIST or DISEASE_DICT or RESOLVED_COLS or DATASET_ERROR:
        return

    try:
        if not CSV_PATH.exists():
            raise FileNotFoundError(f"CSVが存在しません: {CSV_PATH}")

        df = _read_csv_with_fallback(CSV_PATH)

        col_disease = _resolve_column(df, "disease")
        col_period = _resolve_column(df, "period")
        col_remarks = _resolve_column(df, "remarks")

        tmp_dict: Dict[str, Dict[str, str]] = {}
        for _, row in df.iterrows():
            raw = row.get(col_disease)
            if pd.isna(raw):
                continue
            disease = str(raw).strip()
            if not disease:
                continue

            period = row.get(col_period)
            remarks = row.get(col_remarks)

            tmp_dict[disease] = {
                "period": "" if pd.isna(period) else str(period).strip(),
                "remarks": "" if pd.isna(remarks) else str(remarks).strip(),
            }

        DISEASE_DICT = tmp_dict
        DISEASE_LIST = sorted(tmp_dict.keys())
        RESOLVED_COLS = (col_disease, col_period, col_remarks)

        print("CSV読み込み:", CSV_PATH)
        print("解決したカラム:", RESOLVED_COLS)
        print("登録疾患数:", len(DISEASE_LIST))

    except Exception as e:
        DATASET_ERROR = str(e)
        print("DATASET ERROR:", DATASET_ERROR)


# -----------------------------
# Search / answer
# -----------------------------
def _rank_candidates(query: str, top_n: int = TOP_N_CANDIDATES) -> List[Tuple[str, int]]:
    _ensure_dataset_loaded()
    if DATASET_ERROR:
        return []

    q = _normalize_text(query)
    if not q:
        return []

    substring_hits: List[Tuple[str, int]] = []
    scored: List[Tuple[str, int]] = []

    for disease in DISEASE_LIST:
        d_norm = _normalize_text(disease)
        dist = levenshtein_distance(q, d_norm)
        if q in d_norm:
            substring_hits.append((disease, dist))
        else:
            scored.append((disease, dist))

    if substring_hits:
        substring_hits.sort(key=lambda x: x[1])
        return substring_hits[:top_n]

    scored.sort(key=lambda x: x[1])
    return scored[:top_n]


def _format_answer(disease: str) -> str:
    info = DISEASE_DICT.get(disease)
    if not info:
        return "該当する情報がありません。"

    period = info.get("period", "")
    remarks = info.get("remarks", "")

    lines = [f"", f"推奨治療期間：{period if period else '（記載なし）'}"]
    if remarks:
        lines.append(f"備考：{remarks}")
    return "\n".join(lines)


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    _ensure_dataset_loaded()
    return jsonify(
        {
            "csv_path": str(CSV_PATH),
            "loaded": bool(DISEASE_LIST) and not bool(DATASET_ERROR),
            "n_diseases": len(DISEASE_LIST),
            "resolved_cols": RESOLVED_COLS,
            "error": DATASET_ERROR,
        }
    )


# ★ 追加：A列（疾患名）を全件返す
@app.route("/diseases", methods=["GET"])
def diseases():
    _ensure_dataset_loaded()
    if DATASET_ERROR:
        return jsonify({"error": DATASET_ERROR}), 500

    # 既にユニーク&ソート済み（DISEASE_LIST）だが、念のため空文字を除外
    diseases_list = [d for d in DISEASE_LIST if isinstance(d, str) and d.strip()]
    return jsonify({"diseases": diseases_list, "n_diseases": len(diseases_list)})


@app.route("/ask-text", methods=["POST"])
def ask_text():
    _ensure_dataset_loaded()
    if DATASET_ERROR:
        return jsonify({"error": DATASET_ERROR}), 500

    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify({"error": "テキストが空です"}), 400

    ranked = _rank_candidates(text)
    candidates = []
    for disease, dist in ranked:
        info = DISEASE_DICT.get(disease, {})
        candidates.append(
            {
                "disease": disease,
                "distance": dist,
                "period": info.get("period", ""),
                "remarks": info.get("remarks", ""),
                "answer": _format_answer(disease),
            }
        )

    return jsonify({"input": text, "candidates": candidates})


if __name__ == "__main__":
    _ensure_dataset_loaded()
    print(f"Flaskサーバー起動: http://{HOST}:{PORT}")
    # threaded=True はローカル用途で十分。外部公開はWSGI推奨。
    app.run(host=HOST, port=PORT, threaded=True)
