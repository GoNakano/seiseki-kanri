"""GPA・GPSの計算と、ランキング用の集計。"""

from db import get_db


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
