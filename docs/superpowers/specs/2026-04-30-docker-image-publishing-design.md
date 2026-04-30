# Docker Image Publishing Design

## Goal

Make the project runnable by other users through prebuilt Docker images. A user should be able to copy the production environment template, set required secrets and host values, then run `docker compose up -d` without building application images locally.

## Chosen Approach

Use a production-style multi-container deployment:

- Publish a backend application image.
- Publish a frontend Nginx image containing the built Vue app and reverse proxy configuration.
- Continue using standard MySQL and Redis images as dependency services.
- Use Docker Compose as the runtime contract that wires the four services together.

This keeps persistent services out of the application images, which makes database backup, upgrades, and operational recovery clearer.

## Image Model

The Compose file will reference application images through environment variables with practical defaults:

- `CARDSHOP_BACKEND_IMAGE`
- `CARDSHOP_FRONTEND_IMAGE`

Both values will support tags, so the owner can publish versioned images such as `ghcr.io/<owner>/cardshop-backend:1.0.0` and `ghcr.io/<owner>/cardshop-frontend:1.0.0`. A separate build override file will preserve local build behavior for the project owner.

## Runtime Components

### MySQL

MySQL remains a Compose-managed service using a standard image. Data persists in `mysql_data`.

### Redis

Redis remains a Compose-managed service using a standard image. Data persists in `redis_data`.

### Backend

The backend service pulls the published backend image. It reads `.env`, connects to Compose service names `mysql` and `redis`, runs migrations, seeds default demo/admin data, collects static files, and starts Gunicorn.

### Frontend

The frontend service pulls the published frontend image. It serves the built Vue application with Nginx, proxies `/api/` and `/admin/` to the backend, and serves collected Django static files from the shared `static_data` volume.

## Compose Files

The main `docker-compose.yml` will be optimized for consumers:

- use `image:` for backend and frontend;
- keep MySQL and Redis unchanged;
- preserve health checks, volumes, and port mapping;
- avoid local build requirements.

A new `docker-compose.build.yml` will be added for maintainers:

- restore the existing backend build configuration;
- restore the existing frontend build configuration;
- allow local validation with `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build`.

## Configuration

The existing `.env.production.example` remains the primary runtime template. It will gain optional image variables so consumers can point Compose at the image registry and tag they should use.

Required deployment values remain:

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `CORS_ALLOWED_ORIGINS`
- database passwords
- `SITE_URL`
- payment and email settings when those features are enabled

## Documentation

The README will document two flows:

1. Consumer deployment: copy `.env.production.example`, set image names and required settings, run `docker compose up -d`.
2. Maintainer publishing: build backend/frontend images, tag them, push them to a registry, and optionally test the exact published images locally.

## Testing

Implementation verification should include:

- Compose configuration rendering with `docker compose config`.
- Local build override rendering with `docker compose -f docker-compose.yml -f docker-compose.build.yml config`.
- Image build validation for backend and frontend if Docker is available.

If a full container startup is practical in the current environment, verify `http://127.0.0.1:<HTTP_PORT>/api/health` returns `{"status":"ok"}` after Compose startup.
