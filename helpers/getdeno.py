import requests, zipfile, os
from helpers import logUtils as log
OSisWindows = os.name == "nt"

def denodl():
    with open("ejs/deno.version", "r") as nv: nv = nv.read()
    iv = requests.get("https://dl.deno.land/release-latest.txt").text.strip()
    if nv != iv:
        log.warning(f"deno.exe | {nv} --> {iv} Updated!")
        with open("ejs/deno.version", "w") as f: f.write(iv)
    if OSisWindows:
        target = "x86_64-pc-windows-msvc"
        delCmd = "del /f /q deno.zip"
        fileName = "deno.exe"
    else:
        uname = os.popen("uname -sm").read().strip()
        if uname == "Darwin x86_64": target = "x86_64-apple-darwin"
        elif uname == "Darwin arm64": target = "aarch64-apple-darwin"
        elif uname == "Linux aarch64": target = "aarch64-unknown-linux-gnu"
        else: target = "x86_64-unknown-linux-gnu"
        delCmd = "sudo rm -rf deno.zip"
        fileName = "deno"

    r = requests.get(f"https://dl.deno.land/release/{iv}/deno-{target}.zip").content
    with open("deno.zip", "wb") as f: f.write(r)
    with zipfile.ZipFile("deno.zip", 'r') as Zip: Zip.extract(fileName, "ejs")
    if not OSisWindows: os.replace("ejs/deno", "ejs/deno.exe")
    os.system(delCmd)

def dl():
    if not os.path.isfile(f"ejs/deno.exe"): denodl(); log.warning(f"deno 없어서 다운로드함")