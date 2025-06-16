// --- DOM要素の取得 ---
const form = document.getElementById("add-course-form");
const courseNameInput = document.getElementById("course-name");
const courseCreditsInput = document.getElementById("course-credits");
const courseGradeInput = document.getElementById("course-grade");
const courseYearInput = document.getElementById("course-year");
const courseSemesterInput = document.getElementById("course-semester");
const courseCategoryInput = document.getElementById("course-category");
const courseMemoInput = document.getElementById("course-memo");
const courseListBody = document.getElementById("course-list");
const gpaDisplay = document.getElementById("gpa-display");
const totalCreditsDisplay = document.getElementById("total-credits-display");
const submitButton = form.querySelector('button[type="submit"]'); // 追加/更新ボタン
const cancelEditBtn = document.getElementById("cancel-edit-btn"); // キャンセルボタン

// フィルターとソート用のDOM要素
const filterNameInput = document.getElementById("filter-name"); // 追加: 科目名フィルター
const filterYearSelect = document.getElementById("filter-year");
const filterSemesterSelect = document.getElementById("filter-semester");
const filterCategorySelect = document.getElementById("filter-category"); // 追加：カテゴリフィルター
const sortGradeBtn = document.getElementById("sort-grade");
const sortCreditsBtn = document.getElementById("sort-credits");
const sortYearBtn = document.getElementById("sort-year");

// グラフ用のDOM要素
const gpaTrendChartCtx = document.getElementById("gpa-trend-chart");
const gradeDistributionChartCtx = document.getElementById(
  "grade-distribution-chart"
);

// --- データ関連 ---
let courses = [];
let editingIndex = -1;

// GPA計算のための評価ポイント
const gradePoints = {
  "A+": 5,
  A: 4,
  B: 3,
  C: 2,
  F: 0,
};

// GPS（Grade Point Sum）は評価点数×単位数の合計
function calculateGPS() {
  let gps = 0;

  courses.forEach((course) => {
    if (
      gradePoints.hasOwnProperty(course.grade) &&
      !isNaN(parseFloat(course.credits))
    ) {
      const credits = parseFloat(course.credits);
      gps += gradePoints[course.grade] * credits;
    }
  });

  return gps;
}

// 現在のソート状態を保持
let currentSort = {
  field: null,
  ascending: true,
};

// 現在のフィルター状態を保持
let currentFilter = {
  name: "", // 追加: 科目名フィルター
  year: "",
  semester: "",
  category: "", // 追加：カテゴリフィルター
};

// グラフインスタンス
let gpaTrendChart = null;
let gradeDistributionChart = null;

// 評価の色設定
const gradeColors = {
  "A+": "#4CAF50",
  A: "#8BC34A",
  B: "#FFC107",
  C: "#FF9800",
  F: "#F44336",
};

// --- API関連の関数 ---
async function fetchCourses() {
  showLoading(); // ローディング表示
  try {
    const response = await fetch("/api/get_courses");
    if (!response.ok) throw new Error("データの取得に失敗しました");
    courses = await response.json();
    window.courses = courses; // グローバルスコープに公開

    // ページネーションを初期化
    if (window.initPagination) {
      window.initPagination();
    }

    renderCourseList();
    updateYearOptions();
    calculateAndDisplayGPA();
    calculateAndDisplayTotalCredits(); // この中でcalculateAndDisplayGradeDistributionも呼ばれる
    calculateCategoryCredits(); // カテゴリ別単位集計を追加
    updateGpaTrendChart();
    updateGradeDistributionChart();
    updateHeaderStats(); // ヘッダー統計情報を更新
  } catch (error) {
    console.error("Error:", error);
    showNotification("データの取得に失敗しました", "error");
  } finally {
    hideLoading(); // ローディング非表示
  }
}

async function addCourse(course) {
  try {
    const response = await fetch("/api/add_course", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(course),
    });
    if (!response.ok) throw new Error("データの追加に失敗しました");
    await fetchCourses(); // データを再取得
    showNotification(`「${course.name}」を追加しました`, "success");
  } catch (error) {
    console.error("Error:", error);
    showNotification("データの追加に失敗しました", "error");
  }
}

async function updateCourse(index, course) {
  try {
    const response = await fetch("/api/update_course", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ index, course }),
    });

    if (!response.ok) throw new Error("更新に失敗しました");
    await fetchCourses(); // 再取得して画面更新
    showNotification(`「${course.name}」を更新しました`, "success");
  } catch (error) {
    console.error("更新エラー:", error);
    showNotification("更新に失敗しました", "error");
  }
}

// --- 関数定義 ---

// 年度の選択肢を動的に生成する関数
function updateYearOptions() {
  // 年度を数値型に変換してから扱う
  const years = new Set(
    courses
      .map((course) => (course.year ? Number(course.year) : null))
      .filter((year) => year) // nullや0, NaNをフィルタリング
  );
  const options = Array.from(years).sort((a, b) => b - a); // 降順ソート

  filterYearSelect.innerHTML = '<option value="">すべて</option>';

  // 年度不明科目があるかチェック（F評価・不可評価は除く）
  const hasUnknownYear = courses.some(
    (course) =>
      (!course.year || course.year === "" || course.year === null) &&
      course.grade !== "F" &&
      course.grade !== "不可"
  );
  if (hasUnknownYear) {
    const unknownOption = document.createElement("option");
    unknownOption.value = "未修得";
    unknownOption.textContent = "年度不明（履修予定科目）";
    filterYearSelect.appendChild(unknownOption);
  }

  options.forEach((year) => {
    const option = document.createElement("option");
    option.value = year; // 数値のまま設定
    option.textContent = year;
    filterYearSelect.appendChild(option);
  });
}

// フィルターとソートを適用した科目リストを返す関数
function getFilteredAndSortedCourses() {
  let filteredCourses = [...courses];

  // フィルター適用
  // 科目名による絞り込み
  if (currentFilter.name && currentFilter.name.trim() !== "") {
    const searchTerm = currentFilter.name.trim().toLowerCase();
    filteredCourses = filteredCourses.filter((course) => {
      // 科目名が検索ワードを含むものを表示
      return course.name && course.name.toLowerCase().includes(searchTerm);
    });
  }

  if (currentFilter.year) {
    if (currentFilter.year === "未修得") {
      // 年度不明（履修予定科目）の科目をフィルタリング（F評価・不可評価は除く）
      filteredCourses = filteredCourses.filter((course) => {
        return (
          (!course.year || course.year === "" || course.year === null) &&
          course.grade !== "F" &&
          course.grade !== "不可"
        );
      });
    } else {
      // 年度を数値として比較（stringとnumberの比較を避ける）
      const filterYear = Number(currentFilter.year);
      filteredCourses = filteredCourses.filter((course) => {
        // courseのyearが文字列の場合もあるので数値に変換して比較
        const courseYear = Number(course.year);
        return courseYear === filterYear;
      });
    }
  }
  if (currentFilter.semester) {
    filteredCourses = filteredCourses.filter(
      (course) => course.semester === currentFilter.semester
    );
  }

  // カテゴリによるフィルタリングを追加
  if (currentFilter.category) {
    filteredCourses = filteredCourses.filter(
      (course) => course.category === currentFilter.category
    );
  }

  // ソート適用
  if (currentSort.field) {
    filteredCourses.sort((a, b) => {
      let valueA = a[currentSort.field];
      let valueB = b[currentSort.field];

      // 評価の場合はポイントに変換
      if (currentSort.field === "grade") {
        valueA = gradePoints[valueA] || 0;
        valueB = gradePoints[valueB] || 0;
      }

      // 数値の場合は数値として比較
      if (typeof valueA === "number" && typeof valueB === "number") {
        return currentSort.ascending ? valueA - valueB : valueB - valueA;
      }

      // 文字列の場合は文字列として比較
      return currentSort.ascending
        ? String(valueA).localeCompare(String(valueB))
        : String(valueB).localeCompare(String(valueA));
    });
  }

  return filteredCourses;
}

// GPAを計算して表示する関数
function calculateAndDisplayGPA() {
  let totalPoints = 0;
  let totalCredits = 0;

  courses.forEach((course) => {
    // gradePointsに存在する評価かつ、数値の単位数のみ計算対象
    // 評価Fも含めてGPA計算を行う
    if (
      gradePoints.hasOwnProperty(course.grade) &&
      !isNaN(parseFloat(course.credits))
    ) {
      const credits = parseFloat(course.credits);
      totalPoints += gradePoints[course.grade] * credits;

      // GPA計算には落単（F評価）も含める（分母にも入れる）
      totalCredits += credits;
    }
  });

  // GPA計算 (0除算を防ぐ)
  const gpa = totalCredits === 0 ? 0 : totalPoints / totalCredits;

  // 小数点第2位まで表示 (toFixedは文字列を返すので最後に+)
  gpaDisplay.textContent = gpa.toFixed(2);

  // GPS計算と表示
  const gps = calculateGPS();
  const gpsDisplay = document.getElementById("gps-display");
  if (gpsDisplay) {
    gpsDisplay.textContent = gps.toFixed(1);
  }

  // ヘッダー統計の更新
  updateHeaderStats();
}

function calculateAndDisplayTotalCredits() {
  const requiredCredits = 124; // 必要な単位数（大学によって変更OK）
  let totalCredits = 0;

  courses.forEach((course, index) => {
    // 評価F、不可、年度不明は取得単位に含めない
    if (
      course.grade === "F" ||
      course.grade === "不可" ||
      !course.year ||
      course.year === ""
    ) {
      return;
    }

    const raw = course.credits;
    const c = parseFloat(raw);
    if (!isNaN(c)) {
      totalCredits += c;
    } else {
      console.warn(`⚠️ 無効な単位数データ: index=${index}, credits=${raw}`);
    }
  });

  const statusEl = document.getElementById("credit-status");
  if (!statusEl) {
    console.warn("⚠️ credit-status 要素が見つかりません");
    return;
  }

  const remaining = requiredCredits - totalCredits;

  if (remaining <= 0) {
    statusEl.innerHTML = `🎉 卒業条件を達成しています！（合計 ${totalCredits} 単位）<br><small>※ F評価・不可評価・年度不明の科目は単位として認定されませんが、GPAにはグレードポイント0として計算されます（年度不明は除く）</small>`;
    statusEl.style.color = "green";
  } else {
    statusEl.innerHTML = `📚 合計 ${totalCredits} 単位（あと ${remaining.toFixed(
      1
    )} 単位で卒業条件に到達）<br><small>※ F評価・不可評価・年度不明の科目は単位として認定されませんが、GPAにはグレードポイント0として計算されます（年度不明は除く）</small>`;
    statusEl.style.color = "red";
  }

  // 評価別単位数集計も表示を更新
  calculateAndDisplayGradeDistribution();
}

// ★追加: 編集モードを開始する関数
function startEdit(index, id) {
  const courseToEdit = courses[index];
  // フォームに選択された科目の情報をセット
  courseNameInput.value = courseToEdit.name;
  courseCreditsInput.value = courseToEdit.credits;
  courseGradeInput.value = courseToEdit.grade;
  courseYearInput.value = courseToEdit.year;
  courseSemesterInput.value = courseToEdit.semester;
  courseCategoryInput.value = courseToEdit.category || "未分類";
  courseMemoInput.value = courseToEdit.memo || "";

  // 編集モード状態にする
  editingIndex = id || index; // IDがあればそれを使用、なければindexを使用
  submitButton.textContent = "更新"; // ボタンのテキストを変更
  cancelEditBtn.style.display = "inline-block"; // キャンセルボタンを表示
  courseNameInput.focus(); // 科目名入力欄にフォーカスを移動（任意）
}

// ★追加: フォームと編集モードをリセットする関数
function resetFormAndMode() {
  form.reset(); // フォームの入力内容をクリア
  editingIndex = -1; // 編集モードを解除
  submitButton.textContent = "追加"; // ボタンのテキストを元に戻す
  cancelEditBtn.style.display = "none"; // キャンセルボタンを非表示
}

// 科目を削除する関数
async function deleteCourse(id, index) {
  const courseName = courses[index] ? courses[index].name : "この科目";
  if (!confirm(`「${courseName}」を削除しますか？`)) {
    return;
  }

  try {
    const response = await fetch("/api/delete_course", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ index: id }), // idをindexとして送信
    });

    if (!response.ok) {
      throw new Error("削除に失敗しました");
    }

    await fetchCourses(); // サーバーから再取得して表示更新！
    showNotification(`「${courseName}」を削除しました`, "info");

    if (index === editingIndex) {
      resetFormAndMode(); // 編集モードをリセット
    }
  } catch (error) {
    console.error("削除エラー:", error);
    showNotification("削除に失敗しました", "error");
  }
}

// データをローカルストレージに保存する関数
function saveCourses() {
  localStorage.setItem("courses", JSON.stringify(courses));
  updateYearOptions();
}

// GPA推移グラフを更新する関数
function updateGpaTrendChart() {
  // 年度ごとのGPAを計算
  const gpaByYear = {};
  courses.forEach((course) => {
    if (!course.year || !course.grade || !course.credits) return;

    // 評価Fも含めてGPA計算を行う
    const year = course.year;
    if (!gpaByYear[year]) {
      gpaByYear[year] = {
        totalPoints: 0,
        totalCredits: 0,
      };
    }

    const points = gradePoints[course.grade] || 0;
    const credits = parseFloat(course.credits);
    gpaByYear[year].totalPoints += points * credits;

    // GPA計算には落単（F評価）も含める（分母にも入れる）
    gpaByYear[year].totalCredits += credits;
  });

  // データを整形
  const years = Object.keys(gpaByYear).sort();
  const gpaData = years.map((year) => {
    const data = gpaByYear[year];
    return data.totalCredits === 0 ? 0 : data.totalPoints / data.totalCredits;
  });

  // グラフを更新または作成
  if (gpaTrendChart) {
    gpaTrendChart.data.labels = years;
    gpaTrendChart.data.datasets[0].data = gpaData;
    gpaTrendChart.update();
  } else {
    gpaTrendChart = new Chart(gpaTrendChartCtx, {
      type: "bar",
      data: {
        labels: years,
        datasets: [
          {
            label: "GPA",
            data: gpaData,
            backgroundColor: "#2196F3",
            borderColor: "#1976D2",
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: 5,
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 5,
            ticks: {
              font: {
                size: 10,
              },
              callback: function (value) {
                return value.toFixed(1);
              },
            },
            grid: {
              color: "rgba(0, 0, 0, 0.05)",
            },
          },
          x: {
            ticks: {
              font: {
                size: 10,
              },
            },
            grid: {
              display: false,
            },
          },
        },
        plugins: {
          legend: {
            position: "top",
            labels: {
              boxWidth: 12,
              font: {
                size: 12,
              },
            },
          },
          title: {
            display: false,
          },
        },
      },
    });
  }
}

// 評価分布グラフを更新する関数
function updateGradeDistributionChart() {
  // 評価ごとの科目数を集計
  const gradeCount = {
    "A+": 0,
    A: 0,
    B: 0,
    C: 0,
    F: 0,
  };

  courses.forEach((course) => {
    if (course.grade && gradeCount.hasOwnProperty(course.grade)) {
      gradeCount[course.grade]++;
    }
  });

  // データを整形
  const labels = Object.keys(gradeCount);
  const data = Object.values(gradeCount);
  const backgroundColors = labels.map((grade) => gradeColors[grade]);

  // グラフを更新または作成
  if (gradeDistributionChart) {
    gradeDistributionChart.data.labels = labels;
    gradeDistributionChart.data.datasets[0].data = data;
    gradeDistributionChart.data.datasets[0].backgroundColor = backgroundColors;
    gradeDistributionChart.update();
  } else {
    gradeDistributionChart = new Chart(gradeDistributionChartCtx, {
      type: "pie",
      data: {
        labels: labels,
        datasets: [
          {
            data: data,
            backgroundColor: backgroundColors,
            borderWidth: 2,
            borderColor: "#fff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
          padding: 10,
        },
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              font: {
                size: 12,
              },
              padding: 8,
              boxWidth: 15,
            },
          },
          tooltip: {
            bodyFont: {
              size: 12,
            },
            titleFont: {
              size: 12,
            },
            callbacks: {
              label: function (context) {
                const label = context.label || "";
                const value = context.raw || 0;
                const total = context.chart.data.datasets[0].data.reduce(
                  (a, b) => a + b,
                  0
                );
                const percentage = Math.round((value / total) * 100);
                return `${label}: ${value}科目 (${percentage}%)`;
              },
            },
          },
        },
      },
    });
  }
}

/**
 * 科目リストを画面に描画する関数
 */
function renderCourseList() {
  courseListBody.innerHTML = ""; // 一旦リストを空にする
  const filteredCourses = getFilteredAndSortedCourses();

  // ページネーション状態を更新
  if (window.paginationState) {
    window.paginationState.totalItems = filteredCourses.length;
  }

  // 科目が1件もない場合、空状態のメッセージを表示
  const emptyStateDiv = document.getElementById("empty-course-message");
  const tableEmptyMessage = document.getElementById("table-empty-message");

  if (courses.length === 0) {
    // ユーザーがまだ1件も科目を登録していない場合
    if (emptyStateDiv) emptyStateDiv.style.display = "block";
    if (tableEmptyMessage) tableEmptyMessage.style.display = "none";
  } else if (filteredCourses.length === 0) {
    // フィルターの結果、表示する科目がない場合
    if (emptyStateDiv) emptyStateDiv.style.display = "none";
    if (tableEmptyMessage) tableEmptyMessage.style.display = "block";

    // データがない場合のメッセージを表示
    const emptyRow = document.createElement("tr");
    const emptyCell = document.createElement("td");
    emptyCell.colSpan = 9; // チェックボックス列も含めた列数
    emptyCell.className = "empty-table-message";
    emptyCell.textContent =
      "表示する科目データがありません。新しい科目を追加するか、フィルター条件を変更してください。";
    emptyRow.appendChild(emptyCell);
    courseListBody.appendChild(emptyRow);
  } else {
    // 科目がある場合は空状態のメッセージを非表示
    if (emptyStateDiv) emptyStateDiv.style.display = "none";
    if (tableEmptyMessage) tableEmptyMessage.style.display = "none";
  }

  // ページネーションの状態を更新
  if (window.updatePaginationControls) {
    window.updatePaginationControls();
  }

  // ページネーションに基づいて表示するコースを取得
  const coursesToDisplay = window.getPaginatedCourses
    ? window.getPaginatedCourses(filteredCourses)
    : filteredCourses;

  coursesToDisplay.forEach((course, index) => {
    // ページネーションを考慮したインデックスを計算
    const actualIndex = filteredCourses.indexOf(course);

    const tr = document.createElement("tr"); // テーブル行(<tr>)を作成
    // データベースIDを属性として保存（削除や編集用）
    if (course.id) {
      tr.dataset.id = course.id;
    }

    // F評価と未修得科目の視覚的区別
    const isFailedGrade = course.grade === "F" || course.grade === "不可";
    const isPending = (!course.year || course.year === "") && !isFailedGrade;

    if (isFailedGrade) {
      tr.classList.add("course-row", "failed-grade");
    } else if (isPending) {
      tr.classList.add("course-row", "pending-course");
    } else {
      tr.classList.add("course-row");
    }

    // チェックボックス列を追加
    const tdCheckbox = document.createElement("td");
    tdCheckbox.className = "checkbox-column";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "course-checkbox";
    checkbox.dataset.id = course.id || actualIndex;
    tdCheckbox.appendChild(checkbox);
    tr.appendChild(tdCheckbox);

    // 年度セル
    const tdYear = document.createElement("td");
    tdYear.textContent = course.year || "-"; // データがない場合は'-'を表示
    tr.appendChild(tdYear);

    // ★追加: 学期セル
    const tdSemester = document.createElement("td");
    tdSemester.textContent = course.semester || "-"; // データがない場合は'-'を表示
    tr.appendChild(tdSemester);

    // 科目名、単位数、評価のセル(<td>)を作成
    const tdName = document.createElement("td");
    tdName.textContent = course.name;
    tr.appendChild(tdName);

    const tdCredits = document.createElement("td");
    tdCredits.textContent = course.credits;
    tr.appendChild(tdCredits);

    const tdGrade = document.createElement("td");
    tdGrade.textContent = course.grade;
    // F評価と未修得の評価セルスタイリング
    if (isFailedGrade) {
      tdGrade.classList.add("grade-f");
    } else if (isPending) {
      tdGrade.classList.add("grade-pending");
    }
    tr.appendChild(tdGrade);

    // カテゴリセル
    const tdCategory = document.createElement("td");
    tdCategory.textContent = course.category || "未分類";
    tr.appendChild(tdCategory);

    // メモセル
    const tdMemo = document.createElement("td");
    tdMemo.textContent = course.memo || "-";
    tr.appendChild(tdMemo);

    // 操作セル (★変更: 編集ボタンを追加)
    const tdAction = document.createElement("td");

    // 編集ボタンを作成
    const editBtn = document.createElement("button");
    editBtn.textContent = "編集";
    editBtn.classList.add("edit-btn");
    editBtn.onclick = (e) => {
      e.stopPropagation(); // イベントの伝播を停止
      // 編集時にもIDを渡す
      startEdit(actualIndex, course.id); // ★編集開始関数を呼び出す
    };
    tdAction.appendChild(editBtn);

    // 削除ボタンを作成 (変更あり: IDを使用)
    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "削除";
    deleteBtn.classList.add("delete-btn");
    deleteBtn.onclick = (e) => {
      e.stopPropagation(); // イベントの伝播を停止
      const courseId = course.id || actualIndex; // IDがあればそれを使用、なければindexを使用
      deleteCourse(courseId, actualIndex);
    };
    tdAction.appendChild(deleteBtn);

    tr.appendChild(tdAction);

    // モーダル表示用のクリックイベントを追加
    tr.addEventListener("click", () => {
      const courseToShow = { ...course };
      if (window.showCourseModal) {
        window.showCourseModal(courseToShow);
      }
    });

    courseListBody.appendChild(tr); // 作成した行をテーブルに追加
  });

  // ページネーションコントロールを更新
  if (window.updatePaginationControls) {
    window.updatePaginationControls();
  }

  // グラフを更新
  updateGpaTrendChart();
  updateGradeDistributionChart();
  calculateAndDisplayTotalCredits();
  updateHeaderStats(); // ヘッダー統計情報を更新
}

// ヘッダー部分の統計情報を更新
function updateHeaderStats() {
  // GPA更新
  const headerGpaEl = document.getElementById("header-gpa");
  if (headerGpaEl && gpaDisplay) {
    headerGpaEl.textContent = gpaDisplay.textContent;
  }

  // GPS更新
  const headerGpsEl = document.getElementById("header-gps");
  if (headerGpsEl) {
    const gps = calculateGPS();
    headerGpsEl.textContent = gps.toFixed(1);
  }

  // 総取得単位数更新
  const headerCreditsEl = document.getElementById("header-credits");
  if (headerCreditsEl) {
    let totalCredits = 0;
    courses.forEach((course) => {
      if (
        course.grade !== "F" &&
        course.grade !== "不可" &&
        course.year &&
        course.year !== "" &&
        !isNaN(parseFloat(course.credits))
      ) {
        totalCredits += parseFloat(course.credits);
      }
    });
    headerCreditsEl.textContent = totalCredits.toString();
  }

  // 卒業までの残り単位更新
  const headerRemainingEl = document.getElementById("header-remaining");
  if (headerRemainingEl) {
    const requiredCredits = 124; // デフォルト値、後でユーザー設定から取得可能
    let totalCredits = 0;
    courses.forEach((course) => {
      if (course.grade !== "F" && !isNaN(parseFloat(course.credits))) {
        totalCredits += parseFloat(course.credits);
      }
    });
    const remaining = Math.max(0, requiredCredits - totalCredits);
    headerRemainingEl.textContent = remaining.toString();
  }

  // 登録科目数更新
  const headerCoursesEl = document.getElementById("header-courses");
  if (headerCoursesEl) {
    headerCoursesEl.textContent = courses.length.toString();
  }
}

// --- イベントリスナー ---

// 科目名入力時の自動分類機能
courseNameInput.addEventListener("input", () => {
  const subjectName = courseNameInput.value.trim();
  if (subjectName && typeof window.autoSetCategory === "function") {
    window.autoSetCategory(subjectName);
  }
});

// フォームが送信されたときの処理
form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const course = {
    year: parseInt(courseYearInput.value),
    semester: courseSemesterInput.value,
    name: courseNameInput.value,
    credits: parseFloat(courseCreditsInput.value),
    grade: courseGradeInput.value,
    category: courseCategoryInput.value,
    memo: courseMemoInput.value,
  };

  if (editingIndex === -1) {
    // 新規追加
    await addCourse(course);
  } else {
    // 編集
    await updateCourse(editingIndex, course);
  }

  resetFormAndMode(); // フォームをリセット
});

// ★追加: キャンセルボタンがクリックされたときの処理
cancelEditBtn.addEventListener("click", () => {
  resetFormAndMode(); // フォームとモードをリセットするだけ
});

// フィルター変更時のイベント
filterYearSelect.addEventListener("change", () => {
  currentFilter.year = filterYearSelect.value;
  renderCourseList();
});

filterSemesterSelect.addEventListener("change", () => {
  currentFilter.semester = filterSemesterSelect.value;
  renderCourseList();
});

// 科目名フィルター変更時のイベント
filterNameInput.addEventListener("input", () => {
  currentFilter.name = filterNameInput.value;
  renderCourseList();
});

// カテゴリフィルター変更時のイベント
filterCategorySelect.addEventListener("change", () => {
  currentFilter.category = filterCategorySelect.value;
  renderCourseList();
});

// ソートボタンクリック時のイベント
sortGradeBtn.addEventListener("click", () => {
  if (currentSort.field === "grade") {
    currentSort.ascending = !currentSort.ascending;
  } else {
    currentSort.field = "grade";
    currentSort.ascending = true;
  }
  updateSortButtons();
  renderCourseList();
});

sortCreditsBtn.addEventListener("click", () => {
  if (currentSort.field === "credits") {
    currentSort.ascending = !currentSort.ascending;
  } else {
    currentSort.field = "credits";
    currentSort.ascending = true;
  }
  updateSortButtons();
  renderCourseList();
});

sortYearBtn.addEventListener("click", () => {
  if (currentSort.field === "year") {
    currentSort.ascending = !currentSort.ascending;
  } else {
    currentSort.field = "year";
    currentSort.ascending = true;
  }
  updateSortButtons();
  renderCourseList();
});

// ソートボタンの状態を更新する関数
function updateSortButtons() {
  [sortGradeBtn, sortCreditsBtn, sortYearBtn].forEach((btn) => {
    btn.classList.remove("active");
  });

  if (currentSort.field) {
    const activeBtn = document.getElementById(`sort-${currentSort.field}`);
    if (activeBtn) {
      activeBtn.classList.add("active");
      activeBtn.textContent = `${
        currentSort.field === "grade"
          ? "評価"
          : currentSort.field === "credits"
          ? "単位数"
          : "年度"
      }順${currentSort.ascending ? "↑" : "↓"}`;
    }
  }
}

// 通知システム
function showNotification(message, type = "info") {
  // 既存の通知を削除
  const existingNotifications = document.querySelectorAll(".notification");
  existingNotifications.forEach((notification) => {
    document.body.removeChild(notification);
  });

  // 新しい通知を作成
  const notification = document.createElement("div");
  notification.className = `notification ${type}`;

  // アイコン設定
  let icon = "";
  if (type === "success") {
    icon = "✅";
  } else if (type === "error") {
    icon = "❌";
  } else {
    icon = "ℹ️";
  }

  // 通知の内容を設定
  notification.innerHTML = `
    <span class="notification-icon">${icon}</span>
    <span class="notification-message">${message}</span>
    <span class="notification-close">×</span>
  `;

  // 通知をDOMに追加
  document.body.appendChild(notification);

  // アニメーション効果を適用（少し遅延させて適用）
  setTimeout(() => {
    notification.classList.add("show");
  }, 10);

  // クローズボタンのイベントリスナー
  notification
    .querySelector(".notification-close")
    .addEventListener("click", () => {
      notification.classList.remove("show");
      setTimeout(() => {
        if (notification.parentNode) {
          document.body.removeChild(notification);
        }
      }, 300);
    });

  // 自動的に消える
  setTimeout(() => {
    if (document.body.contains(notification)) {
      notification.classList.remove("show");
      setTimeout(() => {
        if (notification.parentNode) {
          document.body.removeChild(notification);
        }
      }, 300);
    }
  }, 5000);
}

// ローディングオーバーレイを表示/非表示にする関数
window.showLoading = function () {
  const overlay = document.querySelector(".loading-overlay");
  if (overlay) {
    overlay.classList.add("show");
  }
};

window.hideLoading = function () {
  const overlay = document.querySelector(".loading-overlay");
  if (overlay) {
    overlay.classList.remove("show");
  }
};

// 追加: 必要な関数をグローバルスコープに公開
window.startEdit = startEdit;
window.showNotification = showNotification;
window.getFilteredAndSortedCourses = getFilteredAndSortedCourses;

// ページ読み込み時にデータを取得
document.addEventListener("DOMContentLoaded", fetchCourses);

// DOM要素の取得（追加部分）
const selectAllBtn = document.getElementById("select-all-btn");
const deselectAllBtn = document.getElementById("deselect-all-btn");
const deleteSelectedBtn = document.getElementById("delete-selected-btn");
const selectAllCheckbox = document.getElementById("select-all-checkbox");

// --- データ関連（追加部分）---
let selectedCourseIds = []; // 選択された科目IDを保持する配列

// 一括削除ボタンの状態を更新する関数
function updateDeleteButtonState() {
  if (selectedCourseIds.length > 0) {
    deleteSelectedBtn.classList.remove("disabled");
    deleteSelectedBtn.textContent = `選択した${selectedCourseIds.length}件を削除`;
  } else {
    deleteSelectedBtn.classList.add("disabled");
    deleteSelectedBtn.textContent = "削除";
  }
}

// 全選択ボタンのクリックイベント
selectAllBtn.addEventListener("click", () => {
  const checkboxes = document.querySelectorAll(".course-checkbox");
  let allChecked = true;

  checkboxes.forEach((checkbox) => {
    if (!checkbox.checked) {
      allChecked = false;
    }
  });

  checkboxes.forEach((checkbox) => {
    checkbox.checked = !allChecked;
    const courseId = checkbox.dataset.id;
    if (!allChecked && !selectedCourseIds.includes(courseId)) {
      selectedCourseIds.push(courseId);
      checkbox.closest("tr").classList.add("selected-for-delete");
    } else {
      selectedCourseIds = selectedCourseIds.filter((id) => id !== courseId);
      checkbox.closest("tr").classList.remove("selected-for-delete");
    }
  });

  // 削除ボタンの状態を更新
  updateDeleteButtonState();
});

// 全選択解除ボタンのクリックイベント
deselectAllBtn.addEventListener("click", () => {
  const checkboxes = document.querySelectorAll(".course-checkbox");
  checkboxes.forEach((checkbox) => {
    checkbox.checked = false;
    const courseId = checkbox.dataset.id;
    selectedCourseIds = selectedCourseIds.filter((id) => id !== courseId);
    checkbox.closest("tr").classList.remove("selected-for-delete");
  });

  // 削除ボタンの状態を更新
  updateDeleteButtonState();
});

// 一括削除ボタンのクリックイベント
deleteSelectedBtn.addEventListener("click", async () => {
  if (selectedCourseIds.length === 0) return;

  if (!confirm(`選択した${selectedCourseIds.length}件の科目を削除しますか？`)) {
    return;
  }

  try {
    const response = await fetch("/api/delete_courses", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ids: selectedCourseIds }),
    });

    if (!response.ok) {
      throw new Error("削除に失敗しました");
    }

    // 削除後は選択状態をリセット
    selectedCourseIds = [];
    document.querySelectorAll(".course-checkbox").forEach((checkbox) => {
      checkbox.checked = false;
      checkbox.closest("tr").classList.remove("selected-for-delete");
    });

    await fetchCourses(); // サーバーから再取得して表示更新！
    showNotification(`選択した科目を削除しました`, "info");
  } catch (error) {
    console.error("削除エラー:", error);
    showNotification("削除に失敗しました", "error");
  }
});

// カテゴリ再分類ボタンのクリックイベント
const reclassifyBtn = document.getElementById("reclassify-btn");
if (reclassifyBtn) {
  reclassifyBtn.addEventListener("click", () => {
    if (typeof window.reclassifyExistingCourses === "function") {
      window.reclassifyExistingCourses();
    } else {
      console.error("reclassifyExistingCourses function not found");
      showNotification("再分類機能が利用できません", "error");
    }
  });
}

// 評価別単位数分布を計算して表示する関数
function calculateAndDisplayGradeDistribution() {
  // 各評価の科目数と単位数を集計する
  const gradeSummary = {
    "A+": { count: 0, credits: 0 },
    A: { count: 0, credits: 0 },
    B: { count: 0, credits: 0 },
    C: { count: 0, credits: 0 },
    F: { count: 0, credits: 0 },
    total: { count: 0, credits: 0 },
  };

  // 全科目をループして集計
  courses.forEach((course) => {
    const grade = course.grade;
    const credits = parseFloat(course.credits);

    // 有効な評価と単位数の場合のみ集計
    if (grade && !isNaN(credits)) {
      // その評価の集計に加算
      if (gradeSummary[grade]) {
        gradeSummary[grade].count++;
        gradeSummary[grade].credits += credits;
      }

      // 合計にも加算
      gradeSummary.total.count++;

      // F評価は単位として認められないので、合計単位には加算しない
      if (grade !== "F") {
        gradeSummary.total.credits += credits;
      }
    }
  });

  // 各評価のDOM要素を更新
  document.getElementById("aplus-count").textContent = gradeSummary["A+"].count;
  document.getElementById("aplus-credits").textContent =
    gradeSummary["A+"].credits.toFixed(1);

  document.getElementById("a-count").textContent = gradeSummary["A"].count;
  document.getElementById("a-credits").textContent =
    gradeSummary["A"].credits.toFixed(1);

  document.getElementById("b-count").textContent = gradeSummary["B"].count;
  document.getElementById("b-credits").textContent =
    gradeSummary["B"].credits.toFixed(1);

  document.getElementById("c-count").textContent = gradeSummary["C"].count;
  document.getElementById("c-credits").textContent =
    gradeSummary["C"].credits.toFixed(1);

  document.getElementById("f-count").textContent = gradeSummary["F"].count;
  document.getElementById("f-credits").textContent =
    gradeSummary["F"].credits.toFixed(1);

  document.getElementById("total-course-count").textContent =
    gradeSummary.total.count;
  document.getElementById("total-grade-credits").textContent =
    gradeSummary.total.credits.toFixed(1);
}
