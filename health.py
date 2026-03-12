from django.db import connection
from django.http import JsonResponse


def health(request):
    """
    Lightweight liveness + readiness check for Railway.
    Verifies the app is running and the DB is reachable.
    Railway expects a 200 response on /health/ after deploy.
    """
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "degraded", "db": db_ok}, status=status)
