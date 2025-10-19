import threading
import logging
import time

from openant.easy.node import Node
from openant.easy.channel import Channel
from openant.base.commons import format_list

from .__init__ import shared_data

# Definition of Variables
NETWORK_KEY = [0xB9, 0xA5, 0x21, 0xFB, 0xBD, 0x72, 0xC3, 0x45]
Device_Type = 123  # 122 = BikeSpeed
Device_Number = 12775  # Change if you need.
Channel_Period = 8118   # 8118 counts (~4.04Hz, 4 messages/second)
#Channel_Period = 16236   # 16236 counts (~2.02Hz, 4 messages/second)
#Channel_Period = 32472   # 8118 counts (~1.01Hz, 4 messages/second)
Channel_Frequency = 57

#BikeSpeed = 27.0 / 3.6  # m/s => 10km/h
# BikeSpeed = None
# lock = threading.Lock()

# Fictive Config of Treadmill


##########################################################################
class AntBikeSpeed:
       
    def __init__(self, shared_data, logger):
        self.logger = logger.getChild("AntServer")
        
        self.shared_data = shared_data

        self.ANTMessageCount_Speed = 0
        self.ANTMessagePayload_Speed = [0, 0, 0, 0, 0, 0, 0, 0]

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


    def Create_Next_DataPage_Speed(self):
        # Define Variables
        self.ANTMessageCount_Speed += 1
        self.PageToggleCount = 0
        self.PageToggleBit = 0x00;  # or #0x80

        # Time Calculations
        self.TotalIntervals += 1
        
        BikeSpeedEventTimeFull = 1024.0 * self.TotalIntervals / self.event_interval
        
        with shared_data.lock:
            # SPEED calculation
            avg_speed = 0.5 * (shared_data.BikeSpeed + self.LastBikeSpeed) /3.6
            self.LastBikeSpeed = shared_data.BikeSpeed
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
        if self.ANTMessageCount_Speed <= 2:
            # technical message
            self.ANTMessagePayload[0] = 0x02  # DataPage 02 (Manufacturer ID)
            self.ANTMessagePayload[1] = 1  # Manufacturer ID
            self.ANTMessagePayload[2] = 0xFF  # Serial Number
            self.ANTMessagePayload[3] = 0xFF  # Serial Number
        elif self.ANTMessageCount_Speed <= 4:
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
        if (self.ANTMessageCount_Speed >> 2) & 0x01:
            self.ANTMessagePayload[0] ^= 0x80

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"TotaInt:{self.TotalIntervals} BikeSpeed:{shared_data.BikeSpeed:.2f} [m/s] avg_speed: {avg_speed:.2f} [m/s] distance_traveled: {distance_traveled:.2f} Rotations:{self.TotalWheelRotations:.2f}")

        # ANTMessageCount_Speed reset
        if self.ANTMessageCount_Speed > 68:
            self.ANTMessageCount_Speed = 0

        return self.ANTMessagePayload

    # TX Event
    def on_event_tx(self, data):
        ANTMessagePayload = self.Create_Next_DataPage_Speed()
        self.ActualTime = time.time() - self.TimeProgramStart

        # ANTMessagePayload = array.array('B', [1, 255, 133, 128, 8, 0, 128, 0])    # just for Debuggung pourpose

        self.channel.send_broadcast_data(
            self.ANTMessagePayload
        )  # Final call for broadcasting data
        
        #
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("{:05.2f} TX:{}, {}, {} ".format(self.ActualTime, Device_Number, Device_Type, format_list(ANTMessagePayload)))

    # Open Channel and start transmission
    #def OpenChannel(self):
    def start(self):

        self.node = Node()  # initialize the ANT+ device as node

        if self.logger.isEnabledFor(logging.INFO):
            self.logger.info(f"ANT+ Send Broadcast")

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
        finally:
            self.logger.debug("Closing ANT+ ...")

    def stop(self):
        if (self.channel):
            self.node.remove_channel(self.channel)
        self.node.stop()
        