from flask import Flask, request, render_template, jsonify, send_from_directory
from datetime import datetime
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
import os
import json
import threading

app = Flask(__name__)

# ==============================
# SETTINGS
# ==============================

SAVE_DIR = "/home/aswin/waste-ai/received_images"
RESULT_FILE = "/home/aswin/waste-ai/latest_result.json"

os.makedirs(SAVE_DIR, exist_ok=True)

# Gemini API key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("Gemini API: CONFIGURED")
else:
    client = None
    print("WARNING: GEMINI_API_KEY not configured")


# ==============================
# SAVE RESULT
# ==============================

def save_result(data):
    temp_file = RESULT_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    os.replace(temp_file, RESULT_FILE)


# ==============================
# GEMINI CLASSIFICATION
# ==============================

def classify_waste(image_path, filename):

    print("\n========== GEMINI AI ==========")
    print("Analyzing:", filename)

    if client is None:
        result = {
            "status": "error",
            "filename": filename,
            "classification": "AI ERROR",
            "confidence": 0,
            "reason": "Gemini API key is not configured."
        }

        save_result(result)
        return

    try:

        # Read image
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Image input
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )

        prompt = """
You are a waste classification AI.

Analyze the waste object in the image.

Classify it into EXACTLY one of these two categories:

1. Biodegradable
2. Non-Biodegradable

Return only JSON with these fields:

{
    "classification": "Biodegradable",
    "confidence": 0.95,
    "reason": "Short explanation"
}

Rules:
- classification must be exactly "Biodegradable" or "Non-Biodegradable"
- confidence must be a number between 0 and 1
- reason must briefly explain the visual evidence
"""

        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=[
                image_part,
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": [
                                "Biodegradable",
                                "Non-Biodegradable"
                            ]
                        },
                        "confidence": {
                            "type": "number"
                        },
                        "reason": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "classification",
                        "confidence",
                        "reason"
                    ]
                }
            )
        )

        # Parse Gemini response
        result = json.loads(response.text)

        classification = result.get("classification", "Unknown")
        confidence = float(result.get("confidence", 0))
        reason = result.get("reason", "")

        # Keep confidence between 0 and 1
        confidence = max(0, min(1, confidence))

        final_result = {
            "status": "success",
            "filename": filename,
            "classification": classification,
            "confidence": confidence,
            "reason": reason
        }

        save_result(final_result)

        print("Classification:", classification)
        print("Confidence:", confidence)
        print("Reason:", reason)
        print("================================")

    except Exception as e:

        print("Gemini ERROR:", str(e))

        result = {
            "status": "error",
            "filename": filename,
            "classification": "AI ERROR",
            "confidence": 0,
            "reason": str(e)
        }

        save_result(result)


# ==============================
# WEBSITE
# ==============================

@app.route("/")
def home():
    return render_template("index.html")


# ==============================
# ESP32-CAM UPLOAD
# ==============================

@app.route("/upload", methods=["POST"])
def upload():

    print("\n========== NEW IMAGE ==========")

    print("Received file fields:", list(request.files.keys()))

    image = request.files.get("image")

    # Fallback if ESP32 uses another field name
    if image is None and len(request.files) > 0:
        image = next(iter(request.files.values()))
        print("Using first received file.")

    if image is None:
        print("ERROR: No image received")

        return jsonify({
            "status": "error",
            "message": "No image received"
        }), 400

    # Generate unique filename
    filename = datetime.now().strftime(
        "waste_%Y%m%d_%H%M%S_%f.jpg"
    )

    filename = secure_filename(filename)

    filepath = os.path.join(
        SAVE_DIR,
        filename
    )

    # Save image
    image.save(filepath)

    print("Image received:", image.filename)
    print("Image saved:", filepath)

    # Immediately tell ESP32-CAM upload succeeded
    # Gemini runs in background
    save_result({
        "status": "processing",
        "filename": filename,
        "classification": "Analyzing...",
        "confidence": 0,
        "reason": "Gemini AI is analyzing the image..."
    })

    # Start Gemini automatically
    thread = threading.Thread(
        target=classify_waste,
        args=(filepath, filename),
        daemon=True
    )

    thread.start()

    return jsonify({
        "status": "success",
        "filename": filename,
        "classification": "Analyzing..."
    }), 200


# ==============================
# LATEST RESULT
# ==============================

@app.route("/latest")
def latest():

    if not os.path.exists(RESULT_FILE):

        return jsonify({
            "status": "waiting",
            "filename": None,
            "classification": "Waiting for waste...",
            "confidence": 0,
            "reason": ""
        })

    try:

        with open(
            RESULT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            result = json.load(f)

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "status": "error",
            "filename": None,
            "classification": "ERROR",
            "confidence": 0,
            "reason": str(e)
        })


# ==============================
# SERVE IMAGE
# ==============================

@app.route("/images/<filename>")
def images(filename):

    return send_from_directory(
        SAVE_DIR,
        filename
    )


# ==============================
# HEALTH CHECK
# ==============================

@app.route("/health")
def health():

    return jsonify({
        "server": "online",
        "gemini": "configured" if client else "not configured"
    })


# ==============================
# START SERVER
# ==============================

if __name__ == "__main__":

    print("\n===================================")
    print(" Smart Waste Classification System")
    print("===================================")
    print("Laptop IP : 10.242.81.79")
    print("Website   : http://10.242.81.79:5000")
    print("Upload    : http://10.242.81.79:5000/upload")
    print("===================================\n")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )