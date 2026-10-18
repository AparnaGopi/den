from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_safe

from .urls import urlpatterns as app_urlpatterns


@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


urlpatterns = [path("health/", health, name="deployment-health"), *app_urlpatterns]
