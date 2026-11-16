/* Voltiq staff dashboard behaviour and Chart.js renderers */
(function () {
  "use strict";

  /* Mobile sidebar */
  var sidebar = document.getElementById("dash-sidebar");
  var backdrop = document.querySelector(".dash-backdrop");
  function openSidebar() {
    if (sidebar) sidebar.classList.add("is-open");
    if (backdrop) backdrop.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeSidebar() {
    if (sidebar) sidebar.classList.remove("is-open");
    if (backdrop) backdrop.hidden = true;
    document.body.style.overflow = "";
  }
  document.querySelectorAll("[data-dash-open]").forEach(function (btn) {
    btn.addEventListener("click", openSidebar);
  });
  document.querySelectorAll("[data-dash-close]").forEach(function (btn) {
    btn.addEventListener("click", closeSidebar);
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeSidebar();
  });

  /* Toasts */
  document.querySelectorAll("[data-toast-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var toast = btn.closest("[data-toast]");
      if (toast) toast.remove();
    });
  });

  /* Chart.js */
  var config = window.VOLTIQ_CHARTS;
  if (!config || typeof Chart === "undefined") return;

  Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#64748b";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;

  function npr(value) {
    return "Rs. " + Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  }

  var gridColor = "rgba(148,163,184,.18)";

  var revenueCanvas = document.getElementById("revenueChart");
  if (revenueCanvas && config.labels) {
    new Chart(revenueCanvas, {
      type: "line",
      data: {
        labels: config.labels,
        datasets: [
          {
            label: "Revenue (NPR)",
            data: config.revenue || [],
            borderColor: "#2563eb",
            backgroundColor: "rgba(37,99,235,.12)",
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 2,
            pointHoverRadius: 5,
            yAxisID: "y",
          },
          {
            label: "Orders",
            data: config.orders || [],
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245,158,11,.1)",
            borderWidth: 2,
            borderDash: [5, 4],
            tension: 0.3,
            pointRadius: 0,
            yAxisID: "y1",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          tooltip: {
            callbacks: {
              label: function (ctx) {
                if (ctx.dataset.yAxisID === "y1") return "Orders: " + ctx.parsed.y;
                return "Revenue: " + npr(ctx.parsed.y);
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
          y: {
            beginAtZero: true,
            grid: { color: gridColor },
            border: { display: false },
            ticks: { callback: function (v) { return Number(v).toLocaleString("en-IN"); } },
          },
          y1: {
            beginAtZero: true,
            position: "right",
            grid: { display: false },
            border: { display: false },
            ticks: { precision: 0, maxTicksLimit: 6 },
          },
        },
      },
    });
  }

  var statusCanvas = document.getElementById("statusChart");
  if (statusCanvas && config.statusLabels) {
    new Chart(statusCanvas, {
      type: "doughnut",
      data: {
        labels: config.statusLabels,
        datasets: [
          {
            data: config.statusValues || [],
            backgroundColor: ["#2563eb", "#7c3aed", "#0ea5e9", "#f59e0b", "#10b981", "#22c55e", "#ef4444", "#94a3b8"],
            borderWidth: 0,
            hoverOffset: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "66%",
        plugins: { legend: { position: "bottom", labels: { padding: 14 } } },
      },
    });
  }

  var paymentCanvas = document.getElementById("paymentChart");
  if (paymentCanvas && config.paymentLabels) {
    new Chart(paymentCanvas, {
      type: "doughnut",
      data: {
        labels: config.paymentLabels,
        datasets: [
          {
            data: config.paymentValues || [],
            backgroundColor: ["#60bb46", "#5c2d91", "#0b1220", "#0e7490", "#f59e0b"],
            borderWidth: 0,
            hoverOffset: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: { legend: { position: "bottom", labels: { padding: 14 } } },
      },
    });
  }
})();
