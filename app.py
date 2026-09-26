"""成績管理アプリの入口。

Flaskアプリの設定・ログイン管理・セキュリティヘッダーをまとめ、
機能ごとのルート（routes/）を登録する。
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask
from flask_login import LoginManager

from db import initialize_database
from models import User
from routes import auth, campus_import, courses, ranking, reviews
from settings import BASE_DIR, IS_PRODUCTION, RANKING_ENABLED

app = Flask(__name__)

# セキュリティ設定：環境に応じたSECRET_KEYの設定
if IS_PRODUCTION:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    if not app.config['SECRET_KEY']:
        raise ValueError("本番環境ではSECRET_KEYの環境変数が必要です")
    app.config['DEBUG'] = False
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
else:
    app.config['SECRET_KEY'] = 'dev-key-do-not-use-in-production'
    app.config['DEBUG'] = True


# セキュリティヘッダーの設定
@app.after_request
def after_request(response):
    """レスポンスヘッダーにセキュリティ設定を追加"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# ログ設定（本番環境のみ）
if not app.debug and IS_PRODUCTION:
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
login_manager.login_view = 'auth.login'
login_manager.login_message = 'この機能を使用するにはログインしてください。'


@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))


@app.context_processor
def inject_app_flags():
    return {'ranking_enabled': RANKING_ENABLED}


for module in (auth, courses, campus_import, reviews, ranking):
    app.register_blueprint(module.bp)

# Gunicornなどはこのファイルをimportして起動するため、__main__だけでは初期化されない。
if os.environ.get('SKIP_DB_INIT') != '1':
    initialize_database(app.logger)

if __name__ == "__main__":
    # 環境に応じた実行
    if IS_PRODUCTION:
        print("🚀 本番環境でアプリケーションを起動中...")
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
    else:
        print("🛠️  開発環境でアプリケーションを起動中...")
        print("📱 外部アクセス（iPhone等）有効")
        port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5001)))
        app.run(host='0.0.0.0', debug=True, port=port)
