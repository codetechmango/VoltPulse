/*
 * VoltPulse Smart Electricity System - Stage 3: End-to-End Hardware Integration
 * 
 * Hardware Target: ESP32 DevKit V1 + INA219 Sensor
 * Connections:
 *   - INA219 VCC  -> ESP32 3V3 (or 5V depending on module)
 *   - INA219 GND  -> ESP32 GND
 *   - INA219 SDA  -> ESP32 GPIO 21
 *   - INA219 SCL  -> ESP32 GPIO 22
 *   - INA219 VIN+ -> High-side power supply input (e.g. +12V / +5V)
 *   - INA219 VIN- -> Load supply input (e.g. DC Fan, Motor, Lamp)
 *   - Common GND  -> Load GND connected with ESP32 GND
 * 
 * Dependencies:
 *   - Adafruit INA219 (by Adafruit)
 *   - Built-in ESP32 libraries: WiFi, HTTPClient, Preferences, Wire, time
 */

#include <Wire.h>
#include <Adafruit_INA219.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <time.h>

// ==============================================================================
// 1. NETWORK & BACKEND CONFIGURATION
// ==============================================================================
// Update these to match your local 2.4GHz WiFi network:
const char* WIFI_SSID     = "Nothing phone 1";
const char* WIFI_PASSWORD = "kiran1818";

// IP address and port of your PC / Server running the FastAPI backend.
// Note: Ensure your PC and ESP32 are on the SAME local Wi-Fi network.
const char* SERVER_BASE_URL = "http://10.119.206.33:8000";

// Persistent Hardware API Key (matches HARDWARE_API_KEY in backend/.env)
const char* HARDWARE_API_KEY = "voltpulse-hw-secret-key-2026";

// Target Consumer User ID in VoltPulse (Priya Kumar = 5)
const int USER_ID = 5;

// Telemetry intervals
const unsigned long TELEMETRY_SAMPLE_INTERVAL_MS = 1000;   // Sample sensor every 1 second (numerical integration)
const unsigned long HTTP_POST_INTERVAL_MS        = 10000;  // Send reading to backend every 10 seconds (adjust to 30000 or 60000 for production)
const unsigned long NVS_COMMIT_INTERVAL_MS       = 30000;  // Save energy to flash every 30s to preserve flash endurance

// ==============================================================================
// 2. HARDWARE PIN DEFINITIONS & OBJECTS
// ==============================================================================
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define INA219_I2C_ADDRESS 0x40

Adafruit_INA219 ina219(INA219_I2C_ADDRESS);
Preferences preferences;

// Measurement state variables
float busVoltage_V     = 0.0f;
float shuntVoltage_mV  = 0.0f;
float current_mA       = 0.0f;
float power_mW         = 0.0f;
float power_W          = 0.0f;

// Energy accumulation variables
float cumulative_kWh   = 0.0f;
float previous_reading = 0.0f;

// Timing counters
unsigned long lastSampleMillis = 0;
unsigned long lastPostMillis   = 0;
unsigned long lastNvsCommit    = 0;
bool sensorReady = false;

// NTP Time Configuration
const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET_SEC = 19800; // IST (+5:30) = 19800 sec. Adjust if in a different timezone.
const int   DAYLIGHT_OFFSET_SEC = 0;

// ==============================================================================
// 3. HELPER FUNCTIONS
// ==============================================================================
String getFormattedDate() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 500)) {
    // If NTP not yet synced, return fallback date
    return "2026-10-22";
  }
  char dateStr[16];
  strftime(dateStr, sizeof(dateStr), "%Y-%m-%d", &timeinfo);
  return String(dateStr);
}

void connectToWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println();
  Serial.print("[WIFI] Connecting to SSID: ");
  Serial.println(WIFI_SSID);

  // Cleanly disconnect any pending connection attempts to avoid ESP-IDF state collision
  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WIFI] Connected! Assigned IP: ");
    Serial.println(WiFi.localIP());
    // Initialize SNTP client for real date stamping
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
  } else {
    Serial.println("[WIFI] Connection timed out. Ensure hotspot is set to 2.4 GHz Band.");
  }
}

void saveEnergyToNVS() {
  preferences.putFloat("kwh", cumulative_kWh);
  preferences.putFloat("prev_kwh", previous_reading);
  Serial.printf("[NVS] Persisted state to Flash: Cumulative=%.6f kWh | Prev=%.6f kWh\n", cumulative_kWh, previous_reading);
}

void sendReadingToBackend() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] WiFi not connected, attempting reconnection...");
    connectToWiFi();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[HTTP] Skipped HTTP POST: No WiFi connection.");
      return;
    }
  }

  HTTPClient http;
  String targetUrl = String(SERVER_BASE_URL) + "/meter/add-reading";
  http.begin(targetUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", HARDWARE_API_KEY);
  http.addHeader("X-User-ID", String(USER_ID));

  String readingDate = getFormattedDate();

  // Construct JSON Payload
  String payload = "{";
  payload += "\"user_id\":" + String(USER_ID) + ",";
  payload += "\"previous_reading\":" + String(previous_reading, 6) + ",";
  payload += "\"current_reading\":" + String(cumulative_kWh, 6) + ",";
  payload += "\"reading_date\":\"" + readingDate + "\",";
  payload += "\"voltage\":" + String(busVoltage_V, 2) + ",";
  payload += "\"current_mA\":" + String(current_mA, 2) + ",";
  payload += "\"power_w\":" + String(power_W, 3);
  payload += "}";

  Serial.println("\n--------------------------------------------------");
  Serial.print("[HTTP POST] Sending payload to: ");
  Serial.println(targetUrl);
  Serial.print("[PAYLOAD] ");
  Serial.println(payload);

  int httpCode = http.POST(payload);

  if (httpCode == HTTP_CODE_OK || httpCode == 201) {
    String response = http.getString();
    Serial.printf("[HTTP] Success (Status %d)\n", httpCode);
    Serial.print("[SERVER RESPONSE] ");
    Serial.println(response);

    // Update previous_reading for next delta calculation & persist to NVS
    previous_reading = cumulative_kWh;
    saveEnergyToNVS();
  } else {
    Serial.printf("[HTTP ERROR] POST failed with code %d : %s\n", httpCode, http.errorToString(httpCode).c_str());
  }

  http.end();
  Serial.println("--------------------------------------------------");
}

void checkSerialCommands() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.equalsIgnoreCase("RESET")) {
      cumulative_kWh = 0.0f;
      previous_reading = 0.0f;
      saveEnergyToNVS();
      Serial.println("[COMMAND] Cumulative kWh and previous reading reset to 0.000000 in NVS!");
    } else if (cmd.equalsIgnoreCase("POST")) {
      Serial.println("[COMMAND] Triggering immediate HTTP POST telemetry transmission...");
      sendReadingToBackend();
    } else if (cmd.equalsIgnoreCase("STATUS")) {
      Serial.println("\n================ VoltPulse Hardware Status ================");
      Serial.printf("  WiFi Status:       %s\n", (WiFi.status() == WL_CONNECTED ? "CONNECTED" : "DISCONNECTED"));
      if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("  Local IP:          %s (RSSI: %d dBm)\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
      }
      Serial.printf("  Backend Target:    %s/meter/add-reading\n", SERVER_BASE_URL);
      Serial.printf("  Consumer User ID:  %d\n", USER_ID);
      Serial.printf("  Sensor Ready:      %s (Addr: 0x%02X, SDA: %d, SCL: %d)\n",
                    (sensorReady ? "YES (INA219 32V, 2A mode)" : "NO / ERROR"),
                    INA219_I2C_ADDRESS, I2C_SDA_PIN, I2C_SCL_PIN);
      Serial.printf("  Bus Voltage:       %.2f V\n", busVoltage_V);
      Serial.printf("  Shunt Voltage:     %.2f mV\n", shuntVoltage_mV);
      Serial.printf("  Load Current:      %.2f mA\n", current_mA);
      Serial.printf("  Instant Power:     %.3f W\n", power_W);
      Serial.printf("  Cumulative Energy: %.6f kWh\n", cumulative_kWh);
      Serial.printf("  Previous Reading:  %.6f kWh\n", previous_reading);
      Serial.printf("  Reading Date:      %s\n", getFormattedDate().c_str());
      Serial.printf("  Uptime:            %lu sec\n", millis() / 1000);
      Serial.println("===========================================================\n");
    } else if (cmd.equalsIgnoreCase("HELP")) {
      Serial.println("\n--- Available Serial Commands ---");
      Serial.println("  STATUS : Display hardware, WiFi, sensor, and energy health status");
      Serial.println("  POST   : Trigger manual HTTP POST telemetry transmission immediately");
      Serial.println("  RESET  : Reset cumulative kWh counter in NVS memory to 0.0");
      Serial.println("  HELP   : Show this help menu");
      Serial.println("--------------------------------\n");
    }
  }
}

// ==============================================================================
// 4. SETUP
// ==============================================================================
void setup() {
  Serial.begin(115200);
  unsigned long startWait = millis();
  while (!Serial && (millis() - startWait < 2000)) {
    delay(10);
  }

  Serial.println("\n==================================================");
  Serial.println(" VoltPulse - ESP32 + INA219 Live Smart Meter");
  Serial.println("==================================================");

  // 1. Initialize NVS Flash Storage
  preferences.begin("voltpulse", false);
  cumulative_kWh   = preferences.getFloat("kwh", 0.0f);
  previous_reading = preferences.getFloat("prev_kwh", cumulative_kWh);
  Serial.printf("[NVS] Loaded stored energy: %.6f kWh (Prev reading: %.6f kWh)\n", cumulative_kWh, previous_reading);

  // 2. Initialize I2C Bus for INA219
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  delay(100);

  if (!ina219.begin(&Wire)) {
    Serial.println("[ERROR] Failed to find INA219 chip at 0x40!");
    Serial.println("Check SDA (GPIO 21), SCL (GPIO 22), VCC, and GND.");
    sensorReady = false;
  } else {
    // 32V, 2A calibration profile (resolution ~0.8mA)
    ina219.setCalibration_32V_2A();
    sensorReady = true;
    Serial.println("[OK] INA219 calibrated and ready (32V, 2A mode).");
  }

  // 3. Connect to Wi-Fi
  connectToWiFi();

  lastSampleMillis = millis();
  lastPostMillis   = millis();
  lastNvsCommit    = millis();

  Serial.println("[INFO] Live telemetry integration loop starting...");
  Serial.println("Type 'HELP' in Serial Monitor for interactive commands.\n");
}

// ==============================================================================
// 5. MAIN LOOP
// ==============================================================================
void loop() {
  unsigned long now = millis();

  // Check for interactive commands from Serial monitor
  checkSerialCommands();

  // Task 1: High-Frequency Sensor Reading & Numerical Integration
  if (sensorReady && (now - lastSampleMillis >= TELEMETRY_SAMPLE_INTERVAL_MS)) {
    float dt_seconds = (now - lastSampleMillis) / 1000.0f;
    lastSampleMillis = now;

    // Read sensor metrics
    shuntVoltage_mV = ina219.getShuntVoltage_mV();
    busVoltage_V    = ina219.getBusVoltage_V();
    current_mA      = ina219.getCurrent_mA();
    power_mW        = ina219.getPower_mW();

    // Clamp small ADC noise near zero
    if (current_mA < 0.0f && current_mA > -2.0f) {
      current_mA = 0.0f;
    }
    power_W = power_mW / 1000.0f;
    if (power_W < 0.0f) {
      power_W = 0.0f;
    }

    // Numerical integration of power over time into Energy (kWh)
    // Energy (kWh) = (Power in Watts * time delta in hours) / 1000.0
    float dt_hours = dt_seconds / 3600.0f;
    float delta_kWh = (power_W * dt_hours) / 1000.0f;

    if (delta_kWh > 0.0f) {
      cumulative_kWh += delta_kWh;
    }

    // Stream instantaneous serial telemetry
    Serial.printf("[TELEMETRY] Bus: %6.2f V | Current: %7.2f mA | Power: %6.3f W | Accumulated: %10.6f kWh\n",
                  busVoltage_V, current_mA, power_W, cumulative_kWh);
  }

  // Task 2: Periodic HTTP POST to VoltPulse Backend
  if (now - lastPostMillis >= HTTP_POST_INTERVAL_MS) {
    lastPostMillis = now;
    sendReadingToBackend();
  }

  // Task 3: Periodic NVS Flash Backup
  if (now - lastNvsCommit >= NVS_COMMIT_INTERVAL_MS) {
    lastNvsCommit = now;
    saveEnergyToNVS();
  }

  delay(20);
}
