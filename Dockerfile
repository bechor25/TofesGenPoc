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

COPY .streamlit ./.streamlit

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "src/doc2tests/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
