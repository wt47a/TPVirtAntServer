from http.server import BaseHTTPRequestHandler, HTTPServer
import ssl
import json
import threading
import logging
import time
from urllib.parse import urlparse, parse_qs


from .__init__ import shared_data

# Definition of Variables

#BikeSpeed = 27.0 / 3.6  # m/s => 10km/h
# BikeSpeed = None
# lock = threading.Lock()

# Fictive Config of Treadmill

# ======================================================
# HTTPD
# ======================================================
class TPVHttpPRequestHandler(BaseHTTPRequestHandler):
    logger = None
    shared_data = None
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        path = parsed_path.path
        
        if path.startswith("/diagnostic/antstart"):
            response = "Starting ANT diagnostic mode..."
            shared_data.command_queue.put("ANT_START")
            self.logger.info("ANT diagnostic mode started.")
        elif path.startswith("/diagnostic/antstop"):
            response = "Stopping ANT diagnostic mode..."
            shared_data.command_queue.put("ANT_STOP")
            self.logger.info("ANT diagnostic mode stopped.")
            
        # Obsługa żądania GET
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"message": "This is a GET response", "status": "success"}
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        # Obsługa żądania POST
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data)
            if isinstance(data, list):
                data = data[0]  # Pobierz pierwszy element, jeśli to lista

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"message": "JSON received successfully", "received_data": data}).encode("utf-8")
            )
        
            if TPVHttpPRequestHandler.logger:
                TPVHttpPRequestHandler.logger.debug(f"Received JSON: {data}")
        
            speed_rec = data['speed']
            speed_kmh = 3.6*speed_rec/1000.0
            time_recv = time.time()
            with self.shared_data.lock:
                self.shared_data.BikeSpeed = speed_kmh
                # update last_post_time in server
                self.shared_data.last_post_time = time_recv
                
            if TPVHttpPRequestHandler.logger:
                TPVHttpPRequestHandler.logger.debug(f"Speed [Recv]:{speed_rec} Speed [km/h]: {speed_kmh:.1f}")

        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))
    
    def log_message(self, format, *args):
        if TPVHttpPRequestHandler.logger:
            TPVHttpPRequestHandler.logger.debug("%s - - [%s] %s" % (
                self.client_address[0],
                self.log_date_time_string(),
                format % args
            ))


class TPVHttpServer:
    def __init__(self, ip: str, port: int, use_ssl: bool, certFilePath :str | None, keyFilePath :str | None, shared_data, logger):
        self.logger = logger.getChild("HttpServer")
        TPVHttpPRequestHandler.logger = self.logger.getChild("TPVHttpPRequestHandler")

        self.ip = ip
        self.port = port
        self.shared_data = shared_data
        
        self.httpd = HTTPServer((self.ip, self.port), TPVHttpPRequestHandler)
        # przekazanie shared_data do handlera poprzez instancję serwera
        TPVHttpPRequestHandler.shared_data = shared_data
        self.httpd.shared_data = shared_data
   
        # Tworzenie serwera
        if use_ssl:
            # # Certyfikatu SSL generation
            # private_key, cert_pem = generate_self_signed_cert()

            # # Write cert and key file
            # with open("cert.pem", "wb") as cert_file:
            #     cert_file.write(cert_pem)
            # with open("key.pem", "wb") as key_file:
            #     key_file.write(private_key)

            # Konfiguracja SSL
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            #context.load_cert_chain(certfile="config/cert-chain.pem", keyfile="config/key.pem")
            context.load_cert_chain(certfile = certFilePath, keyfile = keyFilePath)

            # Owijanie serwera w SSL
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
            
        self.thread = None
        
    def start(self):
        self.thread = threading.Thread(target=self._serve)
        self.thread.start()
    
    def _serve(self):
        if self.logger.isEnabledFor(logging.INFO):
            actual_ip, actual_port = self.httpd.server_address
            self.logger.info(f"Server running on https://{actual_ip}:{actual_port}/")
        self.httpd.serve_forever()
        
    def stop(self):
        self.logger.info("Stopping HTTP server...")
        self.httpd.shutdown()
        self.thread.join()
        self.logger.info("HTTP server stopped.")
            
