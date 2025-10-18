FROM python:3.12-slim

# Install system dependencies + bash
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    libusb-1.0-0 \
    libglib2.0-0 \
    libudev1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir openant

# Create working dir
WORKDIR /app
COPY src/main.py /app/

# Empty folder for certyficates
RUN mkdir -p /config

# Environment variables with default values
ENV APP_IP=0.0.0.0
ENV APP_PORT=5000
ENV CERT_FILE=/config/cert-chain.pem
ENV KEY_FILE=/config/key.pem
ENV LOG_LEVEL=INFO

# Default initial script
CMD ["bash", "-c", "python3 /app/main.py --ip $APP_IP --port $APP_PORT --cert-file $CERT_FILE --key-file $KEY_FILE --log-level $LOG_LEVEL"]

