import unittest

from subject_categories import SUBJECT_CATEGORIES, classify_subject_by_name


class ClassifySubjectByNameTest(unittest.TestCase):
    def test_exact_match_uses_subject_list(self):
        self.assertEqual(classify_subject_by_name("ソフトウェア工学"), "共通専門科目")

    def test_every_listed_subject_is_classified_into_its_own_category(self):
        for category in SUBJECT_CATEGORIES["categories"]:
            for subject in category["subjects"]:
                with self.subTest(subject=subject):
                    self.assertEqual(classify_subject_by_name(subject), category["name"])

    def test_full_width_digits_are_normalized(self):
        self.assertEqual(
            classify_subject_by_name("Writing for Publication ４0２"), "共通専門科目"
        )

    def test_special_lecture_falls_back_to_common_specialty(self):
        self.assertEqual(classify_subject_by_name("特殊講義 (新しい科目)"), "共通専門科目")

    def test_listed_special_lecture_keeps_its_own_category(self):
        self.assertEqual(
            classify_subject_by_name("特殊講義 (グローバル・キャリア養成)"),
            "グローバル・キャリア養成科目",
        )

    def test_keyword_rules_apply_to_unlisted_subjects(self):
        self.assertEqual(classify_subject_by_name("ENGLISH Reading"), "外国語")
        self.assertEqual(classify_subject_by_name("西洋文学"), "教養科目")
        self.assertEqual(classify_subject_by_name("データ分析入門"), "基礎専門科目")

    def test_unknown_or_empty_subject_is_unclassified(self):
        self.assertEqual(classify_subject_by_name("未知の科目"), "未分類")
        self.assertEqual(classify_subject_by_name(""), "未分類")


if __name__ == "__main__":
    unittest.main()
