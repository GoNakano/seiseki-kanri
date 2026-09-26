# seiseki-kanri

[![CI](https://github.com/GoNakano/seiseki-kanri/actions/workflows/ci.yml/badge.svg)](https://github.com/GoNakano/seiseki-kanri/actions/workflows/ci.yml)

大学の成績を登録して、GPA/GPSや取得単位を確認するFlaskアプリです。

成績表を手入力するだけでなく、大学ポータルからコピーしたHTMLを貼り付けて科目を取り込めるようにしています。登録したデータはユーザーごとに分けてSQLiteへ保存します。

大学公式のサービスではありません。成績情報を扱うため、基本的にはローカルで使う前提です。

このアプリは生成AIを使って作成しました。2026年9月のコード整理（ファイル分割・DB接続の共通化など）と自動テストの追加も、生成AI（Claude Code）で行っています。

デモ：https://seiseki-kanri.onrender.com （初回表示に時間がかかる場合があります。ダミーアカウントとサンプルデータで確認してください）

## できること

- 科目の追加・編集・削除
- GPA/GPS、取得単位、カテゴリ別の進捗の表示
- 年度別GPAと評価分布のグラフ表示
- CAMPUS WEBの成績表HTMLの解析と一括登録
- 自分の成績だけを出力するCSV機能
- 講義レビューの記録と、公開を選んだレビューの匿名表示
- ダミーのサンプルデータを使った画面確認

## 計算と対応範囲

- GPA/GPSの対象は `A+`・`A`・`B`・`C`・`F` の5段階です。その他の評価表記は計算対象外です。
- F評価はGPAの分母に含めます。取得単位にはF評価と年度不明の科目を含めません。
- カテゴリ別の卒業要件は、現在は立命館大学のカリキュラムを前提にしています。
- HTML取込は立命館CAMPUSの想定テーブル形式に対応しています。刷新後の実際の成績表HTMLでの動作は未確認です。

公開環境で確認する場合も、実際の成績HTML・大学ID・パスワード・個人情報は入力せず、サンプルデータだけを使用してください。

## 画面イメージ

> 以下はダミーデータを用いた画面例です。実際の成績情報は含まれていません。

### 科目管理画面

![科目管理画面](docs/screenshots/course-list.png)

### GPA・単位取得状況の可視化画面

![GPA・単位取得状況の可視化画面](docs/screenshots/dashboard-charts.png)

---

## このリポジトリで見てほしいところ

### HTMLの取込

CAMPUS WEBからユーザーがコピーしたHTMLをBeautifulSoupで解析し、科目名・単位数・評価・年度を取り出します。大学IDやパスワードをアプリに入力させる自動ログインは実装していません。

### ユーザーごとのデータ分離

成績の取得・追加・更新・削除は、ログイン中のユーザーIDを条件にして処理しています。CSV出力も自分のデータだけが対象です。

### GPAと取得単位

Python側の集計とブラウザ側の表示で同じ5段階のルールを使うようにしています。F評価はGPAに含め、取得単位には含めません。

### 公開を前提にした設定

`.env`、SQLiteのDB、ログはGit管理に含めない設定です。ランキングと初期管理者は環境変数で無効にできます。

### 自動テスト

`tests/` で、ダミーデータを使って次の点を確認しています。GitHub Actionsでpushのたびに実行します。

- 他のユーザーの科目が一覧に出ず、更新・削除もできないこと、CSV出力が自分の科目だけになること
- ログイン（誤ったパスワードでは入れないこと）と、アカウント削除で本人のレビューも消えること
- 科目名からのカテゴリ推定（全角数字の扱い、キーワードによる推定を含む）
- GPAと取得単位の計算（F評価の扱いを含む）
- 成績表HTMLの解析と、想定外のHTMLを拒否すること
- 講義レビューの匿名表示と、非公開レビューが一覧に出ないこと
- デモデータの登録がログイン必須で、重複しないこと

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 使用技術

### バックエンド

- Python
- Flask
- SQLite
- Flask-Login
- Flask-WTF
- BeautifulSoup4

### フロントエンド

- HTML
- CSS
- JavaScript
- Chart.js

### その他

- Git / GitHub
- GitHub Actions（pushのたびに自動テスト）
- Dependabot（依存ライブラリの更新通知）

### 起動・運用

- Gunicornによる本番起動
- `/healthz`による稼働確認

---

## ファイル構成

```text
app.py                 アプリの入口（設定・ログイン管理・セキュリティヘッダー・ルートの登録）
settings.py            環境変数から読む設定
db.py                  データベースの接続（get_db）・テーブル作成
models.py              ログインに使うユーザー
forms.py               入力フォーム
stats.py               GPA・GPSの計算とランキング用の集計
subject_categories.py  科目名からカテゴリを推定する
routes/
  auth.py              ログイン・新規登録・プロフィール
  courses.py           ホーム画面、科目の登録・更新・削除・CSV出力
  campus_import.py     成績表HTMLの解析
  reviews.py           講義レビュー
  ranking.py           ランキング（ENABLE_RANKINGで無効にできる）
static/data/subject_categories.json  科目一覧と分類ルール（サーバーと画面で共通）
templates/             画面のHTML（スタイルとスクリプトは static/ に分けている）
tests/                 自動テスト
```

## データの流れ

1. ユーザーがログインし、科目を手入力するか成績表HTMLを貼り付ける
2. Flaskが入力を検証し、SQLiteへ保存する
3. ブラウザがAPIから自分の科目だけを取得して、GPA/GPSとグラフを更新する
4. HTML取込は解析結果を確認してから登録する

大学ポータルへ自動ログインする機能はありません。講義レビューは、公開を選んだものだけ匿名で表示します。

## セットアップ

Python 3.11以降を使用してください。

### 1. リポジトリをクローン

GitHubの「Code」から取得したURLを使ってクローンします。

```bash
git clone https://github.com/GoNakano/seiseki-kanri.git
cd seiseki-kanri
```

### 2. 仮想環境を作成

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windowsの場合:

```bash
.venv\Scripts\activate
```

### 3. 依存関係をインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数ファイルを作成

```bash
cp .env.example .env
```

`.env`内の`SECRET_KEY`や`ADMIN_PASSWORD`は必要に応じて変更してください。

### 5. アプリを起動

```bash
python3 app.py
```

`.env`の`PORT=5000`を使用するため、開発環境では以下のURLからアクセスできます。

```text
http://localhost:5000
```

ポートが使用中の場合は、`.env`の`PORT`を変更してください。

```env
PORT=5001
```

## デプロイ時の起動

公開環境では、`Procfile`に定義したGunicornからアプリケーションを起動します。

```text
gunicorn --bind 0.0.0.0:$PORT app:app
```

公開環境では、以下の環境変数を必ず設定してください。

- `FLASK_ENV=production`
- `SECRET_KEY`：推測されにくいランダムな値
- `ENABLE_RANKING=false`：公開デモではランキングを無効化
- `ENABLE_DEMO_ADMIN=false`：公開デモでは初期管理者を作成しない
- `ADMIN_PASSWORD`：`ENABLE_DEMO_ADMIN=true`にする場合のみ、初期管理者用に設定

稼働確認には`/healthz`へアクセスし、`{"status": "ok"}`が返ることを確認します。

公開デモでは、実際の成績情報を登録しないでください。SQLiteを利用しているため、デプロイ先のファイル保存仕様とバックアップ方法も確認してください。

ランキング機能は、学生の成績情報をユーザー間で共有するため、公開環境では`ENABLE_RANKING=false`を推奨します。デモ用の初期管理者アカウントも、必要な場合だけ`ENABLE_DEMO_ADMIN=true`で有効化してください。

---

## 使い方

1. 画面の「新規登録」からダミーアカウントを作ってログインする
2. 科目が空の状態で表示される「サンプルデータで試す」を押す
3. 科目一覧、GPA/GPS、単位のグラフを確認する
4. 実際のHTMLを使う場合は、ローカル環境だけで解析と登録を行う

初期管理者アカウントは作成されません。管理者機能が必要な場合だけ、`ENABLE_DEMO_ADMIN=true`と強力な`ADMIN_PASSWORD`を設定してください。

## 公開時の注意

このアプリは大学公式のサービスではありません。計算結果は自己管理用の参考値です。大学の制度や成績表HTMLが変わると、取込結果が変わる可能性があります。

次のファイルはGitHubに公開しない設定です。

```text
.env
*.db
*.sqlite
*.sqlite3
__pycache__/
.DS_Store
```

実際の成績データや個人情報を含むHTML・DBは、公開リポジトリに入れないでください。

## 残っている課題

- CAMPUS WEBの刷新後の実際のHTMLで、取込結果を確認する
- 大学や学部ごとに卒業要件を設定できるようにする
- SQLiteを使った公開環境での保存期間とバックアップ方法を決める

---

## ライセンス

MIT Licenseです。詳しくは [LICENSE](LICENSE) を確認してください。
