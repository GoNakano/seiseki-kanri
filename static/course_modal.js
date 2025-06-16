/**
 * 科目詳細モーダルの操作を担当するファイル
 */

// DOM要素の取得
const courseListModal = document.getElementById("course-list-modal");
const courseCloseBtn = document.querySelector(".course-close");
const courseModalBody = document.querySelector(".course-modal-body");

/**
 * 科目詳細を表示するモーダルを開く
 * @param {Object} course - 表示する科目オブジェクト
 */
function showCourseModal(course) {
  // モーダル要素の存在確認
  if (!courseModalBody) {
    console.error("course-modal-body element not found");
    return;
  }

  // モーダル本体にコンテンツを設定
  courseModalBody.innerHTML = "";

  // テーブル要素を作成
  const table = document.createElement("table");

  // 科目データを表に追加
  const fields = [
    { label: "科目名", value: course.name },
    { label: "年度", value: course.year || "-" },
    { label: "学期", value: course.semester || "-" },
    { label: "単位数", value: course.credits },
    { label: "評価", value: course.grade },
    { label: "カテゴリ", value: course.category || "未分類" },
    { label: "メモ", value: course.memo || "-" },
  ];

  // 各フィールドを表に追加
  fields.forEach((field) => {
    const row = document.createElement("tr");

    const labelCell = document.createElement("th");
    labelCell.textContent = field.label;
    row.appendChild(labelCell);

    const valueCell = document.createElement("td");
    valueCell.textContent = field.value;

    // F評価の場合は赤く表示
    if (field.label === "評価" && field.value === "F") {
      valueCell.classList.add("grade-f");
    }

    row.appendChild(valueCell);
    table.appendChild(row);
  });

  // モーダル内のアクション領域を作成
  const actionDiv = document.createElement("div");
  actionDiv.className = "course-modal-actions";

  // 編集ボタン
  const editBtn = document.createElement("button");
  editBtn.className = "action-button primary";
  editBtn.textContent = "この科目を編集";
  editBtn.addEventListener("click", () => {
    // 編集処理を開始
    const courseIndex = window.courses.findIndex(
      (c) =>
        c.id === course.id || (c.name === course.name && c.year === course.year)
    );

    if (courseIndex !== -1) {
      window.startEdit(courseIndex, course.id);
      closeCourseModal();
    }
  });
  actionDiv.appendChild(editBtn);

  // 閉じるボタン
  const closeBtn = document.createElement("button");
  closeBtn.className = "action-button";
  closeBtn.textContent = "閉じる";
  closeBtn.addEventListener("click", closeCourseModal);
  actionDiv.appendChild(closeBtn);

  // モーダルにテーブルとアクション領域を追加
  courseModalBody.appendChild(table);
  courseModalBody.appendChild(actionDiv);

  // モーダルを表示
  courseListModal.style.display = "block";
}

/**
 * 科目詳細モーダルを閉じる
 */
function closeCourseModal() {
  courseListModal.style.display = "none";
}

// 閉じるボタンのイベントリスナーを設定
if (courseCloseBtn) {
  courseCloseBtn.addEventListener("click", closeCourseModal);
}

// モーダル外をクリックしたときに閉じる
window.addEventListener("click", (event) => {
  if (event.target === courseListModal) {
    closeCourseModal();
  }
});

// Escキーでモーダルを閉じる
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && courseListModal.style.display === "block") {
    closeCourseModal();
  }
});

// グローバルスコープに公開
window.showCourseModal = showCourseModal;
window.closeCourseModal = closeCourseModal;
