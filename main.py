import ctypes
import math
import struct
import io
import os
import logging
import time
import threading 
import atexit

from packages import * # im aware this is not great practice.
from pyngrok import ngrok

log = logging.getLogger('werkzeug')
log.disabled = True

WEBCAMX = 10 
WEBCAMY = 10

Frame = np.zeros((WEBCAMX, WEBCAMY, 3), dtype=np.uint8)

camera = dxcam.create()
camera.start(target_fps = FPS, video_mode=True)

lib = ctypes.CDLL(os.path.join(os.getcwd(), "LivestreamProcessor.dll"))

class ProcessFramesResult(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("size", ctypes.c_size_t),
    ]


lib.process_frames.argtypes = [ctypes.c_char_p, ctypes.c_size_t]

lib.process_frames.restype = ProcessFramesResult

lib.free_result.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
lib.free_result.restype = None

lib.clear_compressor_cache.argtypes = []
lib.clear_compressor_cache.restype = None

def process_frames(frames, width):

    serialized_frames = fast_json.dumps(frames).encode("utf-8")
    result = lib.process_frames(serialized_frames, width)
    data, size = result.data, result.size

    output = ctypes.string_at(data, size)
    lib.free_result(data, size)

    return output

def get_size_in_units(input_string, units=["B", "KB", "MB", "GB"]):
    size_in_bytes = len(input_string)
    unit_index = 0
    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024
        unit_index += 1
    return f"{size_in_bytes:.2f} {units[unit_index]}"

def CreateHTTPTunnel(Port):
    for tunnel in ngrok.get_tunnels():
        tunnel.kill()
    tunnel = ngrok.connect(Port)
    url = tunnel.public_url
    print(f"Created ngrok tunnel at {url}")
    return url

def quantize(img):
    div = 64
    quantized = img // div * div + div // 2
    return quantized

def pack_int(number, bytes):
    packed = bytearray()
    for _ in range(bytes):
        byte = number % 256
        packed.insert(0, byte)
        number = (number - byte) // 256

    return packed

def TakeScreenshots(Data):
    screenshots = [ ]

    Resolution = Data["Resolution"]
    FrameRecordAmount = Data["FrameRecordAmount"]

    X = Resolution["X"]
    Y = Resolution["Y"]

    for i in range(FrameRecordAmount):
        image = camera.get_latest_frame()  
        if image is None:
            screenshots.append([])
            continue

        res = cv2.resize(image, dsize=(X, Y), interpolation=3).reshape(-1, 3)
        screenshots.append(res.tolist())

    return screenshots

def Webcam():
    global Frame
    with pyvirtualcam.Camera(width=WEBCAMX, height=WEBCAMY, fps=20) as cam:
        while True:
            cam.send(Frame)
            cam.sleep_until_next_frame()

def RebuildCamera(data):
    Image = []
    for i in range(0, len(data), 4):
        R = data[i]
        G = data[i + 1]
        B = data[i + 2]
        AM = data[i + 3]
        for i in range(AM):
            Image.append((R, G, B))
        
    return np.array(Image).reshape((WEBCAMX, WEBCAMY, 3)).astype(np.uint8)

def WebcamDaemon():
    WebcamThread = threading.Thread(target=Webcam)
    WebcamThread.daemon = True
    WebcamThread.start()
    return WebcamThread

def GetFrames(Data):
    resolution = Data["Resolution"]
    bits = math.ceil(math.log2(resolution["X"] * resolution["Y"] + 1))
    width = math.ceil(bits / 8)

    start1 = time.time()

    Frames = TakeScreenshots(Data)

    FrameRecordTime = time.time() - start1
    

    start2 = time.time()
    VideoData = process_frames(Frames, width)
    ProcessedTime = time.time() - start2

    print("\033[92m {}\033[00m" .format(f"Captured {Data['FrameRecordAmount']} frames in {FrameRecordTime} seconds\nProcessed frames in {ProcessedTime}"))

    return VideoData

def Click(Body):
    X = Body["X"]
    Y = Body["Y"]
    Type = Body["MouseButton"]
    mouse.move(X, Y)

    if Type == "Left":
        mouse.click()
    elif Type == "Right":
        mouse.right_click()
        
def PressAndRelease(key):
    keyboard.press(key)
    time.sleep(1)
    keyboard.release(key)

def SetVirtualCamera(CameraVideoData):
    global Frame
    for CamFrame in CameraVideoData:
        Frame = RebuildCamera(CamFrame)        

app = Flask(__name__)

@app.route('/PingVM', methods = ["GET"]) 
def PingVM():
    return "OK!"

@app.route('/VMRefresh', methods = ["POST"]) 
def VMRefresh():
    lib.clear_compressor_cache()
    return "OK!"

@app.route('/VMInput', methods = ["POST"]) # type: ignore
def VMInput():
    RequestBody = request.get_json()
    Type = RequestBody.get("Type")
    Body = RequestBody.get("Body")
        
    ({
        "Mouse" : Click,
        "Keyboard" : PressAndRelease
    })[Type](Body)

    return "OK!"

@app.route("/GetVideoData", methods = ["POST", "GET"])
def GetVideoData():
    start = time.time()
    global X, Y, FPS
    print("Got request")

    FrameRecordAmount = 30 
    header = struct.pack('<HHBBB', X, Y, FPS, FrameRecordAmount, SIZE)

    VideoData = header + GetFrames({
        "FrameRecordAmount" : FrameRecordAmount,
        "FPS" : FPS,
        "Resolution" : {
            "X" : X,
            "Y" : Y
        }
    })

    if request.method == "POST":
        RequestBody = request.get_json()

        CameraVideoData = RequestBody.get("Camera")
        if CameraVideoData:
            SetVirtualCamera(CameraVideoData)

        print("/GetVideoData took", time.time()- start, "seconds")     
    
    return Response(io.BytesIO(VideoData), mimetype='application/octet-stream')

def GetIP():
    return requests.get("https://api.ipify.org/?format=json").json()["ip"]

GetFrames({
    "FrameRecordAmount" : 30,
    "FPS" : FPS,
    "Resolution" : {
        "X" : X,
        "Y" : Y
    }
})

def stop_capturer():
    global camera
    camera.stop()
    del camera
    
atexit.register(stop_capturer)

if __name__ == "__main__":
    WebcamDaemon()
    PORT = 42171
    ServerUrl = USE_NGROK and CreateHTTPTunnel(PORT) or f"http://{GetIP()}:{PORT}"
    requests.post("http://172.235.51.119:42070/update_setting", json={"Tunnel": ServerUrl})
    
    print(f"Server is on {ServerUrl}")
    app.run(host='0.0.0.0', port=PORT)
    os.system("cls")


