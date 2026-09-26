"""ホーム画面と、科目（成績）の登録・更新・削除・CSV出力。"""

import csv
import io
import sqlite3

from flask import Blueprint, Response, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from db import get_db
from subject_categories import SUBJECT_CATEGORIES

bp = Blueprint('courses', __name__)


# ホームページを表示
@bp.route("/")
@login_required  # ログインが必要
def home():
    return render_template(
        "index.html",
        required_credits=float(current_user.required_credits or 124.0),
        subject_categories=SUBJECT_CATEGORIES,
    )


@bp.route('/healthz')
def healthz():
    """デプロイ先の稼働確認用エンドポイント。"""
    return jsonify({'status': 'ok'})


@bp.route('/api/export_courses')
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


@bp.route('/api/load_demo_data', methods=['POST'])
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
            current_app.logger.exception('サンプルデータの追加に失敗しました')
            return jsonify({
                'status': 'error',
                'message': 'サンプルデータの追加に失敗しました。',
            }), 500


# 成績データを取得するAPI
@bp.route("/api/get_courses", methods=["GET"])
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
@bp.route("/api/add_course", methods=["POST"])
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


@bp.route('/api/delete_course', methods=['POST'])
@login_required
def delete_course():
    index = request.json.get("index")
    with get_db() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM grades WHERE id = ? AND user_id = ?", (index, current_user.id))
        if c.rowcount == 0:
            return jsonify({'status': 'error', 'message': '削除できる科目が見つかりません。'}), 404
        conn.commit()
    return jsonify({'status': 'deleted'})


@bp.route('/api/update_course', methods=['POST'])
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
            if c.rowcount == 0:
                return jsonify({'status': 'error', 'message': '更新できる科目が見つかりません。'}), 404
            conn.commit()
        return jsonify({'status': 'updated'})
    except Exception as e:
        current_app.logger.error(f"Error updating course: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/add_courses_bulk', methods=['POST'])
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


@bp.route('/api/delete_courses_bulk', methods=['POST'])
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
