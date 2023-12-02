import os
import struct
import ctypes
import threading
import time
import requests
import cv2, fast_json
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from pyngrok import ngrok
import uvicorn

PORT = 28223
OUTPUT_FOLDER_SUFFIX = "_extract"
COMPRESSION_FILE_SUFFIX = "_compressed.blob"


response = None
lib = ctypes.CDLL(os.path.join(os.getcwd(), "LivestreamProcessor.dll"))

class ProcessFramesResult(ctypes.Structure):
    _fields_ = [("data", ctypes.POINTER(ctypes.c_ubyte)), ("size", ctypes.c_size_t)]

lib.process_frames.argtypes = [ctypes.c_char_p]
lib.process_frames.restype = ProcessFramesResult
lib.free_result.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
lib.free_result.restype = None
lib.clear_compressor_cache.argtypes = []
lib.clear_compressor_cache.restype = None

def create_http_tunnel(port):
    tunnel = ngrok.connect(port)
    url = tunnel.public_url
    print(f"Created ngrok tunnel at {url}")
    return url

def process_frames(frames):
    serialized_frames = fast_json.dumps(frames).encode("utf-8")
    result = lib.process_frames(serialized_frames)

    output = ctypes.string_at(result.data, result.size)
    lib.free_result(result.data, result.size)

    return output

def extract_video(video_path, frame_size):
    output_folder = video_path + OUTPUT_FOLDER_SUFFIX
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    elif os.listdir(output_folder):
        print("Frames already extracted")
        return None, None

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        resized_frame = cv2.resize(frame, dsize=frame_size)
        frames.append(resized_frame.reshape(-1, 3).tolist())

    cap.release()
    return frames, int(fps)

def get_compressed_filename(video_path, resolution):
    return f"{video_path}{OUTPUT_FOLDER_SUFFIX}/{resolution[0]}x{resolution[1]}{COMPRESSION_FILE_SUFFIX}"

def check_cached_file(video_path, frame_size):
    compressed_file_name = get_compressed_filename(video_path, frame_size)
    return compressed_file_name if os.path.isfile(compressed_file_name) else None

app = FastAPI()

@app.get("/clear_cache")
async def clear_cache():
    lib.clear_compressor_cache()
    return "Cache cleared!"

@app.get("/")
async def index():
    print("hiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")
    return response

# Main input loop
def inputs():
    global response
    os.system("cls")
    time.sleep(0.1)
    X, Y = int(input("X: ")), int(input("Y: "))

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
            if frames is None:
                continue
            print("Compressing")
            processed = process_frames(frames)
            print("Compression complete")
            compressed_file_name = get_compressed_filename(file_name, (X, Y))
            with open(compressed_file_name, "wb") as file:
                file.write(struct.pack('iii', X, Y, fps) + processed)

        json_payload = fast_json.dumps({"X": X, "Y": Y, "Fps": fps}).encode('utf-8')
        payload_length = struct.pack('I', len(json_payload))
        payload = os.urandom(10) + payload_length + json_payload + processed
	response = payload


if __name__ == "__main__":
    requests.post("https://video.glorytosouthsud.repl.co/", json={"Tunnel": create_http_tunnel(PORT)})
    thread = threading.Thread(target=inputs, daemon=True)
    thread.start()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
