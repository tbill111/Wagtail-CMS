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

    // Xuất ra phạm vi toàn cục để các tính năng AI khác dùng lại
    window.SmartCRM = {
        getCookie: getCookie,
        postJSON: postJSON,
        setLoading: setLoading,
        showToast: showToast,
        escapeHTML: escapeHTML,
        initSuggestReply: initSuggestReply
    };
    window.postJSON = postJSON;
    window.setLoading = setLoading;
    window.showToast = showToast;
})(window, document);
