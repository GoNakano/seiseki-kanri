// 立命館大学のカリキュラム要件（単位数）
const requirementCredits = {
  総単位: 124, // 卒業に必要な総単位数
  専門科目: 100,
  基礎専門科目: 20,
  共通専門科目: 22,
  固有専門科目: 48, // 必修と選択の合計
  外国語: 10,
  教養科目: 14,
};

// カテゴリ別単位数を計算して表示する関数
function calculateCategoryCredits() {
  // カテゴリグループの定義
  const categoryGroups = {
    専門科目: [
      "基礎専門科目",
      "共通専門科目",
      "固有専門科目（必修）",
      "固有専門科目（選択）",
      "グローバル・キャリア養成科目",
    ],
    外国語: ["外国語"],
    教養科目: ["教養科目"],
  };

  // カテゴリごとの単位数を集計（取得済み・未修得別）
  const categoryCredits = {};
  const categoryPendingCredits = {}; // 履修予定科目用
  const groupTotals = {
    専門科目: 0,
    外国語: 0,
    教養科目: 0,
  };
  const groupPendingTotals = {
    専門科目: 0,
    外国語: 0,
    教養科目: 0,
  };

  // すべてのカテゴリで初期化
  for (const group in categoryGroups) {
    for (const category of categoryGroups[group]) {
      categoryCredits[category] = 0;
      categoryPendingCredits[category] = 0;
    }
  }

  // コースをループして各カテゴリの単位数を計算
  courses.forEach((course) => {
    const category = course.category || "未分類";
    const credits = parseFloat(course.credits) || 0;

    // F評価・不可評価は卒業要件進捗から除外（単位として認められない）
    const isFailedGrade = course.grade === "F" || course.grade === "不可";

    // 年度不明は履修予定として扱う（F評価は除く）
    const isPending = (!course.year || course.year === "") && !isFailedGrade;

    if (
      categoryCredits.hasOwnProperty(category) ||
      categoryPendingCredits.hasOwnProperty(category)
    ) {
      if (isFailedGrade) {
        // F評価・不可評価は進捗計算から除外（何もしない）
        return;
      } else if (isPending) {
        // 履修予定科目として追加（年度不明でF評価でない科目）
        if (categoryPendingCredits.hasOwnProperty(category)) {
          categoryPendingCredits[category] += credits;
        }

        // そのカテゴリが属するグループの履修予定合計も更新
        for (const group in categoryGroups) {
          if (categoryGroups[group].includes(category)) {
            groupPendingTotals[group] += credits;
            break;
          }
        }
      } else {
        // 取得済み科目として追加
        if (categoryCredits.hasOwnProperty(category)) {
          categoryCredits[category] += credits;
        }

        // そのカテゴリが属するグループの合計も更新
        for (const group in categoryGroups) {
          if (categoryGroups[group].includes(category)) {
            groupTotals[group] += credits;
            break;
          }
        }
      }
    }
  });

  // DOM更新: 個々のカテゴリ単位数
  for (const category in categoryCredits) {
    const element = document.getElementById(`${category}-credits`);
    if (element) {
      element.textContent = categoryCredits[category].toFixed(1);
    }
  }

  // 固有専門科目の合計を計算して表示
  const fixedSpecialtyTotal =
    (categoryCredits["固有専門科目（必修）"] || 0) +
    (categoryCredits["固有専門科目（選択）"] || 0);
  const fixedSpecialtyElement = document.getElementById("固有専門科目-total");
  if (fixedSpecialtyElement) {
    fixedSpecialtyElement.textContent = fixedSpecialtyTotal.toFixed(1);
  }

  // DOM更新: グループ合計
  for (const group in groupTotals) {
    const element = document.getElementById(`${group}-total`);
    if (element) {
      element.textContent = groupTotals[group].toFixed(1);
    }
  }

  // 総単位数を表示（F評価、不可評価、年度不明を除外）
  const totalCredits = courses.reduce((sum, course) => {
    // F評価、不可評価、年度不明の科目は単位として認められないため除外
    if (
      course.grade === "F" ||
      course.grade === "不可" ||
      !course.year ||
      course.year === ""
    )
      return sum;
    return sum + (parseFloat(course.credits) || 0);
  }, 0);

  const totalElement = document.getElementById("総単位数-display");
  if (totalElement) {
    totalElement.textContent = totalCredits.toFixed(1);
  }

  // カテゴリ別単位分布グラフを更新
  updateCategoryDistributionChart(groupTotals);

  // 卒業要件の進捗を更新（取得済み・履修予定を考慮）
  updateRequirementProgress(
    categoryCredits,
    categoryPendingCredits,
    groupTotals,
    groupPendingTotals,
    totalCredits
  );
}

// カテゴリ別分布のグラフを作成・更新する関数
let categoryDistributionChart = null;

function updateCategoryDistributionChart(groupTotals) {
  const labels = Object.keys(groupTotals);
  const data = Object.values(groupTotals);

  // カテゴリごとの色設定
  const categoryColors = {
    専門科目: "#4CAF50", // 緑
    外国語: "#2196F3", // 青
    教養科目: "#FF9800", // オレンジ
    未分類: "#9E9E9E", // グレー
  };

  const backgroundColors = labels.map((label) => categoryColors[label]);

  const ctx = document.getElementById("category-distribution-chart");
  if (!ctx) return;

  // グラフを更新または作成
  if (categoryDistributionChart) {
    categoryDistributionChart.data.labels = labels;
    categoryDistributionChart.data.datasets[0].data = data;
    categoryDistributionChart.data.datasets[0].backgroundColor =
      backgroundColors;
    categoryDistributionChart.update();
  } else {
    categoryDistributionChart = new Chart(ctx, {
      type: "doughnut",
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
              padding: 10,
              boxWidth: 15,
            },
          },
          tooltip: {
            bodyFont: {
              size: 12,
            },
            titleFont: {
              size: 13,
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
                return `${label}: ${value.toFixed(1)} 単位 (${percentage}%)`;
              },
            },
          },
        },
      },
    });
  }
}

// 卒業要件の進捗度を更新する関数
function updateRequirementProgress(
  categoryCredits,
  categoryPendingCredits,
  groupTotals,
  groupPendingTotals,
  totalCredits
) {
  // 専門科目の進捗
  updateProgressBarWithPending(
    "専門科目",
    groupTotals["専門科目"],
    groupPendingTotals["専門科目"],
    requirementCredits["専門科目"]
  );

  // 基礎専門科目の進捗
  updateProgressBarWithPending(
    "基礎専門科目",
    categoryCredits["基礎専門科目"] || 0,
    categoryPendingCredits["基礎専門科目"] || 0,
    requirementCredits["基礎専門科目"]
  );

  // 共通専門科目の進捗
  updateProgressBarWithPending(
    "共通専門科目",
    categoryCredits["共通専門科目"] || 0,
    categoryPendingCredits["共通専門科目"] || 0,
    requirementCredits["共通専門科目"]
  );

  // 固有専門科目の進捗（必修と選択の合計）
  const fixedSpecialtyTotal =
    (categoryCredits["固有専門科目（必修）"] || 0) +
    (categoryCredits["固有専門科目（選択）"] || 0);
  const fixedSpecialtyPendingTotal =
    (categoryPendingCredits["固有専門科目（必修）"] || 0) +
    (categoryPendingCredits["固有専門科目（選択）"] || 0);
  updateProgressBarWithPending(
    "固有専門科目",
    fixedSpecialtyTotal,
    fixedSpecialtyPendingTotal,
    requirementCredits["固有専門科目"]
  );

  // 外国語の進捗
  updateProgressBarWithPending(
    "外国語",
    groupTotals["外国語"],
    groupPendingTotals["外国語"],
    requirementCredits["外国語"]
  );

  // 教養科目の進捗
  updateProgressBarWithPending(
    "教養科目",
    groupTotals["教養科目"],
    groupPendingTotals["教養科目"],
    requirementCredits["教養科目"]
  );

  // 総単位数の進捗
  const totalPendingCredits = courses.reduce((sum, course) => {
    // 年度不明の科目の単位数を集計（F評価・不可評価は除く）
    if (
      (!course.year || course.year === "") &&
      course.grade !== "F" &&
      course.grade !== "不可"
    ) {
      return sum + (parseFloat(course.credits) || 0);
    }
    return sum;
  }, 0);

  updateProgressBarWithPending(
    "総単位",
    totalCredits,
    totalPendingCredits,
    requirementCredits["総単位"]
  );
}

// プログレスバーを更新する関数（履修予定科目対応）
function updateProgressBarWithPending(
  categoryId,
  currentCredits,
  pendingCredits,
  requiredCredits
) {
  const progressBar = document.getElementById(`${categoryId}-progress`);
  const progressText = document.getElementById(`${categoryId}-progress-text`);

  if (!progressBar || !progressText) return;

  // 取得済み単位の割合
  const currentPercentage = Math.min(
    100,
    (currentCredits / requiredCredits) * 100
  );
  // 履修予定科目を含めた場合の割合
  const totalPotentialPercentage = Math.min(
    100,
    ((currentCredits + pendingCredits) / requiredCredits) * 100
  );

  // プログレスバーのHTMLを更新（履修予定分を含む場合）
  if (pendingCredits > 0) {
    progressBar.innerHTML = `
      <div class="progress-bar-pending" style="width: ${totalPotentialPercentage}%;"></div>
    `;
    progressBar.style.width = `${currentPercentage}%`;
    progressBar.classList.add("with-pending");
  } else {
    progressBar.innerHTML = "";
    progressBar.style.width = `${currentPercentage}%`;
    progressBar.classList.remove("with-pending");
  }

  // テキスト表示の更新
  let displayText = `${Math.round(
    currentPercentage
  )}% (${currentCredits.toFixed(1)}/${requiredCredits}単位)`;
  if (pendingCredits > 0) {
    displayText += ` [履修予定: ${pendingCredits.toFixed(1)}単位]`;
  }
  progressText.textContent = displayText;

  // 進捗度に応じて色を変更
  if (currentPercentage >= 100) {
    progressBar.style.backgroundColor = "#4CAF50"; // 緑（達成）
  } else if (currentPercentage >= 70) {
    progressBar.style.backgroundColor = "#8BC34A"; // 薄い緑（進行中）
  } else if (currentPercentage >= 40) {
    progressBar.style.backgroundColor = "#FFC107"; // 黄色（注意）
  } else {
    progressBar.style.backgroundColor = "#FF5722"; // オレンジ（未達成）
  }
}

// プログレスバーを更新する関数（従来版 - 互換性のため残す）
function updateProgressBar(categoryId, currentCredits, requiredCredits) {
  updateProgressBarWithPending(categoryId, currentCredits, 0, requiredCredits);
}
