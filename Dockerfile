# Python 3.11 Slim - Lightweight runtime for Indian IPO Listing-Day Trading System
FROM python:3.11-slim

# Prevent python from buffering stdout/stderr and writing bytecode
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=5050 \
    AUTH_USERNAME=Anish_5337 \
    AUTH_PASSWORD=Anish_9482

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure storage directories exist
RUN mkdir -p data/cache logs

# Expose web monitoring terminal port
EXPOSE 5050

# Native healthcheck using Python standard library with HTTP Basic Authorization
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, base64, os; req=urllib.request.Request('http://127.0.0.1:5050/api/status'); cred=f\"{os.getenv('AUTH_USERNAME','Anish_5337')}:{os.getenv('AUTH_PASSWORD','Anish_9482')}\".encode(); req.add_header('Authorization', 'Basic ' + base64.b64encode(cred).decode()); urllib.request.urlopen(req, timeout=3)" || exit 1

# Master runner defaults to auto-discovery or pre-seeded candidates on 0.0.0.0:5050
CMD ["python", "run_ipo_trading.py"]
