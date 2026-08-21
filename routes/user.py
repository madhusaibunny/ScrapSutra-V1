from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app
)

from flask_login import login_required, current_user

from database.models import (
    db,
    User,
    ScrapUpload,
    PickupRequest
)

from flask_mail import Message
import threading


admin_bp = Blueprint('admin', __name__)


# ==================================================
# ADMIN PROTECTION
# ==================================================

@admin_bp.before_request
@login_required
def ensure_admin():

    if current_user.role != 'admin':

        flash(
            'Unauthorized access',
            'danger'
        )

        return redirect(
            url_for('user.dashboard')
        )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

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


# ==================================================
# USERS
# ==================================================

@admin_bp.route('/users')
def users():

    users_list = User.query.all()

    return render_template(
        'admin/users.html',
        users=users_list
    )


# ==================================================
# PICKUPS LIST
# ==================================================

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


# ==================================================
# SCRAPS LIST
# ==================================================

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


# ==================================================
# EMAIL FUNCTION
# ==================================================

def send_async_email(app, msg):

    try:

        from app import mail

        with app.app_context():

            mail.send(msg)

        print("Email sent successfully")

    except Exception as e:

        print(f"Mail failed: {e}")


def send_email_in_background(app, msg):

    try:

        thread = threading.Thread(
            target=send_async_email,
            args=(app, msg),
            daemon=True
        )

        thread.start()

    except Exception as e:

        print(f"Email thread error: {e}")


# ==================================================
# APPROVE / REJECT SCRAP
# ==================================================

@admin_bp.route(
    '/approve-scrap/<int:id>',
    methods=['POST']
)
def approve_scrap(id):

    scrap = ScrapUpload.query.get_or_404(id)

    target_user = User.query.get(
        scrap.user_id
    )

    action = request.form.get('action')

    # ----------------------------------------------
    # APPROVE SCRAP
    # ----------------------------------------------

    if action == 'approve':

        try:

            weight = float(
                request.form.get('weight', 0)
            )

        except (ValueError, TypeError):

            weight = 0.0

        if weight <= 0:

            flash(
                'Weight must be greater than zero.',
                'danger'
            )

            return redirect(
                url_for('admin.scraps')
            )

        # Update scrap

        scrap.status = 'approved'

        # IMPORTANT:
        # Make notification appear for user

        scrap.notification_seen = False

        scrap.weight = weight

        # Calculate rate

        rate = scrap.estimated_price or 5.0

        points = int(
            weight * rate
        )

        scrap.points_earned = points

        # Add points to user

        if target_user:

            target_user.eco_score = (
                target_user.eco_score or 0
            ) + points

        # Save changes

        db.session.commit()

        # ------------------------------------------
        # SEND EMAIL
        # ------------------------------------------

        sender_email = current_app.config.get(
            'MAIL_USERNAME'
        )

        if sender_email and target_user:

            msg = Message(

                subject='Your Scrap Request Was Approved!',

                sender=sender_email,

                recipients=[
                    target_user.email
                ],

                body=(
                    f"Hello {target_user.name},\n\n"
                    f"Great news! Your "
                    f"{scrap.scrap_type} scrap request "
                    f"has been approved.\n\n"
                    f"Weight: {weight} kg\n"
                    f"Eco Points Earned: {points}\n\n"
                    f"Thank you for recycling with ScrapSutra!"
                )
            )

            send_email_in_background(
                current_app._get_current_object(),
                msg
            )

        flash(
            f'Scrap approved successfully. '
            f'{points} Eco Points awarded.',
            'success'
        )


    # ----------------------------------------------
    # REJECT SCRAP
    # ----------------------------------------------

    elif action == 'reject':

        scrap.status = 'rejected'

        # IMPORTANT:
        # Make rejection popup appear

        scrap.notification_seen = False

        db.session.commit()

        # Send rejection email

        sender_email = current_app.config.get(
            'MAIL_USERNAME'
        )

        if sender_email and target_user:

            msg = Message(

                subject='Update on Your Scrap Request',

                sender=sender_email,

                recipients=[
                    target_user.email
                ],

                body=(
                    f"Hello {target_user.name},\n\n"
                    f"Unfortunately, your "
                    f"{scrap.scrap_type} scrap request "
                    f"was rejected.\n\n"
                    f"You can upload another scrap request "
                    f"and try again."
                )
            )

            send_email_in_background(
                current_app._get_current_object(),
                msg
            )

        flash(
            'Scrap request rejected.',
            'danger'
        )


    return redirect(
        url_for('admin.scraps')
    )


# ==================================================
# APPROVE PICKUP
# ==================================================

@admin_bp.route(
    '/approve-pickup/<int:id>',
    methods=['POST']
)
def approve_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    target_user = User.query.get(
        pickup.user_id
    )

    # Update status

    pickup.status = 'approved'

    # IMPORTANT:
    # Make popup appear for user

    pickup.notification_seen = False

    # Save database

    db.session.commit()

    # ----------------------------------------------
    # SEND EMAIL
    # ----------------------------------------------

    sender_email = current_app.config.get(
        'MAIL_USERNAME'
    )

    if sender_email and target_user:

        msg = Message(

            subject='Your Pickup Request Was Approved!',

            sender=sender_email,

            recipients=[
                target_user.email
            ],

            body=(
                f"Hello {target_user.name},\n\n"
                f"Your pickup request has been approved!\n\n"
                f"Date: {pickup.pickup_date}\n"
                f"Time: {pickup.time_slot}\n\n"
                f"Our team will contact you soon."
            )
        )

        send_email_in_background(
            current_app._get_current_object(),
            msg
        )

    flash(
        'Pickup request approved successfully.',
        'success'
    )

    return redirect(
        url_for('admin.pickups')
    )


# ==================================================
# REJECT PICKUP
# ==================================================

@admin_bp.route(
    '/reject-pickup/<int:id>',
    methods=['POST']
)
def reject_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    target_user = User.query.get(
        pickup.user_id
    )

    # Update status

    pickup.status = 'rejected'

    # IMPORTANT:
    # Make rejection popup appear

    pickup.notification_seen = False

    # Save database

    db.session.commit()

    # ----------------------------------------------
    # SEND EMAIL
    # ----------------------------------------------

    sender_email = current_app.config.get(
        'MAIL_USERNAME'
    )

    if sender_email and target_user:

        msg = Message(

            subject='Update on Your Pickup Request',

            sender=sender_email,

            recipients=[
                target_user.email
            ],

            body=(
                f"Hello {target_user.name},\n\n"
                f"Unfortunately, your pickup request "
                f"for {pickup.pickup_date} during "
                f"{pickup.time_slot} was rejected.\n\n"
                f"Please submit another pickup request."
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