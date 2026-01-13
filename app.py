from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
from Levenshtein import distance
import os

app = Flask(__name__)
CORS(app)

CSV_PATH = '感染症の治療期間.csv'  # ファイル名を正しく指定
TOP_N_CANDIDATES = 5

if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"CSVファイルが存在しません: {CSV_PATH}")

# CSVファイルを1行目をヘッダーとして読み込み
df = pd.read_csv(CSV_PATH, header=0)
df.columns = df.columns.str.strip()  # カラム名の前後空白削除

print("読み込んだカラム名：", df.columns.tolist())

# CSVのヘッダー名に合わせて指定
col_patient = '疾患/病態'
col_period = '推奨期間'
col_remarks = '備考'

# 必須カラムの存在チェック
for col in [col_patient, col_period, col_remarks]:
    if col not in df.columns:
        raise ValueError(f"CSVに '{col}' カラムが存在しません。カラム名を再確認してください。")

# 疾患リストと辞書を作成
disease_list = df[col_patient].dropna().tolist()

disease_dict = {}
for _, row in df.iterrows():
    disease = row[col_patient]
    if pd.isna(disease):
        continue
    period = str(row[col_period]) if not pd.isna(row[col_period]) else ''
    remarks = str(row[col_remarks]) if not pd.isna(row[col_remarks]) else ''
    disease_dict[disease] = {'period': period, 'remarks': remarks}

def suggest_diseases_partial(user_text, top_n=TOP_N_CANDIDATES):
    user_text_lower = user_text.lower()
    matched_diseases = []
    for disease in disease_list:
        if user_text_lower in disease.lower():
            matched_diseases.append(disease)
    # 部分一致候補が足りなければLevenshtein距離で補う
    if len(matched_diseases) == 0:
        scored = []
        for disease in disease_list:
            dist = distance(user_text_lower, disease.lower())
            scored.append((disease, dist))
        scored.sort(key=lambda x: x[1])
        return [d[0] for d in scored[:top_n]]
    else:
        return matched_diseases[:top_n]

def generate_answer(disease):
    data = disease_dict.get(disease)
    if not data:
        return "該当感染症の情報がありません。"
    ans = f"【{disease}】の推奨治療期間は {data['period']} です。"
    if data['remarks']:
        ans += f"\nマニュアル引用: 「{disease}: {data['period']} {data['remarks']}」"
    return ans

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask-text', methods=['POST'])
def ask_text():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSONが送信されていません"}), 400
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "テキストが空です"}), 400

    candidates = suggest_diseases_partial(text)
    answers = []
    for disease in candidates:
        answer = generate_answer(disease)
        answers.append({"disease": disease, "answer": answer})

    return jsonify({"candidates": answers})

if __name__ == '__main__':
    print("Flaskサーバー起動: http://localhost:5001")
    app.run(host='0.0.0.0', port=5001)
