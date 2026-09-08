#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// =========================
// Wi-Fi
// =========================
const char* ssid = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

// =========================
// Windows Flask Server
// =========================
const char* serverURL = "http://10.180.67.79:5000/upload";

// =========================
// AI Thinker ESP32-CAM pins
// =========================
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


void connectWiFi() {

  WiFi.mode(WIFI_STA);

  // Keep Wi-Fi awake for reliable uploads
  WiFi.setSleep(false);

  Serial.println();
  Serial.println("Connecting to WiFi...");

  WiFi.begin(ssid, password);

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");

    attempts++;

    if (attempts >= 40) {
      Serial.println();
      Serial.println("WiFi connection failed!");
      Serial.println("Restarting...");
      ESP.restart();
    }
  }

  Serial.println();
  Serial.println("WiFi connected!");

  Serial.print("ESP32-CAM IP: ");
  Serial.println(WiFi.localIP());

  Serial.print("Laptop Flask Server: ");
  Serial.println(serverURL);
}


bool initializeCamera() {

  camera_config_t config;

  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;

  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;

  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;

  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;

  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 20000000;

  config.pixel_format = PIXFORMAT_JPEG;

  // Image quality
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 10;
  config.fb_count = 2;

  esp_err_t err = esp_camera_init(&config);

  if (err != ESP_OK) {

    Serial.print("Camera init failed: 0x");
    Serial.println(err, HEX);

    return false;
  }

  Serial.println("Camera initialized!");

  return true;
}


// =========================
// Upload image to Flask
// =========================
bool uploadImage() {

  if (WiFi.status() != WL_CONNECTED) {

    Serial.println("WiFi disconnected!");
    connectWiFi();
  }

  Serial.println();
  Serial.println("Taking photo...");

  camera_fb_t* fb = esp_camera_fb_get();

  if (!fb) {

    Serial.println("Camera capture failed!");

    return false;
  }

  Serial.print("Image size: ");
  Serial.print(fb->len);
  Serial.println(" bytes");

  HTTPClient http;

  http.setConnectTimeout(5000);
  http.setTimeout(20000);

  Serial.println("Connecting to Flask...");

  if (!http.begin(serverURL)) {

    Serial.println("HTTP begin failed!");

    esp_camera_fb_return(fb);

    return false;
  }

  String boundary = "----ESP32CAMBoundary";

  String head =
    "--" + boundary + "\r\n"
    "Content-Disposition: form-data; name=\"image\"; filename=\"esp32cam.jpg\"\r\n"
    "Content-Type: image/jpeg\r\n\r\n";

  String tail = "\r\n--" + boundary + "--\r\n";

  size_t totalLength =
    head.length() +
    fb->len +
    tail.length();

  http.addHeader(
    "Content-Type",
    "multipart/form-data; boundary=" + boundary
  );

  http.addHeader(
    "Content-Length",
    String(totalLength)
  );

  // Send multipart data
  WiFiClient* stream = http.getStreamPtr();

  stream->print(head);

  size_t written = 0;

  while (written < fb->len) {

    size_t chunkSize = 1024;

    if (chunkSize > fb->len - written) {
      chunkSize = fb->len - written;
    }

    stream->write(
      fb->buf + written,
      chunkSize
    );

    written += chunkSize;
  }

  stream->print(tail);

  Serial.println("Image uploaded. Waiting for Flask...");

  int httpCode = http.GET();

  // Some Flask servers expect POST.
  // If GET is not accepted, use the POST method below.
  Serial.print("HTTP response: ");
  Serial.println(httpCode);

  if (httpCode > 0) {

    String response = http.getString();

    Serial.println("Server response:");
    Serial.println(response);

  } else {

    Serial.print("HTTP error: ");
    Serial.println(http.errorToString(httpCode));
  }

  http.end();

  esp_camera_fb_return(fb);

  return httpCode > 0;
}


void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("==============================");
  Serial.println(" ESP32-CAM Waste System");
  Serial.println("==============================");

  // Camera
  if (!initializeCamera()) {

    Serial.println("Camera initialization failed!");
    while (true) {
      delay(1000);
    }
  }

  // Wi-Fi
  connectWiFi();

  Serial.println();
  Serial.println("System ready!");
}


void loop() {

  // No automatic photo capture here.
  // Your ESP32 DevKit can request /capture
  // when the IR sensor detects waste.

  delay(1000);
}
