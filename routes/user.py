import os
import json
import uuid
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

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# USER DASHBOARD
# =========================================================

@user_bp.route("/dashboard")
@login_required
def dashboard():

    # -----------------------------------------------------
    # GET USER SCRAPS
    # -----------------------------------------------------

    scraps = (
        ScrapUpload.query
        .filter_by(user_id=current_user.id)
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )


    # -----------------------------------------------------
    # DASHBOARD COUNTS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # TOTAL ECO POINTS
    # -----------------------------------------------------

    total_points = sum(
        scrap.points_earned or 0
        for scrap in scraps
        if scrap.status == "approved"
    )


    # -----------------------------------------------------
    # DEFAULT NOTIFICATION
    # -----------------------------------------------------

    notification = None


    # =====================================================
    # CHECK SCRAP NOTIFICATION
    # =====================================================

    unseen_scrap = (
        ScrapUpload.query
        .filter(
            ScrapUpload.user_id == current_user.id,
            ScrapUpload.notification_seen.is_(False),
            ScrapUpload.status.in_(
                ["approved", "rejected"]
            )
        )
        .order_by(
            ScrapUpload.created_at.desc()
        )
        .first()
    )


    if unseen_scrap:

        if unseen_scrap.status == "approved":

            notification = {
                "title": "Scrap Approved! 🎉",
                "message": (
                    f"Your {unseen_scrap.scrap_type} "
                    f"scrap has been approved. "
                    f"You earned "
                    f"{unseen_scrap.points_earned or 0} "
                    f"Eco Points!"
                ),
                "status": "success"
            }

        else:

            notification = {
                "title": "Scrap Rejected",
                "message": (
                    f"Your {unseen_scrap.scrap_type} "
                    f"scrap request was rejected "
                    f"by the admin."
                ),
                "status": "error"
            }


        unseen_scrap.notification_seen = True

        db.session.commit()


    # =====================================================
    # CHECK PICKUP NOTIFICATION
    # =====================================================

    else:

        unseen_pickup = (
            PickupRequest.query
            .filter(
                PickupRequest.user_id == current_user.id,
                PickupRequest.notification_seen.is_(False),
                PickupRequest.status.in_(
                    ["approved", "rejected"]
                )
            )
            .order_by(
                PickupRequest.created_at.desc()
            )
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


    # =====================================================
    # LOAD DASHBOARD
    # =====================================================

    return render_template(
        "dashboard.html",
        scraps=scraps,
        pending_count=pending_count,
        approved_count=approved_count,
        total_points=total_points,
        notification=notification
    )


# =========================================================
# UPLOAD SCRAP PAGE
# =========================================================

@user_bp.route(
    "/upload-scrap",
    methods=["GET", "POST"]
)
@login_required
def upload_scrap():

    if request.method == "GET":

        return render_template(
            "upload_scrap.html"
        )


    # -----------------------------------------------------
    # GET IMAGE
    # -----------------------------------------------------

    if "image" not in request.files:

        flash(
            "Please select an image.",
            "danger"
        )

        return redirect(
            url_for(
                "user.upload_scrap"
            )
        )


    file = request.files["image"]


    if file.filename == "":

        flash(
            "Please select an image.",
            "danger"
        )

        return redirect(
            url_for(
                "user.upload_scrap"
            )
        )


    if not allowed_file(file.filename):

        flash(
            "Only PNG, JPG, JPEG and WEBP "
            "images are allowed.",
            "danger"
        )

        return redirect(
            url_for(
                "user.upload_scrap"
            )
        )


    # -----------------------------------------------------
    # SAVE IMAGE
    # -----------------------------------------------------

    original_filename = secure_filename(
        file.filename
    )

    unique_filename = (
        f"{uuid.uuid4().hex}_"
        f"{original_filename}"
    )

    upload_folder = current_app.config.get(
        "UPLOAD_FOLDER",
        "static/uploads"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    image_path = os.path.join(
        upload_folder,
        unique_filename
    )

    file.save(image_path)


    # -----------------------------------------------------
    # DEFAULT AI RESULT
    # -----------------------------------------------------

    detection_type = "uncertain"

    materials = []

    detected_type = "Other/Unknown"

    confidence_score = 0.0


    # =====================================================
    # AI SCRAP DETECTION
    # =====================================================

    try:

        from models.scrap_detector import (
            detect_scrap_type
        )


        result = detect_scrap_type(
            image_path
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


            if (
                detection_type == "single"
                and materials
            ):

                detected_type = materials[0].get(
                    "name",
                    "Other/Unknown"
                )

                confidence_score = float(
                    materials[0].get(
                        "confidence",
                        0
                    )
                )


            elif (
                detection_type == "mixed"
                and materials
            ):

                detected_type = "Mixed Scrap"

                confidence_values = [

                    float(
                        material.get(
                            "confidence",
                            0
                        )
                    )

                    for material
                    in materials

                ]

                if confidence_values:

                    confidence_score = (
                        sum(confidence_values)
                        / len(confidence_values)
                    )


    except Exception as e:

        print(
            f"AI detection failed: {e}"
        )


    # -----------------------------------------------------
    # DETECTED LABELS
    # -----------------------------------------------------

    detected_labels = json.dumps(
        materials
    )


    # -----------------------------------------------------
    # CREATE SCRAP RECORD
    # -----------------------------------------------------

    scrap = ScrapUpload(

        user_id=current_user.id,

        image_url=(
            f"uploads/{unique_filename}"
        ),

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


    db.session.add(scrap)

    db.session.commit()


    # -----------------------------------------------------
    # SHOW RESULT
    # -----------------------------------------------------

    flash(
        "Scrap uploaded successfully! "
        "Waiting for admin approval.",
        "success"
    )


    return redirect(
        url_for(
            "user.dashboard"
        )
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
            "pickup.html"
        )


    # -----------------------------------------------------
    # GET FORM DATA
    # -----------------------------------------------------

    pickup_date = request.form.get(
        "pickup_date"
    )

    time_slot = request.form.get(
        "time_slot"
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


    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not pickup_date or not time_slot or not address:

        flash(
            "Please fill all required fields.",
            "danger"
        )

        return redirect(
            url_for(
                "user.pickup"
            )
        )


    # -----------------------------------------------------
    # CREATE PICKUP REQUEST
    # -----------------------------------------------------

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


    db.session.add(
        pickup_request
    )

    db.session.commit()


    flash(
        "Pickup request submitted successfully!",
        "success"
    )


    return redirect(
        url_for(
            "user.dashboard"
        )
    )