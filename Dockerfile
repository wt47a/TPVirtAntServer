FROM python:3.12-slim

# Instalacja zależności systemowych + bash
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    libusb-1.0-0 \
    libglib2.0-0 \
    libudev1 \
    && rm -rf /var/lib/apt/lists/*

# Instalacja zależności Python
RUN pip install --no-cache-dir openant

# Utworzenie katalogów roboczych
WORKDIR /app
COPY HttpAntServer.py /app/

# Tworzymy pusty katalog na certyfikaty
RUN mkdir -p /config

# Zmienne środowiskowe z domyślnymi wartościami
ENV APP_IP=0.0.0.0
ENV APP_PORT=5000
ENV CERT_FILE=/config/cert-chain.pem
ENV KEY_FILE=/config/key.pem
ENV LOG_LEVEL=INFO

# Domyślne polecenie uruchamiające aplikację
CMD ["bash", "-c", "python3 /app/HttpAntServer.py --ip $APP_IP --port $APP_PORT --cert-file $CERT_FILE --key-file $KEY_FILE --log-level $LOG_LEVEL"]

