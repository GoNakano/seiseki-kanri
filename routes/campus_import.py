"""大学ポータル（CAMPUS）の成績表HTMLを解析して科目データにする。"""

from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request
from flask_login import login_required

from subject_categories import classify_subject_by_name

bp = Blueprint('campus_import', __name__)


@bp.route('/api/parse_campus_html', methods=['POST'])
@login_required
def parse_campus_html():
    """
    CAMPUSウェブからの成績HTMLを解析し、コース情報として返すエンドポイント
    """
    data = request.get_json()
    html_content = data.get('html', '')

    if not html_content:
        return jsonify({"status": "error", "message": "HTMLデータが提供されていません"}), 400

    try:
        # BeautifulSoupで解析
        soup = BeautifulSoup(html_content, 'html.parser')

        # CAMPUSウェブの成績テーブルを探す（様々なクラス名に対応）
        grades_table = soup.find('table', class_='result_title')

        if not grades_table:
            # テーブルが見つからない場合、別の方法で探す
            grades_table = soup.find('table', class_='campusTable')

        if not grades_table:
            # さらに別の方法で探す
            grades_table = soup.find('table', {'id': lambda x: x and 'tbl_' in x})

        if not grades_table:
            return jsonify({"status": "error", "message": "成績テーブルが見つかりませんでした。正しいCAMPUSウェブの成績表のHTMLを貼り付けてください。"}), 400

        rows = grades_table.find_all('tr')

        # ヘッダー行をスキップして科目情報を抽出
        courses = []

        # 最初の行はヘッダーなのでスキップ
        for row in rows[1:]:
            cells = row.find_all('td', class_='list_cell_center')

            # クラスがない場合は一般的なtdタグも検索
            if not cells:
                cells = row.find_all('td')

            # 有効な行のみを処理（列数をチェック）
            if len(cells) >= 5:
                try:
                    # 区分（カテゴリ）- 立命館CAMPUSウェブでは0番目
                    category = cells[0].get_text(strip=True) if len(cells) > 0 else "未分類"

                    # 科目名（コード番号を除去）- 立命館CAMPUSウェブでは1番目
                    name_full = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    # 科目コードを除去（例：「53012 生物科学１ *」→「生物科学１ *」）
                    name = name_full.split(' ', 1)[-1] if ' ' in name_full else name_full
                    name = name.replace(' *', '')  # 遠隔授業マーク(*) を除去

                    # 単位数 - 立命館CAMPUSウェブでは4番目
                    credits_text = cells[4].get_text(strip=True) if len(cells) > 4 else "0"
                    credits = float(credits_text) if credits_text and credits_text.replace('.', '', 1).isdigit() else 0

                    # 成績評価 - 立命館CAMPUSウェブでは5番目
                    grade = cells[5].get_text(strip=True) if len(cells) > 5 else ""

                    # 修得年度 - 立命館CAMPUSウェブでは6番目
                    year_text = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                    year = int(year_text) if year_text and year_text.isdigit() else None

                    # 学期（授業開講期間）- 立命館CAMPUSウェブでは7番目
                    semester_text = cells[7].get_text(strip=True) if len(cells) > 7 else ""
                    semester = map_campus_semester(semester_text)

                    # カテゴリのマッピング
                    mapped_category = map_campus_category_to_app_category(category)

                    # 科目名による自動分類も試行（共通専門科目の場合は優先）
                    name_based_category = classify_subject_by_name(name)
                    if name_based_category == '共通専門科目':
                        mapped_category = name_based_category
                    elif mapped_category == '未分類' and name_based_category != '未分類':
                        mapped_category = name_based_category

                    # 科目名と単位数があれば追加
                    if name and credits > 0:
                        course = {
                            "name": name,
                            "credits": credits,
                            "grade": grade,
                            "year": year if year else "",
                            "semester": semester,
                            "category": mapped_category,
                            "memo": f"CAMPUSウェブから自動インポート: 元区分「{category}」"
                        }
                        courses.append(course)

                except Exception:
                    # 形式が想定と違う行は飛ばして続行する
                    pass

        if not courses:
            return jsonify({"status": "warning", "message": "有効な科目データが見つかりませんでした。HTMLが正しいか確認してください。"}), 200

        return jsonify({
            "status": "success",
            "message": f"{len(courses)}件の科目データが見つかりました。",
            "courses": courses
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"HTMLの解析中にエラーが発生しました: {str(e)}"}), 500


def map_campus_category_to_app_category(campus_category):
    """
    CAMPUSウェブの区分を本アプリのカテゴリに変換するヘルパー関数
    """
    # 小文字にして空白を削除してマッチングしやすくする
    category_lower = campus_category.lower().replace(' ', '')

    # カテゴリマッピング（必要に応じて追加・調整）
    if any(keyword in category_lower for keyword in ['専門', '必修', '選択']):
        if '基礎' in category_lower:
            return '基礎専門科目'
        elif '共通' in category_lower:
            return '共通専門科目'
        elif '必修' in category_lower:
            return '固有専門科目（必修）'
        elif '選択' in category_lower:
            return '固有専門科目（選択）'
        else:
            return '固有専門科目（選択）'  # 「専門科目」は「固有専門科目（選択）」にマッピング
    elif '外国語' in category_lower or 'language' in category_lower:
        return '外国語'
    elif '教養' in category_lower or 'liberal' in category_lower:
        return '教養科目'
    elif 'グローバル' in category_lower or 'キャリア' in category_lower or 'global' in category_lower:
        return 'グローバル・キャリア養成科目'
    else:
        return '未分類'  # デフォルト


def map_campus_semester(campus_semester):
    """
    CAMPUSウェブの学期表記をアプリの学期表記に変換するヘルパー関数
    """
    semester_text = campus_semester.lower()
    if '春' in semester_text:
        return '春学期'
    elif '秋' in semester_text:
        return '秋学期'
    elif '通年' in semester_text:
        return '通年'
    elif '夏' in semester_text:
        return '春学期'  # 夏学期は春学期としてカウント
    elif '冬' in semester_text:
        return '秋学期'  # 冬学期は秋学期としてカウント
    else:
        return '春学期'  # デフォルト
