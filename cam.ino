#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// =====================================================
// WiFi
// =====================================================

const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// =====================================================
// Flask Server
// =====================================================

const char* FLASK_SERVER = "10.180.67.79";
const int FLASK_PORT = 5000;

// =====================================================
// Static ESP32-CAM IP
// =====================================================

IPAddress local_IP(10, 180, 67, 239);
IPAddress gateway(10, 180, 67, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);
IPAddress secondaryDNS(8, 8, 4, 4);

// =====================================================
// AI Thinker ESP32-CAM Pins
// =====================================================

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5

#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// =====================================================
// Web server
// =====================================================

WebServer server(80);


// =====================================================
// Connect WiFi
// =====================================================

void connectWiFi() {

    Serial.println();
    Serial.println("Connecting to WiFi...");

    WiFi.mode(WIFI_STA);

    if (!WiFi.config(
        local_IP,
        gateway,
        subnet,
        primaryDNS,
        secondaryDNS
    )) {

        Serial.println("Static IP configuration failed!");
    }

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;

    while (
        WiFi.status() != WL_CONNECTED &&
        attempts < 40
    ) {

        delay(500);
        Serial.print(".");

        attempts++;
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {

        Serial.println("WiFi connected!");
        Serial.print("ESP32-CAM IP: ");
        Serial.println(WiFi.localIP());

    } else {

        Serial.println("WiFi connection failed!");
    }
}


// =====================================================
// Send image to Flask
// =====================================================

bool uploadImage(camera_fb_t* fb) {

    if (fb == nullptr) {

        Serial.println("Camera frame is NULL!");
        return false;
    }

    if (WiFi.status() != WL_CONNECTED) {

        Serial.println("WiFi not connected!");
        return false;
    }

    HTTPClient http;

    String url =
        "http://" +
        String(FLASK_SERVER) +
        ":" +
        String(FLASK_PORT) +
        "/upload";

    Serial.println();
    Serial.println("Sending image to Flask...");
    Serial.println(url);

    http.begin(url);

    http.setTimeout(30000);

    String boundary = "----ESP32CAMBoundary";

    http.addHeader(
        "Content-Type",
        "multipart/form-data; boundary=" + boundary
    );

    String head =
        "--" + boundary + "\r\n"
        "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
        "Content-Type: image/jpeg\r\n\r\n";

    String tail =
        "\r\n--" + boundary + "--\r\n";

    size_t totalLength =
        head.length() +
        fb->len +
        tail.length();

    uint8_t* payload =
        (uint8_t*)malloc(totalLength);

    if (payload == nullptr) {

        Serial.println("ERROR: Not enough memory for upload!");

        http.end();

        return false;
    }

    memcpy(
        payload,
        head.c_str(),
        head.length()
    );

    memcpy(
        payload + head.length(),
        fb->buf,
        fb->len
    );

    memcpy(
        payload + head.length() + fb->len,
        tail.c_str(),
        tail.length()
    );

    Serial.print("Image size: ");
    Serial.print(fb->len);
    Serial.println(" bytes");

    int httpCode =
        http.POST(payload, totalLength);

    Serial.print("Flask HTTP code: ");
    Serial.println(httpCode);

    if (httpCode > 0) {

        String response =
            http.getString();

        Serial.println("Flask response:");
        Serial.println(response);

    } else {

        Serial.print("Flask connection error: ");
        Serial.println(
            http.errorToString(httpCode)
        );
    }

    free(payload);

    http.end();

    return httpCode >= 200 &&
           httpCode < 300;
}


// =====================================================
// Capture image
// =====================================================

void captureImage() {

    Serial.println();
    Serial.println("==============================");
    Serial.println("CAPTURE REQUEST RECEIVED");
    Serial.println("==============================");

    camera_fb_t* fb =
        esp_camera_fb_get();

    if (!fb) {

        Serial.println(
            "ERROR: Camera capture failed!"
        );

        server.send(
            500,
            "application/json",
            "{\"status\":\"error\",\"message\":\"Camera capture failed\"}"
        );

        return;
    }

    Serial.print("Captured image: ");
    Serial.print(fb->len);
    Serial.println(" bytes");

    bool success =
        uploadImage(fb);

    esp_camera_fb_return(fb);

    if (success) {

        server.send(
            200,
            "application/json",
            "{\"status\":\"success\",\"message\":\"Image captured and uploaded\"}"
        );

    } else {

        server.send(
            500,
            "application/json",
            "{\"status\":\"error\",\"message\":\"Image upload failed\"}"
        );
    }
}


// =====================================================
// Camera test
// =====================================================

void cameraRoot() {

    String html =
        "<html>"
        "<head>"
        "<title>ESP32-CAM</title>"
        "</head>"
        "<body>"
        "<h1>ESP32-CAM Online</h1>"
        "<p>IP: " +
        WiFi.localIP().toString() +
        "</p>"
        "<p>Capture endpoint:</p>"
        "<a href=\"/capture\">/capture</a>"
        "</body>"
        "</html>";

    server.send(
        200,
        "text/html",
        html
    );
}


// =====================================================
// Setup camera
// =====================================================

bool initializeCamera() {

    camera_config_t config;

    config.ledc_channel =
        LEDC_CHANNEL_0;

    config.ledc_timer =
        LEDC_TIMER_0;

    config.pin_d0 =
        Y2_GPIO_NUM;

    config.pin_d1 =
        Y3_GPIO_NUM;

    config.pin_d2 =
        Y4_GPIO_NUM;

    config.pin_d3 =
        Y5_GPIO_NUM;

    config.pin_d4 =
        Y6_GPIO_NUM;

    config.pin_d5 =
        Y7_GPIO_NUM;

    config.pin_d6 =
        Y8_GPIO_NUM;

    config.pin_d7 =
        Y9_GPIO_NUM;

    config.pin_xclk =
        XCLK_GPIO_NUM;

    config.pin_pclk =
        PCLK_GPIO_NUM;

    config.pin_vsync =
        VSYNC_GPIO_NUM;

    config.pin_href =
        HREF_GPIO_NUM;

    config.pin_sccb_sda =
        SIOD_GPIO_NUM;

    config.pin_sccb_scl =
        SIOC_GPIO_NUM;

    config.pin_pwdn =
        PWDN_GPIO_NUM;

    config.pin_reset =
        RESET_GPIO_NUM;

    config.xclk_freq_hz =
        20000000;

    config.pixel_format =
        PIXFORMAT_JPEG;

    if (psramFound()) {

        config.frame_size =
            FRAMESIZE_VGA;

        config.jpeg_quality =
            10;

        config.fb_count =
            2;

    } else {

        config.frame_size =
            FRAMESIZE_QVGA;

        config.jpeg_quality =
            12;

        config.fb_count =
            1;
    }

    esp_err_t err =
        esp_camera_init(&config);

    if (err != ESP_OK) {

        Serial.printf(
            "Camera init failed: 0x%x\n",
            err
        );

        return false;
    }

    sensor_t* sensor =
        esp_camera_sensor_get();

    if (sensor) {

        sensor->set_brightness(
            sensor,
            0
        );

        sensor->set_contrast(
            sensor,
            0
        );

        sensor->set_saturation(
            sensor,
            0
        );
    }

    return true;
}


// =====================================================
// Setup
// =====================================================

void setup() {

    Serial.begin(115200);

    delay(1000);

    Serial.println();
    Serial.println("==============================");
    Serial.println(" SMART WASTE ESP32-CAM");
    Serial.println("==============================");

    if (!initializeCamera()) {

        Serial.println(
            "Camera initialization failed!"
        );

        while (true) {
            delay(1000);
        }
    }

    Serial.println("Camera initialized.");

    connectWiFi();

    server.on(
        "/",
        HTTP_GET,
        cameraRoot
    );

    server.on(
        "/capture",
        HTTP_GET,
        captureImage
    );

    server.begin();

    Serial.println();
    Serial.println("ESP32-CAM server started.");
    Serial.print("Camera URL: http://");
    Serial.println(WiFi.localIP());
    Serial.println("Capture: /capture");
}


// =====================================================
// Loop
// =====================================================

void loop() {

    server.handleClient();

    delay(2);
}
