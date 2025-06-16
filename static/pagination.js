/**
 * 科目リストのページネーション機能を提供するモジュール
 */

// ページネーション関連の状態を管理
let paginationState = {
  currentPage: 1,
  pageSize: 20, // デフォルトでは1ページに20件表示
  totalItems: 0,
  totalPages: 1,
};

/**
 * ページネーションの初期化と各種イベントリスナーの設定
 */
function initPagination() {
  // DOM要素の取得
  const pageSizeSelector = document.getElementById("page-size-selector");
  const prevPageBtn = document.getElementById("prev-page");
  const nextPageBtn = document.getElementById("next-page");
  const pageNumbers = document.getElementById("page-numbers");

  // ページサイズの変更イベント
  pageSizeSelector.addEventListener("change", function () {
    paginationState.pageSize = parseInt(this.value);
    paginationState.currentPage = 1; // ページサイズを変更したら1ページ目に戻る
    renderCourseList();
    updatePaginationControls();
  });

  // 前のページボタンのイベント
  prevPageBtn.addEventListener("click", function () {
    if (paginationState.currentPage > 1) {
      paginationState.currentPage--;
      renderCourseList();
      updatePaginationControls();
    }
  });

  // 次のページボタンのイベント
  nextPageBtn.addEventListener("click", function () {
    if (paginationState.currentPage < paginationState.totalPages) {
      paginationState.currentPage++;
      renderCourseList();
      updatePaginationControls();
    }
  });

  // 初期状態を設定
  paginationState.pageSize = parseInt(pageSizeSelector.value);
  updatePaginationControls();
}

/**
 * ページネーションコントロールを更新する
 */
function updatePaginationControls() {
  const prevPageBtn = document.getElementById("prev-page");
  const nextPageBtn = document.getElementById("next-page");
  const pageNumbers = document.getElementById("page-numbers");
  const paginationStatus = document.getElementById("pagination-status");
  const filteredCourses = getFilteredAndSortedCourses();

  // 全件表示が選択されている場合
  if (paginationState.pageSize === -1) {
    paginationState.totalPages = 1;
    paginationState.currentPage = 1;
    prevPageBtn.disabled = true;
    nextPageBtn.disabled = true;
    pageNumbers.innerHTML = '<span class="current-page">1</span>';
    paginationStatus.textContent = `${filteredCourses.length}件 / 全${filteredCourses.length}件（全件表示）`;
    return;
  }

  // 現在のデータと状態に基づいてページ数を計算
  paginationState.totalItems = filteredCourses.length;
  paginationState.totalPages = Math.ceil(
    paginationState.totalItems / paginationState.pageSize
  );

  // ページがない場合
  if (paginationState.totalPages === 0) {
    paginationState.totalPages = 1;
  }

  // 現在のページが範囲外にならないよう調整
  if (paginationState.currentPage > paginationState.totalPages) {
    paginationState.currentPage = paginationState.totalPages;
  }

  // 前へ/次へボタンの状態を更新
  prevPageBtn.disabled = paginationState.currentPage <= 1;
  nextPageBtn.disabled =
    paginationState.currentPage >= paginationState.totalPages;

  // ページ番号表示を更新
  updatePageNumbers();

  // ステータス表示を更新
  const start =
    (paginationState.currentPage - 1) * paginationState.pageSize + 1;
  const end = Math.min(
    paginationState.currentPage * paginationState.pageSize,
    paginationState.totalItems
  );

  // データがない場合
  if (paginationState.totalItems === 0) {
    paginationStatus.textContent = `0件 / 全0件`;
  } else {
    paginationStatus.textContent = `${start}-${end}件 / 全${paginationState.totalItems}件`;
  }
}

/**
 * ページ番号ボタンを生成・更新する
 */
function updatePageNumbers() {
  const pageNumbers = document.getElementById("page-numbers");
  pageNumbers.innerHTML = "";

  // 表示するページボタンの数
  const maxPageButtons = 5;
  let startPage = Math.max(
    1,
    paginationState.currentPage - Math.floor(maxPageButtons / 2)
  );
  let endPage = Math.min(
    paginationState.totalPages,
    startPage + maxPageButtons - 1
  );

  // 表示する最初と最後のページを調整
  if (endPage - startPage + 1 < maxPageButtons) {
    startPage = Math.max(1, endPage - maxPageButtons + 1);
  }

  // 最初のページへのリンク（必要な場合）
  if (startPage > 1) {
    const firstPageBtn = document.createElement("span");
    firstPageBtn.className = "page-number";
    firstPageBtn.textContent = "1";
    firstPageBtn.addEventListener("click", () => goToPage(1));
    pageNumbers.appendChild(firstPageBtn);

    // 省略記号を表示（必要な場合）
    if (startPage > 2) {
      const ellipsis = document.createElement("span");
      ellipsis.className = "page-ellipsis";
      ellipsis.textContent = "...";
      pageNumbers.appendChild(ellipsis);
    }
  }

  // ページ番号ボタンを生成
  for (let i = startPage; i <= endPage; i++) {
    const pageBtn = document.createElement("span");
    pageBtn.className =
      i === paginationState.currentPage
        ? "page-number current-page"
        : "page-number";
    pageBtn.textContent = i;
    pageBtn.addEventListener("click", () => goToPage(i));
    pageNumbers.appendChild(pageBtn);
  }

  // 最後のページへのリンク（必要な場合）
  if (endPage < paginationState.totalPages) {
    // 省略記号を表示（必要な場合）
    if (endPage < paginationState.totalPages - 1) {
      const ellipsis = document.createElement("span");
      ellipsis.className = "page-ellipsis";
      ellipsis.textContent = "...";
      pageNumbers.appendChild(ellipsis);
    }

    const lastPageBtn = document.createElement("span");
    lastPageBtn.className = "page-number";
    lastPageBtn.textContent = paginationState.totalPages;
    lastPageBtn.addEventListener("click", () =>
      goToPage(paginationState.totalPages)
    );
    pageNumbers.appendChild(lastPageBtn);
  }
}

/**
 * 指定したページに移動する
 */
function goToPage(pageNumber) {
  if (pageNumber >= 1 && pageNumber <= paginationState.totalPages) {
    paginationState.currentPage = pageNumber;
    renderCourseList();
    updatePaginationControls();
  }
}

/**
 * 現在のページに表示すべきコースデータを取得する
 */
function getPaginatedCourses(filteredCourses) {
  // 全件表示が選択されている場合は、全データを返す
  if (paginationState.pageSize === -1) {
    return filteredCourses;
  }

  const startIndex =
    (paginationState.currentPage - 1) * paginationState.pageSize;
  const endIndex = Math.min(
    startIndex + paginationState.pageSize,
    filteredCourses.length
  );
  return filteredCourses.slice(startIndex, endIndex);
}

// グローバルスコープに公開
window.paginationState = paginationState;
window.initPagination = initPagination;
window.updatePaginationControls = updatePaginationControls;
window.getPaginatedCourses = getPaginatedCourses;
