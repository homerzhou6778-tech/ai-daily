/* Keep stale data visibly stale, including when Actions has stopped running. */
(() => {
  const dataUrl = new URL("../data/latest-24h.json", document.currentScript.src);
  const notice = document.getElementById("publicFreshness");
  if (!notice) return;
  const showNotice = (message) => {
    notice.textContent = message;
    notice.className = "public-freshness";
    document.querySelector(".hero")?.appendChild(notice);
  };
  fetch(dataUrl, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error("Snapshot unavailable");
      return response.json();
    })
    .then((data) => {
      const updated = Date.parse(data.generated_at);
      if (!Number.isFinite(updated)) throw new Error("Snapshot timestamp missing");
      if (Date.now() - updated > 4 * 60 * 60 * 1000) {
        showNotice("数据已超过 4 小时未更新，当前展示的是上一次成功采集的快照。");
      }
    })
    .catch(() => showNotice("暂时无法确认数据更新时间，请稍后重试。"));
})();
