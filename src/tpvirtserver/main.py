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
    return args

def get_config():
    args = parse_args()

    # Determine if we should use environment variables
    use_env = getattr(args, "use_env", False) or len(os.sys.argv) == 1
    
    if use_env:
        app_ip = os.getenv("APP_IP", "0.0.0.0")
        app_port = int(os.getenv("APP_PORT", "5000"))
        use_ssl = os.getenv("USE_SSL", "false").lower() in ("1", "true", "yes")
        cert_file = os.getenv("CERT_FILE", "cert.pem")
        key_file = os.getenv("KEY_FILE", "key.pem")
        log_level = os.getenv("LOG_LEVEL", "INFO")
    else:
        app_ip = args.ip
        app_port = args.port
        use_ssl = args.use_ssl
        cert_file = args.cert_file
        key_file = args.key_file
        log_level = args.log_level

    return app_ip, app_port, use_ssl, cert_file, key_file, log_level

def main():
    app_ip, app_port, use_ssl, app_cert_file, app_key_file, app_log_level = get_config()

    # Konfiguracja logowania
    logging.basicConfig(
        level=getattr(logging, app_log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    logging.debug("Sturting up server ....")
    
    shared_data.BikeSpeed = 0 / 3.6  # m/s => 10km/h
    
    httpServer = TPVHttpServer(app_ip, app_port, use_ssl, app_cert_file, app_key_file, shared_data, logging.getLogger())
    antServer = AntBikeSpeed(shared_data, logging.getLogger())

    shared_data.runningAnt = False
    shared_data.running = True
    httpServer.start()

    def shutdown(signum, frame):
        #nonlocal shared_data
        logging.info(f"Signal recieved {signum}, closing app...")
        shared_data.running = False

    # Rejestracja obsługi sygnałów
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    
    try:
        while shared_data.running:
            # conditions to reduce speed and stop channel if no data received from client, optionally release ant device while no data arriver for long time
            if hasattr(shared_data, "last_post_time") and shared_data.last_post_time is not None:
                now = time.time()
                elapsed = now - shared_data.last_post_time

                # if last data post was within 100s and ant channel is not running, start it
                if elapsed < 100:
                    with shared_data.lock:
                        if not antServer.isRunning():
                            shared_data.command_queue.put("ANT_START")

                # every 10s halve speed until 30s
                if elapsed > 3 and elapsed <= 30:
                    with shared_data.lock:
                        shared_data.BikeSpeed *= 0.5
                # after 30s set speed to 0
                elif elapsed > 30 and elapsed <= 300:
                    with shared_data.lock:
                        shared_data.BikeSpeed = 0.0
                # after 5 min (300s) set channel closed flag
                elif elapsed > 300:
                    with shared_data.lock:
                        shared_data.command_queue.put("ANT_STOP")
                
            # conditions controling ant start / stop on commands from queue
            if shared_data.command_queue.qsize() > 0:
                command = shared_data.command_queue.get()
                if command == "ANT_START":
                    if not antServer.isRunning():
                        logging.info("Starting ANT+ server...")
                        antServer.start()
                elif command == "ANT_STOP":
                    if antServer.isRunning():
                        logging.info("Stopping ANT+ server...")
                        shared_data.last_post_time = None
                        antServer.stop()
            
            logging.debug(f"Main loop running... BikeSpeed: {shared_data.BikeSpeed:.2f} [m/s]")
            time.sleep(0.25)
    except KeyboardInterrupt:
        shared_data.running = False
        logging.info("Keyboard interrupt received, closing app...")
    finally:
        httpServer.stop()
        antServer.stop()

if __name__ == "__main__":
    main()
