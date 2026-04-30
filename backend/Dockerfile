ARG PYTHON_IMAGE=m.daocloud.io/docker.io/library/python:3.13-alpine
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv \
    && uv pip install --system -e .

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_demo && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
