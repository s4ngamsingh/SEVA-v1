"""
Configuration settings for the SEVA Smartphone / Laptop Bridge.
Supports Multilingual Indic Voices: Hindi, Marathi, Gujarati, Konkani, and English.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# HARDWARE & NETWORK SETTINGS
# =============================================================================
GLASSES_IP = os.getenv("GLASSES_IP", "192.168.43.100")
CAPTURE_URL = f"http://{GLASSES_IP}/capture"
STATUS_URL = f"http://{GLASSES_IP}/status"
BUTTON_URL = f"http://{GLASSES_IP}/button"

POLL_INTERVAL = 0.25

# =============================================================================
# GEMINI AI CONFIGURATION
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Default language to respond in if user presses button silently (without speaking)
# Options: "hi" (Hindi), "mr" (Marathi), "gu" (Gujarati), "en" (English)
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "hi")

# =============================================================================
# MULTILINGUAL SYSTEM PROMPTS
# =============================================================================
# Instructs Gemini to listen to audio in any of the 5 languages and reply in the same language.
MULTILINGUAL_ASSISTIVE_PROMPT = """You are SEVA, an AI visual assistant for a visually impaired user wearing smart glasses in India.
The user is showing you what is in front of them and has asked a question in the attached audio or text.

SUPPORTED LANGUAGES:
- Hindi (हिन्दी)
- Marathi (मराठी)
- Gujarati (ગુજરાતી)
- Konkani (कोंकणी)
- English

INSTRUCTIONS:
1. Detect which language the user spoke/asked in (Hindi, Marathi, Gujarati, Konkani, or English).
2. Answer their question IN THAT EXACT SAME LANGUAGE.
3. If they ask about medicine, read the exact brand name, active ingredients/strength, and expiry date if visible.
4. Keep your answer under 2 sentences, clear, conversational, and helpful for a blind person.
5. On the very FIRST line, output a language tag:
   [LANG: mr] for Marathi
   [LANG: gu] for Gujarati
   [LANG: hi] for Hindi (or Konkani in Devanagari)
   [LANG: en] for English
6. On the next line, output ONLY the spoken answer.
7. Do NOT use bullet points, bolding, or markdown asterisks (*), as this text is fed directly to speech synthesis.
"""

# Fallback prompt when user clicks button silently (no voice audio recorded)
SILENT_SCENE_PROMPTS = {
    "hi": "[LANG: hi]\nआप एक चश्मे पहने व्यक्ति के सहायक हैं। सामने जो मुख्य वस्तु, व्यक्ति या रुकावट है, उसे 1-2 सरल वाक्यों में बताएं। कोई तारांकन या मार्कडाउन का उपयोग न करें।",
    "mr": "[LANG: mr]\nतुम्ही चष्मा घातलेल्या व्यक्तीचे सहाय्यक आहात. समोर जी मुख्य वस्तू, व्यक्ती किंवा अडथळा आहे, ते १-२ सोप्या वाक्यांत सांगा. कोणतेही मार्कडाउन वापरू नका.",
    "gu": "[LANG: gu]\nતમે ચશ્મા પહેરેલ વ્યક્તિના સહાયક છો. સામે જે મુખ્ય વસ્તુ, વ્યક્તિ કે અવરોધ છે, તે ૧-૨ સરળ વાક્યોમાં જણાવો. કોઈ માર્કડાઉન વાપરશો નહીં.",
    "en": "[LANG: en]\nYou are an assistant for a visually impaired user. In 1 to 2 clear sentences, describe what is directly in front. Do not use asterisks or markdown."
}
