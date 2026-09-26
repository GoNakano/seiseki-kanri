"""環境変数から読み込む設定。

.env ファイルがあれば先に読み込む（本番環境用）。
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

# データベースファイルのパス
database_path = os.environ.get('DATABASE_PATH', 'grades.db')
DB_FILE = database_path if os.path.isabs(database_path) else os.path.join(BASE_DIR, database_path)
db_directory = os.path.dirname(DB_FILE)
if db_directory:
    os.makedirs(db_directory, exist_ok=True)
