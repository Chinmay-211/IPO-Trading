# Python 3.11 Slim - Lightweight runtime for Indian IPO Listing-Day Trading System
FROM python:3.11-slim

# Prevent python from buffering stdout/stderr and writing bytecode
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata \
    HOST=0.0.0.0 \
    PORT=5050

WORKDIR /app

# Install openssl and tzdata for Indian Standard Time and optional HTTPS
RUN apt-get update && apt-get install -y --no-install-recommends openssl tzdata && rm -rf /var/lib/apt/lists/*

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p data/cache data/certs logs

# Expose web monitoring terminal port
EXPOSE 5050

# Native healthcheck using Python standard library (supports both HTTP and HTTPS)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, ssl, base64, os; is_ssl=os.getenv('SSL_ENABLED','').lower() in ('true','1','yes'); scheme='https' if is_ssl else 'http'; ctx=ssl._create_unverified_context() if is_ssl else None; req=urllib.request.Request(f'{scheme}://127.0.0.1:5050/api/status'); cred=f\"{os.getenv('AUTH_USERNAME','admin')}:{os.getenv('AUTH_PASSWORD','admin')}\".encode(); req.add_header('Authorization', 'Basic ' + base64.b64encode(cred).decode()); urllib.request.urlopen(req, timeout=3, context=ctx)" || exit 1

# Master runner defaults to auto-discovery or pre-seeded candidates on 0.0.0.0:5050
CMD ["python", "run_ipo_trading.py"]
