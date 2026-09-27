/* SmartCRM – JavaScript cho các tính năng AI (Vanilla JS, không cần build) */
(function (window, document) {
    "use strict";

    // ------------------------------------------------------------ helper dùng chung
    function getCookie(name) {
        const match = document.cookie.split(";").map(function (c) { return c.trim(); })
            .find(function (c) { return c.startsWith(name + "="); });
        return match ? decodeURIComponent(match.substring(name.length + 1)) : null;
    }

    function getCSRFToken() {
        const input = document.querySelector("input[name=csrfmiddlewaretoken]");
        return getCookie("csrftoken") || (input ? input.value : "");
    }

    /** Gửi POST JSON kèm CSRF; trả về dữ liệu JSON, ném Error (tiếng Việt) nếu lỗi. */
    async function postJSON(url, data) {
        let response;
        try {
            response = await fetch(url, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-CSRFToken": getCSRFToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify(data || {})
            });
        } catch (err) {
            throw new Error("Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại.");
        }

        let payload = null;
        try {
            payload = await response.json();
        } catch (err) {
            payload = null;
        }
        if (!response.ok || !payload || payload.ok === false) {
            let message = (payload && payload.error) || "Có lỗi xảy ra (mã " + response.status + "). Vui lòng thử lại.";
            if (response.status === 403 && !(payload && payload.error)) {
                message = "Phiên làm việc không hợp lệ (CSRF). Vui lòng tải lại trang.";
            }
            const error = new Error(message);
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    /** Bật/tắt trạng thái chờ cho nút: disable + spinner + chữ tạm thời. */
    function setLoading(button, isLoading, text) {
        if (!button) return;
        if (isLoading) {
            if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;
            button.disabled = true;
            button.setAttribute("aria-busy", "true");
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
                escapeHTML(text || "Đang xử lý…");
        } else {
            button.disabled = false;
            button.removeAttribute("aria-busy");
            if (button.dataset.originalHtml) {
                button.innerHTML = button.dataset.originalHtml;
                delete button.dataset.originalHtml;
            }
        }
    }

    function escapeHTML(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    /** Hiển thị Toast Bootstrap. type: success | danger | warning | info */
    function showToast(message, type) {
        const container = document.getElementById("toast-container");
        if (!container || !window.bootstrap) return;
        const colors = { success: "text-bg-success", danger: "text-bg-danger", warning: "text-bg-warning", info: "text-bg-primary" };
        const toastEl = document.createElement("div");
        toastEl.className = "toast align-items-center border-0 " + (colors[type] || colors.info);
        toastEl.setAttribute("role", type === "danger" ? "alert" : "status");
        toastEl.innerHTML = '<div class="d-flex"><div class="toast-body">' + escapeHTML(message) +
            '</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Đóng"></button></div>';
        container.appendChild(toastEl);
        const toast = new window.bootstrap.Toast(toastEl, { delay: type === "danger" ? 7000 : 4000 });
        toastEl.addEventListener("hidden.bs.toast", function () { toastEl.remove(); });
        toast.show();
    }

    // ------------------------------------------------ Tính năng: Gợi ý phản hồi email
    function initSuggestReply(card) {
        if (!card) return;
        const maxLength = parseInt(card.dataset.maxLength || "2000", 10);
        const messageInput = card.querySelector("#ai-message");
        const counter = card.querySelector("#ai-message-count");
        const toneSelect = card.querySelector("#ai-tone");
        const channelSelect = card.querySelector("#ai-channel");
        const suggestBtn = card.querySelector("#ai-suggest-btn");
        const retryBtn = card.querySelector("#ai-retry-btn");
        const resultBox = card.querySelector("#ai-result");
        const resultLabel = card.querySelector("#ai-result-label");
        const replyInput = card.querySelector("#ai-reply");
        const copyBtn = card.querySelector("#ai-copy-btn");
        const saveBtn = card.querySelector("#ai-save-btn");
        const timeline = document.getElementById("interaction-timeline");
        let lastAIReply = "";

        function updateCounter() {
            counter.textContent = messageInput.value.length;
        }
        messageInput.addEventListener("input", updateCounter);
        updateCounter();

        function readMessage() {
            const message = messageInput.value.trim();
            if (!message) {
                showToast("Vui lòng nhập tin nhắn của khách trước khi gợi ý.", "warning");
                messageInput.focus();
                return null;
            }
            if (message.length > maxLength) {
                showToast("Tin nhắn tối đa " + maxLength + " ký tự.", "warning");
                return null;
            }
            return message;
        }

        async function suggest(button) {
            const message = readMessage();
            if (!message) return;
            setLoading(button, true, "✨ AI đang soạn…");
            try {
                const data = await postJSON(card.dataset.suggestUrl, { message: message, tone: toneSelect.value });
                lastAIReply = data.reply;
                replyInput.value = data.reply;
                resultLabel.textContent = "Gợi ý bởi " + (data.provider || "AI Gemini") +
                    (data.mock ? " (chế độ mô phỏng)" : "");
                resultBox.classList.remove("d-none");
                replyInput.focus();
                showToast("AI đã soạn xong gợi ý. Bạn có thể chỉnh sửa trước khi lưu.", "success");
            } catch (err) {
                showToast(err.message, "danger");
            } finally {
                setLoading(button, false);
            }
        }

        suggestBtn.addEventListener("click", function () { suggest(suggestBtn); });
        retryBtn.addEventListener("click", function () { suggest(retryBtn); });

        copyBtn.addEventListener("click", async function () {
            const text = replyInput.value;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(text);
                } else {
                    replyInput.select();
                    document.execCommand("copy");
                }
                showToast("Đã sao chép nội dung phản hồi.", "success");
            } catch (err) {
                showToast("Không sao chép được, vui lòng bôi đen và sao chép thủ công.", "danger");
            }
        });

        saveBtn.addEventListener("click", async function () {
            const message = readMessage();
            if (!message) return;
            const finalReply = replyInput.value.trim();
            if (!finalReply) {
                showToast("Nội dung phản hồi đang trống.", "warning");
                replyInput.focus();
                return;
            }
            setLoading(saveBtn, true, "Đang lưu…");
            try {
                const data = await postJSON(card.dataset.saveUrl, {
                    message: message,
                    ai_suggested_reply: lastAIReply,
                    final_reply: finalReply,
                    channel: channelSelect.value
                });
                const empty = document.getElementById("timeline-empty");
                if (empty) empty.remove();
                timeline.insertAdjacentHTML("afterbegin", data.interaction_html);
                messageInput.value = "";
                replyInput.value = "";
                lastAIReply = "";
                updateCounter();
                resultBox.classList.add("d-none");
                showToast("Đã lưu vào lịch sử tương tác.", "success");
            } catch (err) {
                showToast(err.message, "danger");
            } finally {
                setLoading(saveBtn, false);
            }
        });
    }

    // ------------------------------------------------ Tính năng: Phân loại khách hàng AI
    function initClassifyCard(card) {
        if (!card) return;
        var analyzeUrl = card.dataset.analyzeUrl;
        var applyUrl = card.dataset.applyUrl;
        var classifyBtn = card.querySelector("#classify-btn");
        var emptyDiv = card.querySelector("#classify-empty");
        var resultDiv = card.querySelector("#classify-result");
        var sentimentBadge = card.querySelector("#classify-sentiment");
        var priorityBadge = card.querySelector("#classify-priority");
        var summaryEl = card.querySelector("#classify-summary");
        var actionsEl = card.querySelector("#classify-actions");
        var timeEl = card.querySelector("#classify-time");
        var providerLabel = card.querySelector("#classify-provider-label");
        var providerBadge = card.querySelector("#classify-provider-badge");
        var statusSuggest = card.querySelector("#classify-status-suggest");
        var suggestedLabel = card.querySelector("#classify-suggested-label");
        var applyBtn = card.querySelector("#apply-status-btn");
        var statusBadge = document.getElementById("customer-status-badge");

        var SENTIMENT_MAP = {
            positive: { text: "\ud83d\ude0a T\u00edch c\u1ef1c", cls: "text-bg-success" },
            neutral:  { text: "\ud83d\ude10 Trung l\u1eadp", cls: "text-bg-secondary" },
            negative: { text: "\ud83d\ude1f Ti\u00eau c\u1ef1c", cls: "text-bg-danger" }
        };
        var PRIORITY_MAP = {
            high:   { text: "Cao", cls: "text-bg-danger" },
            medium: { text: "Trung b\u00ecnh", cls: "text-bg-warning" },
            low:    { text: "Th\u1ea5p", cls: "text-bg-success" }
        };

        function renderResult(data, mock, provider) {
            var s = SENTIMENT_MAP[data.sentiment] || SENTIMENT_MAP.neutral;
            sentimentBadge.className = "badge " + s.cls;
            sentimentBadge.textContent = s.text;

            var p = PRIORITY_MAP[data.priority] || PRIORITY_MAP.medium;
            priorityBadge.className = "badge " + p.cls;
            priorityBadge.textContent = p.text;

            summaryEl.textContent = data.summary || "";
            actionsEl.innerHTML = "";
            (data.next_actions || []).forEach(function (action) {
                var li = document.createElement("li");
                li.textContent = action;
                actionsEl.appendChild(li);
            });
            timeEl.textContent = "Ph\u00e2n t\u00edch l\u00fac: " + (data.analyzed_at || "");
            var providerText = "Ph\u00e2n t\u00edch b\u1edfi " + (provider || "AI Gemini");
            if (mock) providerText += " (ch\u1ebf \u0111\u1ed9 m\u00f4 ph\u1ecfng)";
            providerLabel.textContent = providerText;
            providerBadge.textContent = providerText;

            if (data.suggested_status && data.suggested_status_display) {
                suggestedLabel.textContent = data.suggested_status_display;
                statusSuggest.classList.remove("d-none");
            } else {
                statusSuggest.classList.add("d-none");
            }

            if (emptyDiv) emptyDiv.classList.add("d-none");
            resultDiv.classList.remove("d-none");
        }

        if (classifyBtn) {
            classifyBtn.addEventListener("click", async function () {
                setLoading(classifyBtn, true, "\u2728 AI \u0111ang ph\u00e2n t\u00edch\u2026");
                try {
                    var payload = await postJSON(analyzeUrl, {});
                    renderResult(payload.data, payload.mock, payload.provider);
                    classifyBtn.innerHTML = "\u2728 Ph\u00e2n t\u00edch l\u1ea1i";
                    if (classifyBtn.dataset.originalHtml) {
                        classifyBtn.dataset.originalHtml = "\u2728 Ph\u00e2n t\u00edch l\u1ea1i";
                    }
                    showToast("AI \u0111\u00e3 ph\u00e2n t\u00edch xong kh\u00e1ch h\u00e0ng.", "success");
                } catch (err) {
                    showToast(err.message, "danger");
                } finally {
                    setLoading(classifyBtn, false);
                }
            });
        }

        if (applyBtn) {
            applyBtn.addEventListener("click", async function () {
                setLoading(applyBtn, true, "\u0110ang \u00e1p d\u1ee5ng\u2026");
                try {
                    var payload = await postJSON(applyUrl, {});
                    if (statusBadge) {
                        statusBadge.className = "badge " + payload.badge_class;
                        statusBadge.textContent = payload.status_display;
                    }
                    statusSuggest.classList.add("d-none");
                    showToast("Tr\u1ea1ng th\u00e1i kh\u00e1ch h\u00e0ng \u0111\u00e3 \u0111\u01b0\u1ee3c c\u1eadp nh\u1eadt.", "success");
                } catch (err) {
                    showToast(err.message, "danger");
                } finally {
                    setLoading(applyBtn, false);
                }
            });
        }
    }

    // ------------------------------------------------ Tính năng: Báo cáo AI
    function initReportPage(container) {
        if (!container) return;
        var generateUrl = container.dataset.generateUrl;
        var reportBtn = container.querySelector("#report-btn");
        var copyBtn = container.querySelector("#report-copy-btn");
        var resultDiv = container.querySelector("#report-result");
        var insightEl = container.querySelector("#report-insight");
        var providerEl = container.querySelector("#report-provider");
        var timeEl = container.querySelector("#report-time");

        if (reportBtn) {
            reportBtn.addEventListener("click", async function () {
                setLoading(reportBtn, true, "\u2728 AI \u0111ang t\u1ed5ng h\u1ee3p\u2026");
                try {
                    var payload = await postJSON(generateUrl, {});
                    insightEl.textContent = payload.insight || "";
                    var providerText = "Nh\u1eadn \u0111\u1ecbnh b\u1edfi " + (payload.provider || "AI Gemini");
                    if (payload.mock) providerText += " (ch\u1ebf \u0111\u1ed9 m\u00f4 ph\u1ecfng)";
                    providerEl.textContent = providerText;
                    timeEl.textContent = "T\u1ea1o l\u00fac: " + new Date(payload.generated_at).toLocaleString("vi-VN");
                    resultDiv.classList.remove("d-none");
                    if (copyBtn) copyBtn.classList.remove("d-none");
                    showToast("B\u00e1o c\u00e1o AI \u0111\u00e3 \u0111\u01b0\u1ee3c t\u1ea1o.", "success");
                } catch (err) {
                    showToast(err.message, "danger");
                } finally {
                    setLoading(reportBtn, false);
                }
            });
        }

        if (copyBtn) {
            copyBtn.addEventListener("click", async function () {
                var text = insightEl ? insightEl.textContent : "";
                try {
                    if (navigator.clipboard && window.isSecureContext) {
                        await navigator.clipboard.writeText(text);
                    } else {
                        var ta = document.createElement("textarea");
                        ta.value = text;
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand("copy");
                        document.body.removeChild(ta);
                    }
                    showToast("\u0110\u00e3 sao ch\u00e9p b\u00e1o c\u00e1o.", "success");
                } catch (err) {
                    showToast("Kh\u00f4ng sao ch\u00e9p \u0111\u01b0\u1ee3c. Vui l\u00f2ng ch\u1ecdn v\u00e0 sao ch\u00e9p th\u1ee7 c\u00f4ng.", "danger");
                }
            });
        }
    }

    // Xuất ra phạm vi toàn cục để các tính năng AI khác dùng lại
    window.SmartCRM = {
        getCookie: getCookie,
        postJSON: postJSON,
        setLoading: setLoading,
        showToast: showToast,
        escapeHTML: escapeHTML,
        initSuggestReply: initSuggestReply,
        initClassifyCard: initClassifyCard,
        initReportPage: initReportPage
    };
    window.postJSON = postJSON;
    window.setLoading = setLoading;
    window.showToast = showToast;
})(window, document);
