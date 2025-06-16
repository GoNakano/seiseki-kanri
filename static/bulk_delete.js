// 一括削除機能のための処理
document.addEventListener("DOMContentLoaded", function () {
  // DOM要素の取得
  const selectAllBtn = document.getElementById("select-all-btn");
  const deselectAllBtn = document.getElementById("deselect-all-btn");
  const deleteSelectedBtn = document.getElementById("delete-selected-btn");
  const selectAllCheckbox = document.getElementById("select-all-checkbox");

  // 選択された科目IDを保持する配列
  window.selectedCourseIds = [];

  // ヘッダーのチェックボックスの変更イベント
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", function () {
      const checked = this.checked;
      const checkboxes = document.querySelectorAll(".course-checkbox");

      checkboxes.forEach((checkbox) => {
        checkbox.checked = checked;
        const courseId = checkbox.dataset.id;
        const row = checkbox.closest("tr");

        if (checked) {
          if (!window.selectedCourseIds.includes(courseId)) {
            window.selectedCourseIds.push(courseId);
            row.classList.add("selected-for-delete");
          }
        } else {
          window.selectedCourseIds = window.selectedCourseIds.filter(
            (id) => id !== courseId
          );
          row.classList.remove("selected-for-delete");
        }
      });

      updateDeleteButtonState();
    });
  }

  // 全選択ボタンのクリックイベント
  if (selectAllBtn) {
    selectAllBtn.addEventListener("click", function () {
      if (selectAllCheckbox) selectAllCheckbox.checked = true;
      const checkboxes = document.querySelectorAll(".course-checkbox");

      checkboxes.forEach((checkbox) => {
        checkbox.checked = true;
        const courseId = checkbox.dataset.id;
        if (!window.selectedCourseIds.includes(courseId)) {
          window.selectedCourseIds.push(courseId);
          checkbox.closest("tr").classList.add("selected-for-delete");
        }
      });

      updateDeleteButtonState();
    });
  }

  // 全選択解除ボタンのクリックイベント
  if (deselectAllBtn) {
    deselectAllBtn.addEventListener("click", function () {
      if (selectAllCheckbox) selectAllCheckbox.checked = false;
      const checkboxes = document.querySelectorAll(".course-checkbox");

      checkboxes.forEach((checkbox) => {
        checkbox.checked = false;
        const courseId = checkbox.dataset.id;
        window.selectedCourseIds = window.selectedCourseIds.filter(
          (id) => id !== courseId
        );
        checkbox.closest("tr").classList.remove("selected-for-delete");
      });

      updateDeleteButtonState();
    });
  }

  // 選択削除ボタンのクリックイベント
  if (deleteSelectedBtn) {
    deleteSelectedBtn.addEventListener("click", async function () {
      if (window.selectedCourseIds.length === 0) return;

      if (
        !confirm(
          `選択した${window.selectedCourseIds.length}件の科目を削除しますか？`
        )
      ) {
        return;
      }

      try {
        const response = await fetch("/api/delete_courses_bulk", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ ids: window.selectedCourseIds }),
        });

        if (!response.ok) {
          throw new Error("一括削除に失敗しました");
        }

        const data = await response.json();

        // 削除成功後の処理
        window.selectedCourseIds = [];
        if (selectAllCheckbox) selectAllCheckbox.checked = false;

        // 科目リストを再読み込み
        if (typeof fetchCourses === "function") {
          fetchCourses();
        }

        // 通知表示
        if (typeof showNotification === "function") {
          showNotification(
            data.message || `${data.count}件の科目を削除しました`,
            "success"
          );
        } else {
          alert(data.message || `${data.count}件の科目を削除しました`);
        }
      } catch (error) {
        console.error("削除エラー:", error);
        if (typeof showNotification === "function") {
          showNotification("一括削除に失敗しました", "error");
        } else {
          alert("一括削除に失敗しました");
        }
      }
    });
  }

  // 一括削除ボタンの状態を更新する関数
  function updateDeleteButtonState() {
    if (deleteSelectedBtn) {
      if (window.selectedCourseIds.length > 0) {
        deleteSelectedBtn.disabled = false;
        deleteSelectedBtn.textContent = `選択した${window.selectedCourseIds.length}件を削除`;
      } else {
        deleteSelectedBtn.disabled = true;
        deleteSelectedBtn.textContent = "選択項目を削除";
      }
    }
  }

  // renderCourseList関数の後に処理を追加するために、MutationObserverを使用
  const courseListObserver = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (
        mutation.type === "childList" &&
        mutation.target.id === "course-list"
      ) {
        // チェックボックスのイベントリスナーを追加
        document.querySelectorAll(".course-checkbox").forEach((checkbox) => {
          // イベントリスナーが既に追加されていないことを確認
          if (!checkbox.dataset.hasListener) {
            checkbox.dataset.hasListener = "true";
            checkbox.addEventListener("change", function () {
              const courseId = this.dataset.id;
              const row = this.closest("tr");

              if (this.checked) {
                if (!window.selectedCourseIds.includes(courseId)) {
                  window.selectedCourseIds.push(courseId);
                  row.classList.add("selected-for-delete");
                }
              } else {
                window.selectedCourseIds = window.selectedCourseIds.filter(
                  (id) => id !== courseId
                );
                row.classList.remove("selected-for-delete");
                if (selectAllCheckbox) selectAllCheckbox.checked = false;
              }

              updateDeleteButtonState();
            });
          }
        });

        // 削除ボタンの状態を更新
        updateDeleteButtonState();
      }
    });
  });

  const courseListElement = document.getElementById("course-list");
  if (courseListElement) {
    courseListObserver.observe(courseListElement, {
      childList: true,
      subtree: true,
    });
  }
});
