/**
 * Rendering of one analysed entry (label chip + pie chart + insight).
 * Shared by the chat dashboard and the read-only shared-chat page.
 * All user-supplied text goes through textContent — never innerHTML.
 */
const Render = (() => {
  const CHART_COLORS = {
    positive: "#5fd9a4",
    negative: "#f0708a",
    neutral: "#e8c368",
  };
  function colorFor(label) {
    const key = label.toLowerCase();
    if (key.includes("pos")) return CHART_COLORS.positive;
    if (key.includes("neg")) return CHART_COLORS.negative;
    return CHART_COLORS.neutral;
  }
  function labelClass(label) {
    const key = label.toLowerCase();
    if (key.includes("pos")) return "positive";
    if (key.includes("neg")) return "negative";
    return "neutral";
  }

  function chart(canvas, scores) {
    const labels = Object.keys(scores);
    const values = Object.values(scores);
    try {
      if (typeof Chart === "undefined") throw new Error("Chart.js did not load");
      new Chart(canvas, {
        type: "pie",
        data: {
          labels: labels.map((l, i) => `${l} ${(values[i] * 100).toFixed(0)}%`),
          datasets: [
            {
              data: values,
              backgroundColor: labels.map(colorFor),
              borderColor: "#14161d",
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 400 },
          plugins: {
            legend: {
              display: true,
              position: "right",
              labels: { color: "#9aa0ad", boxWidth: 10, boxHeight: 10, font: { size: 12 } },
            },
          },
        },
      });
    } catch (err) {
      console.warn("Chart rendering failed, falling back to text:", err);
      const wrap = canvas.parentElement;
      wrap.innerHTML = "";
      const list = document.createElement("div");
      list.className = "score-fallback";
      labels.forEach((l, i) => {
        const row = document.createElement("div");
        row.textContent = `${l}: ${(values[i] * 100).toFixed(0)}%`;
        list.appendChild(row);
      });
      wrap.appendChild(list);
    }
  }

  /** Append one result card to `container`. Returns the element. */
  function entry(container, result) {
    const el = document.createElement("article");
    el.className = "entry";

    const isMedia = result.source_type === "image" || result.source_type === "video";
    if (isMedia) {
      const src = document.createElement("div");
      src.className = "entry-source";
      src.textContent = `${result.source_type} · ${result.source_name || "upload"} — text extracted from the ${result.source_type}`;
      el.appendChild(src);
    }

    const p = document.createElement("p");
    p.className = "entry-input";
    p.textContent = result.input_text;
    el.appendChild(p);

    const body = document.createElement("div");
    body.className = "entry-body";

    const chip = document.createElement("span");
    chip.className = `label-chip ${labelClass(result.predicted_label)}`;
    const dot = document.createElement("span");
    dot.className = "dot";
    chip.appendChild(dot);
    chip.appendChild(document.createTextNode(result.predicted_label));
    body.appendChild(chip);

    const chartWrap = document.createElement("div");
    chartWrap.className = "entry-chart-wrap";
    const canvas = document.createElement("canvas");
    chartWrap.appendChild(canvas);
    body.appendChild(chartWrap);

    const insight = document.createElement("p");
    insight.className = "entry-insight";
    insight.textContent = result.insight || "";
    body.appendChild(insight);

    el.appendChild(body);
    container.appendChild(el);
    chart(canvas, result.scores);
    return el;
  }

  function error(container, message) {
    const el = document.createElement("div");
    el.className = "entry entry-error";
    el.textContent = message;
    container.appendChild(el);
    return el;
  }

  function batchLabel(container, count) {
    const label = document.createElement("div");
    label.className = "batch-label";
    label.textContent = `Batch of ${count}`;
    container.appendChild(label);
  }

  /** Replay stored items, grouping consecutive items by batch_id. */
  function items(container, list) {
    let lastBatch = null;
    let buffer = [];
    const flush = () => {
      if (buffer.length > 1) batchLabel(container, buffer.length);
      buffer.forEach((it) => entry(container, it));
      buffer = [];
    };
    for (const it of list) {
      if (lastBatch !== null && it.batch_id !== lastBatch) flush();
      buffer.push(it);
      lastBatch = it.batch_id;
    }
    flush();
  }

  return { entry, error, batchLabel, items };
})();
