/*
 * SEVA: Smart Eyewear for Visual Assistance
 * Firmware for ESP32-S3-CAM
 * 
 * Features:
 * 1. Auto-connects to Phone Wi-Fi Hotspot.
 * 2. Streams JPEG snapshot over HTTP at /capture.
 * 3. Fast local hazard reflex loop via VL53L0X ToF sensor (stairs/drop-offs/obstacles).
 * 4. Haptic vibration feedback for hazards and button-click acknowledgment.
 * 5. Push button trigger for on-demand Gemini visual scene description.
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include "camera_pins.h"

// =============================================================================
// 1. WI-FI CREDENTIALS (SET TO YOUR PHONE'S MOBILE HOTSPOT)
// =============================================================================
const char* WIFI_SSID     = "MyPhoneHotspot";     // Replace with your hotspot name
const char* WIFI_PASSWORD = "MyPassword123";     // Replace with your hotspot password
const char* MDNS_HOSTNAME = "seva";               // Accessible at http://seva.local

// =============================================================================
// 2. HARDWARE PIN DEFINITIONS (ADAPTS TO SELECTED BOARD)
// =============================================================================
#if defined(CAMERA_MODEL_XIAO_ESP32S3)
  // Seeed Studio XIAO ESP32S3 Sense Pins
  #define PIN_TOF_SDA     5     // D4 (I2C SDA)
  #define PIN_TOF_SCL     6     // D5 (I2C SCL)
  #define PIN_BUTTON      2     // D1 (Tactile button to GND, INPUT_PULLUP)
  #define PIN_HAPTIC      3     // D2 (Output to NPN Transistor Base)
#else
  // Generic ESP32-S3 CAM Board Pins
  #define PIN_TOF_SDA     1     // I2C Data line for VL53L0X
  #define PIN_TOF_SCL     2     // I2C Clock line for VL53L0X
  #define PIN_BUTTON      21    // Tactile push button (Active LOW, INPUT_PULLUP)
  #define PIN_HAPTIC      3     // Output to NPN Transistor Base (via 1k resistor)
#endif

// =============================================================================
// 3. HAZARD THRESHOLDS (MILLIMETERS)
// =============================================================================
#define HAZARD_OBSTACLE_MM  300   // Warning if an object is closer than 30 cm
#define HAZARD_DROP_DELTA_MM 150  // Warning if floor distance drops suddenly (curb/stairs)

// =============================================================================
// GLOBAL OBJECTS & STATE
// =============================================================================
WebServer server(80);
Adafruit_VL53L0X lox = Adafruit_VL53L0X();

bool tof_available = false;
volatile bool button_pressed_flag = false;
int current_distance_mm = -1;
int baseline_floor_mm = 600;      // Calibrated ground distance when looking ahead
unsigned long last_tof_check = 0;
unsigned long last_button_time = 0;

// =============================================================================
// HAPTIC FEEDBACK ROUTINES
// =============================================================================
void pulse_haptic(int duration_ms, int count = 1) {
  for (int i = 0; i < count; i++) {
    digitalWrite(PIN_HAPTIC, HIGH);
    delay(duration_ms);
    digitalWrite(PIN_HAPTIC, LOW);
    if (count > 1) delay(100);
  }
}

// =============================================================================
// HTTP HANDLERS
// =============================================================================
void handle_capture() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[CAM] Error: Frame capture failed");
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.send_P(200, "image/jpeg", (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void handle_status() {
  String json = "{";
  json += "\"status\":\"online\",";
  json += "\"distance_mm\":" + String(current_distance_mm) + ",";
  json += "\"button_pressed\":" + String(button_pressed_flag ? "true" : "false") + ",";
  json += "\"wifi_rssi\":" + String(WiFi.RSSI());
  json += "}";

  server.send(200, "application/json", json);
}

void handle_consume_button() {
  bool was_pressed = button_pressed_flag;
  button_pressed_flag = false; // Reset flag upon read

  String json = "{\"button_pressed\":" + String(was_pressed ? "true" : "false") + "}";
  server.send(200, "application/json", json);
}

// =============================================================================
// CAMERA INITIALIZATION
// =============================================================================
bool init_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size   = FRAMESIZE_SVGA; // 800x600 for sharp Gemini OCR
    config.jpeg_quality = 12;             // 10-63 (lower = higher quality)
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_VGA;  // 640x480 fallback
    config.jpeg_quality = 15;
    config.fb_count     = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[CAM] Init failed with error 0x%x\n", err);
    return false;
  }

  // Adjust sensor settings for outdoor/indoor visual clarity
  sensor_t *s = esp_camera_sensor_get();
  if (s) {
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
  }

  Serial.println("[CAM] Camera initialized successfully");
  return true;
}

// =============================================================================
// SETUP
// =============================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- [SEVA Assistive Eyewear Booting] ---");

  // Configure GPIOs
  pinMode(PIN_HAPTIC, OUTPUT);
  digitalWrite(PIN_HAPTIC, LOW);

  pinMode(PIN_BUTTON, INPUT_PULLUP);

  // Initialize I2C for VL53L0X
  Wire.begin(PIN_TOF_SDA, PIN_TOF_SCL);
  if (lox.begin()) {
    tof_available = true;
    Serial.println("[TOF] VL53L0X distance sensor connected");
  } else {
    Serial.println("[TOF] Warning: VL53L0X not found. Continuing without ToF.");
  }

  // Initialize Camera
  if (!init_camera()) {
    // Alert via fast buzz pulses if camera fails
    pulse_haptic(100, 3);
  }

  // Connect to Wi-Fi Hotspot
  Serial.printf("[WIFI] Connecting to %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 25) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] Connected!");
    Serial.print("[WIFI] Glasses IP Address: ");
    Serial.println(WiFi.localIP());

    // Start mDNS service (allows accessing http://seva.local)
    if (MDNS.begin(MDNS_HOSTNAME)) {
      Serial.printf("[mDNS] Responder started: http://%s.local\n", MDNS_HOSTNAME);
    }

    // Single buzz to signal connected to phone
    pulse_haptic(150, 1);
  } else {
    Serial.println("\n[WIFI] Failed to connect to hotspot. Check SSID/Password.");
    pulse_haptic(80, 4);
  }

  // Set up HTTP Endpoints
  server.on("/capture", HTTP_GET, handle_capture);
  server.on("/status", HTTP_GET, handle_status);
  server.on("/button", HTTP_GET, handle_consume_button);
  server.begin();
  Serial.println("[HTTP] Server listening on port 80");
}

// =============================================================================
// MAIN LOOP
// =============================================================================
unsigned long last_wifi_retry = 0;

void loop() {
  server.handleClient();

  // 0. AUTO-RECONNECT TO WI-FI IF DISCONNECTED
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - last_wifi_retry > 5000) {
      last_wifi_retry = millis();
      Serial.println("[WIFI] Connection lost! Reconnecting to hotspot...");
      WiFi.reconnect();
    }
  }

  // 1. TACTILE BUTTON DETECTION (WITH DEBOUNCE)
  if (digitalRead(PIN_BUTTON) == LOW) {
    if (millis() - last_button_time > 500) { // 500ms debounce
      button_pressed_flag = true;
      last_button_time = millis();
      Serial.println("[BUTTON] Click detected! Requesting Gemini scene review.");
      // Short haptic click acknowledgment for user
      pulse_haptic(60, 1);
    }
  }

  // 2. INSTANT EDGE REFLEX: VL53L0X TOF SENSOR (EVERY 40MS)
  if (tof_available && (millis() - last_tof_check > 40)) {
    last_tof_check = millis();

    VL53L0X_RangingMeasurementData_t measure;
    lox.rangingTest(&measure, false);

    if (measure.RangeStatus == 0) { // Valid measurement
      current_distance_mm = measure.RangeMilliMeter;

      // Check Obstacle Ahead (Too close)
      if (current_distance_mm < HAZARD_OBSTACLE_MM && current_distance_mm > 40) {
        Serial.printf("[HAZARD] Obstacle close: %d mm\n", current_distance_mm);
        digitalWrite(PIN_HAPTIC, HIGH);
        delay(80);
        digitalWrite(PIN_HAPTIC, LOW);
      }
      // Check Step Down / Drop-Off (Ground distance jumps suddenly)
      else if (current_distance_mm > (baseline_floor_mm + HAZARD_DROP_DELTA_MM)) {
        Serial.printf("[HAZARD] Drop-off / Step detected: %d mm\n", current_distance_mm);
        // Double pulse for drop-offs
        pulse_haptic(100, 2);
      }
    }
  }
}

