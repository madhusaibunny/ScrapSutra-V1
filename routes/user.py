import os
import json

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    current_app
)

from flask_login import login_required, current_user

from database.models import (
    db,
    ScrapUpload,
    PickupRequest,
    Transaction
)

from werkzeug.utils import secure_filename
from models.ai_module import detect_scrap_type


user_bp = Blueprint('user', __name__)


# ==========================================
# USER DASHBOARD
# ==========================================
@user_bp.route('/dashboard')
@login_required
def dashboard():

    # Get all scrap uploads of current user
    scraps = (
        ScrapUpload.query
        .filter_by(user_id=current_user.id)
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    # Dashboard summaries
    pending = sum(
        1 for s in scraps
        if s.status == 'pending'
    )

    approved = sum(
        1 for s in scraps
        if s.status == 'approved'
    )

    total_points = sum(
        s.points_earned
        for s in scraps
        if s.status == 'approved'
    )

    # ==========================================
    # FIND NEW SCRAP NOTIFICATIONS
    # ==========================================
    scrap_notifications = (
        ScrapUpload.query
        .filter(
            ScrapUpload.user_id == current_user.id,
            ScrapUpload.status.in_(['approved', 'rejected']),
            ScrapUpload.notification_seen == False
        )
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    # ==========================================
    # FIND NEW PICKUP NOTIFICATIONS
    # ==========================================
    pickup_notifications = (
        PickupRequest.query
        .filter(
            PickupRequest.user_id == current_user.id,
            PickupRequest.status.in_(['approved', 'rejected']),
            PickupRequest.notification_seen == False
        )
        .order_by(PickupRequest.created_at.desc())
        .all()
    )

    # Combine notifications
    notifications = []

    # Scrap notifications
    for scrap in scrap_notifications:

        if scrap.status == 'approved':

            notifications.append({
                'type': 'success',
                'title': 'Scrap Approved! 🎉',
                'message': (
                    f'Your {scrap.scrap_type.title()} scrap '
                    f'was approved. '
                    f'You earned {scrap.points_earned} Eco Points!'
                )
            })

        elif scrap.status == 'rejected':

            notifications.append({
                'type': 'error',
                'title': 'Scrap Request Rejected',
                'message': (
                    f'Your {scrap.scrap_type.title()} scrap '
                    f'request was rejected by the admin.'
                )
            })

        # Mark notification as seen
        scrap.notification_seen = True


    # Pickup notifications
    for pickup in pickup_notifications:

        if pickup.status == 'approved':

            notifications.append({
                'type': 'success',
                'title': 'Pickup Confirmed! 🚚',
                'message': (
                    f'Your pickup scheduled for '
                    f'{pickup.pickup_date} during '
                    f'{pickup.time_slot} has been approved!'
                )
            })

        elif pickup.status == 'rejected':

            notifications.append({
                'type': 'error',
                'title': 'Pickup Request Rejected',
                'message': (
                    f'Your pickup scheduled for '
                    f'{pickup.pickup_date} during '
                    f'{pickup.time_slot} was rejected.'
                )
            })

        # Mark notification as seen
        pickup.notification_seen = True


    # Save notification_seen changes
    if scrap_notifications or pickup_notifications:
        db.session.commit()


    return render_template(
        'user/dashboard.html',
        scraps=scraps,
        pending_count=pending,
        approved_count=approved,
        total_points=total_points,
        notifications=notifications
    )


# ==========================================
# UPLOAD SCRAP
# ==========================================
@user_bp.route('/upload-scrap', methods=['GET', 'POST'])
@login_required
def upload_scrap():

    if request.method == 'POST':

        # Check image
        if 'scrap_image' not in request.files:
            flash('No image provided', 'danger')
            return redirect(request.url)

        file = request.files['scrap_image']

        manual_category = request.form.get(
            'manual_category'
        )

        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        # Allowed image formats
        allowed_exts = (
            '.png',
            '.jpg',
            '.jpeg',
            '.webp',
            '.heic',
            '.jfif',
            '.avif',
            '.gif'
        )

        if file and file.filename.lower().endswith(
            allowed_exts
        ):

            filename = secure_filename(file.filename)

            upload_path = os.path.join(
                current_app.config.get(
                    'UPLOAD_FOLDER',
                    'static/uploads'
                ),
                filename
            )

            os.makedirs(
                os.path.dirname(upload_path),
                exist_ok=True
            )

            file.save(upload_path)


            # Default AI result
            ai_result = {
                'detection_type': 'uncertain',
                'materials': [],
                'confidence': 0,
                'message': ''
            }


            # Run AI detection only when category
            # was not manually selected
            if not manual_category:

                try:

                    ai_result = detect_scrap_type(
                        upload_path
                    )

                except Exception as e:

                    print(
                        f"AI detection error: {e}"
                    )

                    ai_result = {
                        'detection_type': 'uncertain',
                        'materials': [],
                        'confidence': 0,
                        'message': str(e)
                    }


            detection_type = ai_result.get(
                'detection_type',
                'uncertain'
            )


            if detection_type == 'uncertain':

                ai_category = 'unknown'
                ai_confidence = 0.0
                ai_labels = '[]'


            elif detection_type == 'mixed':

                ai_category = 'mixed'

                ai_confidence = (
                    ai_result['materials'][0]['confidence']
                    if ai_result.get('materials')
                    else 0.0
                )

                ai_labels = json.dumps(
                    [
                        m['name']
                        for m in ai_result.get(
                            'materials',
                            []
                        )
                    ]
                )


            else:

                ai_category = (
                    ai_result['materials'][0]['name']
                    if ai_result.get('materials')
                    else 'unknown'
                )

                ai_confidence = (
                    ai_result['materials'][0]['confidence']
                    if ai_result.get('materials')
                    else 0.0
                )

                ai_labels = json.dumps(
                    [ai_category]
                )


            # Final scrap category
            final_type = (
                manual_category
                if manual_category
                else ai_category
            )


            # Price mapping
            prices = {
                'plastic': 15.0,
                'metal': 40.0,
                'paper': 10.0,
                'cardboard': 8.0,
                'glass': 5.0,
                'e-waste': 50.0
            }


            est_price = prices.get(
                (final_type or 'unknown').lower(),
                0.0
            )


            # Create scrap record
            new_upload = ScrapUpload(

                user_id=current_user.id,

                image_url=filename,

                scrap_type=final_type,

                detected_type=ai_category,

                detected_labels=ai_labels,

                estimated_price=est_price,

                confidence_score=ai_confidence,

                status='pending',

                weight=0.0,

                points_earned=0,

                notification_seen=False
            )


            db.session.add(new_upload)

            db.session.commit()


            flash(
                f"Scrap submitted for admin approval! "
                f"Detection status: {final_type}",
                'success'
            )


            return redirect(
                url_for('user.dashboard')
            )


        else:

            flash(
                f"Unsupported format! "
                f"Please upload an image ending in "
                f"{', '.join(allowed_exts)}.",
                'error'
            )


    return render_template(
        'user/upload.html'
    )


# ==========================================
# PICKUP REQUEST
# ==========================================
@user_bp.route('/pickup', methods=['GET', 'POST'])
@login_required
def pickup():

    if request.method == 'POST':

        date = request.form.get('date')

        time = request.form.get('time')

        address = request.form.get('address')


        # Create pickup request
        req = PickupRequest(

            user_id=current_user.id,

            pickup_date=date,

            time_slot=time,

            address=address,

            status='pending',

            notification_seen=False
        )


        db.session.add(req)

        db.session.commit()


        # Optional email to admin
        try:

            from app import mail
            from flask_mail import Message

            sender_email = current_app.config.get(
                'MAIL_USERNAME'
            )

            if sender_email:

                msg = Message(

                    'New Scrap Pickup Request',

                    sender=sender_email,

                    recipients=[sender_email]
                )

                msg.body = (
                    f"New pickup from "
                    f"{current_user.name} "
                    f"at {address} "
                    f"on {date} "
                    f"during {time}."
                )

                mail.send(msg)

        except Exception as e:

            print(
                f"Pickup email error: {e}"
            )


        flash(
            'Pickup request submitted successfully',
            'success'
        )


        return redirect(
            url_for('user.pickup')
        )


    # Get user's pickup history
    pickups = (
        PickupRequest.query
        .filter_by(user_id=current_user.id)
        .order_by(
            PickupRequest.created_at.desc()
        )
        .all()
    )


    return render_template(
        'user/pickup.html',
        pickups=pickups
    )