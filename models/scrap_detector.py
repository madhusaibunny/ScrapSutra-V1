import os
import json
import time
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

    # Convert every supported image to RGB
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Reduce huge images
    image.thumbnail(
        (1200, 1200)
    )

    return image


# =========================================================
# GEMINI SCRAP DETECTION
# =========================================================

def detect_scrap_type(image_path):

    default_result = uncertain_result()

    image = None

    try:

        print("Starting AI scrap detection...")

        client = get_client()

        if not client:
            return default_result


        image = prepare_image(
            image_path
        )


        prompt = """
You are an expert recyclable scrap material classifier.

Analyze the uploaded image carefully and identify the PRIMARY
recyclable material.

Allowed categories are ONLY:

Plastic
Paper
Cardboard
Metal
Glass
E-Waste
Other/Unknown

RULES:

1. Analyze the actual physical material in the image.

2. If one recyclable material is dominant, return:
   "detection_type": "single"

3. If multiple recyclable materials are clearly visible,
   return:
   "detection_type": "mixed"

4. If the image is unclear, blurry, unrelated to scrap,
   or impossible to classify confidently, return:
   "detection_type": "uncertain"

5. Do not invent objects or materials.

6. Confidence must be between 0 and 1.

7. If detection_type is "uncertain",
   materials MUST be an empty array.

Return ONLY valid JSON.

Example single:

{
    "detection_type": "single",
    "materials": [
        {
            "name": "Plastic",
            "confidence": 0.95
        }
    ]
}

Example mixed:

{
    "detection_type": "mixed",
    "materials": [
        {
            "name": "Plastic",
            "confidence": 0.90
        },
        {
            "name": "Metal",
            "confidence": 0.75
        }
    ]
}

Example uncertain:

{
    "detection_type": "uncertain",
    "materials": []
}
"""


        # =================================================
        # RETRY SETTINGS
        # =================================================

        MAX_RETRIES = 3

        response = None


        # =================================================
        # CALL GEMINI WITH RETRY
        # =================================================

        for attempt in range(MAX_RETRIES):

            try:

                print(
                    f"Gemini detection attempt "
                    f"{attempt + 1}/{MAX_RETRIES}"
                )


                response = client.models.generate_content(

                    model="gemini-3.6-flash",

                    contents=[
                        prompt,
                        image
                    ],

                    config=types.GenerateContentConfig(

                        response_mime_type="application/json",

                        temperature=0.1

                    )

                )


                # If successful, stop retrying

                if response and response.text:

                    print(
                        "AI detection successful"
                    )

                    break


            except Exception as e:

                print(
                    f"Gemini attempt "
                    f"{attempt + 1} failed: {e}"
                )


                # Wait before retrying
                # 2 seconds, then 4, then 6

                if attempt < MAX_RETRIES - 1:

                    wait_time = (attempt + 1) * 2

                    print(
                        f"Retrying in "
                        f"{wait_time} seconds..."
                    )

                    time.sleep(
                        wait_time
                    )

                else:

                    print(
                        "All Gemini attempts failed."
                    )


        # =================================================
        # NO RESPONSE
        # =================================================

        if not response or not response.text:

            return default_result


        print(
            "RAW AI RESPONSE:",
            response.text
        )


        # =================================================
        # PARSE JSON
        # =================================================

        try:

            result = json.loads(
                response.text
            )

        except json.JSONDecodeError:

            print(
                "Invalid JSON returned by AI"
            )

            return default_result


        # =================================================
        # VALIDATE CATEGORIES
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


        # =================================================
        # VALIDATE DETECTION TYPE
        # =================================================

        if detection_type not in {

            "single",
            "mixed",
            "uncertain"

        }:

            print(
                "Invalid detection type:",
                detection_type
            )

            return default_result


        # =================================================
        # UNCERTAIN RESULT
        # =================================================

        if detection_type == "uncertain":

            return default_result


        # =================================================
        # CLEAN MATERIALS
        # =================================================

        cleaned_materials = []


        for material in materials:

            if not isinstance(
                material,
                dict
            ):
                continue


            name = material.get(
                "name"
            )


            confidence = material.get(
                "confidence",
                0
            )


            # Ignore invalid category

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


        # =================================================
        # NO VALID MATERIAL FOUND
        # =================================================

        if not cleaned_materials:

            print(
                "No valid materials detected"
            )

            return default_result


        # =================================================
        # CONFIDENCE CHECK
        # =================================================

        if detection_type == "single":

            best_material = max(
                cleaned_materials,
                key=lambda x: x["confidence"]
            )


            if best_material["confidence"] < 0.60:

                print(
                    "Confidence too low:",
                    best_material["confidence"]
                )

                return default_result


            cleaned_materials = [
                best_material
            ]


        elif detection_type == "mixed":

            cleaned_materials = [

                material

                for material
                in cleaned_materials

                if material["confidence"] >= 0.50

            ]


            if len(
                cleaned_materials
            ) < 2:

                print(
                    "Not enough confident materials"
                )

                return default_result


        # =================================================
        # FINAL RESULT
        # =================================================

        final_result = {

            "detection_type": detection_type,

            "materials": cleaned_materials

        }


        print(
            "FINAL AI DETECTION:",
            final_result
        )


        return final_result


    except Exception as e:

        print(
            f"Scrap detection error: {e}"
        )

        return default_result


    finally:

        # Always close image safely

        if image:

            try:

                image.close()

            except Exception:

                pass