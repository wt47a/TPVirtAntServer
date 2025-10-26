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
# Ant+ Bike Speed server implementation
# (dłuższy opis zastąpiony docstringiem wewnątrz klasy)
###########################################################################
class AntBikeSpeed:
    """ANT+ Bike Speed server manager.

    This class initializes and runs an ANT+ Node and its transmit Channel,
    generates periodic data frames with speed and wheel-rotation information
    and broadcasts them.

    Key points:
    - start() configures the Node and Channel and starts the transmit thread.
    - stop() stops the Node and closes the Channel; both methods are idempotent.
    - Speed values are read from an injected ``shared_data`` object
        (``shared_data.BikeSpeed``) and should be accessed under
        ``shared_data.lock``.

    Public methods:
    - start(): start the ANT+ transmission.
    - stop(): stop the ANT+ transmission and free resources.
    - isRunning(): return True when the node/thread are active.

    Usage example::
            srv = AntBikeSpeed(shared_data, logger)
            srv.start()
            # update shared_data.BikeSpeed (in km/h) under shared_data.lock
            srv.stop()

    Implementation notes:
    - Frame content is prepared in ``Create_Next_DataPage_Speed()``.
    - Rotation counters and event timestamps are stored locally in the
        object state.
    """

    def __init__(self, shared_data, logger):
        """Initialize AntBikeSpeed instance.

        Parameters
        ----------
        shared_data : object
            Shared data object that must provide ``BikeSpeed`` (km/h) and a
            ``lock`` for thread-safe access.
        logger : logging.Logger
            Parent logger; a child logger ``AntServer`` will be created.

        Attributes
        ----------
        ANTMessageCount_Speed : int
            Counter for ANT+ bike speed sensor frames. Used to differentiate frame types
            according to the protocol (some frames contain technical data).
        ANTMessagePayload_Speed : list
            Current ANT+ data frame for bike speed sensor (8 bytes).
        event_interval : float
            Time (in seconds) between consecutive speed measurement events. Used to
            convert speed into wheel rotations since the last frame transmission.
        LastBikeSpeed : float
            Last recorded bike speed (in km/h).
        TotalWheelRotations : float
            Total number of wheel rotations since ANT+ server start.
        LasFullTotalWheelRotations : int
            Last complete wheel rotation count (integer part of TotalWheelRotations).
            Used to calculate rotations since last frame transmission.
        LasFullTotalWheelRotationsInterval : int
            Timestamp of last complete wheel rotation (integer part). Used to
            calculate rotations since last frame transmission.
        LastBikeSpeedEventTimeFull : int
            Timestamp of last bike speed calculation event (in ANT+ time units).
        TotalIntervals : int
            Total count of speed measurement intervals since ANT+ server start.
        TimeProgramStart : float
            Program start time (in seconds since epoch).
        wheel_circumference : float
            Bike wheel circumference (in meters); used to convert speed into
            wheel rotations.
        node : openant.easy.node.Node or None
            ANT+ Node managing the channels.
        channel : openant.easy.channel.Channel or None
            ANT+ channel for transmitting bike speed data.
        lock : threading.Lock
            Lock protecting start/stop/creation of node and channel.
        """
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
        # mark thread as not running
        self.node = None
        self.channel = None
        # lock to protect start/stop/creation of node and channel
        self.lock = threading.Lock()


    def Create_Next_DataPage_Speed(self):
        """Generate the next ANT+ data page for the speed sensor.

        The method reads the current speed from ``shared_data.BikeSpeed`` (under
        ``shared_data.lock``), computes distance and wheel rotations since the
        last interval, updates internal counters and returns an 8-byte payload
        suitable for broadcasting via the ANT+ channel.

        Returns
        -------
        list
            8-byte list representing the ANT+ message payload.
        """
        # Define Variables
        self.ANTMessageCount_Speed += 1
        self.PageToggleCount = 0
        self.PageToggleBit = 0x00;  # or #0x80

        # Time Calculations
        self.TotalIntervals += 1
        
        BikeSpeedEventTimeFull = 1024.0 * self.TotalIntervals / self.event_interval
        
        with self.shared_data.lock:
            # SPEED calculation
            avg_speed = 0.5 * (self.shared_data.BikeSpeed + self.LastBikeSpeed) /3.6
            self.LastBikeSpeed = self.shared_data.BikeSpeed
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
            self.ANTMessagePayload_Speed[0] = 0x02  # DataPage 02 (Manufacturer ID)
            self.ANTMessagePayload_Speed[1] = 1  # Manufacturer ID
            self.ANTMessagePayload_Speed[2] = 0xFF  # Serial Number
            self.ANTMessagePayload_Speed[3] = 0xFF  # Serial Number
        elif self.ANTMessageCount_Speed <= 4:
            # technical message
            self.ANTMessagePayload_Speed[0] = 0x03  # DataPage 03 (Serial number and version)
            self.ANTMessagePayload_Speed[3] = 1  # HW Revision
            self.ANTMessagePayload_Speed[3] = 1  # SW Revision
            self.ANTMessagePayload_Speed[7] = 1  # Model Number
        else:
            # no technical data in standard page
            self.ANTMessagePayload_Speed[0] = 0x00  # Data Page 0 (Standard Data)
            self.ANTMessagePayload_Speed[1] = 0xFF
            self.ANTMessagePayload_Speed[2] = 0xFF
            self.ANTMessagePayload_Speed[3] = 0xFF
        
        # for speed sensor speed is always sent
        self.ANTMessagePayload_Speed[4] = BikeSpeedEventTime_L
        self.ANTMessagePayload_Speed[5] = BikeSpeedEventTime_H
        self.ANTMessagePayload_Speed[6] = WheelRotations_L
        self.ANTMessagePayload_Speed[7] = WheelRotations_H
            
        # Page toogle bit
        if (self.ANTMessageCount_Speed >> 2) & 0x01:
            self.ANTMessagePayload_Speed[0] ^= 0x80

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"TotaInt:{self.TotalIntervals} BikeSpeed:{self.shared_data.BikeSpeed:.2f} [m/s] avg_speed: {avg_speed:.2f} [m/s] distance_traveled: {distance_traveled:.2f} Rotations:{self.TotalWheelRotations:.2f}")

        # ANTMessageCount_Speed reset
        if self.ANTMessageCount_Speed > 68:
            self.ANTMessageCount_Speed = 0

        return self.ANTMessagePayload_Speed

    def on_event_tx(self, data):
        """Callback invoked for each TX event from the ANT channel.

        Parameters
        ----------
        data : bytes or object
            Event data provided by the openant library (ignored by this
            implementation). The method prepares the next data page and
            broadcasts it via the channel.
        """
        ANTMessagePayload_Speed = self.Create_Next_DataPage_Speed()
        self.ActualTime = time.time() - self.TimeProgramStart

        # ANTMessagePayload_Speed = array.array('B', [1, 255, 133, 128, 8, 0, 128, 0])    # just for Debuggung pourpose

        self.channel.send_broadcast_data(
            self.ANTMessagePayload_Speed
        )  # Final call for broadcasting data
        
        #
        self.logger.debug("{:05.2f} TX:{}, {}, {} ".format(self.ActualTime, Device_Number, Device_Type, format_list(ANTMessagePayload_Speed)))

    def start(self):
        """Start the ANT+ server in a thread-safe manner.

        This function is concurrency-safe: it uses ``self.lock`` to prevent
        races with ``stop()`` or other ``start()`` calls. If an active
        transmit thread already exists the call will be ignored. If resources
        exist but no transmit thread is alive, they are cleaned up and
        replaced.
        """
        with self.lock:
            try:
                # If a transmit thread is already running, do not overwrite it.
                if getattr(self, 'thread', None) and getattr(self, 'thread').is_alive():
                    self.logger.info("start() called but transmit thread already running - skipping start")
                    return
                # If no active thread exists but there are partially initialized
                # resources, stop and clean them up before creating a new instance.
                if self.node is not None or self.channel is not None or getattr(self, 'thread', None) is not None:
                    self.logger.info("start() called while a Node/Channel exists but thread not alive - cleaning up and replacing instance")
                    try:
                        if self.node:
                            self.node.stop()
                    except Exception:
                        self.logger.exception("Error stopping existing node")
                    try:
                        if getattr(self, 'thread', None):
                            # if thread is not alive, join and clear reference
                            self.thread.join(timeout=2)
                    except Exception:
                        self.logger.exception("Error joining existing thread")
                    try:
                        if self.channel:
                            self.channel.close()
                    except Exception:
                        self.logger.exception("Error closing existing channel")
                    # clear references before creating a fresh node
                    self.node = None
                    self.channel = None
                    self.thread = None

                # Create and configure a new node and channel
                self.node = Node()
                self.logger.info("ANT+ Server starting ...")

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

                #self.thread = threading.Thread(target=self.node.start, daemon=True)
                self.channel.open()
                self.thread = threading.Thread(target=self.node.start)
                self.thread.start()
            except Exception:
                self.logger.exception("Failed to start ANT+ Node")
                # ensure no partially initialized state remains
                try:
                    if self.node:
                        self.node.stop()
                except Exception:
                    pass
                try:
                    if getattr(self, 'thread', None):
                        self.thread = None
                except Exception:
                    pass
                try:
                    if self.channel:
                        self.channel = None
                except Exception:
                    pass

    def stop(self):
        """Stop the node and close the channel.

        This method acquires the same ``self.lock`` used by ``start()`` to
        ensure that stopping and starting cannot interleave and cause a
        race condition.
        """
        with self.lock:
            if self.node:
                try:
                    self.node.stop()
                except Exception:
                    self.logger.exception("Error stopping node")
                try:
                    if getattr(self, 'thread', None):
                        self.thread.join(timeout=2)
                except Exception:
                    self.logger.exception("Error joining thread during stop")
                self.node = None
                self.thread = None
            if self.channel:
                try:
                    self.channel.close()
                except Exception:
                    self.logger.exception("Error closing channel during stop")
                self.channel = None

    def isRunning(self):
        """Return True if the node transmit thread is active.

        Returns
        -------
        bool
            True when the node and thread exist and the thread is alive.
        """
        return self.node is not None and self.thread is not None and self.thread.is_alive()