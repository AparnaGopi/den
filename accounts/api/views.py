from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginSerializer, RegistrationSerializer, UserSerializer
from accounts.models import User


def token_response(user, status_code=status.HTTP_201_CREATED):
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        },
        status=status_code,
    )


class RegistrationView(APIView):
    permission_classes = (AllowAny,)
    registration_role = None

    def post(self, request):
        data = request.data.copy()
        if self.registration_role == User.Role.CUSTOMER:
            data.setdefault("role", User.Role.CUSTOMER)
        serializer = RegistrationSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["role"] != self.registration_role:
            return Response(
                {"role": [f"This endpoint only registers {self.registration_role} users."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return token_response(serializer.save())


class CustomerRegistrationView(RegistrationView):
    registration_role = User.Role.CUSTOMER


class VendorRegistrationView(RegistrationView):
    registration_role = User.Role.VENDOR


class LoginView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return token_response(serializer.validated_data["user"], status.HTTP_200_OK)


class TokenRefreshView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)