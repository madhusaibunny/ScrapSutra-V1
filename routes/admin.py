import os
import requests

from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request
)

from flask_login import (
    login_required,
    current_user
)

from database.models import (
    db,
    User,
    ScrapUpload,
    PickupRequest
)


# ==================================================
# ADMIN BLUEPRINT
# ==================================================

admin_bp = Blueprint(
    "admin",
    __name__
)


# ==================================================
# SEND EMAIL USING BREVO API
# ==================================================

import threading


def _send_brevo_email(to_email, to_name, subject, html_content):

    try:

        api_key = os.environ.get("BREVO_API_KEY")

        sender_email = os.environ.get("MAIL_SENDER")


        if not api_key:
            print("BREVO ERROR: BREVO_API_KEY is missing")
            return


        if not sender_email:
            print("BREVO ERROR: MAIL_SENDER is missing")
            return


        payload = {
            "sender": {
                "name": "ScrapSutra",
                "email": sender_email
            },
            "to": [
                {
                    "email": to_email,
                    "name": to_name or "ScrapSutra User"
                }
            ],
            "subject": subject,
            "htmlContent": html_content
        }


        response = requests.post(

            "https://api.brevo.com/v3/smtp/email",

            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json"
            },

            json=payload,

            timeout=15

        )


        print(f"BREVO STATUS: {response.status_code}")

        print(f"BREVO RESPONSE: {response.text}")


        if response.status_code in [200, 201]:
            print(f"EMAIL SENT SUCCESSFULLY TO {to_email}")
        else:
            print(f"BREVO EMAIL FAILED FOR {to_email}")


    except Exception as e:

        print(f"BREVO EMAIL ERROR: {str(e)}")


def send_notification_email(
    recipient_email,
    recipient_name,
    subject,
    body
):

    # Convert plain text body to HTML
    html_body = body.replace("\n", "<br>")

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;
                    border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #10b981;">ScrapSutra ♻️</h2>
            <hr style="border-color: #e0e0e0;">
            <p>{html_body}</p>
            <hr style="border-color: #e0e0e0;">
            <p style="font-size: 12px; color: #999;">
                This is an automated message from ScrapSutra.
                Please do not reply to this email.
            </p>
        </div>
    </body>
    </html>
    """

    threading.Thread(
        target=_send_brevo_email,
        args=(recipient_email, recipient_name, subject, html_content),
        daemon=True
    ).start()

    return True


# ==================================================
# ADMIN-ONLY ACCESS GUARD
# ==================================================

def admin_required(view_func):

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        if not current_user.is_authenticated:

            flash(
                "Please log in first.",
                "error"
            )

            return redirect(
                url_for(
                    "auth.login"
                )
            )


        if current_user.role != "admin":

            flash(
                "Admin access required.",
                "error"
            )

            return redirect(
                url_for(
                    "user.dashboard"
                )
            )


        return view_func(
            *args,
            **kwargs
        )


    return wrapped


# ==================================================
# SCRAP CATEGORY RATES
# ==================================================

CATEGORY_RATES = {

    "plastic": 15,

    "metal": 40,

    "paper": 10,

    "cardboard": 8,

    "glass": 5,

    "e-waste": 50

}


DEFAULT_RATE = 10


def get_rate_for_category(category):

    return CATEGORY_RATES.get(

        (category or "")
        .strip()
        .lower(),

        DEFAULT_RATE

    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@admin_bp.route(
    "/dashboard"
)

@login_required
@admin_required
def dashboard():

    total_users = User.query.count()

    total_scrap = ScrapUpload.query.count()

    total_pickups = PickupRequest.query.count()


    recent_users = (

        User.query

        .order_by(
            User.created_at.desc()
        )

        .limit(5)

        .all()

    )


    return render_template(

        "admin/dashboard.html",

        total_users=total_users,

        total_scrap=total_scrap,

        total_pickups=total_pickups,

        recent_users=recent_users

    )


# ==================================================
# USER MANAGEMENT
# ==================================================

@admin_bp.route(
    "/users"
)

@login_required
@admin_required
def users():

    all_users = (

        User.query

        .order_by(
            User.created_at.desc()
        )

        .all()

    )


    return render_template(

        "admin/users.html",

        users=all_users

    )


# ==================================================
# SCRAP MANAGEMENT
# ==================================================

@admin_bp.route(
    "/scraps"
)

@login_required
@admin_required
def scraps():

    all_scraps = (

        ScrapUpload.query

        .order_by(
            ScrapUpload.created_at.desc()
        )

        .all()

    )


    return render_template(

        "admin/scraps.html",

        scraps=all_scraps

    )


# ==================================================
# APPROVE / REJECT SCRAP
# ==================================================

@admin_bp.route(
    "/scraps/<int:id>/approve",
    methods=["POST"]
)

@login_required
@admin_required
def approve_scrap(id):

    scrap = ScrapUpload.query.get_or_404(
        id
    )


    action = request.form.get(
        "action",
        "approve"
    )


    # ==============================================
    # REJECT SCRAP
    # ==============================================

    if action == "reject":

        scrap.status = "rejected"

        scrap.notification_seen = False


        db.session.commit()

        user = User.query.get(scrap.user_id)

        if user and user.email:

            send_notification_email(

                recipient_email=user.email,

                recipient_name=user.name,

                subject="Scrap Upload Rejected - ScrapSutra",

                body=(
                    f"Hello {user.name},\n\n"

                    f"Unfortunately, your recent scrap upload (Type: {scrap.scrap_type}) has been rejected.\n\n"

                    f"Please ensure the image clearly shows recyclable materials and try again.\n\n"

                    f"Thank you for using ScrapSutra."
                )

            )

        flash(

            f"Scrap #{scrap.id} rejected.",

            "success"

        )


        return redirect(

            url_for(
                "admin.scraps"
            )

        )


    # ==============================================
    # GET WEIGHT
    # ==============================================

    try:

        weight = float(

            request.form.get(
                "weight",
                0
            )

        )


    except (
        TypeError,
        ValueError
    ):

        weight = 0.0


    if weight <= 0:

        flash(

            "Please enter a valid weight before approving.",

            "danger"

        )


        return redirect(

            url_for(
                "admin.scraps"
            )

        )


    # ==============================================
    # GET CATEGORY RATE
    # ==============================================

    rate = get_rate_for_category(

        scrap.scrap_type

    )


    # ==============================================
    # CALCULATE POINTS
    # ==============================================

    points = int(

        round(
            weight * rate
        )

    )


    # ==============================================
    # UPDATE SCRAP
    # ==============================================

    scrap.weight = weight

    scrap.estimated_price = rate

    scrap.points_earned = points

    scrap.status = "approved"

    scrap.notification_seen = False


    # ==============================================
    # UPDATE USER WALLET
    # ==============================================

    user = User.query.get(

        scrap.user_id

    )


    if user:

        user.eco_score = (

            user.eco_score or 0

        ) + points


    db.session.commit()

    if user and user.email:

        send_notification_email(

            recipient_email=user.email,

            recipient_name=user.name,

            subject="Scrap Upload Approved! - ScrapSutra",

            body=(
                f"Hello {user.name},\n\n"

                f"Great news! Your scrap upload (Type: {scrap.scrap_type}) has been approved. ♻️\n\n"

                f"Weight: {weight} kg\n"

                f"Points Earned: {points}\n\n"

                f"Your new Eco Score is: {user.eco_score}\n\n"

                f"Thank you for keeping our planet clean!\n\n"
                
                f"ScrapSutra Team"
            )

        )

    flash(

        f"Scrap #{scrap.id} approved — "
        f"{points} points issued.",

        "success"

    )


    return redirect(

        url_for(
            "admin.scraps"
        )

    )


# ==================================================
# PICKUP MANAGEMENT
# ==================================================

@admin_bp.route(
    "/pickups"
)

@login_required
@admin_required
def pickups():

    all_pickups = (

        PickupRequest.query

        .order_by(
            PickupRequest.created_at.desc()
        )

        .all()

    )


    return render_template(

        "admin/pickups.html",

        pickups=all_pickups

    )


# ==================================================
# APPROVE PICKUP
# ==================================================

@admin_bp.route(

    "/pickups/<int:id>/approve",

    methods=["POST"]

)

@login_required
@admin_required
def approve_pickup(id):

    pickup = PickupRequest.query.get_or_404(
        id
    )


    # ==============================================
    # UPDATE PICKUP STATUS FIRST
    # ==============================================

    pickup.status = "approved"

    pickup.notification_seen = False


    db.session.commit()


    # ==============================================
    # GET REGISTERED USER
    # ==============================================

    user = User.query.get(
        pickup.user_id
    )


    # ==============================================
    # SEND EMAIL TO REGISTERED USER
    # ==============================================

    if user and user.email:

        send_notification_email(

            recipient_email=user.email,

            recipient_name=user.name,

            subject="Pickup Approved! - ScrapSutra",

            body=(
                f"Hello {user.name},\n\n"

                f"Great news! Your pickup request "
                f"has been approved. 🚚\n\n"

                f"Pickup Date: "
                f"{pickup.pickup_date}\n"

                f"Time Slot: "
                f"{pickup.time_slot}\n\n"

                f"Our team will collect your scrap "
                f"according to the scheduled pickup.\n\n"

                f"Thank you for using ScrapSutra! ♻️"
            )

        )


    else:

        print(
            "No registered user email found "
            "for this pickup."
        )


    flash(

        f"Pickup #{pickup.id} approved.",

        "success"

    )


    return redirect(

        url_for(
            "admin.pickups"
        )

    )


# ==================================================
# REJECT PICKUP
# ==================================================

@admin_bp.route(

    "/pickups/<int:id>/reject",

    methods=["POST"]

)

@login_required
@admin_required
def reject_pickup(id):

    pickup = PickupRequest.query.get_or_404(
        id
    )


    # ==============================================
    # UPDATE PICKUP STATUS FIRST
    # ==============================================

    pickup.status = "rejected"

    pickup.notification_seen = False


    db.session.commit()


    # ==============================================
    # GET REGISTERED USER
    # ==============================================

    user = User.query.get(
        pickup.user_id
    )


    # ==============================================
    # SEND EMAIL TO REGISTERED USER
    # ==============================================

    if user and user.email:

        send_notification_email(

            recipient_email=user.email,

            recipient_name=user.name,

            subject="Pickup Request Rejected - ScrapSutra",

            body=(
                f"Hello {user.name},\n\n"

                f"Unfortunately, your pickup request "
                f"has been rejected.\n\n"

                f"Pickup Date: "
                f"{pickup.pickup_date}\n"

                f"Time Slot: "
                f"{pickup.time_slot}\n\n"

                f"You can submit another pickup request "
                f"with a different date or time.\n\n"

                f"Thank you for using ScrapSutra."
            )

        )


    else:

        print(
            "No registered user email found "
            "for this pickup."
        )


    flash(

        f"Pickup #{pickup.id} rejected.",

        "success"

    )


    return redirect(

        url_for(
            "admin.pickups"
        )

    )