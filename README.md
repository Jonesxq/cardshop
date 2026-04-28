# AI 虚拟商品发卡商城 MVP

这是一个前后端分离的虚拟商品自动发卡商城 MVP，后端使用 Django 5.2 + Django REST Framework，前端使用 Vue 3 + Vite + Element Plus。

## 功能概览

- 商品分类、公告、商品列表和库存展示
- 下单后预留库存，默认 15 分钟内有效
- 开发环境模拟支付，支付成功后自动发货
- 易支付兼容签名和异步通知接口
- 订单号或联系方式查询订单与卡密
- 邮箱验证码注册、登录、找回密码
- Django Admin 管理商品、分类、公告、卡密、订单和支付流水
- Docker Compose 单机部署配置

## 本地启动后端

```powershell
cd backend
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 0.0.0.0:8000
```

后端默认读取根目录 `.env`。本地推荐复用已有 MySQL/Redis 容器：

```powershell
docker exec lingyan-mysql sh -lc "mysql -uroot -p$MYSQL_ROOT_PASSWORD -e \"CREATE DATABASE IF NOT EXISTS cardshop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'cardshop'@'%' IDENTIFIED BY 'cardshop_dev_password'; GRANT ALL PRIVILEGES ON cardshop.* TO 'cardshop'@'%'; FLUSH PRIVILEGES;\""
```

然后运行 `uv run python manage.py migrate` 初始化表结构。

## 本地启动前端

```powershell
cd frontend
npm install
npm run dev
```

本地开发时，前端会通过 Vite 代理访问 `http://127.0.0.1:8000` 的后端接口。

## Docker

```powershell
Copy-Item .env.example .env
docker compose up --build
```

启动后访问：

- 前端首页：`http://localhost`
- 管理后台：`http://127.0.0.1:8000/admin`
- 健康检查：`http://localhost/api/health`

## 示例账号

运行 `seed_demo` 后会创建示例管理员账号：

- 邮箱：`admin@example.com`
- 密码：`Admin12345!`

## 常用验证命令

```powershell
cd backend
uv run pytest
uv run python manage.py check

cd ..\frontend
npm run build
```

## 登录与支付

- 购买、订单查询、模拟支付都需要先登录。
- 本地开发未配置易支付参数时，订单会进入模拟支付流程。
- QQ 邮箱发验证码：在 `.env` 填 `EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD`、`DEFAULT_FROM_EMAIL`。密码必须使用 QQ 邮箱“授权码”，不是 QQ 登录密码。
- 支付宝沙箱：把 `.env` 里的 `PAYMENT_PROVIDER` 改成 `alipay`，填写 `ALIPAY_APP_ID`、`ALIPAY_APP_PRIVATE_KEY`、`ALIPAY_PUBLIC_KEY`。未配置正式域名时，先验证能生成支付宝沙箱跳转链接。
- 接真实支付回调时，需要正式域名 HTTPS，并填写 `SITE_URL`、`ALIPAY_NOTIFY_URL`、`ALIPAY_RETURN_URL`。
