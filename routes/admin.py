from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from database.models import (
    db,
    ScrapUpload,
    PickupRequest
)


# ==================================================
# USER BLUEPRINT
# ==================================================

user_bp = Blueprint('user', __name__)


# ==================================================
# USER DASHBOARD
# ==================================================

@user_bp.route('/dashboard')
@login_required
def dashboard():

    # Get all scraps of current user
    scraps = (
        ScrapUpload.query
        .filter_by(user_id=current_user.id)
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    # Get counts
    pending_count = (
        ScrapUpload.query
        .filter_by(
            user_id=current_user.id,
            status='pending'
        )
        .count()
    )

    approved_count = (
        ScrapUpload.query
        .filter_by(
            user_id=current_user.id,
            status='approved'
        )
        .count()
    )

    total_points = current_user.eco_score or 0


    # ==================================================
    # CHECK SCRAP NOTIFICATION
    # ==================================================

    scrap_notification = (
        ScrapUpload.query
        .filter(
            ScrapUpload.user_id == current_user.id,
            ScrapUpload.status.in_(['approved', 'rejected']),
            ScrapUpload.notification_seen == False
        )
        .order_by(ScrapUpload.created_at.desc())
        .first()
    )


    notification = None


    if scrap_notification:

        if scrap_notification.status == 'approved':

            notification = {
                'type': 'success',
                'title': 'Scrap Approved! 🎉',
                'message': (
                    f"Your {scrap_notification.scrap_type} "
                    f"scrap request was approved. "
                    f"You earned "
                    f"{scrap_notification.points_earned or 0} "
                    f"Eco Points!"
                )
            }

        elif scrap_notification.status == 'rejected':

            notification = {
                'type': 'error',
                'title': 'Scrap Request Rejected',
                'message': (
                    f"Your {scrap_notification.scrap_type} "
                    f"scrap request was rejected by the admin."
                )
            }

        # Mark notification as seen
        scrap_notification.notification_seen = True

        db.session.commit()


    # ==================================================
    # CHECK PICKUP NOTIFICATION
    # Only if no scrap notification is being shown
    # ==================================================

    if notification is None:

        pickup_notification = (
            PickupRequest.query
            .filter(
                PickupRequest.user_id == current_user.id,
                PickupRequest.status.in_(['approved', 'rejected']),
                PickupRequest.notification_seen == False
            )
            .order_by(PickupRequest.created_at.desc())
            .first()
        )


        if pickup_notification:

            if pickup_notification.status == 'approved':

                notification = {
                    'type': 'success',
                    'title': 'Pickup Approved! 🚚',
                    'message': (
                        f"Your pickup request for "
                        f"{pickup_notification.pickup_date} "
                        f"during {pickup_notification.time_slot} "
                        f"has been approved!"
                    )
                }

            elif pickup_notification.status == 'rejected':

                notification = {
                    'type': 'error',
                    'title': 'Pickup Request Rejected',
                    'message': (
                        f"Your pickup request for "
                        f"{pickup_notification.pickup_date} "
                        f"was rejected by the admin."
                    )
                }

            # Mark notification as seen
            pickup_notification.notification_seen = True

            db.session.commit()


    # ==================================================
    # RENDER DASHBOARD
    # ==================================================

    return render_template(
        'user/dashboard.html',
        scraps=scraps,
        pending_count=pending_count,
        approved_count=approved_count,
        total_points=total_points,
        notification=notification
    )