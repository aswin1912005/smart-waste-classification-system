from flask import Flask, request, render_template, jsonify, send_from_directory
from datetime import datetime
import os

app = Flask(__name__)

# =========================
# IMAGE SAVE DIRECTORY
# =========================

SAVE_DIR = "/home/aswin/waste-ai/received_images"
os.makedirs(SAVE_DIR, exist_ok=True)


# =========================
# WEBSITE
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# ESP32-CAM UPLOAD
# =========================

@app.route("/upload", methods=["POST"])
def upload():

    print("\n========== NEW IMAGE ==========")

    print("Received file fields:", list(request.files.keys()))

    # ESP32 sends field name: image
    image = request.files.get("image")

    # Backup: accept any uploaded file
    if image is None and request.files:
        image = next(iter(request.files.values()))
        print("Using first received file.")

    if image is None:
        print("ERROR: No image received")

        return jsonify({
            "status": "error",
            "message": "No image received"
        }), 400

    # =========================
    # CREATE UNIQUE FILENAME
    # =========================

    filename = datetime.now().strftime(
        "waste_%Y%m%d_%H%M%S_%f.jpg"
    )

    filepath = os.path.join(SAVE_DIR, filename)

    # =========================
    # SAVE IMAGE
    # =========================

    image.save(filepath)

    print("Original filename:", image.filename)
    print("Image saved:", filepath)
    print("Image size:", os.path.getsize(filepath), "bytes")

    # =========================
    # TEMPORARY RESULT
    # =========================

    classification = "Waiting for Qwen"

    # =========================
    # RESPONSE TO ESP32
    # =========================

    return jsonify({
        "status": "success",
        "filename": filename,
        "classification": classification
    }), 200


# =========================
# LATEST IMAGE + RESULT
# =========================

@app.route("/latest")
def latest():

    files = [
        f for f in os.listdir(SAVE_DIR)
        if f.lower().endswith(
            (".jpg", ".jpeg", ".png")
        )
    ]

    if not files:
        return jsonify({
            "filename": None,
            "classification": "Waiting for waste..."
        })

    latest_file = max(
        files,
        key=lambda f: os.path.getmtime(
            os.path.join(SAVE_DIR, f)
        )
    )

    return jsonify({
        "filename": latest_file,
        "classification": "Waiting for Qwen"
    })


# =========================
# DISPLAY IMAGE
# =========================

@app.route("/images/<filename>")
def images(filename):

    return send_from_directory(
        SAVE_DIR,
        filename
    )


# =========================
# HEALTH CHECK
# =========================

@app.route("/health")
def health():

    return jsonify({
        "status": "running"
    })


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    print("===================================")
    print(" Smart Waste Classification")
    print("===================================")
    print("Laptop IP : 10.242.81.79")
    print("Website   : http://10.242.81.79:5000")
    print("Upload    : http://10.242.81.79:5000/upload")
    print("Health    : http://10.242.81.79:5000/health")
    print("Image Dir : " + SAVE_DIR)
    print("===================================")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )