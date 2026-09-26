"""ランキング画面と、その集計API。ENABLE_RANKINGで無効にできる。"""

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from db import get_db
from settings import RANKING_ENABLED
from stats import calculate_distribution, calculate_gpa_gps, get_user_statistics

bp = Blueprint('ranking', __name__)


# ランキング機能のAPIエンドポイント
@bp.route('/api/get_ranking', methods=['GET'])
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


@bp.route('/api/get_my_stats', methods=['GET'])
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


@bp.route('/api/get_distribution_stats', methods=['GET'])
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


@bp.route('/ranking')
@login_required
def ranking():
    """ランキングページを表示"""
    if not RANKING_ENABLED:
        abort(404)
    return render_template('ranking.html')


# 学年フィルタ用の利用可能な学年一覧を取得するAPIエンドポイント
@bp.route('/api/get_available_grades', methods=['GET'])
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
