/**
 * 科目名に基づいてカテゴリを自動分類するためのユーティリティ
 *
 * 科目一覧と判定ルールは static/data/subject_categories.json にあり、
 * index.html が <script id="subject-categories-data"> として埋め込む。
 * サーバー側（subject_categories.py）も同じデータを使う。
 */

const SUBJECT_CATEGORY_DATA = JSON.parse(
  document.getElementById("subject-categories-data")?.textContent ||
    '{"categories": [], "partial_match_rules": [], "fallback_keyword_rules": []}'
);

// 自動設定・再分類の対象にするカテゴリ（科目一覧があるカテゴリ）
const LIST_CATEGORY_NAMES = SUBJECT_CATEGORY_DATA.categories.map(
  (category) => category.name
);

/**
 * 科目一覧と成績表で全角・半角が混在しやすい数字をそろえる
 * @param {string} text
 * @returns {string}
 */
function normalizeDigits(text) {
  return text.replace(/[１-５]/g, (digit) =>
    String.fromCharCode(digit.charCodeAt(0) - 0xfee0)
  );
}

/**
 * キーワードのルールに当てはまるカテゴリを返す（なければnull）
 * @param {string} subjectName
 * @param {Array<{category: string, keywords: string[]}>} rules
 * @returns {string|null}
 */
function findKeywordRule(subjectName, rules) {
  const subjectLower = subjectName.toLowerCase();
  const rule = rules.find((candidate) =>
    candidate.keywords.some((keyword) => subjectLower.includes(keyword))
  );
  return rule ? rule.category : null;
}

/**
 * 科目一覧と部分一致のルールだけでカテゴリを判定する（なければnull）
 * 順番：完全一致 → 数字をそろえて一致 → 部分一致（例：「特殊講義」）
 * @param {string} subjectName
 * @returns {string|null}
 */
function findListCategory(subjectName) {
  const { categories, partial_match_rules: partialMatchRules } =
    SUBJECT_CATEGORY_DATA;

  const exact = categories.find((category) =>
    category.subjects.includes(subjectName)
  );
  if (exact) return exact.name;

  const normalizedName = normalizeDigits(subjectName);
  const normalized = categories.find((category) =>
    category.subjects.some(
      (subject) => normalizeDigits(subject) === normalizedName
    )
  );
  if (normalized) return normalized.name;

  return findKeywordRule(subjectName, partialMatchRules);
}

/**
 * 科目名からカテゴリを推定する（サーバー側の classify_subject_by_name と同じ規則）
 * @param {string} subjectName - 科目名
 * @param {string} currentCategory - 現在のカテゴリ（オプション）
 * @returns {string} 推定されたカテゴリ
 */
function classifySubject(subjectName, currentCategory = "") {
  if (!subjectName) {
    return currentCategory || "未分類";
  }

  const listCategory = findListCategory(subjectName);
  if (listCategory) {
    return listCategory;
  }

  // すでにカテゴリが設定されている場合は、キーワードによる推定では上書きしない
  if (currentCategory && currentCategory !== "未分類") {
    return currentCategory;
  }

  return (
    findKeywordRule(subjectName, SUBJECT_CATEGORY_DATA.fallback_keyword_rules) ||
    "未分類"
  );
}

/**
 * 科目追加フォームでカテゴリを自動設定する関数
 * @param {string} subjectName - 科目名
 */
function autoSetCategory(subjectName) {
  const categorySelect = document.getElementById("course-category");
  if (!categorySelect || !subjectName) return;

  const suggestedCategory = classifySubject(subjectName);
  if (LIST_CATEGORY_NAMES.includes(suggestedCategory)) {
    categorySelect.value = suggestedCategory;
    showCategoryNotification(subjectName, suggestedCategory);
  }
}

/**
 * カテゴリ自動設定の通知を表示する関数
 * @param {string} subjectName - 科目名
 * @param {string} category - 設定されたカテゴリ
 */
function showCategoryNotification(subjectName, category) {
  // 既存の通知システムを使用（存在する場合）
  if (typeof window.showNotification === "function") {
    window.showNotification(
      `「${subjectName}」は「${category}」に自動分類されました`,
      "info"
    );
  }
}

/**
 * 既存のデータベース内の科目を再分類する関数
 * CAMPUSインポートや手動追加済みの科目のカテゴリを修正する
 */
function reclassifyExistingCourses() {
  if (!window.courses || !Array.isArray(window.courses)) {
    if (typeof window.showNotification === "function") {
      window.showNotification("科目データが見つかりません", "error");
    }
    return;
  }

  let reclassifiedCount = 0;
  const updates = [];

  window.courses.forEach((course, index) => {
    if (!course.name) return;

    const currentCategory = course.category || "未分類";
    const suggestedCategory = classifySubject(course.name, currentCategory);

    // 科目一覧があるカテゴリへ変わる場合だけ更新する
    if (
      suggestedCategory !== currentCategory &&
      LIST_CATEGORY_NAMES.includes(suggestedCategory)
    ) {
      updates.push({
        index: index,
        id: course.id,
        oldCategory: currentCategory,
        newCategory: suggestedCategory,
        name: course.name,
      });
      reclassifiedCount++;
    }
  });

  if (updates.length > 0) {
    // ユーザーに確認
    if (
      confirm(
        `${
          updates.length
        }件の科目のカテゴリを自動更新しますか？\n\n変更対象:\n${updates
          .map((u) => `• ${u.name}: ${u.oldCategory} → ${u.newCategory}`)
          .join("\n")}`
      )
    ) {
      // 実際に更新を実行
      executeReclassification(updates);
    }
  } else {
    alert("再分類が必要な科目は見つかりませんでした。");
  }
}

/**
 * 再分類を実行する関数
 * @param {Array} updates - 更新対象の配列
 */
async function executeReclassification(updates) {
  let successCount = 0;
  let errorCount = 0;

  for (const update of updates) {
    try {
      // 科目データを更新
      const updatedCourse = {
        ...window.courses[update.index],
        category: update.newCategory,
      };

      // APIを呼び出して更新
      const response = await fetch("/api/update_course", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          index: update.id,
          course: updatedCourse,
        }),
      });

      if (response.ok) {
        // ローカルデータも更新
        window.courses[update.index].category = update.newCategory;
        successCount++;
      } else {
        const errorData = await response
          .json()
          .catch(() => ({ message: response.statusText }));
        console.error(
          `科目「${update.name}」の更新に失敗:`,
          errorData.message || response.statusText
        );
        errorCount++;
      }
    } catch (error) {
      console.error(`科目「${update.name}」の更新中にエラー:`, error);
      errorCount++;
    }
  }

  // 結果を表示
  if (successCount > 0) {
    alert(`${successCount}件の科目カテゴリを正常に更新しました。`);

    // 画面を再描画 - fetchCoursesを呼び出してサーバーから最新データを取得
    if (typeof window.fetchCourses === "function") {
      await window.fetchCourses();
    } else if (typeof window.renderCourseList === "function") {
      window.renderCourseList();
    }
    if (typeof window.calculateCategoryCredits === "function") {
      window.calculateCategoryCredits();
    }
  }

  if (errorCount > 0) {
    alert(
      `${errorCount}件の科目の更新に失敗しました。詳細はコンソールを確認してください。`
    );
  }
}

// グローバルスコープに関数を公開
window.classifySubject = classifySubject;
window.autoSetCategory = autoSetCategory;
window.reclassifyExistingCourses = reclassifyExistingCourses;
