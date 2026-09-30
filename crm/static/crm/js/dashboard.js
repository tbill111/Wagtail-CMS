/* SmartCRM – biểu đồ trang Tổng quan (Chart.js). Dữ liệu lấy từ <script id="dashboard-charts">. */
(function () {
    "use strict";

    const source = document.getElementById("dashboard-charts");
    if (!source) return;
    const charts = JSON.parse(source.textContent);

    const css = getComputedStyle(document.documentElement);
    const PRIMARY = css.getPropertyValue("--sc-primary").trim() || "#1e3a8a";
    const MUTED = css.getPropertyValue("--sc-muted").trim() || "#6b7280";
    const GRID = css.getPropertyValue("--sc-border").trim() || "#e5e7eb";

    const vnd = new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 });
    const compactVnd = (value) => {
        if (value >= 1e9) return (value / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " tỷ";
        if (value >= 1e6) return (value / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " tr";
        return value.toLocaleString("vi-VN");
    };

    // Mỗi biểu đồ chỉ có 1 chuỗi số liệu -> 1 màu, không cần chú thích (tiêu đề thẻ đã nêu tên)
    const CONFIG = {
        revenue: { horizontal: false, format: (v) => vnd.format(v), tick: compactVnd, header: ["Tháng", "Doanh thu"] },
        status: { horizontal: true, format: (v) => v + " khách", tick: (v) => v, header: ["Trạng thái", "Số khách"], integer: true },
        customers: { horizontal: true, format: (v) => vnd.format(v), tick: compactVnd, header: ["Khách hàng", "Đã chi tiêu"] },
        products: {
            horizontal: true, integer: true, header: ["Sản phẩm", "Đã bán", "Doanh thu"],
            format: (v, row) => `${v} ${row.unit} · ${vnd.format(row.revenue)}`, tick: (v) => v,
        },
    };

    Chart.defaults.font.family = css.getPropertyValue("--bs-body-font-family").trim() || "system-ui";
    Chart.defaults.color = MUTED;

    function fillTable(table, id, rows, cfg) {
        const head = "<thead><tr>" + cfg.header.map((h, i) => `<th${i ? ' class="text-end"' : ""}>${h}</th>`).join("") + "</tr></thead>";
        const body = rows.map((row) => {
            const cells = id === "products"
                ? [`${row.value} ${row.unit}`, vnd.format(row.revenue)]
                : [cfg.format(row.value, row)];
            return "<tr><td></td>" + cells.map((c) => `<td class="text-end">${c}</td>`).join("") + "</tr>";
        }).join("");
        table.innerHTML = head + "<tbody>" + body + "</tbody>";
        // Tên (khách/sản phẩm) do người dùng nhập -> gán bằng textContent để tránh chèn HTML
        table.querySelectorAll("tbody tr").forEach((tr, i) => { tr.firstElementChild.textContent = rows[i].label; });
    }

    Object.entries(CONFIG).forEach(([id, cfg]) => {
        const rows = charts[id] || [];
        const wrapper = document.querySelector(`[data-chart="${id}"]`);
        const table = document.querySelector(`[data-chart-table="${id}"]`);
        if (!wrapper) return;
        if (table) fillTable(table, id, rows, cfg);

        if (!rows.some((row) => row.value > 0)) {
            wrapper.classList.add("d-none");
            document.querySelector(`[data-chart-empty="${id}"]`)?.classList.remove("d-none");
            return;
        }
        if (cfg.horizontal) wrapper.style.height = Math.max(160, rows.length * 44 + 40) + "px";

        const valueAxis = {
            beginAtZero: true,
            grid: { color: GRID, drawTicks: false },
            border: { display: false },
            ticks: { callback: cfg.tick, precision: cfg.integer ? 0 : undefined, padding: 6 },
        };
        const categoryAxis = { grid: { display: false }, border: { color: GRID }, ticks: { padding: 4 } };

        new Chart(wrapper.querySelector("canvas"), {
            type: "bar",
            data: {
                labels: rows.map((row) => row.label),
                datasets: [{
                    data: rows.map((row) => row.value),
                    backgroundColor: PRIMARY,
                    hoverBackgroundColor: css.getPropertyValue("--sc-primary-hover").trim() || PRIMARY,
                    borderRadius: 4,
                    borderSkipped: "start",
                    maxBarThickness: cfg.horizontal ? 22 : 36,
                }],
            },
            options: {
                indexAxis: cfg.horizontal ? "y" : "x",
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 400 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        displayColors: false,
                        callbacks: { label: (ctx) => cfg.format(ctx.parsed[cfg.horizontal ? "x" : "y"], rows[ctx.dataIndex]) },
                    },
                },
                scales: cfg.horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
            },
        });
    });
})();
