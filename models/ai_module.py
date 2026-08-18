import os
import json
import io
from PIL import Image
from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv

# Load environment securely for V1 (points to server/.env if needed, or environment)
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'server', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

API_KEY = os.environ.get('GEMINI_API_KEY')

def compress_image(image_path, quality=50):
    try:
        root, ext = os.path.splitext(image_path)
        compressed_path = f"{root}_compressed{ext}"
        
        img = Image.open(image_path)
        img.verify() # Ensure valid image
        
        # Reload after verify, convert to RGB for JPG format
        img = Image.open(image_path).convert('RGB')
        
        # Resize to max 800x800 to speed up Gemini
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        
        img.save(compressed_path, "JPEG", optimize=True, quality=quality)
        return compressed_path
    except Exception as e:
        print(f"Compression failed: {e}")
        return image_path

def get_gemini_client():
    if not API_KEY: return None
    return genai.Client(api_key=API_KEY)

def detect_scrap_type(image_path=None):
    uncertain_result = {
        'detection_type': 'uncertain',
        'materials': [],
        'confidence': 0,
        'message': 'AI could not confidently identify the scrap.'
    }
    
    if not image_path or not API_KEY:
        print("Missing Image or Gemini API Key!")
        return uncertain_result

    try:
        client = get_gemini_client()
        if not client:
            return uncertain_result
            
        compressed_path = compress_image(image_path)
        img = Image.open(compressed_path)
        
        prompt = """Analyze this image and detect recyclable scrap materials. 
Supported categories: Plastic, Paper, Metal, Glass, E-Waste, Cardboard, Other/Unknown.
Return ONLY a valid JSON object matching this schema:
{
  "detection_type": "single" | "mixed" | "uncertain",
  "materials": [
    {
      "name": "CategoryName",
      "confidence": 0.95
    }
  ]
}
If multiple materials are present, use detection_type "mixed". If none are found or you are unsure, use "uncertain" and empty materials array."""

        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        img.close()
        
        if compressed_path != image_path and os.path.exists(compressed_path):
            os.remove(compressed_path)
            
        print(f"Raw Gemini Response: {response.text}")
        
        try:
            result = json.loads(response.text)
            if 'detection_type' not in result:
                return uncertain_result
            return result
        except json.JSONDecodeError:
            print(f"JSONDecodeError: Response was not valid JSON. Response text: {response.text}")
            return uncertain_result

    except Exception as e:
        print(f"Gemini API Error: {type(e).__name__} - {e}", flush=True)
        return uncertain_result
