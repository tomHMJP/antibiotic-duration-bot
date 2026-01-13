````md
# 抗菌薬治療期間Bot

音声または文字入力で感染症名を受け取り、CSVの疾患マスタから候補を提示し、推奨治療期間（＋備考）を表示するローカル用の簡易Webアプリです（Flask）。

> 注意：本アプリは試作・教育目的です。実臨床では施設方針、患者背景、最新ガイドラインを優先してください。

---

## 1. 要件

- Python 3.10+（推奨：3.11/3.12）
- pip
- （任意）仮想環境（venv または conda）

---

## 2. セットアップ

### 2.1 venv（推奨）
```bash
cd /path/to/antibio_bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
````

### 2.2 conda

```bash
conda create -n antibio-bot python=3.12 -y
conda activate antibio-bot
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## 3. データ（CSV）

### 3.1 既定のCSVファイル名

アプリは同一フォルダにある以下のCSVを読み込みます。

* `感染症の治療期間.csv`

`app.py` 内の `CSV_PATH = '感染症の治療期間.csv'` を変更すれば別名にもできます。

### 3.2 必須カラム

CSVの1行目（ヘッダー）に以下のカラムが必要です。

* `疾患/病態`
* `推奨期間`
* `備考`

例：

```csv
疾患/病態,推奨期間,備考
市中肺炎,5日,臨床的改善を確認
蜂窩織炎,5-7日,重症例は延長を検討
```

---

## 4. 起動

```bash
python app.py
```

起動ログ例：

* `Flaskサーバー起動: http://localhost:5001`

ブラウザで以下にアクセス：

* [http://127.0.0.1:5001](http://127.0.0.1:5001)

---

## 5. API

### POST `/ask-text`

入力テキストから候補疾患（上位N件）と回答を返します。

**Request**

```json
{ "text": "肺炎" }
```

**Response（例）**

```json
{
  "candidates": [
    { "disease": "市中肺炎", "answer": "..." },
    { "disease": "誤嚥性肺炎", "answer": "..." }
  ]
}
```

---

## 6. よくあるトラブル

### 6.1 `ValueError: ... カラムが存在しません`

CSVのヘッダーが想定と一致していません。CSVを開いて、1行目が
`疾患/病態,推奨期間,備考`
になっているか確認してください。

### 6.2 `Address already in use`（ポート使用中）

別プロセスが5001番を使用しています。`app.py` の `port=5001` を別ポートに変更するか、使用中プロセスを停止してください。

macOSで確認：

```bash
lsof -nP -iTCP:5001 -sTCP:LISTEN
```

### 6.3 `.DS_Store` がコミットに入る

macOSの隠しファイルです。通常はGit管理しません。`.gitignore` に追加してください。

例：

```gitignore
.DS_Store
__pycache__/
.venv/
venv/
.env
```

---

## 7. セキュリティ・運用上の注意

* 公開リポジトリに個人情報・患者情報・施設内データを入れないでください。
* 依存パッケージは `requirements.txt` で管理します。
* 本番運用（外部公開）を行う場合は、開発用サーバー（Flask内蔵）ではなくWSGI（gunicorn等）を使用してください。

---

## 8. Third-party data

* データ名：万病辞書データ
* 提供元：https://sociocom.naist.jp/
* 入手元URL：https://sociocom.naist.jp/manbyou-dic/
* ライセンス：https://creativecommons.org/licenses/by/4.0/
* 取得日：2026.Jan.12
* 改変：-

```
::contentReference[oaicite:0]{index=0}
```
