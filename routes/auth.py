"""ログイン・新規登録・ログアウト・プロフィール。"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import generate_password_hash

from db import get_db
from forms import ChangePasswordForm, DeleteAccountForm, LoginForm, ProfileForm, RegistrationForm
from models import User

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('courses.home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_user_id(form.user_id.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('courses.home'))
        flash('ユーザーIDまたはパスワードが正しくありません', 'error')

    return render_template('login.html', form=form, title='ログイン')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('courses.home'))

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
            return redirect(url_for('courses.home'))
        except Exception as e:
            flash(f'登録中にエラーが発生しました: {str(e)}', 'error')

    return render_template('register.html', form=form, title='新規登録')


@bp.route('/logout')
def logout():
    logout_user()
    flash('ログアウトしました', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/profile', methods=['GET', 'POST'])
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
            return redirect(url_for('auth.profile'))
        except Exception as e:
            flash(f'プロフィール更新中にエラーが発生しました: {str(e)}', 'error')

    # パスワード変更のフォーム処理
    if 'change_password' in request.form and password_form.validate_on_submit():
        # 現在のパスワード確認
        if not current_user.check_password(password_form.current_password.data):
            flash('現在のパスワードが正しくありません', 'error')
            return redirect(url_for('auth.profile'))

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
            return redirect(url_for('auth.profile'))
        except Exception as e:
            flash(f'パスワード変更中にエラーが発生しました: {str(e)}', 'error')

    # アカウント削除のフォーム処理
    if 'delete_account' in request.form and delete_form.validate_on_submit():
        # 現在のパスワード確認
        if not current_user.check_password(delete_form.password.data):
            flash('パスワードが正しくありません', 'error')
            return redirect(url_for('auth.profile'))

        try:
            user_id = current_user.id

            # データベース接続
            with get_db() as conn:
                c = conn.cursor()

                # ユーザーの成績データを削除
                c.execute('DELETE FROM grades WHERE user_id = ?', (user_id,))

                # ユーザーの講義レビューと、それに付いた通報・本人が行った通報を削除
                c.execute('''
                    DELETE FROM review_reports
                    WHERE reporter_user_id = ?
                       OR review_id IN (SELECT id FROM course_reviews WHERE user_id = ?)
                ''', (user_id, user_id))
                c.execute('DELETE FROM course_reviews WHERE user_id = ?', (user_id,))

                # ユーザーアカウントを削除
                c.execute('DELETE FROM users WHERE id = ?', (user_id,))

                conn.commit()

            # ログアウト処理
            logout_user()

            flash('アカウントが正常に削除されました。ご利用ありがとうございました。', 'info')
            return redirect(url_for('auth.login'))

        except Exception as e:
            flash(f'アカウント削除中にエラーが発生しました: {str(e)}', 'error')

    return render_template('profile.html', 
                         profile_form=profile_form, 
                         password_form=password_form,
                         delete_form=delete_form)
