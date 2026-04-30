from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
import logging
import random
import smtplib


User = get_user_model()
CODE_TTL_SECONDS = 10 * 60
logger = logging.getLogger(__name__)


def code_key(purpose, email):
    return f"email-code:{purpose}:{email.lower()}"


def make_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class EmailCodeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=["register", "reset"], default="register")

    def save(self):
        email = self.validated_data["email"].lower()
        purpose = self.validated_data["purpose"]
        if purpose == "register" and User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "该邮箱已注册"})
        if purpose == "reset" and not User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "该邮箱尚未注册"})
        code = f"{random.randint(0, 999999):06d}"
        cache.set(code_key(purpose, email), code, CODE_TTL_SECONDS)
        try:
            send_mail(
                subject="邮箱验证码",
                message=f"您的验证码是 {code}，10 分钟内有效。",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except (smtplib.SMTPException, OSError) as exc:
            cache.delete(code_key(purpose, email))
            logger.exception("Failed to send email verification code to %s", email)
            raise serializers.ValidationError(
                {"email": "验证码发送失败，请稍后再试或联系管理员"}
            ) from exc
        return {"message": "验证码已发送", "dev_code": code if settings.DEBUG else None}


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        error_messages={"min_length": "密码至少需要 8 位"},
    )
    code = serializers.CharField(min_length=6, max_length=6, write_only=True)

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("该邮箱已注册")
        return email

    def validate(self, attrs):
        expected = cache.get(code_key("register", attrs["email"].lower()))
        if expected != attrs["code"]:
            raise serializers.ValidationError({"code": "验证码无效或已过期"})
        return attrs

    def save(self):
        email = self.validated_data["email"].lower()
        user = User.objects.create_user(
            username=email,
            email=email,
            password=self.validated_data["password"],
        )
        cache.delete(code_key("register", email))
        return {"user": {"id": user.id, "email": user.email}, "tokens": make_tokens(user)}


class LoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["email"].strip()
        user = User.objects.filter(username__iexact=identifier).first()
        if not user:
            user = User.objects.filter(email__iexact=identifier).first()
        if user:
            user = authenticate(username=user.username, password=attrs["password"])
        if not user:
            raise serializers.ValidationError("账号或密码错误")
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        return {"user": {"id": user.id, "email": user.email}, "tokens": make_tokens(user)}


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        error_messages={"min_length": "密码至少需要 8 位"},
    )
    code = serializers.CharField(min_length=6, max_length=6, write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        expected = cache.get(code_key("reset", email))
        if expected != attrs["code"]:
            raise serializers.ValidationError({"code": "验证码无效或已过期"})
        try:
            attrs["user"] = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError({"email": "该邮箱尚未注册"}) from exc
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        cache.delete(code_key("reset", user.email.lower()))
        return {"message": "密码已重置"}
