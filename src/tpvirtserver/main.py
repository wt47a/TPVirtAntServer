import threading
import logging
import argparse
import signal
import sys
import time
import os

from .__init__ import shared_data
from .ant_module import AntBikeSpeed
from .http_module import TPVHttpServer

BikeSpeed = None
lock = threading.Lock()

class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.ant_speed = 0

def parse_args():
    # Konfiguracja parsera argumentów
    parser = argparse.ArgumentParser(description="TPVirt ANT+ Server")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], default="INFO", help="Log level (default: INFO)")
    parser.add_argument("--ip", type=str, default="0.0.0.0", help="https server listening address")
    parser.add_argument("--port", type=int, default=5000, help="https server listening port")
    parser.add_argument("--cert-file", type=str, default="cert.pem", help="Path to certyficate file")
    parser.add_argument("--key-file", type=str, default="key.pem",help="Path to key file associated with certyficate")
    parser.add_argument("--use-env", action="store_true", help="Force using environment variables instead of CLI arguments")
    
    args = parser.parse_args()

def get_config():
    args = parse_args()

    # Determine if we should use environment variables
    use_env = getattr(args, "use_env", False) or len(os.sys.argv) == 1
    
    if use_env:
        app_ip = os.getenv("APP_IP", "0.0.0.0")
        app_port = int(os.getenv("APP_PORT", "5000"))
        cert_file = os.getenv("CERT_FILE", "cert.pem")
        key_file = os.getenv("KEY_FILE", "key.pem")
        log_level = os.getenv("LOG_LEVEL", "INFO")
    else:
        app_ip = args.ip or os.getenv("APP_IP", "0.0.0.0")
        app_port = args.port or int(os.getenv("APP_PORT", "5000"))
        cert_file = args.cert_file or os.getenv("CERT_FILE", "cert.pem")
        key_file = args.key_file or os.getenv("KEY_FILE", "key.pem")
        log_level = args.log_level or os.getenv("LOG_LEVEL", "INFO")

    return app_ip, app_port, cert_file, key_file, log_level

def main():
    app_ip, app_port, app_cert_file, app_key_file, app_log_level = get_config()

    # Konfiguracja logowania
    logging.basicConfig(
        level=getattr(logging, app_log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logging.debug("Sturting up server ....")
    shared = SharedData()
    shared.BikeSpeed = 0 / 3.6  # m/s => 10km/h
    
    httpServer = TPVHttpServer(app_ip, app_port, app_cert_file, app_key_file, shared, logging.getLogger())
    antServer = AntBikeSpeed(shared, logging.getLogger())

    shared.running = True
    httpServer.start()
    antServer.start()

    
    runningLoopFlag = True

    def shutdown(signum, frame):
        nonlocal shared
        logging.info(f"Signal recieved {signum}, closing app...")
        shared.running = False

    # Rejestracja obsługi sygnałów
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        while shared.running:
            time.sleep(0.25)
            logging.info(f"Running flag {runningLoopFlag}")
    finally:
        httpServer.stop()
        antServer.stop()
        

if __name__ == "__main__":
    main()