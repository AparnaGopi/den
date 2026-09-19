from django.urls import include, path

from .views import (
    CurrentUserView,
    CustomerRegistrationView,
    LoginView,
    TokenRefreshView,
    VendorRegistrationView,
)

app_name = "api-v1"

urlpatterns = [
    path("", include("core.api.urls")),
    path("auth/register/customer/", CustomerRegistrationView.as_view(), name="register-customer"),
    path("auth/register/vendor/", VendorRegistrationView.as_view(), name="register-vendor"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", CurrentUserView.as_view(), name="current-user"),
]