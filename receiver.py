import os
import json
import threading
import getpass
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    render_template
)

from werkzeug.utils import secure_filename

from google import genai
from google.genai import types


# =========================================================
# PROJECT PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

SAVE_DIR = BASE_DIR / "received_images"

RESULT_FILE = BASE_DIR / "latest_result.json"

TEMPLATE_DIR = BASE_DIR / "templates"


SAVE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# NETWORK
# =========================================================

WINDOWS_IP = "10.180.67.79"

CAMERA_IP = "10.180.67.239"

FLASK_PORT = 5000


# =========================================================
# GEMINI API KEY
# =========================================================

print()
print("========================================")
print(" SMART WASTE CLASSIFICATION SERVER")
print("========================================")
print()

GEMINI_API_KEY = getpass.getpass(
    "Enter your Gemini API key: "
).strip()


if not GEMINI_API_KEY:

    print()
    print("ERROR: Gemini API key was not entered.")
    print()

    raise SystemExit(1)


print()
print("Gemini API: CONFIGURED")
print()


# =========================================================
# GEMINI CLIENT
# =========================================================

try:

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

except Exception as e:

    print(
        "Gemini initialization failed:"
    )

    print(e)

    client = None


# =========================================================
# FLASK
# =========================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR)
)


# =========================================================
# RESULT HELPERS
# =========================================================

def save_result(result):

    try:

        with open(
            RESULT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print(
            "Could not save result:",
            e
        )


def get_initial_result():

    return {
        "status": "waiting",
        "classification": "",
        "confidence": 0,
        "reason": "",
        "image": "",
        "timestamp": ""
    }


# =========================================================
# GEMINI CLASSIFICATION
# =========================================================

def classify_waste(image_path):

    print()
    print("----------------------------------------")
    print("Starting Gemini classification")
    print("----------------------------------------")

    if client is None:

        result = {
            "status": "error",
            "classification": "AI ERROR",
            "confidence": 0,
            "reason": "Gemini client is not configured.",
            "image": image_path.name,
            "timestamp": datetime.now().isoformat()
        }

        save_result(result)

        return


    try:

        image_bytes = image_path.read_bytes()


        prompt = """
You are a waste classification AI.

Classify the object in the image into exactly ONE
of these categories:

1. Biodegradable
2. Non-Biodegradable

Return ONLY valid JSON using this exact structure:

{
  "classification": "Biodegradable",
  "confidence": 0.95,
  "reason": "Short explanation"
}

Rules:

- classification must be exactly:
  "Biodegradable"
  OR
  "Non-Biodegradable"

- confidence must be a number between 0 and 1.

- reason must briefly explain why.

Do not return markdown.
Do not return extra text.
"""


        response = client.models.generate_content(

            model="gemini-3.7-flash",

            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                ),
                prompt
            ],

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "classification": {
                            "type": "STRING"
                        },
                        "confidence": {
                            "type": "NUMBER"
                        },
                        "reason": {
                            "type": "STRING"
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


        text = response.text.strip()

        print("Gemini response:")
        print(text)


        data = json.loads(text)


        classification = str(
            data.get(
                "classification",
                ""
            )
        ).strip()


        confidence = float(
            data.get(
                "confidence",
                0
            )
        )


        reason = str(
            data.get(
                "reason",
                ""
            )
        ).strip()


        # ---------------------------------------------
        # Validate classification
        # ---------------------------------------------

        if classification not in [
            "Biodegradable",
            "Non-Biodegradable"
        ]:

            classification = "Unknown"


        # ---------------------------------------------
        # Clamp confidence
        # ---------------------------------------------

        confidence = max(
            0,
            min(
                1,
                confidence
            )
        )


        result = {

            "status": "success",

            "classification":
                classification,

            "confidence":
                confidence,

            "confidence_percent":
                round(
                    confidence * 100,
                    2
                ),

            "reason":
                reason,

            "image":
                image_path.name,

            "timestamp":
                datetime.now().isoformat()
        }


        save_result(result)


        print()
        print("========================================")
        print("CLASSIFICATION COMPLETE")
        print("Classification:", classification)
        print(
            "Confidence:",
            round(confidence * 100, 2),
            "%"
        )
        print("Reason:", reason)
        print("========================================")


    except Exception as e:

        print()
        print("========================================")
        print("GEMINI ERROR")
        print("========================================")
        print(str(e))
        print("========================================")


        result = {

            "status": "error",

            "classification":
                "AI ERROR",

            "confidence":
                0,

            "reason":
                str(e),

            "image":
                image_path.name,

            "timestamp":
                datetime.now().isoformat()
        }


        save_result(result)


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# IMAGE UPLOAD
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    print()
    print("========================================")
    print("IMAGE UPLOAD REQUEST")
    print("========================================")


    # ---------------------------------------------
    # Check files
    # ---------------------------------------------

    if not request.files:

        print("No files received.")

        return jsonify({
            "status": "error",
            "message": "No image received"
        }), 400


    # ---------------------------------------------
    # Expected field = image
    # ---------------------------------------------

    image = request.files.get(
        "image"
    )


    # ---------------------------------------------
    # Fallback
    # ---------------------------------------------

    if image is None:

        image = next(
            iter(
                request.files.values()
            ),
            None
        )


    if image is None:

        print("Image object is None.")

        return jsonify({
            "status": "error",
            "message": "No image received"
        }), 400


    if image.filename == "":

        return jsonify({
            "status": "error",
            "message": "Empty filename"
        }), 400


    # ---------------------------------------------
    # Generate filename
    # ---------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )


    original_name = secure_filename(
        image.filename
    )


    filename = (
        timestamp +
        "_" +
        original_name
    )


    image_path = SAVE_DIR / filename


    # ---------------------------------------------
    # Save image
    # ---------------------------------------------

    try:

        image.save(
            image_path
        )

    except Exception as e:

        print(
            "Image save failed:",
            e
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


    print(
        "Image saved:",
        image_path
    )


    # ---------------------------------------------
    # Save processing state
    # ---------------------------------------------

    result = {

        "status":
            "processing",

        "classification":
            "Processing...",

        "confidence":
            0,

        "confidence_percent":
            0,

        "reason":
            "Image received. Gemini is analyzing it.",

        "image":
            filename,

        "timestamp":
            datetime.now().isoformat()
    }


    save_result(result)


    # ---------------------------------------------
    # Start Gemini in background
    # ---------------------------------------------

    thread = threading.Thread(

        target=classify_waste,

        args=(image_path,),

        daemon=True
    )

    thread.start()


    return jsonify({

        "status":
            "success",

        "message":
            "Image received and processing started",

        "filename":
            filename

    }), 200


# =========================================================
# LATEST RESULT
# =========================================================

@app.route("/latest")
def latest():

    if not RESULT_FILE.exists():

        return jsonify(
            get_initial_result()
        )


    try:

        with open(
            RESULT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)


        return jsonify(data)


    except Exception as e:

        return jsonify({

            "status":
                "error",

            "classification":
                "Server Error",

            "confidence":
                0,

            "reason":
                str(e),

            "image":
                "",

            "timestamp":
                ""
        })


# =========================================================
# SERVE IMAGES
# =========================================================

@app.route(
    "/images/<path:filename>"
)
def serve_image(filename):

    return send_from_directory(
        SAVE_DIR,
        filename
    )


# =========================================================
# HEALTH
# =========================================================

@app.route("/health")
def health():

    return jsonify({

        "status":
            "online",

        "server_ip":
            WINDOWS_IP,

        "server_port":
            FLASK_PORT,

        "camera_ip":
            CAMERA_IP,

        "gemini":
            "configured"
            if client
            else "not configured"
    })


# =========================================================
# GEMINI STATUS
# =========================================================

@app.route("/gemini-status")
def gemini_status():

    return jsonify({

        "gemini_configured":
            client is not None
    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print()
    print("========================================")
    print("FLASK SERVER STARTING")
    print("========================================")

    print(
        "Website : "
        f"http://{WINDOWS_IP}:{FLASK_PORT}"
    )

    print(
        "Upload  : "
        f"http://{WINDOWS_IP}:{FLASK_PORT}/upload"
    )

    print(
        "Latest  : "
        f"http://{WINDOWS_IP}:{FLASK_PORT}/latest"
    )

    print(
        "Health  : "
        f"http://{WINDOWS_IP}:{FLASK_PORT}/health"
    )

    print()
    print("Waiting for ESP32-CAM...")
    print()


    app.run(

        host="0.0.0.0",

        port=FLASK_PORT,

        debug=False,

        threaded=True
    )
