# CineBusca — build frontend + servidor Python
# Local:  docker build -t cinebusca . && docker run --rm -p 8000:8000 -e TMDB_API_KEY=xxx cinebusca
# Render: conecta el repo y usa este Dockerfile (PORT lo inyecta Render)

# ── Stage 1: frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev=false || npm install
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

# ── Stage 2: runtime Python ───────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    nodejs \
    openssl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend + streams
COPY server.py ./
COPY streams ./streams

# Frontend compilado
COPY --from=frontend /app/dist ./dist

# Render y local escuchan en 0.0.0.0:$PORT
EXPOSE 8000

CMD ["python", "server.py"]
