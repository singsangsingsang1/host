import sys
import os


def run(cmd):
    return os.popen(cmd).read().replace("\n", "")

def install_packages(package_list):
    existing_packages = run("pip list")
    for package in package_list:
        if package not in existing_packages:
            print(f"Installing {package}")
            run(f"pip install {package}")


    print("")

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
        from flask import Flask, request, Response
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
