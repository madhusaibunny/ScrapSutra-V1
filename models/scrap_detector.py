import os
import tensorflow as tf
from PIL import Image


# =========================================================
# SCRAPSUTRA LOCAL AI MODEL
# =========================================================

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scrapsutra_model.keras"
)

CLASS_NAMES = [
    "Cardboard",
    "E-Waste",
    "Glass",
    "Metal",
    "Paper",
    "Plastic"
]

_model = None


# =========================================================
# LOAD MODEL
# =========================================================

def get_model():

    global _model

    if _model is None:

        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"ScrapSutra model not found: {MODEL_PATH}"
            )

        print(
            f"Loading ScrapSutra AI model: {MODEL_PATH}",
            flush=True
        )

        _model = tf.keras.models.load_model(
            MODEL_PATH,
            compile=False
        )

        print(
            "ScrapSutra AI model loaded successfully.",
            flush=True
        )

    return _model


# =========================================================
# DEFAULT UNCERTAIN RESULT
# =========================================================

def uncertain_result():

    return {
        "detection_type": "uncertain",
        "materials": []
    }


# =========================================================
# SCRAP DETECTION
# =========================================================

def detect_scrap_type(image_path):

    try:

        print(
            "Starting ScrapSutra local AI detection...",
            flush=True
        )

        model = get_model()

        # Open image
        image = Image.open(image_path).convert("RGB")

        # Model expects 224 x 224
        image = image.resize((224, 224))

        # Convert image to TensorFlow array
        image_array = tf.keras.utils.img_to_array(image)

        # Add batch dimension
        image_array = tf.expand_dims(
            image_array,
            axis=0
        )

        # IMPORTANT:
        # The model already contains Rescaling(1/127.5, offset=-1)
        predictions = model.predict(
            image_array,
            verbose=0
        )[0]

        predicted_index = int(
            tf.argmax(predictions).numpy()
        )

        confidence = float(
            predictions[predicted_index]
        )

        detected_material = CLASS_NAMES[
            predicted_index
        ]

        print(
            f"AI prediction: {detected_material}",
            flush=True
        )

        print(
            f"AI confidence: {confidence:.4f}",
            flush=True
        )

        # Confidence threshold
        if confidence < 0.60:

            print(
                "AI confidence below 60%. Marking as uncertain.",
                flush=True
            )

            return uncertain_result()

        result = {
            "detection_type": "single",
            "materials": [
                {
                    "name": detected_material,
                    "confidence": confidence
                }
            ]
        }

        print(
            f"FINAL AI DETECTION: {result}",
            flush=True
        )

        return result

    except Exception as e:

        print(
            f"Scrap detection error: {e}",
            flush=True
        )

        return uncertain_result()