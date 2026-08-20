from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from businesses.models import Business


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("아이디 또는 비밀번호가 올바르지 않습니다.")
        if not user.is_active:
            raise serializers.ValidationError("비활성화된 계정입니다.")

        attrs["user"] = user
        return attrs


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(required=True, min_length=3, max_length=150)
    password = serializers.CharField(required=True, min_length=8, write_only=True)
    business_name = serializers.CharField(required=False, default="카페비서 1호점", max_length=100)
    representative_name = serializers.CharField(required=False, default="대표자", max_length=50)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 존재하는 아이디입니다.")
        return value

    def validate_password(self, value):
        # Django 기본 검증기(길이/흔한 비밀번호/숫자만 등)를 통과시킨다.
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],
        )
        # 가입 즉시 기본 사업장 생성 및 유저 매핑
        business = Business.objects.create(
            owner=user,
            business_name=validated_data.get("business_name", "카페비서 1호점"),
            representative_name=validated_data.get("representative_name", "대표자"),
            business_status="RUNNING",
            tax_type="일반과세자",
            tax_type_code="01",
            is_demo=False,
        )
        return user, business


class UserBusinessItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "business_name", "representative_name", "tax_type", "is_demo"]


class UserProfileSerializer(serializers.ModelSerializer):
    businesses = UserBusinessItemSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "businesses"]
