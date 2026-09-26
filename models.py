"""ログインに使うユーザーのモデル（Flask-Login）。"""

import json

from flask_login import UserMixin
from werkzeug.security import check_password_hash

from db import get_db


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
