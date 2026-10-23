# VoltPulse — ESP32 + INA219 Smart Meter Firmware

## Overview
This firmware turns an **ESP32 DevKit V1** and an **INA219 sensor** into a connected IoT Smart Electricity Meter for the **VoltPulse** system.

### Key Features
* **High-Precision Telemetry**: Measures Bus Voltage (V), Shunt Voltage (mV), Load Current (mA), and Instantaneous Power (W) over I²C.
* **Energy Integration**: Computes real-time Energy ($\text{kWh} = \frac{P \times \Delta t_{\text{hours}}}{1000}$) via continuous numerical integration every 1 second.
* **NVS Flash Persistence**: Persists accumulated kWh to non-volatile flash storage using `Preferences.h` (`voltpulse` namespace) so readings survive power outages and reboots.
* **Automatic Ingestion**: Transmits periodic JSON telemetry to the FastAPI `/meter/add-reading` endpoint over HTTP POST every 10 seconds.
* **Long-Lived Hardware Authentication**: Authenticates with a persistent `X-API-Key: voltpulse-hw-secret-key-2026` header so tokens never expire.
* **Serial Debugger & Interactive CLI**: Includes clean serial logging and commands (`STATUS`, `POST`, `RESET`, `HELP`).

---

## 1. Hardware Connections

```
              +-------------------+
              |    ESP32 DevKit   |
              |                   |
              |  3V3  GND  21  22 |
              +---+----+---+---+--+
                  |    |   |   |
                  |    |   |   +-------- SCL
                  |    |   +------------ SDA
                  |    +---------------- GND
                  +--------------------- VCC
                                           |
                                  +--------+--------+
                                  |     INA219      |
                                  |                 |
  DC Source (+) ----------------> | VIN+       VIN- | ---------------> Load (+) (Fan / Motor)
                                  +-----------------+
  DC Source (-) -----------------------------------------------------> Load (-) & ESP32 GND
```

### Wiring Table
| INA219 Pin | ESP32 Pin | Connection Target / Notes |
| :--- | :--- | :--- |
| **VCC** | **3V3** (or 5V) | Logic supply for INA219 |
| **GND** | **GND** | Common ground (connect with DC Power Supply GND) |
| **SDA** | **GPIO 21** | I²C Serial Data |
| **SCL** | **GPIO 22** | I²C Serial Clock |
| **VIN+** | — | Connect to (+) terminal of your DC Power Supply / Battery |
| **VIN-** | — | Connect to (+) terminal of the electrical Load (e.g., 12V fan, light) |

---

## 2. Network & Backend Configuration

At the top of `firmware/voltpulse/voltpulse.ino`:

```cpp
// Your Wi-Fi network credentials
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Backend Target Server
const char* SERVER_BASE_URL = "http://10.120.134.33:8000";

// Hardware API Key configured in backend/.env
const char* HARDWARE_API_KEY = "voltpulse-hw-secret-key-2026";

// Target Consumer User ID (Default: 2)
const int USER_ID = 2;
```

---

## 3. CLI Build & Flash Instructions (No IDE Needed)

### Target Board & Port
* **FQBN**: `esp32:esp32:esp32` (ESP32 Dev Module / ESP32 DevKit V1)
* **Serial Port**: `COM15`

### Step 1: Compile the Firmware
From the project root:
```powershell
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/voltpulse
```
*(Uses ~1 MB of program storage and 50 KB of RAM, compiling cleanly).*

### Step 2: Upload to ESP32 on COM15
```powershell
arduino-cli upload -p COM15 --fqbn esp32:esp32:esp32 firmware/voltpulse
```

> **ESP32 Bootloader Tip**: If `Connecting........` appears and hangs, press and hold the **BOOT** (or **IO0**) button on your ESP32 board until the flash progress percentage starts, then release it.

### Step 3: Open the Serial Monitor
```powershell
arduino-cli monitor -p COM15 -c baudrate=115200
```

---

## 4. Interactive Serial CLI Commands

Type any of the following commands into the Serial Monitor at **115200 baud**:

| Command | Action |
| :--- | :--- |
| `STATUS` | Prints complete hardware health: Wi-Fi IP/RSSI, sensor state, live V, mA, W, and accumulated kWh. |
| `POST` | Triggers an immediate HTTP POST telemetry transmission to `/meter/add-reading`. |
| `RESET` | Clears and resets the cumulative kWh counter in ESP32 NVS flash storage back to `0.0`. |
| `HELP` | Prints the interactive commands help menu. |
