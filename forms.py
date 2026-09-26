"""画面の入力フォーム（Flask-WTF）。"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, IntegerField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional, NumberRange

from models import User


# ログインフォームクラス
class LoginForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    password = PasswordField('パスワード', validators=[DataRequired()])
    remember = BooleanField('ログイン状態を保持する')
    submit = SubmitField('ログイン')


# 新規ユーザー登録フォームクラス
class RegistrationForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    nickname = StringField('ニックネーム', validators=[DataRequired(), Length(min=2, max=50)])
    password = PasswordField('パスワード', validators=[
        DataRequired(), 
        Length(min=8, message='パスワードは8文字以上必要です')
    ])
    password2 = PasswordField('パスワード（確認）', validators=[
        DataRequired(), 
        EqualTo('password', message='パスワードが一致しません')
    ])
    current_year = IntegerField('学年', validators=[DataRequired(), NumberRange(min=1, max=6, message='1〜6の間で入力してください')])
    submit = SubmitField('登録')

    def validate_user_id(self, user_id):
        user = User.get_by_user_id(user_id.data)
        if user:
            raise ValidationError('このユーザーIDは既に登録されています。')


# プロフィール編集フォームクラス
class ProfileForm(FlaskForm):
    user_id = StringField('ユーザーID', validators=[DataRequired(), Length(min=3, max=20, message='ユーザーIDは3〜20文字で入力してください')])
    nickname = StringField('ニックネーム', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('メールアドレス（任意）', validators=[Optional(), Email()])
    grade = IntegerField('学年', validators=[Optional(), NumberRange(min=1, max=6, message='1〜6の間で入力してください')])
    required_credits = FloatField('卒業必要単位数', validators=[
        DataRequired(message='卒業必要単位数を入力してください'),
        NumberRange(min=1, max=300, message='1〜300の範囲で入力してください'),
    ])
    submit = SubmitField('更新')

    def __init__(self, original_user_id=None, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.original_user_id = original_user_id

    def validate_user_id(self, user_id):
        # 現在のユーザーIDと同じ場合はチェックをスキップ
        if user_id.data != self.original_user_id:
            user = User.get_by_user_id(user_id.data)
            if user:
                raise ValidationError('このユーザーIDは既に登録されています。')


# パスワード変更フォームクラス
class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('現在のパスワード', validators=[DataRequired()])
    new_password = PasswordField('新しいパスワード', validators=[
        DataRequired(), 
        Length(min=8, message='パスワードは8文字以上必要です')
    ])
    confirm_password = PasswordField('新しいパスワード（確認）', validators=[
        DataRequired(), 
        EqualTo('new_password', message='パスワードが一致しません')
    ])
    submit = SubmitField('パスワード変更')


class DeleteAccountForm(FlaskForm):
    password = PasswordField('パスワード', validators=[DataRequired()])
    confirm_text = StringField('確認テキスト', validators=[DataRequired()])
    submit = SubmitField('アカウントを削除')

    def validate_confirm_text(self, confirm_text):
        if confirm_text.data != 'アカウント削除':
            raise ValidationError('確認テキストが正しくありません。「アカウント削除」と入力してください。')
