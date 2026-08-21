from flask import Blueprint, render_template
from flask_login import login_required, current_user

from database.models import db, ScrapUpload, PickupRequest


user_bp = Blueprint("user", __name__)


# =========================================================
# USER DASHBOARD
# =========================================================

@user_bp.route("/dashboard")
@login_required
def dashboard():

    # -----------------------------------------------------
    # GET USER'S SCRAPS
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
    # CHECK SCRAP APPROVAL / REJECTION
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
                "title": "Scrap Approved!",
                "message": (
                    f"Your {unseen_scrap.scrap_type} scrap "
                    f"has been approved. You earned "
                    f"{unseen_scrap.points_earned or 0} Eco Points!"
                ),
                "status": "success"
            }

        elif unseen_scrap.status == "rejected":

            notification = {
                "title": "Scrap Rejected",
                "message": (
                    f"Your {unseen_scrap.scrap_type} scrap "
                    f"request was rejected by the admin."
                ),
                "status": "error"
            }


        # User will see this notification only once
        unseen_scrap.notification_seen = True

        db.session.commit()


    # =====================================================
    # CHECK PICKUP APPROVAL / REJECTION
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
                    "title": "Pickup Approved!",
                    "message": (
                        f"Your pickup request for "
                        f"{unseen_pickup.pickup_date} "
                        f"has been approved by the admin."
                    ),
                    "status": "success"
                }

            elif unseen_pickup.status == "rejected":

                notification = {
                    "title": "Pickup Rejected",
                    "message": (
                        f"Your pickup request for "
                        f"{unseen_pickup.pickup_date} "
                        f"was rejected by the admin."
                    ),
                    "status": "error"
                }


            # User will see notification only once
            unseen_pickup.notification_seen = True

            db.session.commit()


    # =====================================================
    # LOAD USER DASHBOARD
    # =====================================================

    return render_template(
        "user/dashboard.html",
        scraps=scraps,
        pending_count=pending_count,
        approved_count=approved_count,
        total_points=total_points,
        notification=notification
    )