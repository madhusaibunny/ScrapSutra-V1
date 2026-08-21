from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from database.models import db, User, ScrapUpload, PickupRequest
from flask_mail import Message
import threading

admin_bp = Blueprint('admin', __name__)


# -----------------------------
# ADMIN PROTECTION
# -----------------------------
@admin_bp.before_request
@login_required
def ensure_admin():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user.dashboard'))


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------
@admin_bp.route('/dashboard')
def dashboard():
    total_users = User.query.count()
    total_pickups = PickupRequest.query.count()
    total_scrap = ScrapUpload.query.count()

    recent_users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_pickups=total_pickups,
        total_scrap=total_scrap,
        recent_users=recent_users
    )


# -----------------------------
# USERS
# -----------------------------
@admin_bp.route('/users')
def users():
    users_list = User.query.all()

    return render_template(
        'admin/users.html',
        users=users_list
    )


# -----------------------------
# PICKUPS
# -----------------------------
@admin_bp.route('/pickups')
def pickups():
    pickups_list = (
        PickupRequest.query
        .order_by(PickupRequest.created_at.desc())
        .all()
    )

    return render_template(
        'admin/pickups.html',
        pickups=pickups_list
    )


# -----------------------------
# SCRAP REQUESTS
# -----------------------------
@admin_bp.route('/scraps')
def scraps():
    scraps_list = (
        ScrapUpload.query
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    return render_template(
        'admin/scraps.html',
        scraps=scraps_list
    )


# -----------------------------
# SAFE BACKGROUND EMAIL
# -----------------------------
def send_async_email(app, msg):
    try:
        from app import mail

        with app.app_context():
            mail.send(msg)

        print("Email sent successfully")

    except Exception as e:
        print(f"Mail failed to send: {e}")


def send_email_in_background(app, msg):
    try:
        thread = threading.Thread(
            target=send_async_email,
            args=(app, msg),
            daemon=True
        )

        thread.start()

    except Exception as e:
        print(f"Could not start email thread: {e}")


# -----------------------------
# APPROVE / REJECT SCRAP
# -----------------------------
@admin_bp.route('/approve-scrap/<int:id>', methods=['POST'])
def approve_scrap(id):

    scrap = ScrapUpload.query.get_or_404(id)
    target_user = User.query.get(scrap.user_id)

    try:
        weight = float(request.form.get('weight', 0))
    except (ValueError, TypeError):
        weight = 0.0

    action = request.form.get('action')

    if action == 'approve':

        if weight <= 0:
            flash(
                'Weight must be greater than zero.',
                'error'
            )

            return redirect(
                url_for('admin.scraps')
            )

        scrap.status = 'approved'
        scrap.weight = weight

        rate = (
            scrap.estimated_price
            if getattr(scrap, 'estimated_price', 0) > 0
            else 5.0
        )

        points = int(weight * rate)

        scrap.points_earned = points

        if target_user:
            target_user.eco_score = (
                target_user.eco_score or 0
            ) + points

        # Save database first
        db.session.commit()

        sender_email = current_app.config.get(
            'MAIL_USERNAME'
        )

        if sender_email and target_user:

            msg = Message(
                subject="Your Scrap Request was Approved!",
                sender=sender_email,
                recipients=[target_user.email],
                body=(
                    f"Great news {target_user.name}!\n\n"
                    f"Your {scrap.scrap_type or 'unknown'} "
                    f"upload weighing {weight}kg has been "
                    f"approved!\n\n"
                    f"You earned {points} Eco Points!"
                )
            )

            send_email_in_background(
                current_app._get_current_object(),
                msg
            )

        flash(
            f'Scrap request approved. '
            f'You awarded {points} points.',
            'success'
        )

    elif action == 'reject':

        scrap.status = 'rejected'

        db.session.commit()

        flash(
            'Scrap request rejected.',
            'error'
        )

    return redirect(
        url_for('admin.scraps')
    )


# -----------------------------
# APPROVE PICKUP
# -----------------------------
@admin_bp.route('/approve-pickup/<int:id>', methods=['POST'])
def approve_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    target_user = User.query.get(
        pickup.user_id
    )

    # Update status
    pickup.status = 'approved'

    # Save database first
    db.session.commit()

    print(
        f"Pickup {pickup.id} approved successfully"
    )

    # Send email in background
    sender_email = current_app.config.get(
        'MAIL_USERNAME'
    )

    if sender_email and target_user:

        msg = Message(
            subject="Your Pickup Request was Confirmed!",
            sender=sender_email,
            recipients=[target_user.email],
            body=(
                f"Hello {target_user.name},\n\n"
                f"Your pickup request scheduled for "
                f"{pickup.pickup_date} during "
                f"{pickup.time_slot} has been approved "
                f"by the admin!\n\n"
                f"Our agent will contact you at:\n"
                f"{pickup.address}"
            )
        )

        send_email_in_background(
            current_app._get_current_object(),
            msg
        )

    flash(
        f"Pickup request approved successfully for "
        f"{target_user.name if target_user else 'user'}.",
        "success"
    )

    return redirect(
        url_for('admin.pickups')
    )


# -----------------------------
# REJECT PICKUP
# -----------------------------
@admin_bp.route('/reject-pickup/<int:id>', methods=['POST'])
def reject_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    target_user = User.query.get(
        pickup.user_id
    )

    # Update status
    pickup.status = 'rejected'

    # Save database first
    db.session.commit()

    print(
        f"Pickup {pickup.id} rejected successfully"
    )

    # Send rejection email in background
    sender_email = current_app.config.get(
        'MAIL_USERNAME'
    )

    if sender_email and target_user:

        msg = Message(
            subject="Update on Your Pickup Request",
            sender=sender_email,
            recipients=[target_user.email],
            body=(
                f"Hello {target_user.name},\n\n"
                f"Unfortunately, your pickup request scheduled for "
                f"{pickup.pickup_date} during "
                f"{pickup.time_slot} could not be accepted.\n\n"
                f"Please submit another pickup request with a "
                f"different date or time."
            )
        )

        send_email_in_background(
            current_app._get_current_object(),
            msg
        )

    flash(
        'Pickup request rejected.',
        'danger'
    )

    return redirect(
        url_for('admin.pickups')
    )