from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/customer/", views.customer_dashboard, name="customer-dashboard"),
    path("dashboard/vendor/", views.vendor_dashboard, name="vendor-dashboard"),
]