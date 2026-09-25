from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    # API AJAX cho tính năng AI
    path(
        "api/customers/<int:pk>/suggest-reply/",
        views.api_suggest_reply,
        name="api_suggest_reply",
    ),
    path(
        "api/customers/<int:pk>/save-interaction/",
        views.api_save_interaction,
        name="api_save_interaction",
    ),
]
