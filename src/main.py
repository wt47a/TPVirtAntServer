from http.server import BaseHTTPRequestHandler, HTTPServer
import ssl
import datetime
import json
import threading
import logging
import argparse
import time

from openant.easy.node import Node
from openant.easy.channel import Channel
from openant.base.commons import format_list

# Definition of Variables
NETWORK_KEY = [0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45]
Device_Type = 123  # 122 = BikeSpeed
Device_Number = 12775  # Change if you need.
Channel_Period = 8118   # 8118 counts (~4.04Hz, 4 messages/second)
#Channel_Period = 16236   # 16236 counts (~2.02Hz, 4 messages/second)
#Channel_Period = 32472   # 8118 counts (~1.01Hz, 4 messages/second)
Channel_Frequency = 57

#BikeSpeed = 27.0 / 3.6  # m/s => 10km/h
BikeSpeed = None
lock = threading.Lock()

# Fictive Config of Treadmill


##########################################################################
class AntBikeSpeed:
    def __init__(self):

        self.ANTMessageCount = 0
        self.ANTMessagePayload = [0, 0, 0, 0, 0, 0, 0, 0]

        # Init Variables, needed
        self.event_interval = 1.0 * Channel_Period / 32768

        self.LastBikeSpeed = 0.0
        
        self.TotalWheelRotations = 0.0
        self.LasFullTotalWheelRotations = 0
        self.LasFullTotalWheelRotationsInterval = 0
        self.LastBikeSpeedEventTimeFull = 0
        self.TotalIntervals = 0;

        self.TimeProgramStart = time.time()
        self.wheel_circumference = 2.105    # in meters

    def Create_Next_DataPage(self):
        global BikeSpeed
        # Define Variables
        self.ANTMessageCount += 1
        self.PageToggleCount = 0
        self.PageToggleBit = 0x00;  # or #0x80

        # Time Calculations
        self.TotalIntervals += 1
        
        BikeSpeedEventTimeFull = 1024.0 * self.TotalIntervals / self.event_interval
        
        with lock:
            # SPEED calculation
            avg_speed = 0.5 * (BikeSpeed + self.LastBikeSpeed) /3.6
            self.LastBikeSpeed = BikeSpeed
            distance_traveled = avg_speed / self.event_interval
            rotations = distance_traveled / self.wheel_circumference
            self.TotalWheelRotations += rotations
            # udate event time and weehl rotations in data frame, only after full rotations. Otherwise send the same event time and number of rotations
            #if int(self.TotalWheelRotations) != int(self.LasFullTotalWheelRotations):
            self.LastBikeSpeedEventTimeFull = int (BikeSpeedEventTimeFull)
            self.LasFullTotalWheelRotations = int(self.TotalWheelRotations)
            
            WheelRotations_H = (int(self.LasFullTotalWheelRotations) >> 8) & 0xFF
            WheelRotations_L = (int(self.LasFullTotalWheelRotations)) & 0xFF
            BikeSpeedEventTime_H = (int(self.LastBikeSpeedEventTimeFull) >> 8) & 0xFF
            BikeSpeedEventTime_L = (int(self.LastBikeSpeedEventTimeFull)) & 0xFF

        # prepare ANT+ message
        if self.ANTMessageCount <= 2:
            # technical message
            self.ANTMessagePayload[0] = 0x02  # DataPage 02 (Manufacturer ID)
            self.ANTMessagePayload[1] = 1  # Manufacturer ID
            self.ANTMessagePayload[2] = 0xFF  # Serial Number
            self.ANTMessagePayload[3] = 0xFF  # Serial Number
        elif self.ANTMessageCount <= 4:
            # technical message
            self.ANTMessagePayload[0] = 0x03  # DataPage 03 (Serial number and version)
            self.ANTMessagePayload[3] = 1  # HW Revision
            self.ANTMessagePayload[3] = 1  # SW Revision
            self.ANTMessagePayload[7] = 1  # Model Number
        else:
            # no technical data in standard page
            self.ANTMessagePayload[0] = 0x00  # Data Page 0 (Standard Data)
            self.ANTMessagePayload[1] = 0xFF
            self.ANTMessagePayload[2] = 0xFF
            self.ANTMessagePayload[3] = 0xFF
        
        # for speed sensor speed is always sent
        self.ANTMessagePayload[4] = BikeSpeedEventTime_L
        self.ANTMessagePayload[5] = BikeSpeedEventTime_H
        self.ANTMessagePayload[6] = WheelRotations_L
        self.ANTMessagePayload[7] = WheelRotations_H
            
        # Page toogle bit
        if (self.ANTMessageCount >> 2) & 0x01:
            self.ANTMessagePayload[0] ^= 0x80

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug(f"TotaInt:{self.TotalIntervals} BikeSpeed:{BikeSpeed:.2f} [m/s] avg_speed: {avg_speed:.2f} [m/s] distance_traveled: {distance_traveled:.2f} Rotations:{self.TotalWheelRotations:.2f}")

        # ANTMessageCount reset
        if self.ANTMessageCount > 68:
            self.ANTMessageCount = 0

        return self.ANTMessagePayload

    # TX Event
    def on_event_tx(self, data):
        ANTMessagePayload = self.Create_Next_DataPage()
        self.ActualTime = time.time() - self.TimeProgramStart

        # ANTMessagePayload = array.array('B', [1, 255, 133, 128, 8, 0, 128, 0])    # just for Debuggung pourpose

        self.channel.send_broadcast_data(
            self.ANTMessagePayload
        )  # Final call for broadcasting data
        
        #
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logging.debug("{:05.2f} TX:{}, {}, {} ".format(self.ActualTime, Device_Number, Device_Type, format_list(ANTMessagePayload)))

    # Open Channel
    def OpenChannel(self):

        self.node = Node()  # initialize the ANT+ device as node

        # CHANNEL CONFIGURATION
        self.node.set_network_key(0x00, NETWORK_KEY)  # set network key
        self.channel = self.node.new_channel(
            Channel.Type.BIDIRECTIONAL_TRANSMIT, 0x00, 0x00
        )  # Set Channel, Master TX
        self.channel.set_id(
            Device_Number, Device_Type, 5
        )  # set channel id as <Device Number, Device Type, Transmission Type>
        self.channel.set_period(Channel_Period)  # set Channel Period
        self.channel.set_rf_freq(Channel_Frequency)  # set Channel Frequency

        # Callback function for each TX event
        self.channel.on_broadcast_tx_data = self.on_event_tx

        try:
            self.channel.open()  # Open the ANT-Channel with given configuration
            self.node.start()
        except KeyboardInterrupt:
            logging.debug("Closing ANT+ Channel...")
            self.channel.close()
            self.node.stop()
        finally:
            logging.debug("Final checking...")
            # not sure if there is anything else we should check?! :)


###########################################################################################################################
def mainAntBroadcast():
    if logging.getLogger().isEnabledFor(logging.INFO):
        logging.info(f"ANT+ Send Broadcast Demo")

    ant_senddemo = AntBikeSpeed()

    try:
        ant_senddemo.OpenChannel()  # start
    except KeyboardInterrupt:
        logging.debug("Closing ANT+ Channel!")
    finally:
        logging.debug("Finally...")

    logging.debug("Close demo...")

# ======================================================
# HTTPD
# ======================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Obsługa żądania GET
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = {"message": "This is a GET response", "status": "success"}
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def do_POST(self):
        global BikeSpeed
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
        
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f"Received JSON: {data}")
        
            speed_rec = data['speed']
            speed_kmh = 3.6*speed_rec/1000
            with lock:
                BikeSpeed = speed_kmh
            
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f"Speed [Recv]:{speed_rec} Speed [km/h]: {speed_kmh:.1f}")

        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode("utf-8"))


def mainHttpd(ip: str, port: int, certFilePath :str, keyFilePath :str):
    # Tworzenie serwera
    server_address = (ip, port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)

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
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)


    if logging.getLogger().isEnabledFor(logging.INFO):
        actual_ip, actual_port = httpd.server_address
        logging.info(f"Server running on https://{actual_ip}:{actual_port}/")
    
    httpd.serve_forever()




if __name__ == "__main__":
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

    BikeSpeed = 0 / 3.6  # m/s => 10km/h
    tAnt = threading.Thread(target=mainAntBroadcast, args=())
    tHttpd = threading.Thread(target=mainHttpd, args=(args.ip, args.port, args.cert_file, args.key_file))


    tAnt.start()
    tHttpd.start()

