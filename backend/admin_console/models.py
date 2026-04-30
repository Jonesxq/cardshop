from django.conf import settings
from django.db import models


class AdminProfile(models.Model):
    class Role(models.TextChoices):
        OPERATOR = "operator", "Operator"
        FINANCE = "finance", "Finance"
        SUPERADMIN = "superadmin", "Super Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_profile",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OPERATOR)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.role}"


class AdminOperationLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_operation_logs",
    )
    actor_email = models.EmailField(blank=True)
    actor_role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["action", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["actor_email"]),
        ]

    def __str__(self):
        return f"{self.action} by {self.actor_email}"
