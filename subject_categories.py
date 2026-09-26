"""科目名からカテゴリを推定する。

科目一覧と判定ルールは static/data/subject_categories.json にまとめてあり、
画面側の static/subject_classifier.js も同じファイルを使う。
"""

import json
import os

SUBJECT_CATEGORIES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'static', 'data', 'subject_categories.json'
)

UNCLASSIFIED = '未分類'

# 科目一覧と成績表で全角・半角が混在しやすい数字をそろえる
_DIGIT_TABLE = str.maketrans('１２３４５', '12345')


def load_subject_categories(path=SUBJECT_CATEGORIES_PATH):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


SUBJECT_CATEGORIES = load_subject_categories()


def normalize_digits(text):
    return text.translate(_DIGIT_TABLE)


def _find_keyword_rule(subject_name, rules):
    subject_lower = subject_name.lower()
    for rule in rules:
        if any(keyword in subject_lower for keyword in rule['keywords']):
            return rule['category']
    return None


def classify_subject_by_name(subject_name, data=SUBJECT_CATEGORIES):
    """科目名からカテゴリを推定する。判定できなければ「未分類」を返す。

    判定の順番：
    1. 科目一覧との完全一致（カテゴリの並び順に確認）
    2. 数字の全角・半角をそろえたうえでの一致
    3. 部分一致のルール（例：「特殊講義」を含む → 共通専門科目）
    4. キーワードによる推定（例：「英語」を含む → 外国語）
    """
    if not subject_name:
        return UNCLASSIFIED

    for category in data['categories']:
        if subject_name in category['subjects']:
            return category['name']

    normalized_name = normalize_digits(subject_name)
    for category in data['categories']:
        if normalized_name in (normalize_digits(s) for s in category['subjects']):
            return category['name']

    return (
        _find_keyword_rule(subject_name, data['partial_match_rules'])
        or _find_keyword_rule(subject_name, data['fallback_keyword_rules'])
        or UNCLASSIFIED
    )
