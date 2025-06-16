// 一括追加機能
document.addEventListener("DOMContentLoaded", function () {
  // モーダル関連の要素
  const bulkAddModal = document.getElementById("bulk-add-modal");
  const showBulkAddBtn = document.getElementById("show-bulk-add-btn");
  const closeBtn = document.querySelector(".close");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const executeBulkAddBtn = document.getElementById("execute-bulk-add");

  // 手動入力関連
  const addRowBtn = document.getElementById("add-row-btn");
  const manualCoursesContainer = document.getElementById("manual-courses");

  // モーダルを表示
  showBulkAddBtn.addEventListener("click", function () {
    bulkAddModal.style.display = "block";
  });

  // モーダルを閉じる
  function closeModal() {
    bulkAddModal.style.display = "none";
    // 手動入力欄は1行だけ残す
    const rows = manualCoursesContainer.querySelectorAll(".manual-row");
    if (rows.length > 1) {
      Array.from(rows)
        .slice(1)
        .forEach((row) => row.remove());
    }
    // 1行目のデータをクリア
    const firstRow = manualCoursesContainer.querySelector(".manual-row");
    if (firstRow) {
      firstRow.querySelector(".manual-name").value = "";
      firstRow.querySelector(".manual-credits").value = 2;
      firstRow.querySelector(".manual-grade").value = "";
    }
  }

  closeBtn.addEventListener("click", closeModal);
  closeModalBtn.addEventListener("click", closeModal);

  // ウィンドウ外クリックで閉じる
  window.addEventListener("click", function (event) {
    if (event.target === bulkAddModal) {
      closeModal();
    }
  });

  // 行の追加ボタン
  addRowBtn.addEventListener("click", function () {
    addManualRow();
  });

  // 手動入力の行を追加
  function addManualRow() {
    const row = document.createElement("tr");
    row.className = "manual-row";

    // 現在の年を取得
    const currentYear = new Date().getFullYear();

    row.innerHTML = `
      <td>
        <input type="number" class="manual-year" value="${currentYear}" min="2000" max="2100">
      </td>
      <td>
        <select class="manual-semester">
          <option value="春学期">春学期</option>
          <option value="秋学期">秋学期</option>
        </select>
      </td>
      <td>
        <input type="text" class="manual-name" placeholder="科目名">
      </td>
      <td>
        <input type="number" class="manual-credits" value="2" min="0.5" step="0.5">
      </td>
      <td>
        <select class="manual-grade">
          <option value="">未評価</option>
          <option value="A+">A+</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
          <option value="F">F</option>
        </select>
      </td>
      <td>
        <select class="manual-category">
          <option value="基礎専門科目">基礎専門科目</option>
          <option value="共通専門科目">共通専門科目</option>
          <option value="固有専門科目（必修）">固有専門科目（必修）</option>
          <option value="固有専門科目（選択）">固有専門科目（選択）</option>
          <option value="グローバル・キャリア養成科目">グローバル・キャリア養成科目</option>
          <option value="外国語">外国語</option>
          <option value="教養科目">教養科目</option>
          <option value="未分類">未分類</option>
        </select>
      </td>
      <td>
        <button type="button" class="delete-row-btn">×</button>
      </td>
    `;

    manualCoursesContainer.appendChild(row);

    // 削除ボタンにイベントリスナーを追加
    row.querySelector(".delete-row-btn").addEventListener("click", function () {
      row.remove();
    });

    // 科目名入力時の自動分類機能を追加
    const nameInput = row.querySelector(".manual-name");
    const categorySelect = row.querySelector(".manual-category");

    nameInput.addEventListener("input", function () {
      const subjectName = this.value.trim();
      if (subjectName && typeof window.classifySubject === "function") {
        const suggestedCategory = window.classifySubject(subjectName);
        if (suggestedCategory === "共通専門科目") {
          categorySelect.value = "共通専門科目";
        } else if (suggestedCategory === "固有専門科目（必修）") {
          categorySelect.value = "固有専門科目（必修）";
        } else if (suggestedCategory === "固有専門科目（選択）") {
          categorySelect.value = "固有専門科目（選択）";
        } else if (suggestedCategory === "基礎専門科目") {
          categorySelect.value = "基礎専門科目";
        } else if (suggestedCategory === "グローバル・キャリア養成科目") {
          categorySelect.value = "グローバル・キャリア養成科目";
        }
      }
    });
  }

  // 削除ボタンのイベントリスナーを初期行に追加
  document.querySelectorAll(".delete-row-btn").forEach((btn) => {
    btn.addEventListener("click", function () {
      // 最後の1行は削除しない
      if (document.querySelectorAll(".manual-row").length > 1) {
        this.closest(".manual-row").remove();
      }
    });
  });

  // 初期行にも自動分類機能を追加
  function addAutoClassificationToExistingRows() {
    document.querySelectorAll(".manual-row").forEach((row) => {
      const nameInput = row.querySelector(".manual-name");
      const categorySelect = row.querySelector(".manual-category");

      if (
        nameInput &&
        categorySelect &&
        !nameInput.dataset.hasAutoClassification
      ) {
        nameInput.dataset.hasAutoClassification = "true";
        nameInput.addEventListener("input", function () {
          const subjectName = this.value.trim();
          if (subjectName && typeof window.classifySubject === "function") {
            const suggestedCategory = window.classifySubject(subjectName);
            if (suggestedCategory === "共通専門科目") {
              categorySelect.value = "共通専門科目";
            } else if (suggestedCategory === "固有専門科目（必修）") {
              categorySelect.value = "固有専門科目（必修）";
            } else if (suggestedCategory === "固有専門科目（選択）") {
              categorySelect.value = "固有専門科目（選択）";
            } else if (suggestedCategory === "基礎専門科目") {
              categorySelect.value = "基礎専門科目";
            } else if (suggestedCategory === "グローバル・キャリア養成科目") {
              categorySelect.value = "グローバル・キャリア養成科目";
            }
          }
        });
      }
    });
  }

  // 初期化時に既存行に自動分類機能を追加
  addAutoClassificationToExistingRows();

  // 手動入力から科目データを集める
  function collectManualCourses() {
    const courses = [];
    const manualRows = manualCoursesContainer.querySelectorAll(".manual-row");

    manualRows.forEach((row) => {
      const name = row.querySelector(".manual-name").value.trim();

      // 科目名が入力されていない行はスキップ
      if (!name) return;

      const course = {
        year:
          parseInt(row.querySelector(".manual-year").value) ||
          new Date().getFullYear(),
        semester: row.querySelector(".manual-semester").value,
        name: name,
        credits: parseFloat(row.querySelector(".manual-credits").value) || 2,
        grade: row.querySelector(".manual-grade").value,
        category: row.querySelector(".manual-category").value,
      };

      courses.push(course);
    });

    return courses;
  }

  // 一括追加の実行
  executeBulkAddBtn.addEventListener("click", async function () {
    const courses = collectManualCourses();

    // データがない場合は処理しない
    if (courses.length === 0) {
      showNotification("追加する科目がありません", "error");
      return;
    }

    // ローディング表示
    showLoading();

    try {
      const response = await fetch("/api/add_courses_bulk", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(courses),
      });

      const result = await response.json();

      if (response.ok) {
        showNotification(`${result.count}科目を一括追加しました`, "success");
        closeModal();
        await fetchCourses(); // 科目一覧を更新
      } else {
        showNotification(
          `エラー: ${result.message || "追加に失敗しました"}`,
          "error"
        );
      }
    } catch (error) {
      console.error("一括追加エラー:", error);
      showNotification("サーバーとの通信に失敗しました", "error");
    } finally {
      hideLoading();
    }
  });
});
