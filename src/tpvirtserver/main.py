import threading
import logging
import argparse

from .__init__ import shared_data
from .ant_module import AntBikeSpeed
from .http_module import TPVHttpServer

BikeSpeed = None
lock = threading.Lock()

class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.ant_speed = 0

def main():
    # Konfiguracja parsera argumentów
    parser = argparse.ArgumentParser(description="Logowanie diagnostyczne")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Log level (default: INFO)")
    parser.add_argument("--ip", type=str, default="0.0.0.0", help="https server listening address")
    parser.add_argument("--port", type=int, default=5000, help="https server listening port")
    parser.add_argument("--cert-file", type=str, default="cert.pem", help="Path to certyficate file")
    parser.add_argument("--key-file", type=str, default="key.pem",help="Path to key file associated with certyficate")

    args = parser.parse_args()

    # Konfiguracja logowania
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    shared = SharedData()
    shared.BikeSpeed = 0 / 3.6  # m/s => 10km/h
    
    httpServer = TPVHttpServer(args.ip, args.port, args.cert_file, args.key_file, shared)
    antServer = AntBikeSpeed(shared)

    httpServer.start()
    antServer.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        antServer.stop()
        httpServer.stop()

if __name__ == "__main__":
    main()