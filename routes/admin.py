from functools import wraps
from flask import Blueprint

admin_bp = Blueprint("admin", __name__)
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from database.models import (
    db,
    User,
    ScrapUpload,
    PickupRequest
)


# ==================================================
# ADMIN BLUEPRINT
# ==================================================

admin_bp = Blueprint('admin', __name__)


# ==================================================
# ADMIN-ONLY ACCESS GUARD
# ==================================================

def admin_required(view_func):

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('user.dashboard'))

        return view_func(*args, **kwargs)

    return wrapped


# ==================================================
# SCRAP CATEGORY RATES (₹ per kg)
# Keep this in sync with the /pricing page in app.py
# ==================================================

CATEGORY_RATES = {
    'plastic': 15,
    'metal': 40,
    'paper': 10,
    'cardboard': 8,
    'glass': 5,
    'e-waste': 50,
}

DEFAULT_RATE = 10


def get_rate_for_category(category):
    return CATEGORY_RATES.get((category or '').strip().lower(), DEFAULT_RATE)


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():

    total_users = User.query.count()
    total_scrap = ScrapUpload.query.count()
    total_pickups = PickupRequest.query.count()

    recent_users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_scrap=total_scrap,
        total_pickups=total_pickups,
        recent_users=recent_users
    )


# ==================================================
# USER MANAGEMENT
# ==================================================

@admin_bp.route('/users')
@login_required
@admin_required
def users():

    all_users = (
        User.query
        .order_by(User.created_at.desc())
        .all()
    )

    return render_template(
        'admin/users.html',
        users=all_users
    )


# ==================================================
# SCRAP VERIFICATION
# ==================================================

@admin_bp.route('/scraps')
@login_required
@admin_required
def scraps():

    all_scraps = (
        ScrapUpload.query
        .order_by(ScrapUpload.created_at.desc())
        .all()
    )

    return render_template(
        'admin/scraps.html',
        scraps=all_scraps
    )


@admin_bp.route('/scraps/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_scrap(id):

    scrap = ScrapUpload.query.get_or_404(id)

    action = request.form.get('action', 'approve')

    if action == 'reject':

        scrap.status = 'rejected'
        scrap.notification_seen = False

        db.session.commit()

        flash(f'Scrap #{scrap.id} rejected.', 'success')

        return redirect(url_for('admin.scraps'))

    # -----------------------------------------------------
    # APPROVE: read verified weight, calculate price/points
    # -----------------------------------------------------

    try:
        weight = float(request.form.get('weight', 0))
    except (TypeError, ValueError):
        weight = 0.0

    if weight <= 0:
        flash('Please enter a valid weight before approving.', 'danger')
        return redirect(url_for('admin.scraps'))

    rate = get_rate_for_category(scrap.scrap_type)
    points = int(round(weight * rate))

    scrap.weight = weight
    scrap.estimated_price = rate
    scrap.points_earned = points
    scrap.status = 'approved'
    scrap.notification_seen = False

    # Credit the user's eco score
    user = User.query.get(scrap.user_id)
    if user:
        user.eco_score = (user.eco_score or 0) + points

    db.session.commit()

    flash(f'Scrap #{scrap.id} approved — {points} points issued.', 'success')

    return redirect(url_for('admin.scraps'))


# ==================================================
# PICKUP SCHEDULING
# ==================================================

@admin_bp.route('/pickups')
@login_required
@admin_required
def pickups():

    all_pickups = (
        PickupRequest.query
        .order_by(PickupRequest.created_at.desc())
        .all()
    )

    return render_template(
        'admin/pickups.html',
        pickups=all_pickups
    )


@admin_bp.route('/pickups/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    pickup.status = 'approved'
    pickup.notification_seen = False

    db.session.commit()

    flash(f'Pickup #{pickup.id} approved and dispatched.', 'success')

    return redirect(url_for('admin.pickups'))


@admin_bp.route('/pickups/<int:id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_pickup(id):

    pickup = PickupRequest.query.get_or_404(id)

    pickup.status = 'rejected'
    pickup.notification_seen = False

    db.session.commit()

    flash(f'Pickup #{pickup.id} rejected.', 'success')

    return redirect(url_for('admin.pickups'))