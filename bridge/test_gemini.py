"""
SEVA: Quick Gemini API Sanity Test
Run this script first to verify that your GEMINI_API_KEY works properly.
"""

import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "")

if not API_KEY:
    print("[ERROR] GEMINI_API_KEY is missing!")
    print("Please create a .env file and add: GEMINI_API_KEY=your_actual_key_here")
    exit(1)

print(f"[TEST] Using API Key: {API_KEY[:6]}...{API_KEY[-4:]}")

# Create a simple test image in memory
test_img = Image.new("RGB", (300, 150), color=(30, 144, 255))
d = ImageDraw.Draw(test_img)
d.text((20, 60), "SEVA Assistive Vision", fill=(255, 255, 255))

try:
    from google import genai
    client = genai.Client(api_key=API_KEY)
    print("[TEST] Calling Gemini 1.5 Flash...")
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[test_img, "What text and colors do you see in this image? Answer in 1 short sentence."]
    )
    print("\n[SUCCESS] Gemini Response:")
    print(f" -> {response.text.strip()}\n")
    print("Your Gemini API setup is 100% verified and ready for SEVA!")
except Exception as e:
    print(f"[ERROR] Gemini API call failed: {e}")
