import os
import struct
import ctypes
import threading
import time
import requests
import cv2, fast_json
import numpy as np
import zlib, pyperclip
from flask import Flask, request, Response

from pyngrok import ngrok

PORT = 28223
OUTPUT_FOLDER_SUFFIX = "_data"
COMPRESSION_FILE_SUFFIX = "_compressed.blob"


response = "whar"
current_playing_video = None
lib = ctypes.CDLL(os.path.join(os.getcwd(), "LivestreamProcessor.dll"))

events = []

class RequestEvent:
    def __init__(self):
        self.event = threading.Event()
        self.data = None
        events.append(self)

    def wait(self):
        self.event.wait()
        return self.data

    def set_data(self, data):
        self.data = data
        self.event.set()




def DecompressZlib(Data : bytes):
    return zlib.decompress(Data).decode("utf-8")


class ProcessFramesResult(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("size", ctypes.c_size_t),
    ]


lib.process_frames.argtypes = [ctypes.c_char_p]
lib.process_frames.restype = ProcessFramesResult

lib.free_result.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
lib.free_result.restype = None

lib.clear_compressor_cache.argtypes = []
lib.clear_compressor_cache.restype = None

def create_http_tunnel(port):
    ngrok.kill()
    tunnel = ngrok.connect(port)
    url = tunnel.public_url
    print(f"Created ngrok tunnel at {url}")
    return url

def pack_int(number, bytes):
    packed = bytearray()
    for _ in range(bytes):
        byte = number % 256
        packed.insert(0, byte)
        number = (number - byte) // 256
    return packed

def unpack_bytes(bytes):
    number = 0
    for byte in bytes:
        number = (number * 256) + byte
    return number


def post_process(output, size):
    frames = fast_json.loads(DecompressZlib(output))
    newoutput = bytearray()

    resolution = size[0] * size[1]
    bits = math.ceil(math.log2(resolution + 1))
    width = math.ceil(bits / 8)

    for frame in frames: 
        for pixel_set in frame:
            R = pack_int(pixel_set[0], 1) 
            G = pack_int(pixel_set[1], 1) 
            B = pack_int(pixel_set[2], 1) 

            run_length = pack_int(pixel_set[3], width) 
            
            jump_offset = len(pixel_set) == 5 and pixel_set[4] or 0

            jump_offset =  pack_int(jump_offset, width) 
            packed = bytearray([R, G, B, run_length, jump_offset])

            newoutput.extend(packed)

    return newoutput




def process_frames(frames):
    print("processing frames")
    serialized_frames = fast_json.dumps(frames).encode("utf-8")
    result = lib.process_frames(serialized_frames)

    output = ctypes.string_at(result.data, result.size)
    lib.free_result(result.data, result.size)


    return post_process(output)


def save_processed_chunk(chunk, output_folder, chunk_index, frame_size, fps):
    processed = process_frames(chunk, frame_size)
    chunk_filename = os.path.join(output_folder, f"chunk_{chunk_index}.blob")
    with open(chunk_filename, "wb") as file:
        file.write(struct.pack('HHB', frame_size[0], frame_size[1], fps) + processed)

def get_video_chunk(video_path, chunk_index):
    output_folder = video_path + OUTPUT_FOLDER_SUFFIX
    chunk_filename = os.path.join(output_folder, f"chunk_{chunk_index}.blob")
    with open(chunk_filename, "rb") as f:
        return f.read()

def len_of_chunks(video_path):
    output_folder = video_path + OUTPUT_FOLDER_SUFFIX
    if not os.path.exists(output_folder):
        return 0

    chunk_files = [f for f in os.listdir(output_folder) if f.startswith('chunk_') and f.endswith('.blob')]
    return len(chunk_files)


def extract_video(video_path, frame_size):
    output_folder = video_path + OUTPUT_FOLDER_SUFFIX
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)


    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    chunk_index = 0
    chunk = []
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        resized_frame = cv2.resize(frame, dsize=frame_size, interpolation=3)
        chunk.append(resized_frame.reshape(-1, 3).tolist())

        if len(chunk) == fps * 2: 
            save_processed_chunk(chunk, output_folder, chunk_index, frame_size, fps)
            chunk_index += 1
            chunk.clear()
        

    if len(chunk) > 0:
        save_processed_chunk(chunk, output_folder, chunk_index, frame_size, fps)
        chunk.clear()


    cap.release()

app = Flask(__name__)

@app.route('/clear_cache', methods=['GET'])
async def clear_cache():
    lib.clear_compressor_cache()
    return "Cache cleared!"

chunk_indices = { 

}


@app.route('/', methods=['POST'])
def index():
    
    if not current_playing_video:
        print("unselected")
        return "Nothing"

    data = request.get_json()

    JobId = data["JobId"]

    if not chunk_indices.get(JobId):
        chunk_indices[JobId] = 0

    chunk_index = chunk_indices[JobId]

    if chunk_index == len_of_chunks(current_playing_video):
        print("at end")
        return "Nothing"

    video_chunk = get_video_chunk(current_playing_video, chunk_index)
    
    chunk_indices[JobId] += 1
    
    return Response(video_chunk, mimetype="application/octet-stream")

def check_if_processed(video_path):
    output_folder = video_path + OUTPUT_FOLDER_SUFFIX
    if os.path.exists(output_folder) and os.listdir(output_folder):
        return True

    return False

def inputs():
    global current_playing_video
    os.system("cls")
    time.sleep(0.1)
    X, Y = int(input("X: ")), int(input("Y: "))
    
    while True:
        file_name = input("File to play: ")
        
        for key in chunk_indices.keys():
            chunk_indices[key] = 0           
        
        if not check_if_processed(file_name):
            extract_video(file_name, (X, Y))

        current_playing_video = file_name
        
        





if __name__ == "__main__":
    requests.post("https://video.glorytosouthsud.repl.co/", json={"Tunnel": create_http_tunnel(PORT)})
    thread = threading.Thread(target=inputs, daemon=True)
    thread.start()
    app.run(host="0.0.0.0", port=PORT)
