# --- stage 1: build the React SPA -> static files ---
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# --- stage 2: python app (serves the API + the built SPA) ---
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# LibreOffice (soffice) so Word (.docx) uploads can be rasterized; fonts for Hebrew.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

WORKDIR /app

# Install dependencies first (cached until pyproject/lock change). The project is a
# package (hatchling builds ./src), so src + README must be present for `uv sync`.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# The compiled SPA (served as static files by FastAPI at "/").
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8501
CMD ["uv", "run", "uvicorn", "doc2tests.api:app", \
     "--host", "0.0.0.0", "--port", "8501"]
