import os
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from database.models import db, ScrapUpload, PickupRequest, Transaction
from werkzeug.utils import secure_filename
from models.ai_module import detect_scrap_type

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    scraps = ScrapUpload.query.filter_by(user_id=current_user.id).order_by(ScrapUpload.created_at.desc()).all()
    # Summaries
    pending = sum(1 for s in scraps if s.status == 'pending')
    approved = sum(1 for s in scraps if s.status == 'approved')
    total_points = sum(s.points_earned for s in scraps if s.status == 'approved')
    return render_template('user/dashboard.html', scraps=scraps, pending_count=pending, approved_count=approved, total_points=total_points)

@user_bp.route('/upload-scrap', methods=['GET', 'POST'])
@login_required
def upload_scrap():
    if request.method == 'POST':
        # Retrieve the file from the request
        if 'scrap_image' not in request.files:
            flash('No image provided', 'danger')
            return redirect(request.url)

        file = request.files['scrap_image']
        manual_category = request.form.get('manual_category')

        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        # Validate file
        allowed_exts = ('.png', '.jpg', '.jpeg', '.webp', '.heic', '.jfif', '.avif', '.gif')
        if file and file.filename.lower().endswith(allowed_exts):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'static/uploads'), filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            file.save(upload_path)

            ai_result = {'detection_type': 'uncertain', 'materials': [], 'confidence': 0, 'message': ''}
            
            # Only run AI detection if user did not manually specify
            if not manual_category:
                try:
                    ai_result = detect_scrap_type(upload_path)
                except Exception as e:
                    print(f"AI detection error: {e}")
                    ai_result = {'detection_type': 'uncertain', 'materials': [], 'confidence': 0, 'message': str(e)}
                
            detection_type = ai_result.get('detection_type', 'uncertain')
            
            if detection_type == 'uncertain':
                ai_category = 'unknown'
                ai_confidence = 0.0
                ai_labels = '[]'
            elif detection_type == 'mixed':
                ai_category = 'mixed'
                ai_confidence = ai_result['materials'][0]['confidence'] if ai_result.get('materials') else 0.0
                ai_labels = json.dumps([m['name'] for m in ai_result.get('materials', [])])
            else:
                ai_category = ai_result['materials'][0]['name'] if ai_result.get('materials') else 'unknown'
                ai_confidence = ai_result['materials'][0]['confidence'] if ai_result.get('materials') else 0.0
                ai_labels = json.dumps([ai_category])

            final_type = manual_category if manual_category else ai_category
            
            # Map price per kg for user visibility
            prices = {'plastic': 15.0, 'metal': 40.0, 'paper': 10.0, 'cardboard': 8.0, 'glass': 5.0, 'e-waste': 50.0}
            est_price = prices.get((final_type or 'unknown').lower(), 0.0)
            
            # Create Database Record
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
                points_earned=0
            )
            
            db.session.add(new_upload)
            db.session.commit()
            flash(f"Scrap submitted for admin approval! Detection status: {final_type}", 'success')
            return redirect(url_for('user.dashboard'))
        else:
            flash(f"Unsupported check format! Please upload an image ending in {', '.join(allowed_exts)}.", 'error')
            
    return render_template('user/upload.html')

@user_bp.route('/pickup', methods=['GET', 'POST'])
@login_required
def pickup():
    if request.method == 'POST':
        date = request.form.get('date')
        time = request.form.get('time')
        address = request.form.get('address')
        
        req = PickupRequest(
            user_id=current_user.id, pickup_date=date,
            time_slot=time, address=address
        )
        db.session.add(req)
        db.session.commit()
        
        # Dispatch SMTP Pickup email matching actual identity to prevent spoofing rejection
        try:
            from app import mail
            from flask_mail import Message
            sender_email = current_app.config.get('MAIL_USERNAME')
            if sender_email:
                msg = Message('New Scrap Pickup Request',
                              sender=sender_email,
                              recipients=[sender_email])
                msg.body = f"New pickup from {current_user.name} at {address} on {date} during {time}."
                mail.send(msg)
        except Exception:
            pass

        flash('Pickup request submitted successfully', 'success')
        return redirect(url_for('user.pickup'))
        
    pickups = PickupRequest.query.filter_by(user_id=current_user.id).order_by(PickupRequest.created_at.desc()).all()
    return render_template('user/pickup.html', pickups=pickups)


