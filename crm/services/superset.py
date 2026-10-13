"""Cấp quyền nhúng dashboard Apache Superset vào SmartCRM (Embedded SDK + guest token).

Trình duyệt không bao giờ thấy tài khoản Superset: Wagtail đăng nhập Superset phía máy chủ,
xin một guest token ngắn hạn chỉ dùng được cho đúng dashboard đã bật nhúng rồi trả cho trang.
"""

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 15


class SupersetError(Exception):
    """Lỗi khi làm việc với Superset; thông báo bằng tiếng Việt, hiển thị được cho nhân viên."""


def _call(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code == 404:
        raise SupersetError(
            f"Dashboard '{settings.SUPERSET_DASHBOARD_SLUG}' chưa có hoặc chưa bật nhúng. "
            "Hãy chạy: python superset/bootstrap_dashboard.py"
        )
    if response.status_code in (401, 403):
        raise SupersetError("Superset từ chối tài khoản cấu hình trong .env (SUPERSET_ADMIN_USER/PASSWORD).")
    if response.status_code >= 400:
        logger.error("Superset %s %s -> %s: %s", method, path, response.status_code, response.text[:300])
        raise SupersetError(f"Superset trả về lỗi {response.status_code}.")
    return response.json()


def embed_credentials(user):
    """Trả về ``{"uuid": ..., "token": ...}`` để Embedded SDK hiển thị dashboard cho ``user``."""
    if not settings.SUPERSET_ADMIN_PASSWORD:
        raise SupersetError("Chưa cấu hình Superset: thiếu SUPERSET_ADMIN_PASSWORD trong .env.")

    try:
        with httpx.Client(base_url=settings.SUPERSET_URL, timeout=TIMEOUT) as client:
            login = _call(client, "POST", "/api/v1/security/login", json={
                "username": settings.SUPERSET_ADMIN_USER, "password": settings.SUPERSET_ADMIN_PASSWORD,
                "provider": "db", "refresh": False,
            })
            client.headers["Authorization"] = f"Bearer {login['access_token']}"
            embedded = _call(client, "GET", f"/api/v1/dashboard/{settings.SUPERSET_DASHBOARD_SLUG}/embedded")
            uuid = embedded["result"]["uuid"]
            csrf = _call(client, "GET", "/api/v1/security/csrf_token/")["result"]
            token = _call(
                client, "POST", "/api/v1/security/guest_token/",
                headers={"X-CSRFToken": csrf, "Referer": settings.SUPERSET_URL},
                json={
                    "user": {
                        "username": user.get_username(),
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                    },
                    "resources": [{"type": "dashboard", "id": uuid}],
                    "rls": [],
                },
            )["token"]
    except httpx.HTTPError as exc:
        logger.warning("Không kết nối được Superset tại %s: %s", settings.SUPERSET_URL, exc)
        raise SupersetError(
            f"Không kết nối được Superset tại {settings.SUPERSET_URL}. Hãy chạy: docker compose up -d superset"
        ) from exc
    except (KeyError, ValueError) as exc:
        raise SupersetError("Superset trả về dữ liệu không đúng định dạng.") from exc
    return {"uuid": uuid, "token": token}
