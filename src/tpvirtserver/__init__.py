import threading

class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.BikeSpeed = 0
        self.running = False    # Flag for controlling main loop
        self.last_post_time = None

shared_data = SharedData()