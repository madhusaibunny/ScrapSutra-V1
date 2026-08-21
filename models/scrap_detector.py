import os
import json
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types


# =========================================================
# LOAD ENVIRONMENT
# =========================================================

load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY")


# =========================================================
# DEFAULT UNCERTAIN RESULT
# =========================================================

def uncertain_result():

    return {
        "detection_type": "uncertain",
        "materials": []
    }


# =========================================================
# GET GEMINI CLIENT
# =========================================================

def get_client():

    if not API_KEY:
        print("GEMINI_API_KEY is missing")
        return None

    return genai.Client(
        api_key=API_KEY
    )


# =========================================================
# IMAGE PREPARATION
# =========================================================

def prepare_image(image_path):

    image = Image.open(image_path)

    image = image.convert("RGB")

    # Reduce huge images but preserve quality
    image.thumbnail(
        (1200, 1200)
    )

    return image


# =========================================================
# SCRAP DETECTION
# =========================================================

def detect_scrap_type(image_path):

    default_result = uncertain_result()

    try:

        client = get_client()

        if not client:
            return default_result


        image = prepare_image(
            image_path
        )


        prompt = """
You are an expert recyclable scrap material classifier.

Analyze the uploaded image carefully.

Your task is to identify the PRIMARY recyclable materials visible.

Allowed categories are ONLY:

Plastic
Paper
Cardboard
Metal
Glass
E-Waste
Other/Unknown

IMPORTANT RULES:

1. Look carefully at the actual physical material, not just
   the object name.

2. If one main material is clearly dominant, return:
   detection_type = "single"

3. If two or more different recyclable materials are clearly
   visible, return:
   detection_type = "mixed"

4. If the image is blurry, unclear, contains no scrap,
   or you cannot identify the material confidently, return:
   detection_type = "uncertain"

5. Never guess.

6. Confidence must be between 0 and 1.

7. For uncertain results, materials must be an empty array.

Return ONLY valid JSON in exactly this format:

{
    "detection_type": "single",
    "materials": [
        {
            "name": "Plastic",
            "confidence": 0.95
        }
    ]
}
"""


        response = client.models.generate_content(

            model="gemini-2.0-flash",

            contents=[
                prompt,
                image
            ],

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                temperature=0.1

            )

        )


        image.close()


        if not response.text:

            return default_result


        result = json.loads(
            response.text
        )


        # =================================================
        # VALIDATE RESULT
        # =================================================

        allowed_categories = {

            "Plastic",
            "Paper",
            "Cardboard",
            "Metal",
            "Glass",
            "E-Waste",
            "Other/Unknown"

        }


        detection_type = result.get(
            "detection_type"
        )


        materials = result.get(
            "materials",
            []
        )


        if detection_type not in {

            "single",
            "mixed",
            "uncertain"

        }:

            return default_result


        # Uncertain must have no materials

        if detection_type == "uncertain":

            return default_result


        cleaned_materials = []


        for material in materials:

            name = material.get("name")

            confidence = material.get(
                "confidence",
                0
            )


            if name not in allowed_categories:

                continue


            try:

                confidence = float(
                    confidence
                )

            except (
                ValueError,
                TypeError
            ):

                confidence = 0


            # Keep confidence between 0 and 1

            confidence = max(
                0,
                min(
                    confidence,
                    1
                )
            )


            cleaned_materials.append({

                "name": name,

                "confidence": confidence

            })


        # No valid material

        if not cleaned_materials:

            return default_result


        # =================================================
        # CONFIDENCE THRESHOLD
        # =================================================

        if detection_type == "single":

            if cleaned_materials[0]["confidence"] < 0.60:

                return default_result


        elif detection_type == "mixed":

            cleaned_materials = [

                material

                for material
                in cleaned_materials

                if material["confidence"] >= 0.50

            ]


            if len(cleaned_materials) < 2:

                return default_result


        return {

            "detection_type": detection_type,

            "materials": cleaned_materials

        }


    except Exception as e:

        print(
            f"Scrap detection error: {e}"
        )

        return default_result