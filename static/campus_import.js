/**
 * CAMPUSウェブのHTMLデータをインポートするための機能
 * CAMPUSウェブからコピーした成績表のHTMLを解析し、成績データとして取り込む
 */

document.addEventListener("DOMContentLoaded", function () {
  // DOM要素の取得
  const campusImportBtn = document.getElementById("campus-import-btn");
  const campusImportModal = document.getElementById("campus-import-modal");
  const closeCampusModalBtn = document.getElementById("close-campus-modal-btn");
  const closeBtns = document.querySelectorAll(".campus-close");
  const campusHtmlInput = document.getElementById("campus-html-input");
  const parseCampusBtn = document.getElementById("parse-campus-btn");
  const executeCampusImportBtn = document.getElementById(
    "execute-campus-import"
  );
  const campusImportPreview = document.getElementById("campus-import-preview");
  const campusCoursesTable = document.getElementById("campus-courses");
  const campusImportCount = document.getElementById("campus-import-count");
  const campusImportMessage = document.getElementById("campus-import-message");
  const includeUnknownYearCheckbox = document.getElementById(
    "include-unknown-year"
  );

  // 解析されたコース情報を保存する変数
  let parsedCourses = [];
  let allParsedCourses = []; // フィルタ前の全データを保持

  // モーダル表示ボタンのイベントリスナー
  campusImportBtn.addEventListener("click", showCampusModal);

  // モーダルを閉じるボタンのイベントリスナー
  closeCampusModalBtn.addEventListener("click", closeCampusModal);
  closeBtns.forEach((btn) => {
    btn.addEventListener("click", closeCampusModal);
  });

  // 年度不明科目チェックボックスの変更を監視
  includeUnknownYearCheckbox.addEventListener("change", function () {
    if (allParsedCourses.length > 0) {
      // 既に解析済みデータがある場合は再フィルタリング
      filterAndUpdatePreview();
    }
  });

  // ヘルプ表示機能は削除しました

  // モーダル外クリックで閉じる
  window.addEventListener("click", function (event) {
    if (event.target === campusImportModal) {
      closeCampusModal();
    }
  });

  // 解析ボタンのイベントリスナー
  parseCampusBtn.addEventListener("click", parseCampusHtml);

  // インポート実行ボタンのイベントリスナー
  executeCampusImportBtn.addEventListener("click", executeImport);

  /**
   * CAMPUSウェブインポートモーダルを表示
   */
  function showCampusModal() {
    // モーダル表示時の初期化
    campusHtmlInput.value = "";
    campusImportPreview.style.display = "none";
    executeCampusImportBtn.style.display = "none";
    campusImportMessage.innerHTML = "";
    campusImportMessage.className = "import-message";

    // 解析済みデータをクリア
    allParsedCourses = [];
    parsedCourses = [];

    // モーダル表示
    campusImportModal.style.display = "block";
  }

  /**
   * CAMPUSウェブインポートモーダルを閉じる
   */
  function closeCampusModal() {
    campusImportModal.style.display = "none";
  }

  /**
   * CAMPUSウェブからのHTMLを解析する
   */
  function parseCampusHtml() {
    // 入力されたHTMLの取得
    const htmlContent = campusHtmlInput.value.trim();

    if (!htmlContent) {
      showMessage(
        "HTMLが入力されていません。CAMPUSウェブの成績表をコピー＆ペーストしてください。",
        "error"
      );
      return;
    }

    // ローディング表示
    showLoading();

    // 年度不明科目を含めるかどうかの設定
    const includeUnknownYear = includeUnknownYearCheckbox.checked;

    // サーバーに解析リクエストを送信（全データを取得）
    fetch("/api/parse_campus_html", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        html: htmlContent,
        include_unknown_year: true, // 常に全データを取得
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        hideLoading();

        if (data.status === "success") {
          // 成功した場合の処理
          allParsedCourses = data.courses; // 全データを保存
          filterAndUpdatePreview(); // フィルタリングしてプレビュー更新

          showMessage(data.message, "success");
        } else if (data.status === "warning") {
          // 警告の場合
          showMessage(data.message, "warning");
        } else {
          // エラーの場合
          showMessage(data.message, "error");
        }
      })
      .catch((error) => {
        hideLoading();
        showMessage("エラーが発生しました: " + error.message, "error");
      });
  }

  /**
   * 年度が不明かどうかを判定するヘルパー関数
   * @param {any} year - 年度の値
   * @returns {boolean} 年度が不明な場合はtrue
   */
  function isUnknownYear(year) {
    if (
      !year ||
      year === "" ||
      year === "-" ||
      year === "不明" ||
      year === null ||
      year === undefined
    ) {
      return true;
    }

    const yearNum = parseInt(year, 10);
    if (isNaN(yearNum) || yearNum < 1990 || yearNum > 2030) {
      return true;
    }

    return false;
  }

  /**
   * 解析された科目データをプレビューに表示
   * @param {Array} courses - 解析された科目データの配列
   */
  function renderCampusPreview(courses) {
    campusCoursesTable.innerHTML = ""; // テーブルをクリア

    courses.forEach((course) => {
      const row = document.createElement("tr");

      // 年度が不明な場合の視覚的な識別
      const unknownYear = isUnknownYear(course.year);

      if (unknownYear) {
        row.classList.add("unknown-year-row");
      }

      // 各列のデータを追加
      // 年度
      const yearCell = document.createElement("td");
      yearCell.textContent = course.year || "履修予定";
      if (unknownYear) {
        yearCell.style.color = "#ff6f00";
        yearCell.style.fontStyle = "italic";
      }
      row.appendChild(yearCell);

      // 学期
      const semesterCell = document.createElement("td");
      semesterCell.textContent = course.semester || "-";
      row.appendChild(semesterCell);

      // 科目名
      const nameCell = document.createElement("td");
      nameCell.textContent = course.name || "-";
      row.appendChild(nameCell);

      // 単位数
      const creditsCell = document.createElement("td");
      creditsCell.textContent = course.credits || "-";
      row.appendChild(creditsCell);

      // 評価
      const gradeCell = document.createElement("td");
      gradeCell.textContent = course.grade || "-";
      row.appendChild(gradeCell);

      // カテゴリ
      const categoryCell = document.createElement("td");
      categoryCell.textContent = course.category || "未分類";
      row.appendChild(categoryCell);

      campusCoursesTable.appendChild(row);
    });
  }

  /**
   * インポートを実行する
   */
  function executeImport() {
    if (!parsedCourses || parsedCourses.length === 0) {
      showMessage("インポート可能な科目がありません", "warning");
      return;
    }

    // ローディング表示
    showLoading();

    // すでに登録済みの科目と重複している可能性があることを考慮して一括追加APIを使用
    fetch("/api/add_courses_bulk", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(parsedCourses),
    })
      .then((response) => response.json())
      .then((data) => {
        hideLoading();

        if (data.status === "ok") {
          showMessage(
            `${data.count}件の科目を正常にインポートしました！`,
            "success"
          );

          // コースリストを更新（親スクリプトの関数を呼び出し）
          if (typeof fetchCourses === "function") {
            fetchCourses();
          }

          // 3秒後にモーダルを閉じる
          setTimeout(() => {
            closeCampusModal();
          }, 3000);
        } else {
          showMessage(
            "インポート中にエラーが発生しました: " + data.message,
            "error"
          );
        }
      })
      .catch((error) => {
        hideLoading();
        showMessage("エラーが発生しました: " + error.message, "error");
      });
  }

  /**
   * メッセージを表示
   * @param {string} message - 表示するメッセージ
   * @param {string} type - メッセージの種類 (success/warning/error)
   */
  function showMessage(message, type) {
    campusImportMessage.textContent = message;
    campusImportMessage.className = `import-message ${type}`;
  }

  /**
   * ローディング表示の外部関数を呼び出す
   * script.jsで定義されている関数を利用
   */
  function showLoading() {
    if (typeof window.showLoading === "function") {
      window.showLoading();
    }
  }

  /**
   * 年度不明科目のフィルタリングを適用してプレビューを更新
   */
  function filterAndUpdatePreview() {
    const includeUnknownYear = includeUnknownYearCheckbox.checked;

    if (includeUnknownYear) {
      // 年度不明科目も含める場合
      parsedCourses = [...allParsedCourses]; // 配列のコピーを作成
    } else {
      // 年度不明科目を除外する場合
      parsedCourses = allParsedCourses.filter((course) => {
        const isUnknown = isUnknownYear(course.year);
        return !isUnknown;
      });
    }

    campusImportCount.textContent = parsedCourses.length;

    // プレビューを表示
    renderCampusPreview(parsedCourses);
    campusImportPreview.style.display = "block";
    executeCampusImportBtn.style.display = "inline-block";
  }

  /**
   * ローディング非表示の外部関数を呼び出す
   * script.jsで定義されている関数を利用
   */
  function hideLoading() {
    if (typeof window.hideLoading === "function") {
      window.hideLoading();
    }
  }
});
