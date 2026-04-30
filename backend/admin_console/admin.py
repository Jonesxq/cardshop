from django.contrib import admin

from .models import AdminOperationLog, AdminProfile


@admin.register(AdminProfile)
class AdminProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__email", "user__username")


@admin.register(AdminOperationLog)
class AdminOperationLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor_email", "actor_role", "target_type", "target_id", "created_at")
    list_filter = ("action", "actor_role", "target_type")
    search_fields = ("actor_email", "action", "target_type", "target_id", "reason")
    readonly_fields = (
        "actor",
        "actor_email",
        "actor_role",
        "action",
        "target_type",
        "target_id",
        "reason",
        "before",
        "after",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
