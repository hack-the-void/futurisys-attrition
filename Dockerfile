# Image de l'API : Python 3.12, dépendances figées par uv.lock, utilisateur sans privilèges.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Les dépendances changent moins souvent que le code : cette couche reste en cache.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home api
USER api

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Les tables et les rôles sont créés avant, par le service init-db de docker-compose.yml :
# l'API n'a pas les droits pour le faire.
CMD ["uvicorn", "attrition_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
