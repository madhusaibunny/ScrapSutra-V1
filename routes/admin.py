from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from database.models import db, User, ScrapUpload, PickupRequest
from flask_mail import Message
import threading

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
def ensure_admin():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user.dashboard'))

@admin_bp.route('/dashboard')
def dashboard():
    total_users = User.query.count()
    total_pickups = PickupRequest.query.count()
    total_scrap = ScrapUpload.query.count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', total_users=total_users, total_pickups=total_pickups, total_scrap=total_scrap, recent_users=recent_users)

@admin_bp.route('/users')
def users():
    users_list = User.query.all()
    return render_template('admin/users.html', users=users_list)

@admin_bp.route('/pickups')
def pickups():
    pickups_list = PickupRequest.query.order_by(PickupRequest.created_at.desc()).all()
    return render_template('admin/pickups.html', pickups=pickups_list)

@admin_bp.route('/scraps')
def scraps():
    scraps_list = ScrapUpload.query.order_by(ScrapUpload.created_at.desc()).all()
    return render_template('admin/scraps.html', scraps=scraps_list)

def send_async_email(app, msg):
    try:
        from app import mail
        with app.app_context():
            mail.send(msg)
    except Exception as e:
        print(f"Mail failed to send: {e}")

@admin_bp.route('/approve-scrap/<int:id>', methods=['POST'])
def approve_scrap(id):
    scrap = ScrapUpload.query.get_or_404(id)
    target_user = User.query.get(scrap.user_id)
    
    try:
        weight = float(request.form.get('weight', 0))
    except ValueError:
        weight = 0.0

    action = request.form.get('action')

    if action == 'approve':
        if weight <= 0:
            flash('Weight must be greater than zero.', 'error')
            return redirect(url_for('admin.scraps'))
            
        scrap.status = 'approved'
        scrap.weight = weight
        # Use estimated_price if available, else a fallback rate
        rate = scrap.estimated_price if getattr(scrap, 'estimated_price', 0) > 0 else 5.0
        points = int(weight * rate)
        
        scrap.points_earned = points
        if target_user:
            target_user.eco_score = (target_user.eco_score or 0) + points
            
        db.session.commit()
        
        # Dispatch approval email
        sender_email = current_app.config.get('MAIL_USERNAME')
        if sender_email and target_user:
            msg = Message(subject="Your Scrap Request was Approved!",
                        sender=sender_email,
                        recipients=[target_user.email],
                        body=f"Great news {target_user.name}!\n\nYour {scrap.scrap_type or 'unknown'} upload weighing {weight}kg has been approved! You earned {points} Eco Points!")
            threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

        flash(f'Scrap request approved. Paid {points} points.', 'success')
    elif action == 'reject':
        scrap.status = 'rejected'
        db.session.commit()
        flash('Scrap request rejected.', 'error')

    return redirect(url_for('admin.scraps'))

@admin_bp.route('/approve-pickup/<int:id>', methods=['POST'])
def approve_pickup(id):
    pickup = PickupRequest.query.get_or_404(id)
    target_user = User.query.get(pickup.user_id)
    
    pickup.status = 'approved'
    db.session.commit()
    
    sender_email = current_app.config.get('MAIL_USERNAME')
    if sender_email and target_user:
        msg = Message(subject="Your Pickup Request was Confirmed!",
                    sender=sender_email,
                    recipients=[target_user.email],
                    body=f"Hello {target_user.name},\n\nYour pickup request scheduled for {pickup.pickup_date} during {pickup.time_slot} has been successfully approved by the admin! Our agent will contact you at {pickup.address} soon.")
        threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
        
    flash(f"Pickup scheduled and notification sent to {target_user.name if target_user else 'user'}.", "success")
    return redirect(url_for('admin.pickups'))
