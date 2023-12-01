import cv2
import os
import numpy as np
import ctypes
import fast_json
import zlib
import threading
import time
import requests
from flask import Flask, request
import struct 

from pyngrok import ngrok


def create_http_tunnel(Port):
    for tunnel in ngrok.get_tunnels():
        tunnel.kill()

    tunnel = ngrok.connect(Port)

    url = tunnel.public_url

    print(f"Created ngrok tunnel at {url}")

    return url


class ProcessFramesResult(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("size", ctypes.c_size_t),
    ]


lib = ctypes.CDLL(f"{os.getcwd()}\LivestreamProcessor.dll")

lib.process_frames.argtypes = [ctypes.c_char_p]
lib.process_frames.restype = ProcessFramesResult

lib.free_result.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
lib.free_result.restype = None

lib.clear_compressor_cache.argtypes = None
lib.clear_compressor_cache.restype = None

def process_frames(frames):
    serialized_frames = fast_json.dumps(frames).encode("utf-8")
    result = lib.process_frames(serialized_frames)
  
    data_size = result.size
    output = ctypes.string_at(result.data, data_size)
  
    lib.free_result(result.data, data_size)

    return output



def extract_video(video_path, frame_size, interpolation=cv2.INTER_LINEAR):
    output_folder = os.path.basename(video_path) + "_extract"
    frames_extracted = False

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    else:
        if len(os.listdir(output_folder)) > 0:
            print("exists")
            frames_extracted = True

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)  
    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        processed_frame = cv2.resize(frame, dsize=frame_size, interpolation=interpolation)
        frames.append(processed_frame.reshape(-1, 3).tolist())

    print(fps)
    cap.release()
    return frames, int(fps)


app = Flask(__name__)

@app.route('/clear_cache', methods = ["GET"]) 
def clear_cache():
    lib.clear_compressor_cache()
    return "OK!"

class RequestEvent:
    def __init__(self):
        self.event = threading.Event()
        self.data = None

    def wait(self):
        self.event.wait()
        return self.data

    def set(self, data):
        self.data = data
        self.event.set()

events = []

@app.route('/video_data', methods=["GET"])
def video_data():
    print("greh")

    new_event = RequestEvent()
    events.append(new_event)
    response = new_event.wait()
    print("sending")
    return response
    

def get_compressed_filename(video_path, resolution):
    return f"{video_path}_extract/{resolution[0]}x{resolution[1]}_compressed.blob"

def check_cached_file(video_path, frame_size):
    compressed_file_name = get_compressed_filename(video_path, frame_size)
    if os.path.isfile(compressed_file_name):
        return compressed_file_name
    return None

def inputs():
    os.system("cls")
    time.sleep(0.1)
    X = int(input("X: "))
    Y = int(input("Y: "))

    while True:
        file_name = input("File to play: ")
        compressed_file_name = check_cached_file(file_name, (X, Y))
        if compressed_file_name:
            with open(compressed_file_name, "rb") as file:
                header = file.read(12)  
                X, Y, fps = struct.unpack('iii', header)  
                processed = file.read()
        else:
            frames, fps = extract_video(file_name, (X, Y))
            print("compressing")
            processed = process_frames(frames)
            print("compressed")
            compressed_file_name = get_compressed_filename(file_name, (X, Y))
            with open(compressed_file_name, "wb") as file:
                header = struct.pack('iii', X, Y, fps)  
                file.write(header + processed)  
    
        jsonpayload = fast_json.dumps({
            "X": X,
            "Y": Y,
            "Fps": fps
        }).encode('utf-8')  
    
        payload_length = struct.pack('I', len(jsonpayload)) 
    
        payload = payload_length + jsonpayload + processed
        
        for event in events:
          print("sending")
          event.set(payload)
        events.clear()


PORT = 28323

requests.post("https://video.glorytosouthsud.repl.co/", json = {
  "Tunnel": create_http_tunnel(PORT)
})

thread = threading.Thread(target=inputs)
thread.daemon = True
thread.start()

app.run(host='0.0.0.0', port=PORT)
