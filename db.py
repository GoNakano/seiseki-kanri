"""データベースの接続・テーブル作成・初期データ。"""

import sqlite3
from contextlib import contextmanager
import logging
import os

from werkzeug.security import generate_password_hash

from settings import DB_FILE, DEMO_ADMIN_ENABLED

logger = logging.getLogger(__name__)


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


def create_default_user(logger=logger):
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
                logger.info('デフォルト管理者ユーザーを作成しました。')
            conn.commit()
    except Exception:
        logger.exception('管理者アカウントの初期化に失敗しました')
        raise


def initialize_database(logger=logger):
    """開発サーバーとWSGIサーバーの両方でDBを初期化する。"""
    init_db()
    create_default_user(logger)
