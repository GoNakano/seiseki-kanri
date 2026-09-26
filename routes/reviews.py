"""講義レビューの登録・一覧・詳細・削除・通報。"""

import re
import sqlite3
import unicodedata

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from db import get_db

bp = Blueprint('reviews', __name__)


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


@bp.route('/reviews')
@login_required
def reviews():
    return render_template('reviews.html')


@bp.route('/api/reviews', methods=['GET'])
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


@bp.route('/api/reviews/mine', methods=['GET'])
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


@bp.route('/api/reviews/detail', methods=['GET'])
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


@bp.route('/api/reviews', methods=['POST'])
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
            current_app.logger.exception('講義レビューの保存に失敗しました')
            return jsonify({'status': 'error', 'message': '講義レビューを保存できませんでした。'}), 500


@bp.route('/api/reviews/<int:review_id>', methods=['DELETE'])
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


@bp.route('/api/reviews/<int:review_id>/report', methods=['POST'])
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
