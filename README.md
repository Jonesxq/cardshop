# AI 发卡商城

Vue 3 + Django 5.2 的虚拟商品自动发货商城，支持商品管理、库存卡密、订单支付、自动发货、用户体系，以及独立 Vue 后台 `/admin-console`。

## 技术栈

- 前端：Vue 3、Vite、Pinia、Element Plus
- 后端：Django 5.2、Django REST Framework、Simple JWT
- 数据库：MySQL 8，字符集 `utf8mb4`
- 缓存：Redis
- 部署：Docker Compose、Nginx、Gunicorn

## 入口地址

Docker 部署后默认访问：

- 商城前台：`http://服务器IP/`
- Vue 后台：`http://服务器IP/admin-console`
- Django Admin：`http://服务器IP/admin/`
- 健康检查：`http://服务器IP/api/health`

本地开发默认访问：

- 商城前台：`http://127.0.0.1:5173/`
- Vue 后台：`http://127.0.0.1:5173/admin-console`
- 后端接口：`http://127.0.0.1:8000/api/health`

## 快速部署

服务器只需要先装好 Docker 和 Docker Compose。推荐在项目根目录执行：

```bash
cp .env.production.example .env
```

然后编辑 `.env`，至少改掉这些值：

```env
DEBUG=false
SECRET_KEY=换成一段足够长的随机字符串
FERNET_KEY=
ALLOWED_HOSTS=你的域名或服务器IP
CSRF_TRUSTED_ORIGINS=https://你的域名
CORS_ALLOWED_ORIGINS=https://你的域名
HTTP_PORT=80

DB_NAME=cardshop
DB_USER=cardshop
DB_PASSWORD=换成强密码
MYSQL_ROOT_PASSWORD=换成强密码

SITE_URL=https://你的域名
PAYMENT_PROVIDER=dev
```

如果暂时没有域名，先用服务器 IP 部署时可以这样填：

```env
ALLOWED_HOSTS=你的服务器IP
CSRF_TRUSTED_ORIGINS=http://你的服务器IP
CORS_ALLOWED_ORIGINS=http://你的服务器IP
SITE_URL=http://你的服务器IP
PAYMENT_PROVIDER=dev
```

如果服务器的 80 端口已被面板或其他 Nginx 占用，可以改成例如：

```env
HTTP_PORT=8080
SITE_URL=http://你的服务器IP:8080
```

启动：

```bash
docker compose up -d --build
```

`2核2G` 小机建议直接沿用默认的小内存参数，不需要再额外放大 MySQL 和 Gunicorn。

首次启动时，后端容器会自动执行：

```bash
python manage.py migrate
python manage.py seed_demo
python manage.py collectstatic --noinput
```

查看服务状态：

```bash
docker compose ps
docker compose logs -f backend
```

验证：

```bash
curl http://127.0.0.1/api/health
```

返回 `{"status":"ok"}` 就说明后端已通。

## 默认管理员

执行过 `seed_demo` 后会创建并刷新这些管理员账号：

```text
账号：admin@example.com
密码：Admin12345!

账号：xqwd528467
密码：528467
```

`xqwd528467` 是固定超级管理员，可直接登录 `/admin-console`。

## 本地开发

推荐本地开发时前后端分开跑，MySQL 和 Redis 用本机服务或已有容器。

### 1. 准备环境变量

```powershell
Copy-Item .env.example .env
```

确认 `.env` 里的数据库指向本机：

```env
DB_ENGINE=mysql
DB_NAME=cardshop
DB_USER=cardshop
DB_PASSWORD=cardshop_dev_password
DB_HOST=127.0.0.1
DB_PORT=3306
REDIS_URL=redis://127.0.0.1:6379/0
SITE_URL=http://127.0.0.1:5173
PAYMENT_PROVIDER=dev
```

### 2. 启动 MySQL 和 Redis

如果没有现成 MySQL/Redis，可以直接跑临时开发容器：

```powershell
docker run -d --name cardshop-mysql `
  -p 3306:3306 `
  -e MYSQL_DATABASE=cardshop `
  -e MYSQL_USER=cardshop `
  -e MYSQL_PASSWORD=cardshop_dev_password `
  -e MYSQL_ROOT_PASSWORD=root-password `
  mysql:8.4 `
  --character-set-server=utf8mb4 `
  --collation-server=utf8mb4_unicode_ci

docker run -d --name cardshop-redis -p 6379:6379 redis:7-alpine
```

如果容器已存在：

```powershell
docker start cardshop-mysql cardshop-redis
```

### 3. 启动后端

```powershell
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

### 4. 启动前端

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173/admin-console`，用默认管理员登录。

## 常用维护命令

查看日志：

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

查看后端持久化日志：

```bash
docker compose exec backend tail -f /app/logs/app.log
docker compose exec backend tail -f /app/logs/error.log
docker compose exec backend tail -f /app/logs/security.log
```

排查接口问题时，优先记录响应头里的 `X-Request-ID`，再用这个 ID 到 backend 日志里搜索同一次请求。

重启服务：

```bash
docker compose restart backend frontend
```

重新执行迁移和种子数据：

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

进入 Django shell：

```bash
docker compose exec backend python manage.py shell
```

创建新的超级管理员：

```bash
docker compose exec backend python manage.py createsuperuser
```

备份 MySQL：

```bash
docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" cardshop' > cardshop.sql
```

恢复 MySQL：

```bash
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" cardshop' < cardshop.sql
```

## 支付配置

默认 `PAYMENT_PROVIDER=dev`，用于本地和测试环境模拟支付。

启用支付宝沙箱：

```env
PAYMENT_PROVIDER=alipay
ALIPAY_APP_ID=你的沙箱 app_id
ALIPAY_APP_PRIVATE_KEY=应用私钥
ALIPAY_PUBLIC_KEY=支付宝公钥
ALIPAY_GATEWAY_URL=https://openapi-sandbox.dl.alipaydev.com/gateway.do
ALIPAY_NOTIFY_URL=https://你的域名/api/payments/alipay/notify
ALIPAY_RETURN_URL=https://你的域名/orders
```

接真实支付回调时必须使用公网域名和 HTTPS，并确保 `SITE_URL`、`ALIPAY_NOTIFY_URL`、`ALIPAY_RETURN_URL` 都是正式地址。

## 邮件配置

注册、找回密码需要邮件验证码。QQ 邮箱示例：

```env
EMAIL_HOST=smtp.qq.com
EMAIL_PORT=465
EMAIL_USE_SSL=true
EMAIL_USE_TLS=false
EMAIL_HOST_USER=你的QQ邮箱
EMAIL_HOST_PASSWORD=QQ邮箱授权码
DEFAULT_FROM_EMAIL=你的QQ邮箱
```

注意：`EMAIL_HOST_PASSWORD` 填 QQ 邮箱授权码，不是 QQ 登录密码。

## 重要环境变量

| 变量 | 说明 |
| --- | --- |
| `DEBUG` | 生产必须为 `false` |
| `SECRET_KEY` | Django 密钥，生产必须改成长随机字符串 |
| `FERNET_KEY` | 卡密加密密钥；为空时由 `SECRET_KEY` 派生。生产上线后不要随意更换 |
| `ALLOWED_HOSTS` | 允许访问的域名或 IP，逗号分隔 |
| `CSRF_TRUSTED_ORIGINS` | HTTPS 域名需要配置，例如 `https://example.com` |
| `CORS_ALLOWED_ORIGINS` | 前端访问源，逗号分隔 |
| `HTTP_PORT` | Docker 对外暴露的前端端口，默认 `80` |
| `DB_ENGINE` | 默认 `mysql` |
| `DB_HOST` | Docker 内为 `mysql`，本地开发通常为 `127.0.0.1` |
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码，生产必须改强密码 |
| `REDIS_URL` | Docker 内为 `redis://redis:6379/0` |
| `SITE_URL` | 前端站点地址，用于支付跳转和回调 |
| `PAYMENT_PROVIDER` | `dev`、`alipay` 或其他已实现渠道 |

适合 `2核2G` 小机的保守参数：

```env
MYSQL_INNODB_BUFFER_POOL_SIZE=256M
MYSQL_MAX_CONNECTIONS=40
MYSQL_TMP_TABLE_SIZE=16M
MYSQL_MAX_HEAP_TABLE_SIZE=16M
MYSQL_TABLE_OPEN_CACHE=128
MYSQL_THREAD_CACHE_SIZE=8
REDIS_MAXMEMORY=128mb
GUNICORN_WORKERS=2
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=60
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEPALIVE=5
```

这组值偏向低并发、小流量、单机稳态。对当前这种卡密发货站点已经够用，后续只有在访问量明显上涨时再逐步放大。

## 验证和构建

后端：

```powershell
cd backend
uv run pytest -q
uv run python manage.py check
```

前端：

```powershell
cd frontend
npm run test:unit
npm run build
```

## 常见问题

### 登录提示账号或密码错误

先确认已经执行：

```bash
docker compose exec backend python manage.py seed_demo
```

本地开发则执行：

```powershell
cd backend
uv run python manage.py seed_demo
```

然后用 `xqwd528467 / 528467` 登录 `/admin-console`。

### 页面打开了，但接口 502

看后端日志：

```bash
docker compose logs -f backend
```

常见原因是 MySQL 密码、`DB_HOST`、数据库未初始化，或后端迁移还没跑完。

### 部署后静态文件或后台样式异常

重新收集静态文件并重启：

```bash
docker compose exec backend python manage.py collectstatic --noinput
docker compose restart frontend backend
```

### 中文显示乱码

确认 MySQL 使用 `utf8mb4`。本项目 Docker Compose 已设置：

```yaml
command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
```

已有旧数据乱码时，重新执行：

```bash
docker compose exec backend python manage.py seed_demo
```

## 目录结构

```text
backend/                 Django 后端
frontend/                Vue 前端和独立后台
deploy/nginx/            Nginx 配置
docker-compose.yml       单机部署编排
.env.example             本地开发环境变量模板
.env.production.example  生产环境变量模板
```
