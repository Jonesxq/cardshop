# Docker 镜像发布设计

## 目标

让其他用户可以通过预构建 Docker 镜像直接运行本项目。用户只需要复制生产环境变量模板、填写必要的密钥和域名/IP 配置，然后执行 `docker compose up -d`，不需要在本地构建应用镜像。

## 选定方案

采用偏生产部署的多容器方案：

- 发布一个后端应用镜像。
- 发布一个前端 Nginx 镜像，镜像内包含已构建好的 Vue 应用和反向代理配置。
- MySQL 和 Redis 继续使用标准镜像作为依赖服务。
- 使用 Docker Compose 作为运行约定，负责把四个服务连接起来。

这样不会把数据库这类持久化服务塞进应用镜像里，后续备份、升级和故障恢复会更清楚。

## 镜像模型

Compose 文件通过环境变量引用应用镜像，并提供可用的默认值：

- `CARDSHOP_BACKEND_IMAGE`
- `CARDSHOP_FRONTEND_IMAGE`

这两个变量都支持带 tag 的镜像名，所以项目维护者可以发布类似 `ghcr.io/<owner>/cardshop-backend:1.0.0` 和 `ghcr.io/<owner>/cardshop-frontend:1.0.0` 的版本化镜像。项目中会额外保留一个本地构建覆盖文件，方便维护者继续在本机构建和验证。

## 运行组件

### MySQL

MySQL 继续作为 Compose 管理的独立服务运行，使用标准镜像。数据持久化到 `mysql_data`。

### Redis

Redis 继续作为 Compose 管理的独立服务运行，使用标准镜像。数据持久化到 `redis_data`。

### 后端

后端服务拉取已发布的后端镜像。容器启动时读取 `.env`，连接 Compose 服务名 `mysql` 和 `redis`，执行数据库迁移、写入默认演示/管理员数据、收集静态文件，然后启动 Gunicorn。

### 前端

前端服务拉取已发布的前端镜像。它通过 Nginx 提供已构建好的 Vue 应用，把 `/api/` 和 `/admin/` 反向代理到后端，并通过共享的 `static_data` volume 提供 Django 收集后的静态文件。

## Compose 文件

主 `docker-compose.yml` 面向使用者优化：

- 后端和前端使用 `image:`；
- MySQL 和 Redis 保持现有方式；
- 保留健康检查、数据卷和端口映射；
- 不要求使用者本地构建应用镜像。

新增 `docker-compose.build.yml` 面向维护者：

- 恢复现有后端构建配置；
- 恢复现有前端构建配置；
- 支持用 `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build` 做本地构建验证。

## 配置

现有 `.env.production.example` 继续作为主要运行模板。它会新增可选的镜像变量，让使用者可以指定需要拉取的镜像仓库和 tag。

部署时仍然需要重点配置：

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `CORS_ALLOWED_ORIGINS`
- 数据库密码
- `SITE_URL`
- 启用支付和邮件功能时需要填写对应配置

## 文档

README 会补充两个流程：

1. 使用者部署：复制 `.env.production.example`，设置镜像名和必要配置，然后执行 `docker compose up -d`。
2. 维护者发布：构建后端/前端镜像，打 tag，推送到镜像仓库，并可选地在本地验证已发布镜像。

## 验证

实现完成后需要验证：

- 使用 `docker compose config` 检查主 Compose 配置可以正常渲染。
- 使用 `docker compose -f docker-compose.yml -f docker-compose.build.yml config` 检查本地构建覆盖配置可以正常渲染。
- 如果当前环境可用 Docker，验证后端和前端镜像可以构建成功。

如果当前环境适合完整启动容器，则启动 Compose 后确认 `http://127.0.0.1:<HTTP_PORT>/api/health` 返回 `{"status":"ok"}`。
