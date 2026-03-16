"""Public auth views — proxy login to the SuperAdmin API."""
import logging

import requests as http_requests
from django.conf import settings
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class LoginProxyView(APIView):
    """Proxy login requests to the Celiyo SuperAdmin API."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        superadmin_url = getattr(
            settings, "SUPERADMIN_URL", "https://admin.celiyo.com"
        ).rstrip("/")
        login_url = f"{superadmin_url}/api/auth/login/"

        try:
            resp = http_requests.post(
                login_url,
                json=serializer.validated_data,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
        except http_requests.ConnectionError:
            logger.error("Cannot connect to SuperAdmin API at %s", login_url)
            return Response(
                {"error": "Authentication service unavailable", "code": "SERVICE_UNAVAILABLE"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except http_requests.Timeout:
            logger.error("SuperAdmin API timed out")
            return Response(
                {"error": "Authentication service timed out", "code": "SERVICE_TIMEOUT"},
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )

        # Forward the upstream response as-is
        return Response(resp.json(), status=resp.status_code)
