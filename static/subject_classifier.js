/**
 * 科目名に基づいてカテゴリを自動分類するためのユーティリティ
 */

// 共通専門科目の科目名リスト
const COMMON_SPECIALTY_SUBJECTS = [
  "ソフトウェア工学",
  "コンピュータネットワーク",
  "デジタル信号処理",
  "計算機構成論",
  "データベース",
  "オペレーティングシステム",
  "ネットワークセキュリティ",
  "コンピュータグラフィックス",
  "人工知能",
  "情報理工基礎演習",
  "情報倫理と情報技術",
  "情報理論",
  "計算機科学入門",
  "Introduction to Information Systems Engineering",
  "Professional Ethics",
  "Introduction to Experimentation",
  "Experimental Design",
  "論理回路",
  "Information Science in Action",
  "Presentation Plus 401",
  "Writing for Publication 402",
  "Writing for Information Systems Engineering",
  "Advanced Academic Reading 403",
  "Presentation for Information Systems Engineering",
  "特殊講義 (共通専門)",
  "特殊講義 (共通専門) DX",
];

// 固有専門科目（必修）の科目名リスト
const UNIQUE_REQUIRED_SUBJECTS = [
  "プログラミング演習1",
  "プログラミング演習2",
  "システムアーキテクト演習",
  "システムアーキテクトプログラミング演習",
  "計算機科学実験1",
  "計算機科学実験2",
  "システムアーキテクト実験",
  "メディア処理実験",
  "セキュリティ・ネットワーク学実験",
  "セキュリティ・ネットワーク開発演習",
  "社会システムデザイン創成1",
  "社会システムデザイン創成2",
  "実践プログラミング演習",
  "実世界情報演習1",
  "実世界情報演習2",
  "実世界情報演習3",
  "実世界情報実験1",
  "実世界情報実験2",
  "実世界情報実験3",
  "メディア計算機演習",
  "メディア実験1",
  "メディア実験2",
  "メディアプロジェクト演習1",
  "メディアプロジェクト演習2",
  "知能情報基礎演習",
  "知能情報処理演習",
  "知能情報学実験",
  "知能情報システム創成",
  "PBL 1: Problem Analysis and Modeling",
  "PBL 2 Team-based Design",
  "PBL 3: Creative Design",
  "PBL 4: Team-based Creative Design",
  "PBL 5: Design Evolution",
  "Imperative Programming",
  "Imperative Programming Practice",
  "卒業研究1",
  "卒業研究2",
  "卒業研究3",
];

// 固有専門科目（選択）の科目名リスト
const UNIQUE_ELECTIVE_SUBJECTS = [
  "テキストマイニング",
  "Web アプリケーション",
  "プログラミング言語",
  "電気電子回路",
  "セキュリティ・ネットワーク概論",
  "社会システムデザイン概論",
  "Introduction to Programming",
  "Introduction to OOA, OOD, and UML",
  "データ構造とアルゴリズム",
  "ユーザビリティ工学",
  "計算機アーキテクチャ",
  "機械工学概論",
  "インタラクションデザイン論",
  "ロボティクス",
  "メディア基礎数学",
  "生体生理工学",
  "シミュレーション工学",
  "Network Systems",
  "Human Interface",
  "画像情報処理1",
  "画像情報処理2",
  "オブジェクト指向論",
  "自然言語処理",
  "ヒューマンインタフェース",
  "Web 情報技術概論",
  "実世界情報処理",
  "音声音響情報処理1",
  "音声音響情報処理2",
  "センシング工学",
  "データモデル論",
  "IoT",
  "計算論",
  "システムソフトウェア構成論",
  "分散システム",
  "データ線形分析法",
  "ソフトウェア開発論",
  "コンピュータプログラミング論",
  "データサイエンス",
  "暗号理論",
  "システムセキュリティ",
  "言語処理系",
  "インターネット技術",
  "情報通信ネットワーク",
  "情報アクセス論",
  "データマイニング基礎",
  "認知工学",
  "ユビキタスコンピューティング",
  "機械学習",
  "Web コンピューティング",
  "社会デザイン論",
  "知識工学",
  "生体計測工学",
  "システム制御工学",
  "心理物理学",
  "コンピュータグラフィックス応用",
  "パターン認識",
  "色彩工学",
  "脳機能情報処理",
  "実験データ解析論",
  "Distributed Systems",
  "Web Information Engineering",
  "Data Visualization",
  "Image Processing",
  "Systems Ergonomics",
  "Introduction to Robotic Systems",
  "Pattern Recognition and Machine Learning",
  "Data Science",
  "最適化数学",
];

// 外国語科目の科目名リスト
const FOREIGN_LANGUAGE_SUBJECTS = [
  // 英語系科目
  "英語入門 091",
  "英語入門 092",
  "英語初級 101",
  "英語初級 102",
  "英語初級 103",
  "英語初級 104",
  "英語中級 105",
  "英語中級 106",
  "英語中級 107",
  "英語中級 108",
  "英語上級 109",
  "英語上級 110",
  "Professional Communication 301",
  "Academic Literacy 302",
  "Professional Communication 303",
  "Academic Literacy 304",

  // 一般的な英語科目
  "英語1",
  "英語2",
  "英語3",
  "英語4",
  "英語入門",
  "英語初級",
  "英語中級",
  "英語上級",
  "英会話",
  "英語コミュニケーション",
  "ビジネス英語",
  "学術英語",
  "英語プレゼンテーション",
  "English Communication",
  "Business English",
  "Academic English",
  "English Presentation",

  // その他の外国語
  "中国語1",
  "中国語2",
  "中国語3",
  "中国語4",
  "中国語入門",
  "中国語初級",
  "中国語中級",
  "韓国語1",
  "韓国語2",
  "韓国語3",
  "韓国語4",
  "韓国語入門",
  "韓国語初級",
  "韓国語中級",
  "ドイツ語1",
  "ドイツ語2",
  "ドイツ語3",
  "ドイツ語4",
  "ドイツ語入門",
  "ドイツ語初級",
  "ドイツ語中級",
  "フランス語1",
  "フランス語2",
  "フランス語3",
  "フランス語4",
  "フランス語入門",
  "フランス語初級",
  "フランス語中級",
  "スペイン語1",
  "スペイン語2",
  "スペイン語3",
  "スペイン語4",
  "スペイン語入門",
  "スペイン語初級",
  "スペイン語中級",
  "ロシア語1",
  "ロシア語2",
  "ロシア語入門",
  "ロシア語初級",
  "イタリア語1",
  "イタリア語2",
  "イタリア語入門",
  "イタリア語初級",
  "ポルトガル語1",
  "ポルトガル語2",
  "ポルトガル語入門",
  "アラビア語1",
  "アラビア語2",
  "アラビア語入門",
  "タイ語1",
  "タイ語2",
  "タイ語入門",
  "ベトナム語1",
  "ベトナム語2",
  "ベトナム語入門",
  "インドネシア語1",
  "インドネシア語2",
  "インドネシア語入門",
  "日本語1",
  "日本語2",
  "日本語3",
  "日本語4",
  "日本語入門",
  "日本語初級",
  "日本語中級",
  "日本語上級",
  "Japanese Language",
];

// 基礎専門科目の科目名リスト
const BASIC_SPECIALTY_SUBJECTS = [
  "数学1",
  "数学2",
  "数学3",
  "数学4",
  "数学演習1",
  "数学演習2",
  "化学",
  "物理1",
  "物理2",
  "生物科学",
  "Physics",
  "Exercises in Physics",
  "確率・統計",
  "情報基礎数学",
  "Engineering Mathematics 1",
  "Engineering Mathematics 2",
  "Engineering Mathematics 3",
  "Engineering Mathematics 4",
  "フーリエ解析",
  "多変量解析",
  "離散数学",
  "数値解析",
  "Introduction to Differential Equations",
  "Introduction to Probability and Statistics",
  "Statistical Analysis, Simulation, and Modeling",
  "Optimization and Control Theory",
  "Applied Informatics 1",
  "Applied Informatics 2",
];

// グローバル・キャリア養成科目の科目名リスト
const GLOBAL_CAREER_SUBJECTS = [
  "情報と職業",
  "連携講座",
  "海外IT 英語研修プログラム A",
  "海外IT 英語研修プログラムB",
  "海外IT専門研修プログラム A",
  "海外IT専門研修プログラムB",
  "グローバルインターンシップ",
  "情報技術実践1",
  "情報技術実践2",
  "情報技術実践3",
  "技術経営概論",
  "技術経営特論",
  "イノベーション論",
  "ファイナンス入門",
  "ITを活用した業務改革入門",
  "技術の事業化構想入門",
  "ICT 価値探求デザイン演習",
  "プロジェクトマネジメント基礎",
  "特殊講義 (グローバル・キャリア養成)",
];

/**
 * 科目名からカテゴリを自動推定する関数
 * @param {string} subjectName - 科目名
 * @param {string} currentCategory - 現在のカテゴリ（オプション）
 * @returns {string} 推定されたカテゴリ
 */
function classifySubject(subjectName, currentCategory = "") {
  if (!subjectName) {
    return currentCategory || "未分類";
  }

  // 既にカテゴリが指定されている場合は、専門科目の判定を行う
  if (currentCategory && currentCategory !== "未分類") {
    // 共通専門科目かどうかをチェック
    if (isCommonSpecialtySubject(subjectName)) {
      return "共通専門科目";
    }
    // 固有専門科目（必修）かどうかをチェック
    if (isUniqueRequiredSubject(subjectName)) {
      return "固有専門科目（必修）";
    }
    // 固有専門科目（選択）かどうかをチェック
    if (isUniqueElectiveSubject(subjectName)) {
      return "固有専門科目（選択）";
    }
    // 基礎専門科目かどうかをチェック
    if (isBasicSpecialtySubject(subjectName)) {
      return "基礎専門科目";
    }
    // 外国語科目かどうかをチェック
    if (isForeignLanguageSubject(subjectName)) {
      return "外国語";
    }
    // グローバル・キャリア養成科目かどうかをチェック
    if (isGlobalCareerSubject(subjectName)) {
      return "グローバル・キャリア養成科目";
    }
    return currentCategory;
  }

  // 共通専門科目かどうかをチェック
  if (isCommonSpecialtySubject(subjectName)) {
    return "共通専門科目";
  }

  // 固有専門科目（必修）かどうかをチェック
  if (isUniqueRequiredSubject(subjectName)) {
    return "固有専門科目（必修）";
  }

  // 固有専門科目（選択）かどうかをチェック
  if (isUniqueElectiveSubject(subjectName)) {
    return "固有専門科目（選択）";
  }

  // 基礎専門科目かどうかをチェック
  if (isBasicSpecialtySubject(subjectName)) {
    return "基礎専門科目";
  }

  // 外国語科目かどうかをチェック
  if (isForeignLanguageSubject(subjectName)) {
    return "外国語";
  }

  // グローバル・キャリア養成科目かどうかをチェック
  if (isGlobalCareerSubject(subjectName)) {
    return "グローバル・キャリア養成科目";
  }

  // その他の自動分類ルール（必要に応じて追加）
  const subjectLower = subjectName.toLowerCase();

  // 英語関連科目
  if (
    subjectLower.includes("english") ||
    subjectLower.includes("英語") ||
    subjectName.includes("English")
  ) {
    return "外国語";
  }

  // 教養科目の一般的なパターン
  if (
    subjectName.includes("教養") ||
    subjectName.includes("一般") ||
    subjectName.includes("文学") ||
    subjectName.includes("歴史") ||
    subjectName.includes("哲学") ||
    subjectName.includes("心理学") ||
    subjectName.includes("社会学")
  ) {
    return "教養科目";
  }

  // 基礎専門科目の一般的なパターン
  if (
    subjectName.includes("基礎") ||
    subjectName.includes("入門") ||
    subjectName.includes("概論")
  ) {
    return "基礎専門科目";
  }

  // デフォルトは未分類
  return "未分類";
}

/**
 * 科目名が共通専門科目に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} 共通専門科目の場合true
 */
function isCommonSpecialtySubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (COMMON_SPECIALTY_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 部分一致チェック（特殊講義などの場合）
  return COMMON_SPECIALTY_SUBJECTS.some((subject) => {
    if (subject.includes("特殊講義") && subjectName.includes("特殊講義")) {
      return true;
    }
    return false;
  });
}

/**
 * 科目名が固有専門科目（必修）に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} 固有専門科目（必修）の場合true
 */
function isUniqueRequiredSubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (UNIQUE_REQUIRED_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 全角・半角数字の違いを考慮した柔軟なマッチング
  const normalizedSubjectName = subjectName
    .replace(/１/g, "1")
    .replace(/２/g, "2")
    .replace(/３/g, "3")
    .replace(/４/g, "4")
    .replace(/５/g, "5");

  const normalizedList = UNIQUE_REQUIRED_SUBJECTS.map((subject) =>
    subject
      .replace(/１/g, "1")
      .replace(/２/g, "2")
      .replace(/３/g, "3")
      .replace(/４/g, "4")
      .replace(/５/g, "5")
  );

  return normalizedList.includes(normalizedSubjectName);
}

/**
 * 科目名が固有専門科目（選択）に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} 固有専門科目（選択）の場合true
 */
function isUniqueElectiveSubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (UNIQUE_ELECTIVE_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 全角・半角数字の違いを考慮した柔軟なマッチング
  const normalizedSubjectName = subjectName
    .replace(/１/g, "1")
    .replace(/２/g, "2")
    .replace(/３/g, "3")
    .replace(/４/g, "4")
    .replace(/５/g, "5");

  const normalizedList = UNIQUE_ELECTIVE_SUBJECTS.map((subject) =>
    subject
      .replace(/１/g, "1")
      .replace(/２/g, "2")
      .replace(/３/g, "3")
      .replace(/４/g, "4")
      .replace(/５/g, "5")
  );

  return normalizedList.includes(normalizedSubjectName);
}

/**
 * 科目名が基礎専門科目に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} 基礎専門科目の場合true
 */
function isBasicSpecialtySubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (BASIC_SPECIALTY_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 全角・半角数字の違いを考慮した柔軟なマッチング
  const normalizedSubjectName = subjectName
    .replace(/１/g, "1")
    .replace(/２/g, "2")
    .replace(/３/g, "3")
    .replace(/４/g, "4")
    .replace(/５/g, "5");

  const normalizedList = BASIC_SPECIALTY_SUBJECTS.map((subject) =>
    subject
      .replace(/１/g, "1")
      .replace(/２/g, "2")
      .replace(/３/g, "3")
      .replace(/４/g, "4")
      .replace(/５/g, "5")
  );

  return normalizedList.includes(normalizedSubjectName);
}

/**
 * 科目名が外国語科目に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} 外国語科目の場合true
 */
function isForeignLanguageSubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (FOREIGN_LANGUAGE_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 全角半角数字の変換をして再チェック
  const normalizedSubjectName = subjectName
    .replace(/１/g, "1")
    .replace(/２/g, "2")
    .replace(/３/g, "3")
    .replace(/４/g, "4")
    .replace(/５/g, "5");

  const normalizedList = FOREIGN_LANGUAGE_SUBJECTS.map((subject) =>
    subject
      .replace(/１/g, "1")
      .replace(/２/g, "2")
      .replace(/３/g, "3")
      .replace(/４/g, "4")
      .replace(/５/g, "5")
  );

  return normalizedList.includes(normalizedSubjectName);
}

/**
 * 科目名がグローバル・キャリア養成科目に該当するかチェックする関数
 * @param {string} subjectName - 科目名
 * @returns {boolean} グローバル・キャリア養成科目の場合true
 */
function isGlobalCareerSubject(subjectName) {
  if (!subjectName) return false;

  // 完全一致チェック
  if (GLOBAL_CAREER_SUBJECTS.includes(subjectName)) {
    return true;
  }

  // 全角・半角数字の違いを考慮した柔軟なマッチング
  const normalizedSubjectName = subjectName
    .replace(/１/g, "1")
    .replace(/２/g, "2")
    .replace(/３/g, "3")
    .replace(/４/g, "4")
    .replace(/５/g, "5");

  const normalizedList = GLOBAL_CAREER_SUBJECTS.map((subject) =>
    subject
      .replace(/１/g, "1")
      .replace(/２/g, "2")
      .replace(/３/g, "3")
      .replace(/４/g, "4")
      .replace(/５/g, "5")
  );

  return normalizedList.includes(normalizedSubjectName);
}

/**
 * 科目追加フォームでカテゴリを自動設定する関数
 * @param {string} subjectName - 科目名
 */
function autoSetCategory(subjectName) {
  const categorySelect = document.getElementById("course-category");
  if (!categorySelect || !subjectName) return;

  const suggestedCategory = classifySubject(subjectName);

  // 共通専門科目の場合は自動設定
  if (suggestedCategory === "共通専門科目") {
    categorySelect.value = "共通専門科目";

    // ユーザーに通知
    showCategoryNotification(subjectName, "共通専門科目");
  }
  // 固有専門科目（必修）の場合は自動設定
  else if (suggestedCategory === "固有専門科目（必修）") {
    categorySelect.value = "固有専門科目（必修）";

    // ユーザーに通知
    showCategoryNotification(subjectName, "固有専門科目（必修）");
  }
  // 固有専門科目（選択）の場合は自動設定
  else if (suggestedCategory === "固有専門科目（選択）") {
    categorySelect.value = "固有専門科目（選択）";

    // ユーザーに通知
    showCategoryNotification(subjectName, "固有専門科目（選択）");
  }
  // 基礎専門科目の場合は自動設定
  else if (suggestedCategory === "基礎専門科目") {
    categorySelect.value = "基礎専門科目";

    // ユーザーに通知
    showCategoryNotification(subjectName, "基礎専門科目");
  }
  // 外国語科目の場合は自動設定
  else if (suggestedCategory === "外国語") {
    categorySelect.value = "外国語";

    // ユーザーに通知
    showCategoryNotification(subjectName, "外国語");
  }
  // グローバル・キャリア養成科目の場合は自動設定
  else if (suggestedCategory === "グローバル・キャリア養成科目") {
    categorySelect.value = "グローバル・キャリア養成科目";

    // ユーザーに通知
    showCategoryNotification(subjectName, "グローバル・キャリア養成科目");
  }
}

/**
 * カテゴリ自動設定の通知を表示する関数
 * @param {string} subjectName - 科目名
 * @param {string} category - 設定されたカテゴリ
 */
function showCategoryNotification(subjectName, category) {
  // 既存の通知システムを使用（存在する場合）    if (typeof window.showNotification === "function") {
  window.showNotification(
    `「${subjectName}」は「${category}」に自動分類されました`,
    "info"
  );
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

    // カテゴリが変更される場合（共通専門科目または固有専門科目（必修）または固有専門科目（選択）または基礎専門科目または外国語またはグローバル・キャリア養成科目）
    if (
      suggestedCategory !== currentCategory &&
      (suggestedCategory === "共通専門科目" ||
        suggestedCategory === "固有専門科目（必修）" ||
        suggestedCategory === "固有専門科目（選択）" ||
        suggestedCategory === "基礎専門科目" ||
        suggestedCategory === "外国語" ||
        suggestedCategory === "グローバル・キャリア養成科目")
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
window.isCommonSpecialtySubject = isCommonSpecialtySubject;
window.isUniqueRequiredSubject = isUniqueRequiredSubject;
window.isUniqueElectiveSubject = isUniqueElectiveSubject;
window.isBasicSpecialtySubject = isBasicSpecialtySubject;
window.isGlobalCareerSubject = isGlobalCareerSubject;
window.autoSetCategory = autoSetCategory;
window.reclassifyExistingCourses = reclassifyExistingCourses;
