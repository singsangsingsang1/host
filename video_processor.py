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

    if not frames_extracted:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            processed_frame = cv2.resize(frame, dsize=frame_size, interpolation=interpolation)
            frames.append(processed_frame.reshape(-1, 3).tolist())

            frame_file = os.path.join(output_folder, f"frame_{len(frames)}.jpg")
            cv2.imwrite(frame_file, processed_frame)

    else:
        for i in range(len(os.listdir(output_folder))):
            frame_file = os.path.join(output_folder, f"frame_{i+1}.jpg")
            frame = cv2.imread(frame_file)
            frames.append(frame.reshape(-1, 3).tolist())

    cap.release()
    print("finished")
    return frames, fps


app = Flask(__name__)

@app.route('/clear_cache', methods = ["POST"]) 
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
    new_event = RequestEvent()
    events.append(new_event)
    response = new_event.wait()
  
    return response

def inputs():
  os.system("cls")
  time.sleep(0.1)
  X = int(input("X: "))
  Y = int(input("Y: "))
  
  while True:
    file_name = input("File to play: ")
    frames, fps = extract_video(file_name, (X, Y))
    processed = process_frames(frames) 
    print("compressed")
    jsonpayload = fast_json.dumps({
        "X": X,
        "Y": Y,
        "Fps": fps
    })
    
    payload = chr(len(jsonpayload)) + jsonpayload + processed.decode("utf-8") 
    
    for event in events:
      print("sending")
      event.set(payload)
    events.clear()


PORT = 28323

requests.post("https://video.glorytosouthsud.repl.co/", data = {
  "Tunnel": create_http_tunnel(PORT)
})

thread = threading.Thread(target=inputs)
thread.daemon = True
thread.start()

app.run(host='0.0.0.0', port=PORT)
