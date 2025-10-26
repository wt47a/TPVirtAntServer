import threading
import queue

class SharedData:
    def __init__(self):
        self.lock = threading.Lock()
        self.BikeSpeed = 0
        self.last_post_time = None
        self.command_queue = queue.Queue()
        
shared_data = SharedData()