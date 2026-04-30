from .models import AdminOperationLog
from .permissions import get_admin_role


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_operation(
    *,
    request,
    action,
    target=None,
    reason="",
    before=None,
    after=None,
):
    user = getattr(request, "user", None)
    actor = user if user and user.is_authenticated else None
    target_type = target.__class__.__name__ if target is not None else ""
    target_id = str(getattr(target, "pk", "")) if target is not None else ""

    return AdminOperationLog.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        actor_role=get_admin_role(actor),
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        before=before or {},
        after=after or {},
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
