from flask import Flask, Response, render_template, jsonify, request, redirect, url_for, flash, session, abort
import sqlite3
from contextlib import contextmanager
import csv
import io
import os
import re
import unicodedata
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

from subject_categories import SUBJECT_CATEGORIES, classify_subject_by_name

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# .envファイルが存在する場合は読み込む（本番環境用）
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'
RANKING_ENABLED = env_flag('ENABLE_RANKING', default=not IS_PRODUCTION)
DEMO_ADMIN_ENABLED = env_flag('ENABLE_DEMO_ADMIN', default=False)

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
database_path = os.environ.get('DATABASE_PATH', 'grades.db')
DB_FILE = database_path if os.path.isabs(database_path) else os.path.join(BASE_DIR, database_path)
db_directory = os.path.dirname(DB_FILE)
if db_directory:
    os.makedirs(db_directory, exist_ok=True)


@contextmanager
def get_db():
    """DBに接続し、withブロックを抜けるときに必ず接続を閉じる。

    行は列名でも番号でも参照できる（sqlite3.Row）。
    変更を保存するには、ブロックの中で conn.commit() を呼ぶ。
    commit せずに抜けた変更は保存されない。
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

if IS_PRODUCTION:
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

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
    logs_directory = os.path.join(BASE_DIR, 'logs')
    os.makedirs(logs_directory, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(logs_directory, 'app.log'),
        maxBytes=10240,
        backupCount=10,
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('成績管理アプリケーション起動')

# Flask-Loginの設定
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'この機能を使用するにはログインしてください。'


@app.context_processor
def inject_app_flags():
    return {'ranking_enabled': RANKING_ENABLED}

def init_db():
    with get_db() as conn:
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
            current_year INTEGER,
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

        # 講義レビューは成績データと分離し、公開範囲をユーザーが選べるようにする。
        c.execute('''CREATE TABLE IF NOT EXISTS course_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_key TEXT NOT NULL,
            course_name TEXT NOT NULL,
            course_code TEXT,
            instructor TEXT,
            term TEXT NOT NULL DEFAULT '',
            difficulty INTEGER NOT NULL,
            workload INTEGER NOT NULL,
            attendance TEXT NOT NULL DEFAULT '不明',
            assessment TEXT,
            comment TEXT,
            is_public INTEGER NOT NULL DEFAULT 0,
            is_reported INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, course_key, term)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS review_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            reporter_user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(review_id, reporter_user_id)
        )''')

        conn.commit()

def create_default_user():
    """明示的に有効化された場合だけ初期管理者ユーザーを作成する。"""
    if not DEMO_ADMIN_ENABLED:
        return

    try:
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if not admin_password:
            raise RuntimeError(
                'ENABLE_DEMO_ADMIN=true の場合は ADMIN_PASSWORD の環境変数が必要です'
            )

        password_hash = generate_password_hash(admin_password)
        # INSERT OR IGNOREで、開発サーバーの再読み込みや複数ワーカー起動にも耐える。
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR IGNORE INTO users (email, name, password_hash, current_year, required_credits, user_id, nickname)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ("admin@example.com", "管理者", password_hash, 2025, 124.0, "admin", "管理者"))
            if c.rowcount == 1:
                app.logger.info('デフォルト管理者ユーザーを作成しました。')
            conn.commit()
    except Exception:
        app.logger.exception('管理者アカウントの初期化に失敗しました')
        raise


def initialize_database():
    """開発サーバーとWSGIサーバーの両方でDBを初期化する。"""
    init_db()
    create_default_user()


# Gunicornなどはこのファイルをimportして起動するため、__main__だけでは初期化されない。
if os.environ.get('SKIP_DB_INIT') != '1':
    initialize_database()

# ホームページを表示
@app.route("/")
@login_required  # ログインが必要
def home():
    return render_template(
        "index.html",
        required_credits=float(current_user.required_credits or 124.0),
        subject_categories=SUBJECT_CATEGORIES,
    )


@app.route('/healthz')
def healthz():
    """デプロイ先の稼働確認用エンドポイント。"""
    return jsonify({'status': 'ok'})


@app.route('/api/export_courses')
@login_required
def export_courses():
    """ログイン中のユーザーの成績だけをCSVで出力する。"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT year, semester, name, credits, grade, category, memo
            FROM grades
            WHERE user_id = ?
            ORDER BY year IS NULL, year, semester, id
        ''', (current_user.id,))
        rows = c.fetchall()

    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(['年度', '学期', '科目名', '単位数', '評価', 'カテゴリ', 'メモ'])
    writer.writerows(
        [
            row['year'],
            row['semester'],
            row['name'],
            row['credits'],
            row['grade'],
            row['category'],
            row['memo'],
        ]
        for row in rows
    )

    response = Response(
        chr(0xfeff) + output.getvalue(),
        content_type='text/csv; charset=utf-8',
    )
    response.headers['Content-Disposition'] = 'attachment; filename=seiseki-kanri-courses.csv'
    return response


@app.route('/api/load_demo_data', methods=['POST'])
@login_required
def load_demo_data():
    """ログイン中のユーザーに、画面確認用のダミー成績を追加する。"""
    demo_courses = [
        (2024, '春学期', 'データ構造とアルゴリズム', 2.0, 'A+', '基礎専門科目', 'サンプルデータ'),
        (2024, '秋学期', 'Webアプリケーション開発', 2.0, 'A', '固有専門科目（選択）', 'サンプルデータ'),
        (2025, '春学期', 'データベース', 2.0, 'B', '基礎専門科目', 'サンプルデータ'),
        (2025, '春学期', '機械学習', 2.0, 'A', '固有専門科目（選択）', 'サンプルデータ'),
        (2025, '秋学期', 'ソフトウェア工学', 2.0, 'B', '共通専門科目', 'サンプルデータ'),
        (2025, '秋学期', '英語コミュニケーション', 2.0, 'C', '外国語', 'サンプルデータ'),
        (2026, '春学期', '卒業研究', 4.0, 'A+', '固有専門科目（必修）', 'サンプルデータ'),
        ('', '秋学期', '履修予定科目', 2.0, '', '未分類', 'サンプルデータ（履修予定）'),
    ]

    with get_db() as conn:
        try:
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM grades WHERE user_id = ?', (current_user.id,))
            if c.fetchone()[0] > 0:
                return jsonify({
                    'status': 'error',
                    'message': '既に科目データがあるため、サンプルデータは追加しませんでした。',
                }), 409

            c.executemany('''
                INSERT INTO grades (year, semester, name, credits, grade, category, memo, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [course + (current_user.id,) for course in demo_courses])
            conn.commit()
            return jsonify({
                'status': 'ok',
                'count': len(demo_courses),
                'message': 'サンプルデータを追加しました。',
            })
        except sqlite3.Error:
            conn.rollback()
            app.logger.exception('サンプルデータの追加に失敗しました')
            return jsonify({
                'status': 'error',
                'message': 'サンプルデータの追加に失敗しました。',
            }), 500


def normalize_review_text(value):
    """講義名・科目コードの表記揺れを減らして検索キーを作る。"""
    normalized = unicodedata.normalize('NFKC', str(value or '')).strip().lower()
    return re.sub(r'\s+', '', normalized)


def make_review_course_key(course_name, course_code):
    code_key = normalize_review_text(course_code)
    if code_key:
        return f'code:{code_key}'
    return f'name:{normalize_review_text(course_name)}'


def parse_review_payload(data):
    """レビュー入力を検証し、DBへ保存する値に整形する。"""
    data = data or {}
    course_name = str(data.get('course_name', '')).strip()
    course_code = str(data.get('course_code', '')).strip()
    instructor = str(data.get('instructor', '')).strip()
    term = str(data.get('term', '')).strip()
    attendance = str(data.get('attendance', '不明')).strip() or '不明'
    assessment = str(data.get('assessment', '')).strip()
    comment = str(data.get('comment', '')).strip()

    if not course_name or len(course_name) > 100:
        return None, '科目名は1〜100文字で入力してください。'
    if len(course_code) > 50:
        return None, '科目コードは50文字以内で入力してください。'
    if len(instructor) > 80:
        return None, '担当者名は80文字以内で入力してください。'
    if len(term) > 40:
        return None, '開講時期は40文字以内で入力してください。'
    if attendance not in {'毎回出席', '一部出席', '自由出席', '不明'}:
        return None, '出席情報の値が不正です。'
    if len(assessment) > 100:
        return None, '評価方法は100文字以内で入力してください。'
    if len(comment) > 500:
        return None, 'コメントは500文字以内で入力してください。'

    try:
        difficulty = int(data.get('difficulty', 0))
        workload = int(data.get('workload', 0))
    except (TypeError, ValueError):
        return None, '難易度と課題量は1〜5で入力してください。'

    if not 1 <= difficulty <= 5 or not 1 <= workload <= 5:
        return None, '難易度と課題量は1〜5で入力してください。'

    return {
        'course_key': make_review_course_key(course_name, course_code),
        'course_name': course_name,
        'course_code': course_code,
        'instructor': instructor,
        'term': term,
        'difficulty': difficulty,
        'workload': workload,
        'attendance': attendance,
        'assessment': assessment,
        'comment': comment,
        'is_public': 1 if data.get('is_public') is True else 0,
    }, None


@app.route('/reviews')
@login_required
def reviews():
    return render_template('reviews.html')


@app.route('/api/reviews', methods=['GET'])
@login_required
def list_reviews():
    """公開設定された講義レビューを匿名集計して返す。"""
    query = request.args.get('query', '').strip().lower()
    with get_db() as conn:
        conditions = ['is_public = 1', 'is_reported = 0']
        params = []
        if query:
            like_query = f'%{query}%'
            conditions.append(
                '(LOWER(course_name) LIKE ? OR LOWER(course_code) LIKE ? OR LOWER(instructor) LIKE ?)'
            )
            params.extend([like_query, like_query, like_query])

        c = conn.cursor()
        c.execute(f'''
            SELECT
                course_key,
                MAX(course_name) AS course_name,
                MAX(course_code) AS course_code,
                MAX(instructor) AS instructor,
                COUNT(*) AS review_count,
                ROUND(AVG(difficulty), 1) AS average_difficulty,
                ROUND(AVG(workload), 1) AS average_workload,
                MAX(updated_at) AS latest_review
            FROM course_reviews
            WHERE {' AND '.join(conditions)}
            GROUP BY course_key
            ORDER BY review_count DESC, latest_review DESC
            LIMIT 50
        ''', params)
        return jsonify([dict(row) for row in c.fetchall()])


@app.route('/api/reviews/mine', methods=['GET'])
@login_required
def list_my_reviews():
    """ログイン中のユーザー自身のレビューを公開範囲に関係なく返す。"""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, course_key, course_name, course_code, instructor, term,
                   difficulty, workload, attendance, assessment, comment,
                   is_public, is_reported, updated_at
            FROM course_reviews
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 50
        ''', (current_user.id,))
        return jsonify([dict(row) for row in c.fetchall()])


@app.route('/api/reviews/detail', methods=['GET'])
@login_required
def review_detail():
    course_key = request.args.get('course_key', '').strip()
    if not course_key:
        return jsonify({'status': 'error', 'message': '講義を指定してください。'}), 400

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT
                course_key,
                MAX(course_name) AS course_name,
                MAX(course_code) AS course_code,
                MAX(instructor) AS instructor,
                COUNT(*) AS review_count,
                ROUND(AVG(difficulty), 1) AS average_difficulty,
                ROUND(AVG(workload), 1) AS average_workload
            FROM course_reviews
            WHERE course_key = ? AND is_public = 1 AND is_reported = 0
            GROUP BY course_key
        ''', (course_key,))
        aggregate = c.fetchone()
        if aggregate is None:
            return jsonify({'status': 'error', 'message': '公開レビューが見つかりません。'}), 404

        c.execute('''
            SELECT id, course_name, course_code, instructor, term,
                   difficulty, workload, attendance, assessment, comment, updated_at
            FROM course_reviews
            WHERE course_key = ? AND is_public = 1 AND is_reported = 0
              AND comment IS NOT NULL AND comment != ''
            ORDER BY updated_at DESC
            LIMIT 30
        ''', (course_key,))
        comments = [dict(row) for row in c.fetchall()]

        c.execute('''
            SELECT id, course_name, course_code, instructor, term,
                   difficulty, workload, attendance, assessment, comment,
                   is_public, is_reported
            FROM course_reviews
            WHERE course_key = ? AND user_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
        ''', (course_key, current_user.id))
        own_reviews = [dict(row) for row in c.fetchall()]

        return jsonify({
            'status': 'ok',
            'aggregate': dict(aggregate),
            'comments': comments,
            'own_reviews': own_reviews,
        })


@app.route('/api/reviews', methods=['POST'])
@login_required
def save_review():
    payload, error = parse_review_payload(request.get_json(silent=True))
    if error:
        return jsonify({'status': 'error', 'message': error}), 400

    with get_db() as conn:
        try:
            c = conn.cursor()
            c.execute('''
                SELECT id FROM course_reviews
                WHERE user_id = ? AND course_key = ? AND term = ?
            ''', (current_user.id, payload['course_key'], payload['term']))
            existing = c.fetchone()

            values = (
                payload['course_name'], payload['course_code'], payload['instructor'],
                payload['difficulty'], payload['workload'], payload['attendance'],
                payload['assessment'], payload['comment'], payload['is_public'],
            )
            if existing:
                c.execute('''
                    UPDATE course_reviews
                    SET course_name = ?, course_code = ?, instructor = ?,
                        difficulty = ?, workload = ?, attendance = ?,
                        assessment = ?, comment = ?, is_public = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                ''', values + (existing[0], current_user.id))
                review_id = existing[0]
            else:
                c.execute('''
                    INSERT INTO course_reviews (
                        course_key, course_name, course_code, instructor, term,
                        difficulty, workload, attendance, assessment, comment,
                        is_public, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payload['course_key'], payload['course_name'], payload['course_code'],
                    payload['instructor'], payload['term'], payload['difficulty'],
                    payload['workload'], payload['attendance'], payload['assessment'],
                    payload['comment'], payload['is_public'], current_user.id,
                ))
                review_id = c.lastrowid
            conn.commit()
            return jsonify({'status': 'ok', 'review_id': review_id})
        except sqlite3.Error:
            conn.rollback()
            app.logger.exception('講義レビューの保存に失敗しました')
            return jsonify({'status': 'error', 'message': '講義レビューを保存できませんでした。'}), 500


@app.route('/api/reviews/<int:review_id>', methods=['DELETE'])
@login_required
def delete_review(review_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            'DELETE FROM course_reviews WHERE id = ? AND user_id = ?',
            (review_id, current_user.id),
        )
        if c.rowcount == 0:
            return jsonify({'status': 'error', 'message': '削除できるレビューが見つかりません。'}), 404
        c.execute('DELETE FROM review_reports WHERE review_id = ?', (review_id,))
        conn.commit()
        return jsonify({'status': 'ok'})


@app.route('/api/reviews/<int:review_id>/report', methods=['POST'])
@login_required
def report_review(review_id):
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT user_id FROM course_reviews WHERE id = ?', (review_id,))
        review = c.fetchone()
        if review is None:
            return jsonify({'status': 'error', 'message': 'レビューが見つかりません。'}), 404
        if review[0] == current_user.id:
            return jsonify({'status': 'error', 'message': '自分のレビューは通報できません。'}), 400

        c.execute('''
            INSERT OR IGNORE INTO review_reports (review_id, reporter_user_id)
            VALUES (?, ?)
        ''', (review_id, current_user.id))
        # 通報されたレビューは、確認が終わるまで公開一覧から外す。
        c.execute('UPDATE course_reviews SET is_reported = 1 WHERE id = ?', (review_id,))
        conn.commit()
        return jsonify({'status': 'ok', 'message': 'レビューを公開一覧から外しました。'})

# 成績データを取得するAPI
@app.route("/api/get_courses", methods=["GET"])
@login_required
def get_courses():
    with get_db() as conn:
        c = conn.cursor()
        # 修正: 現在ログインしているユーザーのデータのみを取得
        c.execute("SELECT * FROM grades WHERE user_id = ?", (current_user.id,))
        rows = c.fetchall()
    courses = [dict(row) for row in rows]
    return jsonify(courses)

# 成績データを追加するAPI
@app.route("/api/add_course", methods=["POST"])
@login_required
def add_course():
    data = request.get_json()
    with get_db() as conn:
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
    return jsonify({"status": "ok"})

@app.route('/api/delete_course', methods=['POST'])
@login_required
def delete_course():
    index = request.json.get("index")
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM grades WHERE id = ? AND user_id = ?", (index, current_user.id))
        conn.commit()
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

        with get_db() as conn:
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

    with get_db() as conn:
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
            return jsonify({"status": "ok", "count": len(courses_data)})

        except Exception as e:
            conn.rollback()
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

    with get_db() as conn:
        c = conn.cursor()

        try:
            # IDのリストを使用して、対象の科目を削除（ユーザーIDでもフィルタリング）
            placeholders = ', '.join(['?'] * len(ids))
            query = f"DELETE FROM grades WHERE id IN ({placeholders}) AND user_id = ?"
            params = ids + [current_user.id]
            c.execute(query, params)

            deleted_count = c.rowcount
            conn.commit()

            return jsonify({
                "status": "ok", 
                "message": f"{deleted_count}件の科目を削除しました",
                "count": deleted_count
            })

        except Exception as e:
            conn.rollback()
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
    current_year = IntegerField('学年', validators=[DataRequired(), NumberRange(min=1, max=6, message='1〜6の間で入力してください')])
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
    required_credits = FloatField('卒業必要単位数', validators=[
        DataRequired(message='卒業必要単位数を入力してください'),
        NumberRange(min=1, max=300, message='1〜300の範囲で入力してください'),
    ])
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
    def __init__(self, id, email, name, password_hash=None, current_year=None, required_credits=124.0, settings_json=None, user_id=None, nickname=None):
        self.id = id
        self.email = email
        self.name = name
        self.user_id = user_id
        self.nickname = nickname
        self.password_hash = password_hash
        self.current_year = current_year
        self.required_credits = required_credits
        self.settings = json.loads(settings_json) if settings_json else {}

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # 古いDBでは後から追加した列がないことがあるため、存在しなければNoneにする
    OPTIONAL_COLUMNS = ('email', 'user_id', 'nickname')

    @staticmethod
    def _find_one(column, value):
        """usersテーブルから1件取得してUserにする。見つからなければNone。"""
        if column not in ('id', 'user_id'):
            raise ValueError(f'検索に使えない列です: {column}')

        with get_db() as conn:
            row = conn.execute(f'SELECT * FROM users WHERE {column} = ?', (value,)).fetchone()
        if row is None:
            return None

        optional = {
            key: row[key] if key in row.keys() else None
            for key in User.OPTIONAL_COLUMNS
        }
        try:
            return User(
                id=row['id'],
                name=row['name'],
                password_hash=row['password_hash'],
                current_year=row['current_year'],
                required_credits=row['required_credits'],
                settings_json=row['settings_json'],
                **optional,
            )
        except Exception:
            return None

    @staticmethod
    def get_by_user_id(user_id):
        return User._find_one('user_id', user_id)

    @staticmethod
    def get_by_id(user_id):
        return User._find_one('id', user_id)

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

            with get_db() as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO users (email, name, password_hash, current_year, user_id, nickname)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ('', form.nickname.data, password_hash, form.current_year.data, form.user_id.data, form.nickname.data))
                conn.commit()
                user_id = c.lastrowid

            user = User.get_by_id(user_id)
            login_user(user)
            flash('アカウント登録が完了しました！ホーム画面から、1科目の手動追加・複数科目の一括追加・サンプルデータでの確認を始められます。対応形式の成績HTMLも取り込めます。', 'success')
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
        profile_form.grade.data = current_user.current_year
        profile_form.required_credits.data = current_user.required_credits or 124.0

    # パスワード変更フォームの初期化
    password_form = ChangePasswordForm()

    # アカウント削除フォームの初期化
    delete_form = DeleteAccountForm()

    # プロフィール更新のフォーム処理
    if 'update_profile' in request.form and profile_form.validate_on_submit():
        try:
            with get_db() as conn:
                c = conn.cursor()
                c.execute('''
                    UPDATE users
                    SET user_id = ?, nickname = ?, email = ?, current_year = ?, required_credits = ?
                    WHERE id = ?
                ''', (
                    profile_form.user_id.data,
                    profile_form.nickname.data,
                    profile_form.email.data,
                    profile_form.grade.data,
                    profile_form.required_credits.data,
                    current_user.id
                ))
                conn.commit()

            # セッション内のユーザー情報を更新
            current_user.user_id = profile_form.user_id.data
            current_user.nickname = profile_form.nickname.data
            current_user.email = profile_form.email.data
            current_user.current_year = profile_form.grade.data
            current_user.required_credits = profile_form.required_credits.data

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
            with get_db() as conn:
                c = conn.cursor()
                c.execute('''
                    UPDATE users
                    SET password_hash = ?
                    WHERE id = ?
                ''', (password_hash, current_user.id))
                conn.commit()

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
            with get_db() as conn:
                c = conn.cursor()

                # ユーザーの成績データを削除
                c.execute('DELETE FROM grades WHERE user_id = ?', (user_id,))

                # ユーザーアカウントを削除
                c.execute('DELETE FROM users WHERE id = ?', (user_id,))

                conn.commit()

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
    with get_db() as conn:
        c = conn.cursor()
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
        'A+': 5.0, 'A': 4.0, 'B': 3.0, 'C': 2.0, 'F': 0.0
    }

    total_credits = 0  # GPA計算用の総単位数（F評価含む）
    total_grade_points = 0.0
    earned_credits = 0  # 修得単位数（F/年度不明を除外）

    for grade_row in grades:
        grade = grade_row['grade']
        credits = grade_row['credits']
        year = grade_row['year']

        if grade in grade_points and credits > 0:
            point = grade_points[grade]
            # GPA計算にはF評価も含める（分母に含める）
            total_credits += credits
            total_grade_points += point * credits

            # 取得単位数にはF評価と年度不明を含めない
            if grade != 'F' and year is not None and year != '':
                earned_credits += credits

    if total_credits == 0:
        return 0.0, 0.0, 0

    gpa = total_grade_points / total_credits
    gps = total_grade_points

    return round(gpa, 2), round(gps, 2), earned_credits


def get_user_statistics(user_id):
    """ユーザーの詳細統計情報を取得"""
    with get_db() as conn:
        c = conn.cursor()
        # 年度別GPAも単位数で加重し、取得単位からF評価を除外する。
        c.execute('''
            SELECT year, COUNT(*) as courses,
                   SUM(CASE WHEN grade != 'F' THEN credits ELSE 0 END) as credits,
                   ROUND(SUM(CASE grade
                       WHEN 'A+' THEN 5.0
                       WHEN 'A' THEN 4.0
                       WHEN 'B' THEN 3.0
                       WHEN 'C' THEN 2.0
                       ELSE 0.0
                   END * credits) / SUM(credits), 2) as avg_gpa
            FROM grades
            WHERE user_id = ? AND grade IN ('A+', 'A', 'B', 'C', 'F')
              AND credits > 0 AND year IS NOT NULL AND year != ""
            GROUP BY year
            ORDER BY year
        ''', (user_id,))
        yearly_stats = c.fetchall()

        # 成績分布
        c.execute('''
            SELECT grade, COUNT(*) as count
            FROM grades 
            WHERE user_id = ? AND grade IN ('A+', 'A', 'B', 'C', 'F') AND credits > 0
            GROUP BY grade
        ''', (user_id,))
        grade_distribution = c.fetchall()

        # カテゴリ別統計（未修得単位と年度不明を除外）
        c.execute('''
            SELECT category, COUNT(*) as courses, 
                   SUM(CASE WHEN grade != 'F' AND year IS NOT NULL AND year != '' THEN credits ELSE 0 END) as credits
            FROM grades
            WHERE user_id = ? AND grade IN ('A+', 'A', 'B', 'C', 'F') AND credits > 0
              AND category IS NOT NULL AND category != ""
            GROUP BY category
        ''', (user_id,))
        category_stats = c.fetchall()

        return {
            'yearly_stats': [dict(row) for row in yearly_stats],
            'grade_distribution': [dict(row) for row in grade_distribution],
            'category_stats': [dict(row) for row in category_stats]
        }


# ランキング機能のAPIエンドポイント
@app.route('/api/get_ranking', methods=['GET'])
@login_required
def get_ranking():
    """全ユーザーのランキングデータを取得する"""
    if not RANKING_ENABLED:
        return jsonify({'status': 'error', 'message': 'ランキング機能は現在無効です。'}), 404

    try:
        sort_by = request.args.get('sort_by', 'gpa')  # gpa, gps, credits
        grade_filter = request.args.get('grade', 'all')  # 学年フィルタ

        with get_db() as conn:
            c = conn.cursor()

            # 学年フィルタに応じてクエリを変更
            if grade_filter == 'all':
                c.execute('SELECT id, nickname, current_year FROM users WHERE nickname IS NOT NULL')
            else:
                c.execute('SELECT id, nickname, current_year FROM users WHERE nickname IS NOT NULL AND current_year = ?', (int(grade_filter),))

            users = c.fetchall()

        ranking_data = []

        for user in users:
            gpa, gps, total_credits = calculate_gpa_gps(user['id'])

            # 最低限のデータがある場合のみランキングに含める
            if total_credits > 0:
                ranking_data.append({
                    'user_id': user['id'],
                    'nickname': user['nickname'],
                    'current_year': user['current_year'],
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
    if not RANKING_ENABLED:
        return jsonify({'status': 'error', 'message': 'ランキング機能は現在無効です。'}), 404

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
    if not RANKING_ENABLED:
        return jsonify({'status': 'error', 'message': 'ランキング機能は現在無効です。'}), 404

    try:
        grade_filter = request.args.get('grade', 'all')  # 学年フィルタ

        with get_db() as conn:
            c = conn.cursor()

            # 学年フィルタに応じてユーザーを取得
            if grade_filter == 'all':
                c.execute('SELECT id FROM users WHERE nickname IS NOT NULL')
            else:
                c.execute('SELECT id FROM users WHERE nickname IS NOT NULL AND current_year = ?', (int(grade_filter),))

            users = c.fetchall()

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
    if not RANKING_ENABLED:
        abort(404)
    return render_template('ranking.html')

# 学年フィルタ用の利用可能な学年一覧を取得するAPIエンドポイント
@app.route('/api/get_available_grades', methods=['GET'])
@login_required
def get_available_grades():
    """利用可能な学年一覧を取得する"""
    if not RANKING_ENABLED:
        return jsonify({'status': 'error', 'message': 'ランキング機能は現在無効です。'}), 404

    try:
        with get_db() as conn:
            c = conn.cursor()

            # データが存在するユーザーの学年を取得
            c.execute('''
                SELECT DISTINCT u.current_year 
                FROM users u 
                WHERE u.nickname IS NOT NULL 
                AND u.current_year IS NOT NULL 
                AND EXISTS (
                    SELECT 1 FROM grades g 
                    WHERE g.user_id = u.id 
                    AND g.grade IS NOT NULL 
                    AND g.grade != ''
                )
                ORDER BY u.current_year
            ''')
            grades = c.fetchall()

        available_grades = [row['current_year'] for row in grades if row['current_year'] is not None]

        return jsonify({
            'status': 'success',
            'data': available_grades
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    # 環境に応じた実行
    if os.environ.get('FLASK_ENV') == 'production':
        print("🚀 本番環境でアプリケーションを起動中...")
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
    else:
        print("🛠️  開発環境でアプリケーションを起動中...")
        print("📱 外部アクセス（iPhone等）有効")
        port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5001)))
        app.run(host='0.0.0.0', debug=True, port=port)
