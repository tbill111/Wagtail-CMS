/* SmartCRM – nhúng dashboard Apache Superset bằng Embedded SDK (Vanilla JS, không cần build) */
(function (window, document) {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const page = document.getElementById("analytics-page");
        if (!page) return;

        const status = document.getElementById("analytics-status");
        const container = document.getElementById("superset-container");
        const reloadButton = document.getElementById("analytics-reload");

        function showError(message) {
            container.classList.add("d-none");
            status.classList.remove("d-none");
            status.textContent = "⚠️ " + message;
        }

        async function load() {
            status.classList.remove("d-none");
            status.textContent = "Đang tải dashboard từ Superset…";
            container.classList.add("d-none");
            container.innerHTML = "";

            if (!window.supersetEmbeddedSdk) {
                showError("Không tải được thư viện nhúng Superset. Vui lòng kiểm tra mạng và thử lại.");
                return;
            }

            let first;
            try {
                first = await SmartCRM.postJSON(page.dataset.tokenUrl);
            } catch (err) {
                showError(err.message);
                return;
            }

            // Token đầu tiên dùng ngay; SDK tự gọi lại hàm này để gia hạn trước khi token hết hạn
            let cachedToken = first.token;
            function fetchGuestToken() {
                if (cachedToken) {
                    const token = cachedToken;
                    cachedToken = null;
                    return Promise.resolve(token);
                }
                return SmartCRM.postJSON(page.dataset.tokenUrl).then(function (data) { return data.token; });
            }

            container.classList.remove("d-none");
            try {
                await window.supersetEmbeddedSdk.embedDashboard({
                    id: first.uuid,
                    supersetDomain: page.dataset.supersetUrl,
                    mountPoint: container,
                    fetchGuestToken: fetchGuestToken,
                    dashboardUiConfig: {
                        hideTitle: true,
                        filters: { visible: true, expanded: false }
                    }
                });
                const frame = container.querySelector("iframe");
                if (frame) frame.title = "Dashboard Superset – Phân tích kinh doanh";
                status.classList.add("d-none");
            } catch (err) {
                showError("Không hiển thị được dashboard Superset. Vui lòng thử tải lại.");
            }
        }

        reloadButton.addEventListener("click", load);
        load();
    });
})(window, document);
