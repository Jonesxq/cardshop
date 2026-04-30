# Production Logging Design

## Goal

Add production-ready runtime logging to the AI card shop so operators can trace requests, diagnose failures, and inspect critical order and payment flows after deployment.

The logging system must write to both Docker standard output and persistent log files. It must not add a runtime-log viewer to `/admin-console`; the existing admin operation log page remains focused on business audit records only.

## Current Project Context

The project is a Django 5.2 + Django REST Framework backend with a Vue 3 + Vite frontend, deployed with Docker Compose, Nginx, Gunicorn, MySQL, and Redis.

Current logging is minimal:

- `accounts.serializers` already uses a module logger for email verification failures.
- `admin_console.AdminOperationLog` stores business audit records for privileged admin actions.
- There is no Django `LOGGING` configuration.
- There is no request ID, request/response logging middleware, slow request logging, or structured business event logging.
- Docker Compose currently exposes backend logs through the container process output only.

The new work should extend runtime observability without replacing the existing admin audit model.

## Chosen Approach

Use structured application logging with both console and rotating file handlers:

- Standard output remains always enabled so `docker compose logs -f backend` works for real-time troubleshooting.
- File logging is enabled by default in production and stores logs under a configurable directory.
- Every HTTP request gets a request ID. If the client sends `X-Request-ID`, the backend reuses it after validation; otherwise the backend generates a new ID.
- The response includes the effective `X-Request-ID`.
- Request, response, exception, security, and critical business events are logged with consistent fields.
- Sensitive data is explicitly redacted before logging.

This approach gives useful production diagnostics for a single-server Docker deployment without introducing external systems such as ELK, Sentry, or OpenTelemetry.

## Non-Goals

This work does not include:

- A system runtime log viewer in `/admin-console`.
- Shipping logs to a remote log platform.
- User behavior analytics or frontend click tracking.
- Replacing `AdminOperationLog`.
- Logging card secret plaintext, passwords, verification codes, JWT tokens, private keys, or full sensitive payment payloads.

## Log Destinations

Runtime logs should be written to:

- `stdout`: all enabled application logs, formatted for container log collection.
- `logs/app.log`: general application and business event logs at `INFO` and above.
- `logs/error.log`: errors and exceptions at `ERROR` and above.
- `logs/security.log`: security-relevant events at `WARNING` and above.

In Docker production, `logs/` should be mounted as a named volume so file logs survive container restarts. The backend container should still be usable without the mounted volume; if the directory exists and is writable, file logging works.

## Configuration

Add environment variables:

- `LOG_LEVEL`: default `INFO`.
- `LOG_TO_FILE`: default `true` when `DEBUG=false`, default `false` when `DEBUG=true`.
- `LOG_DIR`: default `BASE_DIR / "logs"` locally and `/app/logs` in Docker.
- `LOG_MAX_BYTES`: default `10485760`.
- `LOG_BACKUP_COUNT`: default `5`.
- `SLOW_REQUEST_MS`: default `1000`.

The `.env.example` and `.env.production.example` files should document these variables. Docker Compose should mount a backend log volume to the configured production path.

## Request ID And Context

Add a small request context module responsible for storing per-request values in Python `contextvars`:

- `request_id`
- `user_id`
- `user_email`
- `client_ip`

Add a logging filter that injects these values into each log record. Logs created outside a request should use empty or `-` values for request-scoped fields.

The request middleware should:

1. Read `X-Request-ID` from the incoming request.
2. Accept it only if it is short and contains safe characters.
3. Generate a new UUID-style request ID when the header is missing or unsafe.
4. Store request context before calling the view.
5. Log the request completion with method, path, status code, duration, user, IP, and response size when available.
6. Log slow requests at `WARNING`.
7. Log unhandled exceptions with stack trace at `ERROR`.
8. Add `X-Request-ID` to the response.
9. Clear request context after the response is built.

Health checks at `/api/health` should not create noisy info logs. They may be logged at `DEBUG` or skipped by the request middleware.

## Log Format

Use a consistent line format that remains readable in Docker logs:

```text
timestamp level logger request_id user_id client_ip event message key=value ...
```

The implementation can use Python `logging.Formatter` and `extra={...}` fields rather than adding a JSON logging dependency. Field values should be stable and searchable.

Required fields for request logs:

- `event`: `http_request`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `user_id`
- `client_ip`
- `request_id`

Required fields for business event logs:

- `event`
- entity identifiers such as `order_no`, `payment_id`, `provider`, or `product_id`
- outcome such as `success`, `rejected`, `ignored`, or `failed`
- reason or error class when useful and safe

## Sensitive Data Rules

Logs must not include:

- Passwords.
- Email verification codes.
- JWT access or refresh tokens.
- Card secret plaintext or decrypted delivery items.
- `FERNET_KEY`, payment keys, private keys, or signatures.
- Full raw payment callback payloads.
- Authorization headers or cookies.

Payment callback logs may include safe identifiers:

- provider
- `out_trade_no`
- `trade_no`
- amount
- callback status
- signature verification result

If a payload is logged for troubleshooting, it must pass through a sanitizer that masks common sensitive keys such as `password`, `token`, `secret`, `key`, `sign`, `authorization`, `cookie`, `code`, `card`, `private`, `email`, `mobile`, and `phone`.

## Logger Names

Use explicit logger names by domain:

- `cardshop.request`: request lifecycle and slow requests.
- `cardshop.orders`: order creation, duplicate pending orders, stock reservation, expiration, and delivery outcomes.
- `cardshop.payments`: payment response creation and payment completion events.
- `cardshop.payments.notify`: payment callback verification, ignored statuses, provider failures, and callback processing results.
- `cardshop.security`: invalid signatures, suspicious request IDs, forbidden access patterns when explicitly handled.
- Existing module loggers continue to work and inherit the same handlers.

## Business Events

Add logs at these points:

- Order creation succeeds: log order number, product ID, quantity, amount, user ID when present, and expiration time.
- Duplicate pending order is rejected: log existing order number, product ID, user ID or guest contact hash, and outcome `rejected`.
- Stock is insufficient: log product ID, requested quantity, and outcome `rejected`.
- Pending orders expire: log expired order count and released reserved card count.
- Payment response is built: log provider, order number, amount, and mode.
- Payment callback signature fails: log provider, safe order identifier if present, IP, and outcome `rejected` to `cardshop.security`.
- Payment callback status is ignored: log provider, order number, provider status, and outcome `ignored`.
- Payment completes successfully: log order number, provider, transaction ID, amount, quantity delivered, and outcome `success`.
- Payment completion fails because of amount mismatch, expired order, invalid state, missing order, or stock inconsistency: log safe identifiers and reason.
- Email verification send failure: keep the existing exception log and ensure request ID context is included automatically.

Guest contact values should not be logged directly. If linking guest activity is needed, log a short deterministic hash derived from the normalized contact and `SECRET_KEY`.

## Admin Audit Boundary

The existing `AdminOperationLog` remains the source of truth for admin-visible business audit records.

Runtime logs may mention that a privileged operation failed or completed, but `/admin-console/logs` continues to return only `AdminOperationLog` records. Runtime logs can contain stack traces and provider details, so they must stay outside the admin UI.

## Deployment Notes

Docker Compose should add a backend log volume:

```yaml
backend_logs:
```

and mount it into the backend service at `/app/logs`.

The backend Docker command can continue to run migrations, seed data, collect static files, and start Gunicorn. Gunicorn access and error logs should be directed to stdout/stderr so container logs remain complete.

README maintenance docs should mention:

- `docker compose logs -f backend` for live logs.
- `docker compose exec backend tail -f /app/logs/app.log` for persisted application logs.
- `docker compose exec backend tail -f /app/logs/error.log` for exceptions.
- `docker compose exec backend tail -f /app/logs/security.log` for signature and security warnings.
- Use `X-Request-ID` from API responses to correlate support reports with backend logs.

## Testing Strategy

Backend tests should cover:

- Middleware generates `X-Request-ID` when the request does not provide one.
- Middleware preserves a valid incoming `X-Request-ID`.
- Middleware rejects unsafe incoming request IDs and generates a replacement.
- Request logs include status code and duration.
- Unhandled exceptions include the active request ID in error logs.
- `/api/health` does not produce noisy info-level request logs.
- Payment callback invalid signatures write a warning to `cardshop.security`.
- Payment success writes an info event to `cardshop.payments`.
- Sanitization masks sensitive fields before they can be logged.
- Guest contact hashing does not expose raw contact values.

Verification commands:

```powershell
cd backend
uv run pytest -q
uv run python manage.py check
```

Deployment verification:

```bash
docker compose up -d --build
docker compose logs -f backend
docker compose exec backend ls -la /app/logs
docker compose exec backend tail -n 50 /app/logs/app.log
```

## Rollout Plan

The implementation should land in focused steps:

1. Add request context, logging filter, sanitizer, and tests.
2. Add request logging middleware and tests.
3. Add Django logging configuration, environment variables, Docker volume, and documentation.
4. Add order and payment business event logs with tests.
5. Run the full backend test suite and Django system checks.

