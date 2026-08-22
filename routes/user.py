import os
import json
import uuid

from PIL import Image

from werkzeug.utils import secure_filename

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from flask_login import (
    login_required,
    current_user
)

from database.models import (
    db,
    ScrapUpload,
    PickupRequest
)


# =========================================================
# USER BLUEPRINT
# =========================================================

user_bp = Blueprint("user", __name__)


# =========================================================
# ALLOWED IMAGE FILES
# =========================================================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def allowed_file(filename):

    if not filename:
        return False

    filename = filename.strip()

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].strip().lower()

    return extension in ALLOWED_EXTENSIONS


# =========================================================
# VERIFY IMAGE
# =========================================================

def verify_image(file):

    try:

        file.stream.seek(0)

        image = Image.open(file.stream)

        image.verify()

        file.stream.seek(0)

        return True

    except Exception as e:

        print(
            f"Invalid image upload: {type(e).__name__} - {e}",
            flush=True
        )

        try:
            file.stream.seek(0)
        except Exception:
            pass

        return False


# =========================================================
# USER DASHBOARD
# =========================================================

@user_bp.route("/dashboard")
@login_required
def dashboard():

    scraps = (
        ScrapUpload.query
        .filter_by(user_id=current_user.id)
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    pending_count = sum(
        1
        for scrap in scraps
        if scrap.status == "pending"
    )

    approved_count = sum(
        1
        for scrap in scraps
        if scrap.status == "approved"
    )

    total_points = sum(
        scrap.points_earned or 0
        for scrap in scraps
        if scrap.status == "approved"
    )

    notification = None


    # =====================================================
    # CHECK SCRAP NOTIFICATIONS
    # =====================================================

    unseen_scrap = (
        ScrapUpload.query
        .filter(
            ScrapUpload.user_id == current_user.id,
            ScrapUpload.notification_seen.is_(False),
            ScrapUpload.status.in_(["approved", "rejected"])
        )
        .order_by(ScrapUpload.created_at.desc())
        .first()
    )

    if unseen_scrap:

        if unseen_scrap.status == "approved":

            notification = {
                "title": "Scrap Approved! 🎉",
                "message": (
                    f"Your {unseen_scrap.scrap_type} scrap "
                    f"has been approved. You earned "
                    f"{unseen_scrap.points_earned or 0} Eco Points!"
                ),
                "status": "success"
            }

        else:

            notification = {
                "title": "Scrap Rejected",
                "message": (
                    f"Your {unseen_scrap.scrap_type} scrap "
                    f"request was rejected by the admin."
                ),
                "status": "error"
            }

        unseen_scrap.notification_seen = True

        db.session.commit()


    # =====================================================
    # CHECK PICKUP NOTIFICATIONS
    # =====================================================

    else:

        unseen_pickup = (
            PickupRequest.query
            .filter(
                PickupRequest.user_id == current_user.id,
                PickupRequest.notification_seen.is_(False),
                PickupRequest.status.in_(["approved", "rejected"])
            )
            .order_by(PickupRequest.created_at.desc())
            .first()
        )

        if unseen_pickup:

            if unseen_pickup.status == "approved":

                notification = {
                    "title": "Pickup Approved! 🚚",
                    "message": (
                        f"Your pickup request for "
                        f"{unseen_pickup.pickup_date} "
                        f"has been approved by the admin."
                    ),
                    "status": "success"
                }

            else:

                notification = {
                    "title": "Pickup Rejected",
                    "message": (
                        f"Your pickup request for "
                        f"{unseen_pickup.pickup_date} "
                        f"was rejected by the admin."
                    ),
                    "status": "error"
                }

            unseen_pickup.notification_seen = True

            db.session.commit()


    return render_template(
        "user/dashboard.html",
        scraps=scraps,
        pending_count=pending_count,
        approved_count=approved_count,
        total_points=total_points,
        notification=notification
    )


# =========================================================
# UPLOAD SCRAP
# =========================================================

@user_bp.route(
    "/upload-scrap",
    methods=["GET", "POST"]
)
@login_required
def upload_scrap():

    # =====================================================
    # GET REQUEST
    # =====================================================

    if request.method == "GET":

        return render_template(
            "user/upload.html"
        )


    # =====================================================
    # CHECK IMAGE FIELD
    # =====================================================

    if "scrap_image" not in request.files:

        flash(
            "Please select an image.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    file = request.files["scrap_image"]


    # =====================================================
    # CHECK EMPTY FILE
    # =====================================================

    if not file or not file.filename:

        flash(
            "Please select an image.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # CLEAN FILENAME
    # =====================================================

    original_filename = secure_filename(
        file.filename
    )


    if not original_filename:

        flash(
            "Invalid image filename.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # CHECK FILE EXTENSION
    # =====================================================

    if not allowed_file(original_filename):

        extension = ""

        if "." in original_filename:

            extension = original_filename.rsplit(
                ".",
                1
            )[1].lower()

        print(
            f"Rejected file: {original_filename} | "
            f"Extension: {extension} | "
            f"MIME: {file.mimetype}",
            flush=True
        )

        flash(
            "Only PNG, JPG, JPEG and WEBP images are allowed.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # VERIFY REAL IMAGE
    # =====================================================

    if not verify_image(file):

        flash(
            "The uploaded file is not a valid image.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # CREATE UNIQUE FILENAME
    # =====================================================

    unique_filename = (
        f"{uuid.uuid4().hex}_"
        f"{original_filename}"
    )


    # =====================================================
    # GET UPLOAD FOLDER
    # =====================================================

    upload_folder = current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.join(
            "static",
            "uploads"
        )
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )


    # =====================================================
    # CREATE IMAGE PATH
    # =====================================================

    image_path = os.path.join(
        upload_folder,
        unique_filename
    )


    # =====================================================
    # SAVE IMAGE
    # =====================================================

    try:

        file.save(image_path)

        print(
            f"Image saved successfully: {image_path}",
            flush=True
        )

    except Exception as e:

        print(
            f"IMAGE SAVE ERROR: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        flash(
            "Unable to save the uploaded image.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # DEFAULT DETECTION VALUES
    # =====================================================

    detection_type = "uncertain"

    materials = []

    detected_type = "Other/Unknown"

    confidence_score = 0.0


    # =====================================================
    # MANUAL CATEGORY
    # =====================================================

    manual_category = request.form.get(
        "manual_category",
        ""
    ).strip()


    # =====================================================
    # AI SCRAP DETECTION
    # =====================================================

    try:

        # ---------------------------------------------
        # MANUAL CATEGORY SELECTED
        # ---------------------------------------------

        if manual_category:

            detection_type = "single"

            detected_type = manual_category

            confidence_score = 1.0

            materials = [
                {
                    "name": manual_category,
                    "confidence": 1.0
                }
            ]

            print(
                f"Manual category selected: "
                f"{manual_category}",
                flush=True
            )


        # ---------------------------------------------
        # AI DETECTION
        # ---------------------------------------------

        else:

            print(
                "Starting AI scrap detection...",
                flush=True
            )

            from models.scrap_detector import (
                detect_scrap_type
            )

            result = detect_scrap_type(
                image_path
            )

            print(
                f"AI DETECTION RESULT: {result}",
                flush=True
            )


            if result:

                detection_type = result.get(
                    "detection_type",
                    "uncertain"
                )

                materials = result.get(
                    "materials",
                    []
                )


                # =====================================
                # SINGLE SCRAP
                # =====================================

                if (
                    detection_type == "single"
                    and materials
                ):

                    detected_type = materials[0].get(
                        "name",
                        "Other/Unknown"
                    )

                    try:

                        confidence_score = float(
                            materials[0].get(
                                "confidence",
                                0
                            )
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        confidence_score = 0.0


                # =====================================
                # MIXED SCRAP
                # =====================================

                elif (
                    detection_type == "mixed"
                    and materials
                ):

                    detected_type = "Mixed Scrap"

                    confidence_values = []

                    for material in materials:

                        try:

                            confidence = float(
                                material.get(
                                    "confidence",
                                    0
                                )
                            )

                            confidence_values.append(
                                confidence
                            )

                        except (
                            TypeError,
                            ValueError
                        ):

                            pass


                    if confidence_values:

                        confidence_score = (
                            sum(confidence_values)
                            / len(confidence_values)
                        )


                # =====================================
                # UNCERTAIN
                # =====================================

                else:

                    detection_type = "uncertain"

                    detected_type = "Other/Unknown"

                    confidence_score = 0.0

                    materials = []


    except Exception as e:

        print(
            f"AI DETECTION FAILED: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        detection_type = "uncertain"

        detected_type = "Other/Unknown"

        confidence_score = 0.0

        materials = []


    # =====================================================
    # SAVE DETECTED LABELS
    # =====================================================

    detected_labels = json.dumps(
        materials
    )


    # =====================================================
    # CREATE SCRAP RECORD
    # =====================================================

    scrap = ScrapUpload(

        user_id=current_user.id,

        # IMPORTANT:
        # Save ONLY the filename.
        # Example:
        # abc123_metal.webp
        image_url=unique_filename,

        scrap_type=detected_type,

        detected_type=detected_type,

        detected_labels=detected_labels,

        confidence_score=confidence_score,

        estimated_price=0.0,

        status="pending",

        weight=0.0,

        points_earned=0,

        notification_seen=True
    )


    # =====================================================
    # SAVE TO DATABASE
    # =====================================================

    try:

        db.session.add(scrap)

        db.session.commit()

        print(
            f"SCRAP SAVED SUCCESSFULLY | "
            f"ID: {scrap.id} | "
            f"USER: {current_user.id} | "
            f"TYPE: {detected_type}",
            flush=True
        )


    except Exception as e:

        db.session.rollback()

        print(
            f"DATABASE ERROR: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        flash(
            "Unable to save your scrap request.",
            "danger"
        )

        return redirect(
            url_for("user.upload_scrap")
        )


    # =====================================================
    # SUCCESS MESSAGE
    # =====================================================

    if detection_type == "mixed":

        flash(
            "Mixed scrap detected successfully! "
            "Your request has been sent for admin review.",
            "success"
        )

    elif detection_type == "uncertain":

        flash(
            "We could not confidently identify the scrap. "
            "Your image has been sent for admin review.",
            "warning"
        )

    else:

        flash(
            f"{detected_type} detected successfully! "
            "Waiting for admin approval.",
            "success"
        )


    return redirect(
        url_for("user.dashboard")
    )


# =========================================================
# PICKUP REQUEST
# =========================================================

@user_bp.route(
    "/pickup",
    methods=["GET", "POST"]
)
@login_required
def pickup():

    if request.method == "GET":

        return render_template(
            "user/pickup.html"
        )


    # =====================================================
    # GET FORM DATA
    # =====================================================

    pickup_date = request.form.get(
        "date"
    )

    time_slot = request.form.get(
        "time"
    )

    address = request.form.get(
        "address"
    )

    latitude = request.form.get(
        "latitude"
    )

    longitude = request.form.get(
        "longitude"
    )


    # =====================================================
    # VALIDATION
    # =====================================================

    if (
        not pickup_date
        or not time_slot
        or not address
    ):

        flash(
            "Please fill all required fields.",
            "danger"
        )

        return redirect(
            url_for("user.pickup")
        )


    # =====================================================
    # CREATE PICKUP REQUEST
    # =====================================================

    pickup_request = PickupRequest(

        user_id=current_user.id,

        pickup_date=pickup_date,

        time_slot=time_slot,

        address=address,

        latitude=latitude,

        longitude=longitude,

        status="pending",

        notification_seen=True
    )


    try:

        db.session.add(
            pickup_request
        )

        db.session.commit()

        print(
            f"PICKUP SAVED SUCCESSFULLY | "
            f"ID: {pickup_request.id}",
            flush=True
        )


    except Exception as e:

        db.session.rollback()

        print(
            f"PICKUP DATABASE ERROR: "
            f"{type(e).__name__} - {e}",
            flush=True
        )

        flash(
            "Unable to submit pickup request.",
            "danger"
        )

        return redirect(
            url_for("user.pickup")
        )


    flash(
        "Pickup request submitted successfully!",
        "success"
    )


    return redirect(
        url_for("user.dashboard")
    )