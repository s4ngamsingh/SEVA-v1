# SEVA: Smart Eyewear for Visual Assistance
An Argus-inspired, split-architecture wireless assistive vision device built for hackathons under ₹2,100.

---

## Project Structure

```
SEVA/
├── EXECUTION_PLAN.md                  # Detailed hackathon execution roadmap
├── requirements.txt                   # Python dependencies for bridge app
├── .env.example                       # Environment configuration template
│
├── firmware/
│   └── seva_glasses/
│       ├── seva_glasses.ino           # Arduino firmware for ESP32-S3-CAM
│       └── camera_pins.h              # Camera pin definitions (ESP32-S3 Eye / Freenove / Xiao)
│
└── bridge/
    ├── config.py                      # Network, Gemini, and TTS configuration
    ├── app.py                         # Main companion app (HTTP poller + Gemini + Speech)
    └── test_gemini.py                 # Sanity test script for Gemini API verification
```

---

## Quick Start Guide

### Step 1: Python Bridge Setup (Laptop / Phone)

1. Open a terminal in the `SEVA` folder:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```
3. Open `.env` and paste your `GEMINI_API_KEY`.
4. Test that your Gemini API works:
   ```bash
   python bridge/test_gemini.py
   ```

---

### Step 2: Flash the XIAO ESP32S3 Sense Firmware

1. Install **Arduino IDE** (version 2.x recommended).
2. Go to **File > Preferences** and add the ESP32 board manager URL:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. In **Tools > Board > Boards Manager**, search for `esp32` by Espressif and install it.
4. In **Sketch > Include Library > Manage Libraries**, install:
   * **Adafruit_VL53L0X** (by Adafruit)
5. Open `firmware/seva_glasses/seva_glasses.ino` in Arduino IDE.
6. Configure your board settings under **Tools**:
   * **Board:** `XIAO_ESP32S3` *(Found under Tools > Board > esp32)*
   * **PSRAM:** `OPI PSRAM`
   * **USB CDC On Boot:** `Enabled`
   * **Upload Speed:** `921600`
7. Update `WIFI_SSID` and `WIFI_PASSWORD` at the top of the file to match your phone's mobile hotspot.
8. Connect the XIAO ESP32S3 Sense via USB-C and click **Upload**.


---

### Step 3: Run the Full System

1. Turn on your **Mobile Hotspot** on your phone (ensure 4G/5G mobile data is ON).
2. Power on the glasses (flick the slide switch).
3. Check your phone hotspot's "Connected Devices" list to find the IP address assigned to the glasses (e.g., `192.168.43.100`).
4. Update `GLASSES_IP` in `.env` with that IP address.
5. Connect your **Bluetooth Speaker / Earphones** to your laptop or phone.
6. Start the companion bridge:
   ```bash
   python bridge/app.py
   ```
7. **Ask Questions in ANY Language (Marathi, Konkani, Hindi, Gujarati, English):**
   * **Voice Input:** Tap the glasses button (or press `Enter` in console). When it says *"Listening..."*, speak naturally:
     * **Marathi (मराठी):** *"हे कोणते औषध आहे?"* or *"समोर काय आहे?"*
     * **Hindi (हिन्दी):** *"यह कौन सी दवाई है?"* or *"एक्सपायरी डेट क्या है?"*
     * **Gujarati (ગુજરાતી):** *"આ કઈ દવા છે?"* or *"સામે શું છે?"*
     * **Konkani (कोंकणी):** *"हें खंयचें वखत आसा?"* or *"मुखार कितें आसा?"*
     * **English:** *"Which medicine is this?"* or *"What is in front of me?"*
   * **Automatic Speech Output:** Gemini detects the language automatically and speaks back in the **exact same language and native accent** through your Bluetooth speaker.
   * **Silent Button Tap:** If you press the button without speaking, it automatically speaks a general scene description in your configured `DEFAULT_LANGUAGE` (Hindi/Marathi/Gujarati).

