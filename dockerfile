# ===== Stage 1: builder (Wolfi/Chainguard, nonroot) =====
FROM cgr.dev/chainguard/python:latest-dev AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# deps first (cache-friendly)
COPY requirements.txt .

# Install dependencies into a writable app-local path
RUN mkdir -p /app/site-packages && \
    python -m pip install --upgrade pip && \
    pip install --no-cache-dir --target /app/site-packages -r requirements.txt

# app code
COPY main.py /app/main.py

# ===== Stage 2: debug runtime (Wolfi/Chainguard, has shell/tools) =====
FROM cgr.dev/chainguard/python:latest-dev AS debug

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/site-packages \
    PORT=8080

WORKDIR /app

# Optional: uncomment if you want extra debug tools inside container
# RUN apk add --no-cache curl bind-tools iproute2 iputils busybox-extras procps

COPY --from=builder /app/site-packages /app/site-packages
COPY --from=builder /app/main.py       /app/main.py

USER nonroot
EXPOSE 8080
ENTRYPOINT ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

# ===== Stage 3: prod runtime (Distroless, tiny/secure) =====
FROM gcr.io/distroless/python3-debian12 AS prod

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/site-packages \
    PORT=8080

WORKDIR /app
USER nonroot:nonroot

COPY --from=builder /app/site-packages /app/site-packages
COPY --from=builder /app/main.py       /app/main.py

EXPOSE 8080
ENTRYPOINT ["/usr/bin/python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]