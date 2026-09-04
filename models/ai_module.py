import os
import json
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY")


# ==========================================
# DEFAULT RESULT
# ==========================================

def get_uncertain_result():
    return {
        "detection_type": "uncertain",
        "materials": [],
        "confidence": 0,
        "message": "AI could not confidently identify the scrap."
    }


# ==========================================
# GEMINI CLIENT
# ==========================================

def get_gemini_client():

    if not API_KEY:
        print("ERROR: GEMINI_API_KEY is missing!", flush=True)
        return None

    try:
        return genai.Client(api_key=API_KEY)

    except Exception as e:
        print(
            f"ERROR creating Gemini client: {type(e).__name__} - {e}",
            flush=True
        )
        return None


# ==========================================
# COMPRESS IMAGE
# ==========================================

def compress_image(image_path, quality=85):

    compressed_path = None

    try:
        root, _ = os.path.splitext(image_path)

        compressed_path = f"{root}_compressed.jpg"

        with Image.open(image_path) as img:

            img = img.convert("RGB")

            img.thumbnail(
                (1200, 1200),
                Image.Resampling.LANCZOS
            )

            img.save(
                compressed_path,
                "JPEG",
                optimize=True,
                quality=quality
            )

        return compressed_path

    except Exception as e:

        print(
            f"Image compression failed: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        return image_path


# ==========================================
# AI SCRAP DETECTION
# ==========================================

def detect_scrap_type(image_path=None):

    uncertain_result = get_uncertain_result()

    # --------------------------------------
    # CHECK IMAGE
    # --------------------------------------

    if not image_path:

        print(
            "ERROR: No image path provided.",
            flush=True
        )

        return uncertain_result


    # --------------------------------------
    # CHECK API KEY
    # --------------------------------------

    if not API_KEY:

        print(
            "ERROR: GEMINI_API_KEY is missing from environment.",
            flush=True
        )

        return uncertain_result


    compressed_path = None
    img = None


    try:

        # ----------------------------------
        # CREATE CLIENT
        # ----------------------------------

        client = get_gemini_client()

        if not client:
            return uncertain_result


        # ----------------------------------
        # COMPRESS IMAGE
        # ----------------------------------

        compressed_path = compress_image(image_path)


        # ----------------------------------
        # OPEN IMAGE
        # ----------------------------------

        img = Image.open(compressed_path)


        # ----------------------------------
        # AI PROMPT
        # ----------------------------------

        prompt = """
You are an AI system for ScrapSutra, a scrap and recyclable
material identification platform.

Analyze the uploaded image carefully.

Identify the PRIMARY recyclable scrap material.

You MUST choose only from these categories:

Plastic
Paper
Metal
Glass
E-Waste
Cardboard
Other/Unknown

Examples:

- Plastic bottles, containers, wrappers → Plastic
- Newspapers, office paper, books → Paper
- Steel, iron, aluminium, copper → Metal
- Bottles or broken glass → Glass
- Wires, chargers, phones, electronic components → E-Waste
- Cartons and corrugated boxes → Cardboard

Return ONLY valid JSON.

Use exactly this format:

{
    "detection_type": "single",
    "materials": [
        {
            "name": "Plastic",
            "confidence": 0.95
        }
    ]
}

Rules:

1. confidence must be between 0 and 1.
2. Use the most likely category if the image clearly contains scrap.
3. Only use "uncertain" when the image truly cannot be identified.
4. Do not add explanations.
5. Do not add markdown.
6. Do not return text outside JSON.
"""


        # ----------------------------------
        # CALL GEMINI
        # ----------------------------------

        response = client.models.generate_content(

            model="gemini-3.6-flash",

            contents=[
                prompt,
                img
            ],

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                temperature=0.1

            )
        )


        # ----------------------------------
        # DEBUG RESPONSE
        # ----------------------------------

        print(
            f"RAW GEMINI RESPONSE: {response.text}",
            flush=True
        )


        # ----------------------------------
        # CHECK EMPTY RESPONSE
        # ----------------------------------

        if not response.text:

            print(
                "ERROR: Gemini returned an empty response.",
                flush=True
            )

            return uncertain_result


        # ----------------------------------
        # PARSE JSON
        # ----------------------------------

        result = json.loads(response.text)


        # ----------------------------------
        # VALIDATE RESULT
        # ----------------------------------

        if not isinstance(result, dict):

            print(
                "ERROR: Gemini response is not a dictionary.",
                flush=True
            )

            return uncertain_result


        detection_type = result.get("detection_type")

        materials = result.get("materials", [])


        if detection_type not in [
            "single",
            "mixed",
            "uncertain"
        ]:

            print(
                f"ERROR: Invalid detection type: "
                f"{detection_type}",
                flush=True
            )

            return uncertain_result


        if not isinstance(materials, list):

            print(
                "ERROR: Materials is not a list.",
                flush=True
            )

            return uncertain_result


        # ----------------------------------
        # CLEAN MATERIAL DATA
        # ----------------------------------

        allowed_categories = [

            "Plastic",
            "Paper",
            "Metal",
            "Glass",
            "E-Waste",
            "Cardboard",
            "Other/Unknown"

        ]


        cleaned_materials = []


        for material in materials:

            name = material.get("name", "Other/Unknown")

            confidence = material.get(
                "confidence",
                0
            )


            # Fix invalid category

            if name not in allowed_categories:

                name = "Other/Unknown"


            # Convert confidence safely

            try:

                confidence = float(confidence)

            except (TypeError, ValueError):

                confidence = 0


            # Keep confidence between 0 and 1

            confidence = max(
                0,
                min(1, confidence)
            )


            cleaned_materials.append({

                "name": name,

                "confidence": confidence

            })


        # ----------------------------------
        # RETURN FINAL RESULT
        # ----------------------------------

        result["materials"] = cleaned_materials


        # Main confidence

        if cleaned_materials:

            result["confidence"] = max(

                material["confidence"]

                for material in cleaned_materials

            )

        else:

            result["confidence"] = 0


        print(
            f"FINAL AI RESULT: {result}",
            flush=True
        )


        return result


    # ======================================
    # ERROR HANDLING
    # ======================================

    except Exception as e:

        print(
            f"GEMINI DETECTION ERROR: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        return uncertain_result


    # ======================================
    # CLEANUP
    # ======================================

    finally:

        if img:

            try:
                img.close()

            except Exception:
                pass


        if (
            compressed_path
            and compressed_path != image_path
            and os.path.exists(compressed_path)
        ):

            try:
                os.remove(compressed_path)

            except Exception as e:

                print(
                    f"Could not remove compressed image: {e}",
                    flush=True
                )