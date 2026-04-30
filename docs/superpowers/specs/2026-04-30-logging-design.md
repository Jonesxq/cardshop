# 生产日志设计

## 目标

给 AI 发卡商城增加一套适合生产环境使用的运行日志，方便上线后追踪请求、定位异常、排查订单和支付链路问题。

日志需要同时写到 Docker 标准输出和持久化日志文件。`/admin-console` 不新增“系统运行日志”页面；现有后台“操作日志”继续只展示管理员业务审计记录。

## 当前项目情况

项目是 Django 5.2 + Django REST Framework 后端，Vue 3 + Vite 前端，使用 Docker Compose、Nginx、Gunicorn、MySQL、Redis 部署。

当前日志能力比较少：

- `accounts.serializers` 已经有一个模块 logger，用于记录邮件验证码发送失败。
- `admin_console.AdminOperationLog` 已经存储后台高权限操作的业务审计记录。
- 还没有 Django `LOGGING` 配置。
- 还没有请求 ID、请求/响应日志中间件、慢请求日志、统一异常日志、关键业务事件日志。
- Docker Compose 目前主要依赖后端容器进程输出查看日志。

本次工作要补的是“运行日志”和“业务链路排错日志”，不是替换现有的后台审计日志。

## 选定方案

使用结构化应用日志，同时输出到控制台和轮转文件：

- 标准输出始终开启，保证 `docker compose logs -f backend` 可以实时看日志。
- 文件日志在生产环境默认开启，写到可配置目录。
- 每个 HTTP 请求都有一个 `request_id`。如果客户端带了安全的 `X-Request-ID`，后端沿用；否则后端生成新的 ID。
- 响应头返回最终使用的 `X-Request-ID`。
- 请求、响应、异常、安全事件、关键业务事件都使用一致字段记录。
- 所有敏感数据在写日志前必须脱敏或排除。

这个方案适合当前单机 Docker 部署，不引入 ELK、Sentry、OpenTelemetry 这类外部系统。

## 不做的范围

本次不做：

- `/admin-console` 系统运行日志查看页面。
- 日志远程上报平台。
- 用户点击行为分析或前端埋点。
- 替换 `AdminOperationLog`。
- 记录卡密明文、密码、验证码、JWT token、私钥、支付密钥、完整敏感支付回调报文。

## 日志输出位置

运行日志写到这些位置：

- `stdout`：所有启用的应用日志，方便 Docker 收集和实时查看。
- `logs/app.log`：普通应用日志和业务事件日志，级别 `INFO` 及以上。
- `logs/error.log`：异常和错误日志，级别 `ERROR` 及以上。
- `logs/security.log`：安全相关日志，级别 `WARNING` 及以上，例如验签失败。

Docker 生产部署时，`logs/` 需要挂载为命名 volume，让文件日志在容器重启后仍然保留。即使没有挂载 volume，容器也应该能正常启动；只要目录存在且可写，文件日志就生效。

## 配置项

新增环境变量：

- `LOG_LEVEL`：默认 `INFO`。
- `LOG_TO_FILE`：`DEBUG=false` 时默认 `true`，`DEBUG=true` 时默认 `false`。
- `LOG_DIR`：本地默认 `BASE_DIR / "logs"`，Docker 里默认 `/app/logs`。
- `LOG_MAX_BYTES`：默认 `10485760`。
- `LOG_BACKUP_COUNT`：默认 `5`。
- `SLOW_REQUEST_MS`：默认 `1000`。

`.env.example` 和 `.env.production.example` 要说明这些变量。Docker Compose 要给 backend 服务挂载日志 volume 到生产日志目录。

## 请求 ID 和上下文

新增一个轻量请求上下文模块，用 Python `contextvars` 保存当前请求信息：

- `request_id`
- `user_id`
- `user_email`
- `client_ip`

新增 logging filter，把这些值自动注入每条日志。请求外产生的日志使用空值或 `-` 作为请求字段。

请求日志中间件负责：

1. 读取请求头 `X-Request-ID`。
2. 只接受长度较短、字符安全的 ID。
3. 请求头缺失或不安全时生成新的 UUID 风格 ID。
4. 调用 view 前写入请求上下文。
5. 请求结束时记录 method、path、status code、耗时、用户、IP、响应大小等信息。
6. 慢请求使用 `WARNING` 级别记录。
7. 未处理异常使用 `ERROR` 级别记录，并带堆栈。
8. 响应头写入 `X-Request-ID`。
9. 响应完成后清理请求上下文。

`/api/health` 健康检查不要产生大量 info 请求日志。可以跳过，也可以只打 `DEBUG`。

## 日志格式

使用 Docker 日志里也容易阅读和搜索的行格式：

```text
timestamp level logger request_id user_id client_ip event message key=value ...
```

实现上优先使用 Python 标准库 `logging.Formatter` 和 `extra={...}` 字段，不额外引入 JSON 日志依赖。字段名要稳定，方便搜索。

请求日志必须包含：

- `event`: `http_request`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `user_id`
- `client_ip`
- `request_id`

业务事件日志必须包含：

- `event`
- 相关实体 ID，例如 `order_no`、`payment_id`、`provider`、`product_id`
- 结果，例如 `success`、`rejected`、`ignored`、`failed`
- 必要且安全的原因或异常类型

## 敏感数据规则

日志禁止记录：

- 密码。
- 邮箱验证码。
- JWT access token 或 refresh token。
- 卡密明文或已解密的发货内容。
- `FERNET_KEY`、支付密钥、私钥、签名。
- 完整原始支付回调 payload。
- `Authorization` 请求头或 Cookie。

支付回调日志可以记录安全标识：

- 支付渠道 provider。
- `out_trade_no`。
- `trade_no`。
- 金额。
- 回调状态。
- 验签结果。

如果为了排错确实需要记录 payload，必须先经过 sanitizer，屏蔽常见敏感键，例如 `password`、`token`、`secret`、`key`、`sign`、`authorization`、`cookie`、`code`、`card`、`private`、`email`、`mobile`、`phone`。

## Logger 命名

按业务域使用清晰 logger 名称：

- `cardshop.request`：请求生命周期和慢请求。
- `cardshop.orders`：订单创建、重复待支付订单、库存预留、订单过期、发货结果。
- `cardshop.payments`：支付响应创建和支付完成事件。
- `cardshop.payments.notify`：支付回调验签、忽略状态、渠道失败、回调处理结果。
- `cardshop.security`：验签失败、可疑 request ID、显式处理的禁止访问场景。
- 现有模块 logger 继续可用，并继承同一套 handlers。

## 业务事件

这些位置需要补日志：

- 订单创建成功：记录订单号、商品 ID、数量、金额、用户 ID、过期时间。
- 重复待支付订单被拒绝：记录已有订单号、商品 ID、用户 ID 或游客联系方式哈希，结果为 `rejected`。
- 库存不足：记录商品 ID、请求数量，结果为 `rejected`。
- 待支付订单过期：记录过期订单数量和释放的预留卡数量。
- 支付响应创建：记录 provider、订单号、金额、mode。
- 支付回调验签失败：记录 provider、安全订单标识、IP，结果为 `rejected`，写入 `cardshop.security`。
- 支付回调状态被忽略：记录 provider、订单号、渠道状态，结果为 `ignored`。
- 支付成功完成：记录订单号、provider、交易号、金额、发货数量，结果为 `success`。
- 支付失败：金额不一致、订单过期、订单状态不可支付、订单不存在、库存异常等场景记录安全标识和原因。
- 邮件验证码发送失败：保留现有异常日志，并自动带上 request ID。

游客联系方式不能直接写入日志。如果需要关联游客行为，使用标准化联系方式加 `SECRET_KEY` 生成短哈希后记录。

## 后台审计边界

现有 `AdminOperationLog` 继续作为后台可见的业务审计来源。

运行日志可以记录某个高权限操作成功或失败，但 `/admin-console/logs` 仍然只返回 `AdminOperationLog`。运行日志可能包含异常堆栈和支付渠道细节，不能暴露在后台 UI 里。

## 部署说明

Docker Compose 要新增 backend 日志 volume：

```yaml
backend_logs:
```

并挂载到 backend 服务的 `/app/logs`。

backend Docker 启动命令可以继续执行 migrate、seed、collectstatic，然后启动 Gunicorn。Gunicorn access log 和 error log 要输出到 stdout/stderr，确保容器日志完整。

README 维护文档要补充：

- 用 `docker compose logs -f backend` 查看实时日志。
- 用 `docker compose exec backend tail -f /app/logs/app.log` 查看持久化应用日志。
- 用 `docker compose exec backend tail -f /app/logs/error.log` 查看异常日志。
- 用 `docker compose exec backend tail -f /app/logs/security.log` 查看验签和安全警告。
- 用户反馈接口问题时，用响应头里的 `X-Request-ID` 对应后端日志。

## 测试策略

后端测试要覆盖：

- 没有传入 `X-Request-ID` 时，中间件会生成并返回一个 ID。
- 传入合法 `X-Request-ID` 时，中间件会沿用。
- 传入不安全 `X-Request-ID` 时，中间件会丢弃并生成新 ID。
- 请求日志包含状态码和耗时。
- 未处理异常日志包含当前 request ID。
- `/api/health` 不产生大量 info 请求日志。
- 支付回调验签失败会向 `cardshop.security` 写 warning。
- 支付成功会向 `cardshop.payments` 写 info 业务事件。
- sanitizer 会屏蔽敏感字段。
- 游客联系方式哈希不会暴露原始联系方式。

验证命令：

```powershell
cd backend
uv run pytest -q
uv run python manage.py check
```

部署验证：

```bash
docker compose up -d --build
docker compose logs -f backend
docker compose exec backend ls -la /app/logs
docker compose exec backend tail -n 50 /app/logs/app.log
```

## 实施顺序

实现时按这些步骤推进：

1. 增加请求上下文、logging filter、sanitizer 和测试。
2. 增加请求日志中间件和测试。
3. 增加 Django 日志配置、环境变量、Docker volume 和文档。
4. 增加订单与支付业务事件日志和测试。
5. 跑完整后端测试和 Django system check。

