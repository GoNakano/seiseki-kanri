from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
import sqlite3
import os
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, IntegerField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional, NumberRange
from bs4 import BeautifulSoup
import json
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

# .envファイルが存在する場合は読み込む（本番環境用）
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

app = Flask(__name__)

# セキュリティ設定：環境に応じたSECRET_KEYの設定
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        raise ValueError("本番環境ではSECRET_KEYの環境変数が必要です")
    app.config['DEBUG'] = False
else:
    app.config['SECRET_KEY'] = 'dev-key-do-not-use-in-production'
    app.config['DEBUG'] = True

# データベースファイルのパス
DB_FILE = os.environ.get('DATABASE_PATH', 'grades.db')

# セキュリティヘッダーの設定
@app.after_request
def after_request(response):
    """レスポンスヘッダーにセキュリティ設定を追加"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ログ設定（本番環境のみ）
if not app.debug and os.environ.get('FLASK_ENV') == 'production':
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('立命館大学成績管理アプリケーション起動')

# Flask-Loginの設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'この機能を使用するにはログインしてください。'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # ユーザーテーブルの作成
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        user_id TEXT UNIQUE,
        nickname TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        graduation_year INTEGER,
        required_credits REAL DEFAULT 124.0,
        settings_json TEXT
    )''')
    
    # 既存のgradesテーブルがない場合は作成
    c.execute('''CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER,
        semester TEXT,
        name TEXT,
        credits REAL,
        grade TEXT,
        category TEXT DEFAULT '未分類',
        memo TEXT,
        user_id INTEGER
    )''')
    
    conn.commit()
    conn.close()

def create_default_user():
    """アプリケーションの初回起動時に管理者ユーザーを作成する関数"""
    try:
        # デフォルトユーザーが存在するか確認
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", ("admin",))
        user = c.fetchone()
        
        # 存在しない場合は作成
        if not user:
            # 本番環境では強力なパスワードを生成
            if os.environ.get('FLASK_ENV') == 'production':
                admin_password = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(16)
                print(f"🔐 管理者アカウント作成完了")
                print(f"👤 ユーザーID: admin")
                print(f"🔑 パスワード: {admin_password}")
                print(f"⚠️  このパスワードは安全に保管してください")
            else:
                admin_password = "admin1234"
                print("デフォルト管理者ユーザーを作成しました。ユーザーID: admin, パスワード: admin1234")
                
            password_hash = generate_password_hash(admin_password)
            c.execute('''
                INSERT INTO users (email, name, password_hash, graduation_year, required_credits, user_id, nickname)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ("admin@example.com", "管理者", password_hash, 2025, 124.0, "admin", "管理者"))
            conn.commit()
        
        conn.close()
    except Exception as e:
        pass  # エラーは無視（管理者アカウントが既に存在する可能性）

# ホームページを表示
@app.route("/")
@login_required  # ログインが必要
def home():
    return render_template("index.html")

# 成績データを取得するAPI
@app.route("/api/get_courses", methods=["GET"])
@login_required
def get_courses():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # 修正: 現在ログインしているユーザーのデータのみを取得
    c.execute("SELECT * FROM grades WHERE user_id = ?", (current_user.id,))
    rows = c.fetchall()
    conn.close()
    courses = [dict(row) for row in rows]
    return jsonify(courses)

# 成績データを追加するAPI
@app.route("/api/add_course", methods=["POST"])
@login_required
def add_course():
    data = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO grades (year, semester, name, credits, grade, category, memo, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("year"),
        data.get("semester"),
        data.get("name"),
        float(data.get("credits", 0)),
        data.get("grade"),
        data.get("category", "未分類"),
        data.get("memo", ""),
        current_user.id
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/delete_course', methods=['POST'])
@login_required
def delete_course():
    index = request.json.get("index")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM grades WHERE id = ? AND user_id = ?", (index, current_user.id))
    conn.commit()
    conn.close()
    return jsonify({'status': 'deleted'})

@app.route('/api/update_course', methods=['POST'])
@login_required
def update_course():
    try:
        req = request.get_json()
        index = req.get("index")
        course = req.get("course")
        
        if not index or not course:
            return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            UPDATE grades
            SET year = ?, semester = ?, name = ?, credits = ?, grade = ?, category = ?, memo = ?
            WHERE id = ? AND user_id = ?
        """, (
            course.get("year"),
            course.get("semester"),
            course.get("name"),
            float(course.get("credits", 0)),
            course.get("grade"),
            course.get("category", "未分類"),
            course.get("memo", ""),
            index,
            current_user.id
        ))
        conn.commit()
        conn.close()
        return jsonify({'status': 'updated'})
    except Exception as e:
        app.logger.error(f"Error updating course: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/add_courses_bulk', methods=['POST'])
@login_required
def add_courses_bulk():
    courses_data = request.get_json()
    
    if not courses_data or not isinstance(courses_data, list):
        return jsonify({"status": "error", "message": "無効なデータ形式です"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        for course in courses_data:
            c.execute("""
                INSERT INTO grades (year, semester, name, credits, grade, category, memo, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                course.get("year"),
                course.get("semester"),
                course.get("name"),
                float(course.get("credits", 0)),
                course.get("grade", ""),
                course.get("category", "未分類"),
                course.get("memo", ""),
                current_user.id
            ))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "count": len(courses_data)})
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/delete_courses_bulk', methods=['POST'])
@login_required
def delete_courses_bulk():
    """
    複数の科目を一括削除するエンドポイント
    """
    ids = request.get_json().get('ids', [])
    
    if not ids or not isinstance(ids, list):
        return jsonify({"status": "error", "message": "無効なデータ形式です"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        # IDのリストを使用して、対象の科目を削除（ユーザーIDでもフィルタリング）
        placeholders = ', '.join(['?'] * len(ids))
        query = f"DELETE FROM grades WHERE id IN ({placeholders}) AND user_id = ?"
        params = ids + [current_user.id]
        c.execute(query, params)
        
        deleted_count = c.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "ok", 
            "message": f"{deleted_count}件の科目を削除しました",
            "count": deleted_count
        })
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/parse_campus_html', methods=['POST'])
@login_required
def parse_campus_html():
    """
    CAMPUSウェブからの成績HTMLを解析し、コース情報として返すエンドポイント
    """
    data = request.get_json()
    html_content = data.get('html', '')
    
    if not html_content:
        return jsonify({"status": "error", "message": "HTMLデータが提供されていません"}), 400
    
    try:
        # BeautifulSoupで解析
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # CAMPUSウェブの成績テーブルを探す（様々なクラス名に対応）
        grades_table = soup.find('table', class_='result_title')
        
        if not grades_table:
            # テーブルが見つからない場合、別の方法で探す
            grades_table = soup.find('table', class_='campusTable')
            
        if not grades_table:
            # さらに別の方法で探す
            grades_table = soup.find('table', {'id': lambda x: x and 'tbl_' in x})
        
        if not grades_table:
            return jsonify({"status": "error", "message": "成績テーブルが見つかりませんでした。正しいCAMPUSウェブの成績表のHTMLを貼り付けてください。"}), 400
        
        rows = grades_table.find_all('tr')
        
        # ヘッダー行をスキップして科目情報を抽出
        courses = []
        
        # 最初の行はヘッダーなのでスキップ
        for row in rows[1:]:
            cells = row.find_all('td', class_='list_cell_center')
            
            # クラスがない場合は一般的なtdタグも検索
            if not cells:
                cells = row.find_all('td')
            
            # 有効な行のみを処理（列数をチェック）
            if len(cells) >= 5:
                try:
                    # 区分（カテゴリ）- 立命館CAMPUSウェブでは0番目
                    category = cells[0].get_text(strip=True) if len(cells) > 0 else "未分類"
                    
                    # 科目名（コード番号を除去）- 立命館CAMPUSウェブでは1番目
                    name_full = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    # 科目コードを除去（例：「53012 生物科学１ *」→「生物科学１ *」）
                    name = name_full.split(' ', 1)[-1] if ' ' in name_full else name_full
                    name = name.replace(' *', '')  # 遠隔授業マーク(*) を除去
                    
                    # 単位数 - 立命館CAMPUSウェブでは4番目
                    credits_text = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    credits = float(credits_text) if credits_text and credits_text.replace('.', '', 1).isdigit() else 0
                    
                    # 成績評価 - 立命館CAMPUSウェブでは5番目
                    grade = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    
                    # 修得年度 - 立命館CAMPUSウェブでは6番目
                    year_text = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                    year = int(year_text) if year_text and year_text.isdigit() else None
                    
                    # 学期（授業開講期間）- 立命館CAMPUSウェブでは7番目
                    semester_text = cells[7].get_text(strip=True) if len(cells) > 7 else ""
                    semester = map_campus_semester(semester_text)
                    
                    # カテゴリのマッピング
                    mapped_category = map_campus_category_to_app_category(category)
                    
                    # 科目名による自動分類も試行（共通専門科目の場合は優先）
                    name_based_category = classify_subject_by_name(name)
                    if name_based_category == '共通専門科目':
                        mapped_category = name_based_category
                    elif mapped_category == '未分類' and name_based_category != '未分類':
                        mapped_category = name_based_category
                    
                    # 科目名と単位数があれば追加
                    if name and credits > 0:
                        course = {
                            "name": name,
                            "credits": credits,
                            "grade": grade,
                            "year": year if year else "",
                            "semester": semester,
                            "category": mapped_category,
                            "memo": f"CAMPUSウェブから自動インポート: 元区分「{category}」"
                        }
                        courses.append(course)
                        
                except Exception as e:
                    # エラーがあっても続行
                    pass
        
        if not courses:
            return jsonify({"status": "warning", "message": "有効な科目データが見つかりませんでした。HTMLが正しいか確認してください。"}), 200
        
        return jsonify({
            "status": "success",
            "message": f"{len(courses)}件の科目データが見つかりました。",
            "courses": courses
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"HTMLの解析中にエラーが発生しました: {str(e)}"}), 500


def map_campus_category_to_app_category(campus_category):
    """
    CAMPUSウェブの区分を本アプリのカテゴリに変換するヘルパー関数
    """
    # 小文字にして空白を削除してマッチングしやすくする
    category_lower = campus_category.lower().replace(' ', '')
    
    # カテゴリマッピング（必要に応じて追加・調整）
    if any(keyword in category_lower for keyword in ['専門', '必修', '選択']):
        if '基礎' in category_lower:
            return '基礎専門科目'
        elif '共通' in category_lower:
            return '共通専門科目'
        elif '必修' in category_lower:
            return '固有専門科目（必修）'
        elif '選択' in category_lower:
            return '固有専門科目（選択）'
        else:
            return '固有専門科目（選択）'  # 「専門科目」は「固有専門科目（選択）」にマッピング
    elif '外国語' in category_lower or 'language' in category_lower:
        return '外国語'
    elif '教養' in category_lower or 'liberal' in category_lower:
        return '教養科目'
    elif 'グローバル' in category_lower or 'キャリア' in category_lower or 'global' in category_lower:
        return 'グローバル・キャリア養成科目'
    else:
        return '未分類'  # デフォルト


def classify_subject_by_name(subject_name):
    """
    科目名に基づいてカテゴリを自動判定するヘルパー関数
    """
    if not subject_name:
        return '未分類'
    
    # 共通専門科目の科目名リスト
    common_specialty_subjects = [
        'ソフトウェア工学',
        'コンピュータネットワーク',
        'デジタル信号処理',
        '計算機構成論',
        'データベース',
        'オペレーティングシステム',
        'ネットワークセキュリティ',
        'コンピュータグラフィックス',
        '人工知能',
        '情報理工基礎演習',
        '情報倫理と情報技術',
        '情報理論',
        '計算機科学入門',
        'Introduction to Information Systems Engineering',
        'Professional Ethics',
        'Introduction to Experimentation',
        'Experimental Design',
        '論理回路',
        'Information Science in Action',
        'Presentation Plus 401',
        'Writing for Publication 402',
        'Writing for Information Systems Engineering',
        'Advanced Academic Reading 403',
        'Presentation for Information Systems Engineering',
        '特殊講義 (共通専門)',
        '特殊講義 (共通専門) DX'
    ]
    
    # 固有専門科目（必修）の科目名リスト
    unique_required_subjects = [
        'プログラミング演習1',
        'プログラミング演習2',
        'システムアーキテクト演習',
        'システムアーキテクトプログラミング演習',
        '計算機科学実験1',
        '計算機科学実験2',
        'システムアーキテクト実験',
        'メディア処理実験',
        'セキュリティ・ネットワーク学実験',
        'セキュリティ・ネットワーク開発演習',
        '社会システムデザイン創成1',
        '社会システムデザイン創成2',
        '実践プログラミング演習',
        '実世界情報演習1',
        '実世界情報演習2',
        '実世界情報演習3',
        '実世界情報実験1',
        '実世界情報実験2',
        '実世界情報実験3',
        'メディア計算機演習',
        'メディア実験1',
        'メディア実験2',
        'メディアプロジェクト演習1',
        'メディアプロジェクト演習2',
        '知能情報基礎演習',
        '知能情報処理演習',
        '知能情報学実験',
        '知能情報システム創成',
        'PBL 1: Problem Analysis and Modeling',
        'PBL 2 Team-based Design',
        'PBL 3: Creative Design',
        'PBL 4: Team-based Creative Design',
        'PBL 5: Design Evolution',
        'Imperative Programming',
        'Imperative Programming Practice',
        '卒業研究1',
        '卒業研究2',
        '卒業研究3'
    ]
    
    # 固有専門科目（選択）の科目名リスト
    unique_elective_subjects = [
        'テキストマイニング',
        'Web アプリケーション',
        'プログラミング言語',
        '電気電子回路',
        'セキュリティ・ネットワーク概論',
        '社会システムデザイン概論',
        'Introduction to Programming',
        'Introduction to OOA, OOD, and UML',
        'データ構造とアルゴリズム',
        'ユーザビリティ工学',
        '計算機アーキテクチャ',
        '機械工学概論',
        'インタラクションデザイン論',
        'ロボティクス',
        'メディア基礎数学',
        '生体生理工学',
        'シミュレーション工学',
        'Network Systems',
        'Human Interface',
        '画像情報処理1',
        '画像情報処理2',
        'オブジェクト指向論',
        '自然言語処理',
        'ヒューマンインタフェース',
        'Web 情報技術概論',
        '実世界情報処理',
        '音声音響情報処理1',
        '音声音響情報処理2',
        'センシング工学',
        'データモデル論',
        'IoT',
        '計算論',
        'システムソフトウェア構成論',
        '分散システム',
        'データ線形分析法',
        'ソフトウェア開発論',
        'コンピュータプログラミング論',
        'データサイエンス',
        '暗号理論',
        'システムセキュリティ',
        '言語処理系',
        'インターネット技術',
        '情報通信ネットワーク',
        '情報アクセス論',
        'データマイニング基礎',
        '認知工学',
        'ユビキタスコンピューティング',
        '機械学習',
        'Web コンピューティング',
        '社会デザイン論',
        '知識工学',
        '生体計測工学',
        'システム制御工学',
        '心理物理学',
        'コンピュータグラフィックス応用',
        'パターン認識',
        '色彩工学',
        '脳機能情報処理',
        '実験データ解析論',
        'Distributed Systems',
        'Web Information Engineering',
        'Data Visualization',
        'Image Processing',
        'Systems Ergonomics',
        'Introduction to Robotic Systems',
        'Pattern Recognition and Machine Learning',
        'Data Science',
        '最適化数学'
    ]
    
    # 基礎専門科目の科目名リスト
    basic_specialty_subjects = [
        '数学1',
        '数学2',
        '数学3',
        '数学4',
        '数学演習1',
        '数学演習2',
        '化学',
        '物理1',
        '物理2',
        '生物科学',
        'Physics',
        'Exercises in Physics',
        '確率・統計',
        '情報基礎数学',
        'Engineering Mathematics 1',
        'Engineering Mathematics 2',
        'Engineering Mathematics 3',
        'Engineering Mathematics 4',
        'フーリエ解析',
        '多変量解析',
        '離散数学',
        '数値解析',
        'Introduction to Differential Equations',
        'Introduction to Probability and Statistics',
        'Statistical Analysis, Simulation, and Modeling',
        'Optimization and Control Theory',
        'Applied Informatics 1',
        'Applied Informatics 2'
    ]
    
    # 外国語科目の科目名リスト
    foreign_language_subjects = [
        # 英語系科目
        '英語入門 091',
        '英語入門 092', 
        '英語初級 101',
        '英語初級 102',
        '英語初級 103',
        '英語初級 104',
        '英語中級 105',
        '英語中級 106',
        '英語中級 107',
        '英語中級 108',
        '英語上級 109',
        '英語上級 110',
        'Professional Communication 301',
        'Academic Literacy 302',
        'Professional Communication 303',
        'Academic Literacy 304',
        
        # 一般的な英語科目
        '英語1',
        '英語2',
        '英語3',
        '英語4',
        '英語入門',
        '英語初級',
        '英語中級',
        '英語上級',
        '英会話',
        '英語コミュニケーション',
        'ビジネス英語',
        '学術英語',
        '英語プレゼンテーション',
        'English Communication',
        'Business English',
        'Academic English',
        'English Presentation',
        
        # その他の外国語
        '中国語1',
        '中国語2', 
        '中国語3',
        '中国語4',
        '中国語入門',
        '中国語初級',
        '中国語中級',
        '韓国語1',
        '韓国語2',
        '韓国語3', 
        '韓国語4',
        '韓国語入門',
        '韓国語初級',
        '韓国語中級',
        'ドイツ語1',
        'ドイツ語2',
        'ドイツ語3',
        'ドイツ語4',
        'ドイツ語入門',
        'ドイツ語初級',
        'ドイツ語中級',
        'フランス語1',
        'フランス語2',
        'フランス語3',
        'フランス語4',
        'フランス語入門',
        'フランス語初級',
        'フランス語中級',
        'スペイン語1',
        'スペイン語2',
        'スペイン語3',
        'スペイン語4',
        'スペイン語入門',
        'スペイン語初級',
        'スペイン語中級',
        'ロシア語1',
        'ロシア語2',
        'ロシア語入門',
        'ロシア語初級',
        'イタリア語1',
        'イタリア語2',
        'イタリア語入門',
        'イタリア語初級',
        'ポルトガル語1',
        'ポルトガル語2',
        'ポルトガル語入門',
        'アラビア語1',
        'アラビア語2',
        'アラビア語入門',
        'タイ語1',
        'タイ語2',
        'タイ語入門',
        'ベトナム語1',
        'ベトナム語2',
        'ベトナム語入門',
        'インドネシア語1',
        'インドネシア語2',
        'インドネシア語入門',
        '日本語1',
        '日本語2',
        '日本語3',
        '日本語4',
        '日本語入門',
        '日本語初級',
        '日本語中級',
        '日本語上級',
        'Japanese Language'
    ]
    
    # グローバル・キャリア養成科目の科目名リスト
    global_career_subjects = [
        '情報と職業',
        '連携講座',
        '海外IT 英語研修プログラム A',
        '海外IT 英語研修プログラムB',
        '海外IT専門研修プログラム A',
        '海外IT専門研修プログラムB',
        'グローバルインターンシップ',
        '情報技術実践1',
        '情報技術実践2',
        '情報技術実践3',
        '技術経営概論',
        '技術経営特論',
        'イノベーション論',
        'ファイナンス入門',
        'ITを活用した業務改革入門',
        '技術の事業化構想入門',
        'ICT 価値探求デザイン演習',
        'プロジェクトマネジメント基礎',
        '特殊講義 (グローバル・キャリア養成)'
    ]
    
    # 完全一致チェック
    if subject_name in common_specialty_subjects:
        return '共通専門科目'
    
    if subject_name in unique_required_subjects:
        return '固有専門科目（必修）'
    
    if subject_name in unique_elective_subjects:
        return '固有専門科目（選択）'
    
    if subject_name in basic_specialty_subjects:
        return '基礎専門科目'
    
    if subject_name in foreign_language_subjects:
        return '外国語'
    
    if subject_name in global_career_subjects:
        return 'グローバル・キャリア養成科目'
    
    # 全角・半角数字の違いを考慮した柔軟なマッチング（固有専門科目（必修））
    normalized_subject_name = subject_name.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5')
    normalized_unique_required_list = [s.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5') for s in unique_required_subjects]
    
    if normalized_subject_name in normalized_unique_required_list:
        return '固有専門科目（必修）'
    
    # 全角・半角数字の違いを考慮した柔軟なマッチング（固有専門科目（選択））
    normalized_unique_elective_list = [s.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5') for s in unique_elective_subjects]
    
    if normalized_subject_name in normalized_unique_elective_list:
        return '固有専門科目（選択）'
    
    # 全角・半角数字の違いを考慮した柔軟なマッチング（基礎専門科目）
    normalized_basic_specialty_list = [s.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5') for s in basic_specialty_subjects]
    
    if normalized_subject_name in normalized_basic_specialty_list:
        return '基礎専門科目'
    
    # 全角・半角数字の違いを考慮した柔軟なマッチング（外国語科目）
    normalized_foreign_language_list = [s.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5') for s in foreign_language_subjects]
    
    if normalized_subject_name in normalized_foreign_language_list:
        return '外国語'
    
    # 全角・半角数字の違いを考慮した柔軟なマッチング（グローバル・キャリア養成科目）
    normalized_global_career_list = [s.replace('１', '1').replace('２', '2').replace('３', '3').replace('４', '4').replace('５', '5') for s in global_career_subjects]
    
    if normalized_subject_name in normalized_global_career_list:
        return 'グローバル・キャリア養成科目'
    
    # 部分一致チェック（特殊講義などの場合）
    for subject in common_specialty_subjects:
        if '特殊講義' in subject and '特殊講義' in subject_name:
            return '共通専門科目'
    
    # その他の自動分類ルール
    subject_lower = subject_name.lower()
    
    # 英語関連科目
    if any(keyword in subject_lower for keyword in ['english', '英語']):
        return '外国語'
    
    # 教養科目の一般的なパターン
    if any(keyword in subject_name for keyword in ['教養', '一般', '文学', '歴史', '哲学', '心理学', '社会学']):
        return '教養科目'
    
    # 基礎専門科目の一般的なパターン
    if any(keyword in subject_name for keyword in ['基礎', '入門', '概論']):
        return '基礎専門科目'
    
    return '未分類'


def map_campus_semester(campus_semester):
    """
    CAMPUSウェブの学期表記をアプリの学期表記に変換するヘルパー関数
    """
    semester_text = campus_semester.lower()
    if '春' in semester_text:
        return '春学期'
    elif '秋' in semester_text:
        return '秋学期'
    elif '通年' in semester_text:
        return '通年'
    elif '夏' in semester_text:
        return '春学期'  # 夏学期は春学期としてカウント
    elif '冬' in semester_text:
        return '秋学期'  # 冬学期は秋学期としてカウント
    else:
        return '春学期'  # デフォルト


# ログインフォームクラス
class LoginForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    password = PasswordField('パスワード', validators=[DataRequired()])
    remember = BooleanField('ログイン状態を保持する')
    submit = SubmitField('ログイン')

# 新規ユーザー登録フォームクラス
class RegistrationForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    nickname = StringField('ニックネーム', validators=[DataRequired(), Length(min=2, max=50)])
    password = PasswordField('パスワード', validators=[
        DataRequired(), 
        Length(min=8, message='パスワードは8文字以上必要です')
    ])
    password2 = PasswordField('パスワード（確認）', validators=[
        DataRequired(), 
        EqualTo('password', message='パスワードが一致しません')
    ])
    graduation_year = IntegerField('学年', validators=[DataRequired(), NumberRange(min=1, max=6, message='1〜6の間で入力してください')])
    submit = SubmitField('登録')
    
    def validate_user_id(self, user_id):
        user = User.get_by_user_id(user_id.data)
        if user:
            raise ValidationError('このユーザーIDは既に登録されています。')

# プロフィール編集フォームクラス
class ProfileForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    nickname = StringField('ニックネーム', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('メールアドレス（任意）', validators=[Optional(), Email()])
    grade = IntegerField('学年', validators=[Optional(), NumberRange(min=1, max=6, message='1〜6の間で入力してください')])
    submit = SubmitField('更新')
    
    def __init__(self, original_user_id=None, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.original_user_id = original_user_id
    
    def validate_user_id(self, user_id):
        # 現在のユーザーIDと同じ場合はチェックをスキップ
        if user_id.data != self.original_user_id:
            user = User.get_by_user_id(user_id.data)
            if user:
                raise ValidationError('このユーザーIDは既に登録されています。')

# パスワード変更フォームクラス
class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('現在のパスワード', validators=[DataRequired()])
    new_password = PasswordField('新しいパスワード', validators=[
        DataRequired(), 
        Length(min=8, message='パスワードは8文字以上必要です')
    ])
    confirm_password = PasswordField('新しいパスワード（確認）', validators=[
        DataRequired(), 
        EqualTo('new_password', message='パスワードが一致しません')
    ])
    submit = SubmitField('パスワード変更')

class DeleteAccountForm(FlaskForm):
    password = PasswordField('パスワード', validators=[DataRequired()])
    confirm_text = StringField('確認テキスト', validators=[DataRequired()])
    submit = SubmitField('アカウントを削除')
    
    def validate_confirm_text(self, confirm_text):
        if confirm_text.data != 'アカウント削除':
            raise ValidationError('確認テキストが正しくありません。「アカウント削除」と入力してください。')

# Flask-Loginのユーザーモデル
class User(UserMixin):
    def __init__(self, id, email, name, password_hash=None, graduation_year=None, required_credits=124.0, settings_json=None, user_id=None, nickname=None):
        self.id = id
        self.email = email
        self.name = name
        self.user_id = user_id
        self.nickname = nickname
        self.password_hash = password_hash
        self.graduation_year = graduation_year
        self.required_credits = required_credits
        self.settings = json.loads(settings_json) if settings_json else {}
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def get_by_email(email):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            try:
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    name=user_data['name'],
                    user_id=user_data['user_id'] if 'user_id' in user_data.keys() else None,
                    nickname=user_data['nickname'] if 'nickname' in user_data.keys() else None,
                    password_hash=user_data['password_hash'],
                    graduation_year=user_data['graduation_year'],
                    required_credits=user_data['required_credits'],
                    settings_json=user_data['settings_json']
                )
            except Exception as e:
                return None
        return None
    
    @staticmethod
    def get_by_user_id(user_id):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            try:
                return User(
                    id=user_data['id'],
                    email=user_data['email'] if 'email' in user_data.keys() else None,
                    name=user_data['name'],
                    user_id=user_data['user_id'] if 'user_id' in user_data.keys() else None,
                    nickname=user_data['nickname'] if 'nickname' in user_data.keys() else None,
                    password_hash=user_data['password_hash'],
                    graduation_year=user_data['graduation_year'],
                    required_credits=user_data['required_credits'],
                    settings_json=user_data['settings_json']
                )
            except Exception as e:
                return None
        return None
    
    @staticmethod
    def get_by_id(user_id):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_data = c.fetchone()
        conn.close()
        
        if user_data:
            try:
                return User(
                    id=user_data['id'],
                    email=user_data['email'] if 'email' in user_data.keys() else None,
                    name=user_data['name'],
                    user_id=user_data['user_id'] if 'user_id' in user_data.keys() else None,
                    nickname=user_data['nickname'] if 'nickname' in user_data.keys() else None,
                    password_hash=user_data['password_hash'],
                    graduation_year=user_data['graduation_year'],
                    required_credits=user_data['required_credits'],
                    settings_json=user_data['settings_json']
                )
            except Exception as e:
                return None
        return None

# Flask-Loginのユーザーローダー
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_user_id(form.user_id.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home'))
        flash('ユーザーIDまたはパスワードが正しくありません', 'error')
    
    return render_template('login.html', form=form, title='ログイン')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            password_hash = generate_password_hash(form.password.data)
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''
                INSERT INTO users (email, name, password_hash, graduation_year, user_id, nickname)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('', form.nickname.data, password_hash, form.graduation_year.data, form.user_id.data, form.nickname.data))
            conn.commit()
            user_id = c.lastrowid
            conn.close()
            
            user = User.get_by_id(user_id)
            login_user(user)
            flash('アカウント登録が完了しました！以下のいずれかの方法で科目を追加して成績管理を始めましょう：1) 上部のフォームから個別に科目を追加、2) 「CAMPUSウェブから取込」で成績データをインポート、または 3) 「複数科目をまとめて追加」で一括登録', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'登録中にエラーが発生しました: {str(e)}', 'error')
    
    return render_template('register.html', form=form, title='新規登録')

@app.route('/logout')
def logout():
    logout_user()
    flash('ログアウトしました', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # プロフィール編集フォームの初期化（現在のユーザーIDを渡す）
    profile_form = ProfileForm(original_user_id=current_user.user_id)
    # 初期値を設定
    if request.method == 'GET':
        profile_form.user_id.data = current_user.user_id
        profile_form.nickname.data = current_user.nickname or current_user.name
        profile_form.email.data = current_user.email or ''
        profile_form.grade.data = current_user.graduation_year
    
    # パスワード変更フォームの初期化
    password_form = ChangePasswordForm()
    
    # アカウント削除フォームの初期化
    delete_form = DeleteAccountForm()
    
    # プロフィール更新のフォーム処理
    if 'update_profile' in request.form and profile_form.validate_on_submit():
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''
                UPDATE users
                SET user_id = ?, nickname = ?, email = ?, graduation_year = ?
                WHERE id = ?
            ''', (
                profile_form.user_id.data,
                profile_form.nickname.data,
                profile_form.email.data,
                profile_form.grade.data,
                current_user.id
            ))
            conn.commit()
            conn.close()
            
            # セッション内のユーザー情報を更新
            current_user.user_id = profile_form.user_id.data
            current_user.nickname = profile_form.nickname.data
            current_user.email = profile_form.email.data
            current_user.graduation_year = profile_form.grade.data
            
            flash('プロフィールが更新されました', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f'プロフィール更新中にエラーが発生しました: {str(e)}', 'error')
    
    # パスワード変更のフォーム処理
    if 'change_password' in request.form and password_form.validate_on_submit():
        # 現在のパスワード確認
        if not current_user.check_password(password_form.current_password.data):
            flash('現在のパスワードが正しくありません', 'error')
            return redirect(url_for('profile'))
            
        try:
            # 新しいパスワードのハッシュ化
            password_hash = generate_password_hash(password_form.new_password.data)
            
            # データベース更新
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            ''', (password_hash, current_user.id))
            conn.commit()
            conn.close()
            
            # ユーザーモデル更新
            current_user.password_hash = password_hash
            
            flash('パスワードが正常に変更されました', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f'パスワード変更中にエラーが発生しました: {str(e)}', 'error')
    
    # アカウント削除のフォーム処理
    if 'delete_account' in request.form and delete_form.validate_on_submit():
        # 現在のパスワード確認
        if not current_user.check_password(delete_form.password.data):
            flash('パスワードが正しくありません', 'error')
            return redirect(url_for('profile'))
            
        try:
            user_id = current_user.id
            
            # データベース接続
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # ユーザーの成績データを削除
            c.execute('DELETE FROM grades WHERE user_id = ?', (user_id,))
            
            # ユーザーアカウントを削除
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
            
            conn.commit()
            conn.close()
            
            # ログアウト処理
            logout_user()
            
            flash('アカウントが正常に削除されました。ご利用ありがとうございました。', 'info')
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'アカウント削除中にエラーが発生しました: {str(e)}', 'error')
    
    return render_template('profile.html', 
                         profile_form=profile_form, 
                         password_form=password_form,
                         delete_form=delete_form)

# GPA/GPS計算とランキング関連の関数
def calculate_gpa_gps(user_id):
    """指定されたユーザーのGPAとGPSを計算する"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        # 該当ユーザーの成績データを取得
        c.execute(
            'SELECT grade, credits, year FROM grades WHERE user_id = ? AND grade IS NOT NULL AND grade != ""',
            (user_id,)
        )
        grades = c.fetchall()
        
        if not grades:
            return 0.0, 0.0, 0  # GPA, GPS, 総単位数
        
        # 成績のポイント換算表（ホームページと統一）
        grade_points = {
            'A+': 5.0, 'A': 4.0, 'B': 3.0, 'C': 2.0, 'F': 0.0,
            'S': 5.0, '秀': 5.0, '優': 4.0, '良': 3.0, '可': 2.0, '不可': 0.0
        }
        
        total_credits = 0  # GPA計算用の総単位数（F評価含む）
        total_grade_points = 0.0
        earned_credits = 0  # 修得単位数（F/不可/年度不明を除外）
        
        for grade_row in grades:
            grade = grade_row['grade']
            credits = grade_row['credits']
            year = grade_row['year']
            
            if grade in grade_points and credits > 0:
                point = grade_points[grade]
                # GPA計算にはF評価も含める（分母に含める）
                total_credits += credits
                total_grade_points += point * credits
                
                # 取得単位数にはF評価、不可評価、年度不明を含めない
                if grade not in ['F', '不可'] and year is not None and year != '':
                    earned_credits += credits
        
        if total_credits == 0:
            return 0.0, 0.0, 0
        
        gpa = total_grade_points / total_credits
        gps = total_grade_points
        
        return round(gpa, 2), round(gps, 2), earned_credits
        
    finally:
        conn.close()

def get_user_statistics(user_id):
    """ユーザーの詳細統計情報を取得"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        # 年度別の成績統計（未修得単位と年度不明を除外）
        c.execute('''
            SELECT year, COUNT(*) as courses, 
                   SUM(CASE WHEN grade NOT IN ('F', '不可') AND year IS NOT NULL AND year != '' THEN credits ELSE 0 END) as credits,
                   AVG(CASE 
                       WHEN grade IN ('A+', 'S', '秀') THEN 5.0
                       WHEN grade IN ('A', '優') THEN 4.0
                       WHEN grade IN ('B', '良') THEN 3.0
                       WHEN grade IN ('C', '可') THEN 2.0
                       ELSE 0.0
                   END) as avg_gpa
            FROM grades 
            WHERE user_id = ? AND grade IS NOT NULL AND grade != "" AND year IS NOT NULL AND year != ""
            GROUP BY year
            ORDER BY year
        ''', (user_id,))
        yearly_stats = c.fetchall()
        
        # 成績分布
        c.execute('''
            SELECT grade, COUNT(*) as count
            FROM grades 
            WHERE user_id = ? AND grade IS NOT NULL AND grade != ""
            GROUP BY grade
        ''', (user_id,))
        grade_distribution = c.fetchall()
        
        # カテゴリ別統計（未修得単位と年度不明を除外）
        c.execute('''
            SELECT category, COUNT(*) as courses, 
                   SUM(CASE WHEN grade NOT IN ('F', '不可') AND year IS NOT NULL AND year != '' THEN credits ELSE 0 END) as credits
            FROM grades 
            WHERE user_id = ? AND category IS NOT NULL AND category != ""
            GROUP BY category
        ''', (user_id,))
        category_stats = c.fetchall()
        
        return {
            'yearly_stats': [dict(row) for row in yearly_stats],
            'grade_distribution': [dict(row) for row in grade_distribution],
            'category_stats': [dict(row) for row in category_stats]
        }
        
    finally:
        conn.close()

# ランキング機能のAPIエンドポイント
@app.route('/api/get_ranking', methods=['GET'])
@login_required
def get_ranking():
    """全ユーザーのランキングデータを取得する"""
    try:
        sort_by = request.args.get('sort_by', 'gpa')  # gpa, gps, credits
        grade_filter = request.args.get('grade', 'all')  # 学年フィルタ
        
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 学年フィルタに応じてクエリを変更
        if grade_filter == 'all':
            c.execute('SELECT id, nickname, graduation_year FROM users WHERE nickname IS NOT NULL')
        else:
            c.execute('SELECT id, nickname, graduation_year FROM users WHERE nickname IS NOT NULL AND graduation_year = ?', (int(grade_filter),))
        
        users = c.fetchall()
        conn.close()
        
        ranking_data = []
        
        for user in users:
            gpa, gps, total_credits = calculate_gpa_gps(user['id'])
            
            # 最低限のデータがある場合のみランキングに含める
            if total_credits > 0:
                ranking_data.append({
                    'user_id': user['id'],
                    'nickname': user['nickname'],
                    'graduation_year': user['graduation_year'],
                    'gpa': gpa,
                    'gps': gps,
                    'total_credits': total_credits,
                    'is_current_user': user['id'] == current_user.id
                })
        
        # ソート
        if sort_by == 'gpa':
            ranking_data.sort(key=lambda x: x['gpa'], reverse=True)
        elif sort_by == 'gps':
            ranking_data.sort(key=lambda x: x['gps'], reverse=True)
        elif sort_by == 'credits':
            ranking_data.sort(key=lambda x: x['total_credits'], reverse=True)
        
        # ランク付け
        for i, user_data in enumerate(ranking_data):
            user_data['rank'] = i + 1
        
        return jsonify({
            'status': 'success',
            'data': ranking_data,
            'sort_by': sort_by,
            'grade_filter': grade_filter
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_my_stats', methods=['GET'])
@login_required
def get_my_stats():
    """現在のユーザーの詳細統計を取得する"""
    try:
        gpa, gps, total_credits = calculate_gpa_gps(current_user.id)
        stats = get_user_statistics(current_user.id)
        
        return jsonify({
            'status': 'success',
            'data': {
                'gpa': gpa,
                'gps': gps,
                'total_credits': total_credits,
                'stats': stats
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/get_distribution_stats', methods=['GET'])
@login_required
def get_distribution_stats():
    """全ユーザーのGPA・GPS分布統計を取得する"""
    try:
        grade_filter = request.args.get('grade', 'all')  # 学年フィルタ
        
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 学年フィルタに応じてユーザーを取得
        if grade_filter == 'all':
            c.execute('SELECT id FROM users WHERE nickname IS NOT NULL')
        else:
            c.execute('SELECT id FROM users WHERE nickname IS NOT NULL AND graduation_year = ?', (int(grade_filter),))
        
        users = c.fetchall()
        conn.close()
        
        gpa_values = []
        gps_values = []
        
        # 各ユーザーのGPA・GPSを計算
        for user in users:
            gpa, gps, total_credits = calculate_gpa_gps(user['id'])
            
            # 最低限のデータがある場合のみ統計に含める
            if total_credits > 0:
                gpa_values.append(gpa)
                gps_values.append(gps)
        
        # GPA分布を計算
        gpa_distribution = calculate_distribution(gpa_values, 'gpa')
        
        # GPS分布を計算
        gps_distribution = calculate_distribution(gps_values, 'gps')
        
        return jsonify({
            'status': 'success',
            'data': {
                'gpa_distribution': gpa_distribution,
                'gps_distribution': gps_distribution,
                'total_users': len(gpa_values),
                'grade_filter': grade_filter
            }
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def calculate_distribution(values, metric_type):
    """数値リストから分布データを計算する"""
    if not values:
        return []
    
    # 区間を定義
    if metric_type == 'gpa':
        # GPA用の区間（0.5刻み）
        ranges = [
            (0.0, 0.5, "0.0-0.5"),
            (0.5, 1.0, "0.5-1.0"),
            (1.0, 1.5, "1.0-1.5"),
            (1.5, 2.0, "1.5-2.0"),
            (2.0, 2.5, "2.0-2.5"),
            (2.5, 3.0, "2.5-3.0"),
            (3.0, 3.5, "3.0-3.5"),
            (3.5, 4.0, "3.5-4.0"),
            (4.0, 4.5, "4.0-4.5"),
            (4.5, 5.0, "4.5-5.0")  # A+評価があるため5.0まで
        ]
    else:  # GPS
        # GPS用の区間（0から適切な上限まで50刻み）
        if not values:
            return []
            
        min_val = min(values)
        max_val = max(values)
        
        # 50ポイント刻みで区間を作成（0から開始）
        step = 50
        start = 0  # 常に0から開始
        end = int(max_val // step + 1) * step
        
        ranges = []
        current = start
        while current < end:
            next_val = current + step
            ranges.append((current, next_val, f"{current}-{next_val}"))
            current = next_val
    
    # 各区間のカウントを計算
    distribution = []
    for min_val, max_val, label in ranges:
        count = sum(1 for v in values if min_val <= v < max_val)
        # 0件の区間も含める
        distribution.append({
            'range': label,
            'count': count,
            'min_value': min_val,
            'max_value': max_val
        })
    
    return distribution

@app.route('/ranking')
@login_required
def ranking():
    """ランキングページを表示"""
    return render_template('ranking.html')

# 学年フィルタ用の利用可能な学年一覧を取得するAPIエンドポイント
@app.route('/api/get_available_grades', methods=['GET'])
@login_required
def get_available_grades():
    """利用可能な学年一覧を取得する"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # データが存在するユーザーの学年を取得
        c.execute('''
            SELECT DISTINCT u.graduation_year 
            FROM users u 
            WHERE u.nickname IS NOT NULL 
            AND u.graduation_year IS NOT NULL 
            AND EXISTS (
                SELECT 1 FROM grades g 
                WHERE g.user_id = u.id 
                AND g.grade IS NOT NULL 
                AND g.grade != ''
            )
            ORDER BY u.graduation_year
        ''')
        grades = c.fetchall()
        conn.close()
        
        available_grades = [row['graduation_year'] for row in grades if row['graduation_year'] is not None]
        
        return jsonify({
            'status': 'success',
            'data': available_grades
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    init_db()  # アプリケーション起動時にデータベース初期化
    create_default_user()  # デフォルトユーザーの作成
    
    # 環境に応じた実行
    if os.environ.get('FLASK_ENV') == 'production':
        print("🚀 本番環境でアプリケーションを起動中...")
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
    else:
        print("🛠️  開発環境でアプリケーションを起動中...")
        print("📱 外部アクセス（iPhone等）有効")
        port = int(os.environ.get('FLASK_RUN_PORT', 5001))
        app.run(host='0.0.0.0', debug=True, port=port)
