import threading

class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.BikeSpeed = 0

shared_data = SharedData()