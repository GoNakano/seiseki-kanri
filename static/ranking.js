document.addEventListener("DOMContentLoaded", function () {
  let currentSort = "gpa";
  let currentGrade = "all";
  let currentStatsGrade = "all"; // 分布用の学年フィルタ
  let rankingData = [];
  let myStats = {};
  let gpaChart = null; // GPAチャートのインスタンス
  let gpsChart = null; // GPSチャートのインスタンス

  // 利用可能な学年を読み込んで学年セレクタを初期化
  loadAvailableGrades();

  // タブ切り替え機能
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const targetTab = this.dataset.tab;

      // ボタンのアクティブ状態を更新
      tabButtons.forEach((btn) => btn.classList.remove("active"));
      this.classList.add("active");

      // タブコンテンツの表示を更新
      tabContents.forEach((content) => content.classList.remove("active"));
      document.getElementById(targetTab + "-tab").classList.add("active");

      // 分布タブが選択された場合、分布チャートを描画
      if (targetTab === "stats") {
        loadDistributionStats();
      }
    });
  });

  // ソートボタンのイベントリスナー
  const sortButtons = document.querySelectorAll(".sort-btn");
  sortButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const sortType = this.dataset.sort;
      currentSort = sortType;

      // ボタンのアクティブ状態を更新
      sortButtons.forEach((btn) => btn.classList.remove("active"));
      this.classList.add("active");

      // ランキングを再読み込み
      loadRanking();
    });
  });

  // ランキングデータを取得・表示
  function loadRanking() {
    fetch(`/api/get_ranking?sort_by=${currentSort}&grade=${currentGrade}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          rankingData = data.data;
          displayRanking(rankingData);
          updatePersonalStats(rankingData);
        } else {
          showError("ランキングデータの取得に失敗しました");
        }
      })
      .catch((error) => {
        console.error("loadRanking Error:", error);
        showError("ランキングデータの取得中にエラーが発生しました");
      });
  }

  // ランキングテーブルを表示
  function displayRanking(data) {
    const container = document.getElementById("ranking-content");

    if (data.length === 0) {
      const gradeText =
        currentGrade === "all" ? "すべての学年" : `${currentGrade}年生`;
      container.innerHTML = `<div class="error">${gradeText}のランキングデータがありません</div>`;
      return;
    }

    const gradeHeaderText =
      currentGrade === "all"
        ? "全学年ランキング"
        : `${currentGrade}年生ランキング`;

    let html = `
          <div class="ranking-header-info">
            <h3>${gradeHeaderText} (${data.length}人)</h3>
          </div>
          <div class="table-responsive">
          <table class="ranking-table">
              <thead>
                  <tr>
                      <th>順位</th>
                      <th>ニックネーム</th>
                      <th>学年</th>
                      <th>GPA</th>
                      <th>GPS</th>
                      <th>取得単位数</th>
                  </tr>
              </thead>
              <tbody>
      `;

    data.forEach((user) => {
      const rankClass =
        user.rank <= 3 ? ["", "gold", "silver", "bronze"][user.rank] : "";
      const currentUserClass = user.is_current_user ? "current-user" : "";

      html += `
              <tr class="${currentUserClass}">
                  <td>
                      <span class="rank-badge ${rankClass}">${user.rank}</span>
                  </td>
                  <td>${user.nickname}</td>
                  <td>${user.current_year}年生</td>
                  <td>${user.gpa}</td>
                  <td>${user.gps}</td>
                  <td>${user.total_credits}</td>
              </tr>
          `;
    });

    html += "</tbody></table></div>";
    container.innerHTML = html;
  }

  // 個人統計を更新
  function updatePersonalStats(rankingData) {
    const myData = rankingData.find((user) => user.is_current_user);

    if (myData) {
      document.getElementById("my-gpa").textContent = myData.gpa;
      document.getElementById("my-gps").textContent = myData.gps;
      document.getElementById("my-credits").textContent =
        myData.total_credits;
      document.getElementById("my-rank").textContent = `${myData.rank}位`;
    } else {
      // 現在のユーザーが選択された学年のランキングに含まれていない場合
      const gradeText =
        currentGrade === "all"
          ? ""
          : `（${currentGrade}年生内での順位は表示されません）`;
      document.getElementById("my-gpa").textContent = "-";
      document.getElementById("my-gps").textContent = "-";
      document.getElementById("my-credits").textContent = "-";
      document.getElementById("my-rank").textContent = "-";
    }
  }

  // 分布統計データを取得
  function loadDistributionStats() {
    fetch(`/api/get_distribution_stats?grade=${currentStatsGrade}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          drawDistributionCharts(data.data);
          populateDistributionTables(data.data);
          updateStatsUserCount(data.data);
        } else {
          console.error("分布統計データの取得に失敗しました");
        }
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  }

  // 分布対象ユーザー数を更新
  function updateStatsUserCount(data) {
    const userCountEl = document.getElementById("stats-user-count");
    const gradeText =
      currentStatsGrade === "all" ? "全学年" : `${currentStatsGrade}年生`;
    userCountEl.textContent = `${gradeText} ${data.total_users}人のデータ`;
  }

  // 分布チャートを描画
  function drawDistributionCharts(data) {
    drawGpaDistributionChart(data.gpa_distribution);
    drawGpsDistributionChart(data.gps_distribution);
  }

  // GPA分布チャート
  function drawGpaDistributionChart(gpaData) {
    // 既存のチャートがあれば破棄
    if (gpaChart) {
      gpaChart.destroy();
    }

    const ctx = document
      .getElementById("gpaDistributionChart")
      .getContext("2d");

    const labels = gpaData.map((item) => item.range);
    const counts = gpaData.map((item) => item.count);

    const gradeText =
      currentStatsGrade === "all" ? "全学年" : `${currentStatsGrade}年生`;

    gpaChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "人数",
            data: counts,
            backgroundColor: "rgba(25, 118, 210, 0.7)",
            borderColor: "rgba(25, 118, 210, 1)",
            borderWidth: 2,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: "人数",
            },
            ticks: {
              stepSize: 1,
            },
          },
          x: {
            title: {
              display: true,
              text: "GPA区間",
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          title: {
            display: true,
            text: `${
              currentStatsGrade === "all"
                ? "全学年"
                : `${currentStatsGrade}年生`
            }GPA分布グラフ`,
            font: {
              size: 16,
              weight: "bold",
            },
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `人数: ${context.parsed.y}人`;
              },
            },
          },
        },
      },
    });
  }

  // GPS分布チャート
  function drawGpsDistributionChart(gpsData) {
    // 既存のチャートを破棄
    if (gpsChart) {
      gpsChart.destroy();
    }

    const ctx = document
      .getElementById("gpsDistributionChart")
      .getContext("2d");

    const labels = gpsData.map((item) => item.range);
    const counts = gpsData.map((item) => item.count);

    gpsChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "人数",
            data: counts,
            backgroundColor: "rgba(3, 169, 244, 0.7)",
            borderColor: "rgba(3, 169, 244, 1)",
            borderWidth: 2,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: "人数",
            },
            ticks: {
              stepSize: 1,
            },
          },
          x: {
            title: {
              display: true,
              text: "GPS区間",
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          title: {
            display: true,
            text: `${
              currentStatsGrade === "all"
                ? "全学年"
                : `${currentStatsGrade}年生`
            }GPS分布グラフ`,
            font: {
              size: 16,
              weight: "bold",
            },
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `人数: ${context.parsed.y}人`;
              },
            },
          },
        },
      },
    });
  }

  // 分布テーブルを生成
  function populateDistributionTables(data) {
    populateGpaDistributionTable(data.gpa_distribution);
    populateGpsDistributionTable(data.gps_distribution);
  }

  // GPA分布テーブル
  function populateGpaDistributionTable(gpaData) {
    const tbody = document.querySelector("#gpa-distribution-table tbody");
    const totalCount = gpaData.reduce((sum, item) => sum + item.count, 0);
    let cumulativeCount = 0;

    tbody.innerHTML = "";

    gpaData.forEach((item) => {
      cumulativeCount += item.count;
      const percentage = ((item.count / totalCount) * 100).toFixed(1);
      const cumulativePercentage = (
        (cumulativeCount / totalCount) *
        100
      ).toFixed(1);

      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="range-label">${item.range}</td>
        <td class="count-cell">${item.count}人</td>
        <td class="percentage-cell">${percentage}%</td>
        <td class="cumulative-cell">${cumulativePercentage}%</td>
      `;
      tbody.appendChild(row);
    });
  }

  // GPS分布テーブル
  function populateGpsDistributionTable(gpsData) {
    const tbody = document.querySelector("#gps-distribution-table tbody");
    const totalCount = gpsData.reduce((sum, item) => sum + item.count, 0);
    let cumulativeCount = 0;

    tbody.innerHTML = "";

    gpsData.forEach((item) => {
      cumulativeCount += item.count;
      const percentage = ((item.count / totalCount) * 100).toFixed(1);
      const cumulativePercentage = (
        (cumulativeCount / totalCount) *
        100
      ).toFixed(1);

      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="range-label">${item.range}</td>
        <td class="count-cell">${item.count}人</td>
        <td class="percentage-cell">${percentage}%</td>
        <td class="cumulative-cell">${cumulativePercentage}%</td>
      `;
      tbody.appendChild(row);
    });
  }

  function showError(message) {
    const container = document.getElementById("ranking-content");
    container.innerHTML = `<div class="error">${message}</div>`;
  }

  // 利用可能な学年を読み込む
  function loadAvailableGrades() {
    fetch("/api/get_available_grades")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "success") {
          const gradeSelect = document.getElementById("grade-select");
          const statsGradeSelect =
            document.getElementById("stats-grade-select");

          // ランキング用学年セレクタの設定
          while (gradeSelect.children.length > 1) {
            gradeSelect.removeChild(gradeSelect.lastChild);
          }

          // 統計分析用学年セレクタの設定
          while (statsGradeSelect.children.length > 1) {
            statsGradeSelect.removeChild(statsGradeSelect.lastChild);
          }

          // 利用可能な学年を両方に追加
          data.data.forEach((grade) => {
            // ランキング用
            const option1 = document.createElement("option");
            option1.value = grade;
            option1.textContent = `${grade}年生`;
            gradeSelect.appendChild(option1);

            // 分布用
            const option2 = document.createElement("option");
            option2.value = grade;
            option2.textContent = `${grade}年生`;
            statsGradeSelect.appendChild(option2);
          });

          // ランキング学年選択のイベントリスナーを設定
          gradeSelect.addEventListener("change", function () {
            currentGrade = this.value;
            loadRanking();
          });

          // 分布学年選択のイベントリスナーを設定
          statsGradeSelect.addEventListener("change", function () {
            currentStatsGrade = this.value;
            loadDistributionStats();
          });

          // 初期データを読み込み
          loadRanking();
        } else {
          console.error("利用可能な学年の取得に失敗しました");
          // エラーでも初期データは読み込む
          loadRanking();
        }
      })
      .catch((error) => {
        console.error("loadAvailableGrades Error:", error);
        // エラーでも初期データは読み込む
        loadRanking();
      });
  }
});
