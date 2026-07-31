FROM python:3.12-slim

WORKDIR /srv

# curl_cffi (dependência do fli) precisa de libs de sistema para
# simular o fingerprint TLS de um browser real -- sem isso o Google
# bloqueia a requisição antes mesmo de chegar no endpoint.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 12000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:12000/saude || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12000", "--workers", "2"]
