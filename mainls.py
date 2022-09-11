import requests, json, keyboard, time, threading, pyvirtualcam, logging, zlib, itertools, numpy as np
from mouse import move, click
from mss import mss
from PIL import Image
from flask import Flask, request
from pyngrok import ngrok


for tunnel in ngrok.get_tunnels():
    tunnel.kill()
tunnel = ngrok.connect(42069)

settings = {
    "X": 192,
    "Y": 108,
    "Size": 3,
    "FPS": 30,
    "Tunnel": tunnel.public_url
}

def updateSetting(seting): #idk why i over complicated it
    global settings
    count = 0
    for v in settings:
        if count == len(seting):
            break
        settings[v] = int(seting[count])
        count += 1
    print(json.dumps(settings, indent=4))
    requests.post("https://imageserver.not888.repl.co/",json=json.dumps(settings))

requests.post("https://imageserver.not888.repl.co/",json=json.dumps(settings))
print(json.dumps(settings, indent=4))




app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.disabled = True
app.logger.disabled = True

current = ""
frame = ""

FrameRecordAmount = 14
resX = 192
resY = 108
image = np.zeros((100, 100, 3), np.uint8)  

threads = []
def make_thread(target):
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    threads.append(thread)


def rebuildData(frames):
    done = []
    for data in frames:
        framecomp = []
        for i in range(0,len(data),4):
            r = data[i]
            g = data[i+1]
            b = data[i+2]
            v = data[i+3]
            for i in range(v):
                framecomp.append((r,g,b))
        done.append(framecomp)
    return done

def start_camera():
    global frame, image
    while True:
        if frame == "":
            continue
        list_frames = rebuildData(frame)
        for data in list_frames:
            image = np.array(data).reshape((100, 100, 3)).astype(np.uint8)
            time.sleep(0.2)

def mck(data):
    move(data[1],data[2],True,0)
    time.sleep(0.1)
    click(button=data[3])

def before_request():
    app.jinja_env.cache = {}



@app.route('/pixandcam', methods=['POST'])
def pixandcam():
    global current, frame
    if request.method == 'POST':
        jsonf = json.loads(request.data)
        if frame != jsonf:
            frame = jsonf
        #print("roblox requested")
        return current


@app.route('/inputkey', methods=['POST'])
def inputkey():
    if request.method == 'POST':
        mdata = json.loads(request.data)
        if mdata[0] == "Mouse":
            mck(mdata)
            app.before_request(before_request)
        else:
            keyboard.press(mdata[1])
            time.sleep(0.3)
            keyboard.release(mdata[1])
        return "Done!"
    else:
        return "wrong method"


def quantize(img):
    input = np.array(img) 
    div = 32
    quantized = input // div * div + div // 2
    input = input[:, :, ::1].copy() 
    return Image.fromarray(quantized)

def start_server():
    app.run(host='0.0.0.0', port=42069)

store = []
space = ord(" ")
lb = ord("[")
rb = ord("]")

def handleUpload(stuff):
    global current
    str = "!".join(stuff).translate({space:None,lb:None,rb:None})
    current = zlib.compress(str.encode("UTF-8"))
    stuff.clear()


def screenshot():
    old = [None,None,None,None]
    with mss() as sct:
        for num, monitor in enumerate(sct.monitors[1:], 1):
            sct_img = sct.grab(monitor)
            guy = []
            myScreenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            myScreenshot = myScreenshot.resize((settings["X"],settings["Y"]))
            pixelvalues = list(quantize(myScreenshot).getdata())
            for r,g,b in pixelvalues:
                new = [r,g,b,1]
                if r == old[0] and g == old[1] and b == old[2]:
                    old[3] += 1
                else:
                    guy.append(new)
                    old = new
    flat = [*itertools.chain.from_iterable(guy)]
    store.append(str(flat))
    guy.clear()
 

def consle():
    global FrameRecordAmount
    ncmd = input("").lower()

    if "update " in ncmd:
        cmd = ncmd.split(" ")[1].split(",")
        updateSetting(cmd)
        consle()
    elif "fps " in ncmd:
        cmd = ncmd.split(" ")[1]
        settings["FPS"] = int(cmd)
        print("New fps: ",settings["FPS"])
        consle()
    elif "fpsrate " in ncmd:
        cmd = ncmd.split(" ")[1]
        FrameRecordAmount = int(cmd)
        print("FrameRecordAmount ",FrameRecordAmount)
        consle() 
    elif ncmd == "help":
        print('''
        (Update settings of stream) Update X,Y,Size,Fps
        (Update fps only) Fps FPSHere
        (Edit amount of frames in 1 request) fpsrate Number
        ''')
        consle()


def handleCamera():
    with pyvirtualcam.Camera(width=100, height=100, fps=30) as cam:
        print(f'camera: {cam.device}')
        while True:
            cam.send(image)
            cam.sleep_until_next_frame()

make_thread(start_camera)
print("Started camera")
make_thread(start_server)
print("Started server")
make_thread(consle)
print("Started console")
make_thread(handleCamera)
print("Started camera")

while True:
    for i in range(FrameRecordAmount):
        screenshot()
    handleUpload(store)
# sang so hot