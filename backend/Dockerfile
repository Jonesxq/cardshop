FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i \
            -e 's|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' \
            -e 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
            -e 's|https://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
            -e 's|https://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' \
            /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i \
            -e 's|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' \
            -e 's|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g' \
            -e 's|http://security.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g' \
            -e 's|https://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
            -e 's|https://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' \
            -e 's|https://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
            /etc/apt/sources.list; \
    fi; \
    apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system -e .

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
