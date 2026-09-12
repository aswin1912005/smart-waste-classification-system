#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

// =========================
// WiFi
// =========================
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// =========================
// ESP32-CAM
// =========================
const char* CAMERA_IP = "10.180.67.239";
const int CAMERA_PORT = 80;

// =========================
// IR Sensor
// =========================
#define IR_SENSOR_PIN 27

// Most IR obstacle sensors output LOW when object detected
#define OBJECT_DETECTED LOW

// =========================
// Settings
// =========================
unsigned long cooldown = 5000;
unsigned long lastDetection = 0;

bool previousState = HIGH;


// =========================
// Connect WiFi
// =========================
void connectWiFi() {

    Serial.println();
    Serial.print("Connecting to WiFi");

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;

    while (WiFi.status() != WL_CONNECTED && attempts < 30) {

        delay(500);
        Serial.print(".");

        attempts++;
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {

        Serial.println("WiFi connected!");
        Serial.print("ESP32 IP: ");
        Serial.println(WiFi.localIP());

    } else {

        Serial.println("WiFi connection failed!");
    }
}


// =========================
// Tell ESP32-CAM to capture
// =========================
void triggerCamera() {

    if (WiFi.status() != WL_CONNECTED) {

        Serial.println("WiFi not connected.");
        return;
    }

    HTTPClient http;

    String url =
        "http://" +
        String(CAMERA_IP) +
        ":" +
        String(CAMERA_PORT) +
        "/capture";

    Serial.println();
    Serial.println("Triggering ESP32-CAM...");
    Serial.println(url);

    http.begin(url);

    http.setTimeout(15000);

    int httpCode = http.GET();

    if (httpCode > 0) {

        Serial.print("Camera HTTP code: ");
        Serial.println(httpCode);

        String response = http.getString();

        Serial.println("Camera response:");
        Serial.println(response);

    } else {

        Serial.print("Camera request failed: ");
        Serial.println(http.errorToString(httpCode));
    }

    http.end();
}


// =========================
// Setup
// =========================
void setup() {

    Serial.begin(115200);

    pinMode(IR_SENSOR_PIN, INPUT);

    Serial.println();
    Serial.println("==============================");
    Serial.println(" SMART WASTE ESP32 CONTROLLER");
    Serial.println("==============================");

    connectWiFi();
}


// =========================
// Loop
// =========================
void loop() {

    if (WiFi.status() != WL_CONNECTED) {

        connectWiFi();
        delay(1000);
        return;
    }

    bool sensorState = digitalRead(IR_SENSOR_PIN);

    // Object detected
    if (
        sensorState == OBJECT_DETECTED &&
        previousState != OBJECT_DETECTED
    ) {

        unsigned long now = millis();

        if (now - lastDetection >= cooldown) {

            Serial.println();
            Serial.println("================================");
            Serial.println("OBJECT DETECTED!");
            Serial.println("================================");

            triggerCamera();

            lastDetection = now;
        }
    }

    previousState = sensorState;

    delay(50);
}
