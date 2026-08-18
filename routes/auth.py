from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, make_response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from database.models import db, User
from flask_mail import Message
import threading
from google.oauth2 import id_token
from google.auth.transport import requests

auth_bp = Blueprint('auth', __name__)

def send_async_email(app, msg):
    try:
        from app import mail
        with app.app_context():
            mail.send(msg)
    except:
        pass

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            
            sender_email = current_app.config.get('MAIL_USERNAME')
            if sender_email:
                msg = Message(subject="New Login Detected",
                              sender=sender_email,
                              recipients=[user.email],
                              body=f"Hello {user.name},\n\nA login was detected on your account.")
                threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
            
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('user.dashboard'))
        else:
            flash('Invalid email or password', 'error')

    response = make_response(render_template('auth/login.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists', 'error')
            return redirect(url_for('auth.signup'))

        new_user = User(
            name=name, email=email, phone=phone,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        sender_email = current_app.config.get('MAIL_USERNAME')
        if sender_email:
            msg = Message(subject="Welcome to ScrapSutra",
                          sender=sender_email,
                          recipients=[new_user.email],
                          body=f"Hello {new_user.name},\n\nWelcome to ScrapSutra! Start recycling and earn rewards.")
            threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

        return redirect(url_for('user.dashboard'))

    response = make_response(render_template('auth/signup.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth_bp.route('/google-login', methods=['POST'])
def google_login():
    data = request.get_json()
    token = data.get('id_token') if data else None
    
    if not token:
        return jsonify({"success": False, "error": "No ID token provided"}), 400
        
    try:
        # Verify the Firebase ID token
        firebase_project_id = current_app.config.get('FIREBASE_PROJECT_ID', 'scarpsutra')
        decoded_token = id_token.verify_firebase_token(token, requests.Request(), audience=firebase_project_id)
        
        email = decoded_token.get('email', '').strip().lower()
        name = decoded_token.get('name', 'Google User')
        
        if not email:
            return jsonify({"success": False, "error": "Token missing email"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "error": f"Invalid token: {str(e)}"}), 401
    
    # Synchronize Firebase user with SQLite database
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        # Create a new user for Google login with a random password since they authenticate via Google
        import secrets
        random_password = secrets.token_hex(16)
        user = User(
            name=name, 
            email=email, 
            phone="Not Provided",  # Google doesn't easily provide phone number
            password=generate_password_hash(random_password, method='pbkdf2:sha256')
        )
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email using existing system
        sender_email = current_app.config.get('MAIL_USERNAME')
        if sender_email:
            msg = Message(subject="Welcome to ScrapSutra via Google",
                          sender=sender_email,
                          recipients=[user.email],
                          body=f"Hello {user.name},\n\nWelcome to ScrapSutra! Start recycling and earn rewards.")
            threading.Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()

    login_user(user)
    return jsonify({"success": True, "redirect": url_for('user.dashboard')})
