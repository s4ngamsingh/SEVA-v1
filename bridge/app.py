"""
SEVA: Smart Eyewear for Visual Assistance - Multilingual Companion Bridge
Supports: Marathi, Konkani, Hindi, Gujarati, and English.

Features:
1. Multimodal Audio + Vision: Captures user's voice in ANY language (Hindi, Marathi, Gujarati, Konkani, English)
   and sends the raw audio + image directly to Gemini 1.5 Flash.
2. Zero language configuration needed: Gemini understands the spoken language automatically.
3. Natural Indian TTS: Uses Google Text-to-Speech (gTTS) with native accents for Hindi, Marathi, and Gujarati.
4. Auto-detects medicine, expiry dates, text, and scene obstacles.
"""

import io
import os
import re
import sys
import time
import tempfile
import threading
import requests
from PIL import Image

# Initialize Pygame for audio playback (if available)
try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

# Initialize gTTS for Indian languages
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False

# Fallback offline TTS
try:
    import pyttsx3
    offline_tts = pyttsx3.init()
    offline_tts.setProperty("rate", 160)
except Exception:
    offline_tts = None

# Audio recording via SpeechRecognition
try:
    import speech_recognition as sr
    HAS_SR = True
    recognizer = sr.Recognizer()
except ImportError:
    HAS_SR = False
    recognizer = None

from config import (
    GLASSES_IP,
    CAPTURE_URL,
    STATUS_URL,
    BUTTON_URL,
    POLL_INTERVAL,
    GEMINI_API_KEY,
    GEMINI_MODEL_NAME,
    DEFAULT_LANGUAGE,
    MULTILINGUAL_ASSISTIVE_PROMPT,
    SILENT_SCENE_PROMPTS,
)

# =============================================================================
# MULTILINGUAL SPEECH SYNTHESIS (OUTPUT)
# =============================================================================
def speak_multilingual(text: str, lang_code: str = "hi"):
    """
    Speaks text aloud using native accents for Indian languages:
    'mr' -> Marathi
    'gu' -> Gujarati
    'hi' -> Hindi / Konkani (Devanagari)
    'en' -> English
    """
    print(f"\n[SPEAKING in {lang_code.upper()}]: \"{text}\"\n")
    
    if HAS_GTTS and HAS_PYGAME:
        try:
            # Map konkani to marathi or hindi voice (phonetically closest in Devanagari)
            target_lang = "mr" if lang_code == "mr" else ("gu" if lang_code == "gu" else ("en" if lang_code == "en" else "hi"))
            
            tts = gTTS(text=text, lang=target_lang, slow=False)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_filename = fp.name
                tts.save(temp_filename)
            
            # Play through connected Bluetooth speaker via pygame
            pygame.mixer.music.load(temp_filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.05)
            
            # Clean up temp file
            try:
                os.remove(temp_filename)
            except Exception:
                pass
            return
        except Exception as e:
            print(f"[gTTS Warning] Playback failed: {e}. Falling back to offline TTS.")

    # Fallback to offline engine
    if offline_tts:
        try:
            offline_tts.say(text)
            offline_tts.runAndWait()
        except Exception as e:
            print(f"[Offline TTS Error]: {e}")

# =============================================================================
# MICROPHONE RECORDING (INPUT)
# =============================================================================
def record_user_voice(timeout: int = 4, phrase_time_limit: int = 6) -> bytes:
    """
    Records the user's spoken voice into in-memory WAV bytes.
    Works for ANY spoken language (Hindi, Marathi, Gujarati, Konkani, etc.).
    """
    if not HAS_SR:
        print("[MIC] SpeechRecognition not installed.")
        return None

    try:
        with sr.Microphone() as source:
            print("[MIC] Calibrating microphone for room noise...")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            # Play short chime prompt
            speak_multilingual("Listening...", lang_code="en")
            print("\n>>> BOLYE / SPEAK NOW (Hindi, Marathi, Gujarati, Konkani, English)... <<<")
            
            audio_data = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            wav_bytes = audio_data.get_wav_data()
            print(f"[MIC] Audio captured successfully ({len(wav_bytes)} bytes).")
            return wav_bytes

    except sr.WaitTimeoutError:
        print("[MIC] No speech detected (silence).")
        return None
    except Exception as e:
        print(f"[MIC Error]: {e}")
        return None

# =============================================================================
# INITIALIZE GEMINI CLIENT
# =============================================================================
client = None

def init_gemini():
    global client
    if not GEMINI_API_KEY:
        print("[WARNING] GEMINI_API_KEY is not set! Set it in your .env file.")
        return False
    
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"[AI] Gemini client initialized with model: {GEMINI_MODEL_NAME}")
        return True
    except ImportError:
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=GEMINI_API_KEY)
            client = legacy_genai.GenerativeModel(GEMINI_MODEL_NAME)
            print(f"[AI] Fallback to legacy google-generativeai with model: {GEMINI_MODEL_NAME}")
            return True
        except Exception as e:
            print(f"[AI Error] Could not initialize Gemini library: {e}")
            return False

# =============================================================================
# CORE MULTIMODAL INFERENCE
# =============================================================================
is_processing = False

def process_interaction(voice_mode: bool = True, typed_question: str = None):
    global is_processing
    if is_processing:
        print("[BUSY] Already processing a request, please wait...")
        return
    
    is_processing = True
    start_time = time.time()
    
    try:
        # 1. Capture User's Voice Audio
        audio_wav_bytes = None
        if not typed_question and voice_mode and HAS_SR:
            audio_wav_bytes = record_user_voice(timeout=3, phrase_time_limit=6)

        # 2. Fetch Image from Glasses
        print(f"\n[CAPTURE] Fetching frame from glasses ({CAPTURE_URL})...")
        resp = requests.get(CAPTURE_URL, timeout=4.0)
        if resp.status_code != 200:
            speak_multilingual("Glasses camera connection failed. Please check Wi-Fi.", lang_code="en")
            is_processing = False
            return
        
        image_bytes = resp.content
        image = Image.open(io.BytesIO(image_bytes))
        print(f"[CAPTURE] Image acquired ({len(image_bytes)} bytes).")

        # 3. Assemble Multimodal Contents
        contents = [image]

        if audio_wav_bytes:
            # Pass raw recorded audio (Multimodal Audio + Vision)
            try:
                from google.genai import types
                audio_part = types.Part.from_bytes(data=audio_wav_bytes, mime_type="audio/wav")
                contents.append(audio_part)
                contents.append(MULTILINGUAL_ASSISTIVE_PROMPT)
                print("[AI] Sending Image + Spoken Audio Question directly to Gemini...")
            except Exception:
                # If types.Part fails, fallback to passing prompt
                contents.append(MULTILINGUAL_ASSISTIVE_PROMPT)
        elif typed_question:
            # User typed question in terminal
            prompt = (
                f"{MULTILINGUAL_ASSISTIVE_PROMPT}\n"
                f"The user typed this exact question: \"{typed_question}\". "
                f"Identify the language of their question and answer in that exact same language."
            )
            contents.append(prompt)
            print(f"[AI] Asking Gemini with typed question: \"{typed_question}\"...")
        else:
            # Silent button tap -> Default to selected local language
            fallback_prompt = SILENT_SCENE_PROMPTS.get(DEFAULT_LANGUAGE, SILENT_SCENE_PROMPTS["hi"])
            contents.append(fallback_prompt)
            print(f"[AI] Silent button tap. Asking for general description in {DEFAULT_LANGUAGE.upper()}...")

        # 4. Call Gemini 1.5 Flash
        response_text = ""
        if hasattr(client, "models"):
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=contents,
            )
            response_text = response.text
        else:
            response = client.generate_content(contents)
            response_text = response.text

        latency = time.time() - start_time
        print(f"[AI Latency]: {latency:.2f} seconds")

        # 5. Parse Language Tag & Spoken Answer
        detected_lang = DEFAULT_LANGUAGE
        spoken_text = response_text.strip()

        # Check for [LANG: xx] tag on first line
        match = re.search(r"\[LANG:\s*([a-zA-Z]{2})\]", response_text)
        if match:
            detected_lang = match.group(1).lower()
            spoken_text = re.sub(r"\[LANG:\s*[a-zA-Z]{2}\]", "", response_text).strip()
        else:
            # Fallback Unicode character detection
            for char in spoken_text:
                code = ord(char)
                if 0x0A80 <= code <= 0x0AFF:
                    detected_lang = "gu" # Gujarati
                    break
                elif 0x0900 <= code <= 0x097F:
                    detected_lang = "hi" # Devanagari (Hindi/Marathi/Konkani)
                    break

        # Clean any stray formatting asterisks
        clean_text = spoken_text.replace("*", "").replace("#", "").strip()
        
        # 6. Speak in Native Accent
        speak_multilingual(clean_text, lang_code=detected_lang)

    except requests.exceptions.RequestException as e:
        print(f"[Network Error] Could not reach glasses at {GLASSES_IP}: {e}")
        speak_multilingual("Glasses connection timed out.", lang_code="en")
    except Exception as e:
        print(f"[Inference Error]: {e}")
        speak_multilingual("Error analyzing image.", lang_code="en")
    finally:
        is_processing = False

# =============================================================================
# BUTTON POLLING THREAD
# =============================================================================
def poll_glasses_button():
    """Polls glasses button to trigger voice question when clicked."""
    while True:
        try:
            resp = requests.get(BUTTON_URL, timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("button_pressed", False):
                    print("\n>>> TACTILE BUTTON PRESSED ON GLASSES! <<<")
                    process_interaction(voice_mode=True)
        except requests.exceptions.RequestException:
            pass
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)

# =============================================================================
# MAIN CONTROLLER
# =============================================================================
def main():
    print("=" * 70)
    print("  SEVA - Multilingual Visual Assistant")
    print("  Supported Languages: Marathi, Konkani, Hindi, Gujarati, English")
    print(f"  Target Glasses IP: {GLASSES_IP}")
    print("=" * 70)

    if not init_gemini():
        print("\nPlease configure your GEMINI_API_KEY in .env before running.")
        return

    # Start button poller
    t = threading.Thread(target=poll_glasses_button, daemon=True)
    t.start()

    speak_multilingual("SEVA visual assistant is online. आप प्रश्न विचारू शकता.", lang_code=DEFAULT_LANGUAGE)

    print("\n--- INSTRUCTIONS ---")
    print("  [1] Tap glasses button OR press [Enter] -> Speak in Hindi, Marathi, Gujarati, Konkani, or English.")
    print("  [2] Type a question in ANY language (e.g. 'हे कोणते औषध आहे?', 'આ કઈ દવા છે?', 'यह क्या है?')")
    print("  [3] Type 'q' to quit.\n")

    while True:
        try:
            cmd = input("Command [Enter=Voice, or type question] > ").strip()
            if cmd.lower() == "q":
                print("Exiting SEVA...")
                break
            elif cmd == "":
                process_interaction(voice_mode=True)
            else:
                process_interaction(voice_mode=False, typed_question=cmd)
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
