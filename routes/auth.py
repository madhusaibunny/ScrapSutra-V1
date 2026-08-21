from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    current_app,
    make_response,
    session
)

from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database.models import db, User, PickupRequest

from flask_mail import Message
import threading

from google.oauth2 import id_token
from google.auth.transport import requests


auth_bp = Blueprint('auth', __name__)


# ==========================================
# SEND EMAIL IN BACKGROUND
# ==========================================
def send_async_email(app, msg):
    try:
        from app import mail

        with app.app_context():
            mail.send(msg)

    except Exception as e:
        print(f"Email error: {e}")


# ==========================================
# CHECK PICKUP STATUS FOR LOGIN POPUP
# ==========================================
def check_pickup_notification(user_id):
    """
    Find the latest approved or rejected pickup
    and store it temporarily for the dashboard popup.
    """

    pickup = (
        PickupRequest.query
        .filter(
            PickupRequest.user_id == user_id,
            PickupRequest.status.in_(['approved', 'rejected'])
        )
        .order_by(PickupRequest.created_at.desc())
        .first()
    )

    if pickup:
        session['pickup_notification'] = {
            'status': pickup.status,
            'date': pickup.pickup_date,
            'time': pickup.time_slot
        }


# ==========================================
# LOGIN
# ==========================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter(
            db.func.lower(User.email) == email
        ).first()

        if user and check_password_hash(user.password, password):

            # LOGIN USER
            login_user(user)

            # ==================================
            # CHECK PICKUP STATUS AFTER LOGIN
            # ==================================
            if user.role != 'admin':
                check_pickup_notification(user.id)

            # ==================================
            # LOGIN EMAIL
            # ==================================
            sender_email = current_app.config.get(
                'MAIL_USERNAME'
            )

            if sender_email:

                msg = Message(
                    subject="New Login Detected",
                    sender=sender_email,
                    recipients=[user.email],
                    body=(
                        f"Hello {user.name},\n\n"
                        f"A login was detected on your ScrapSutra account."
                    )
                )

                threading.Thread(
                    target=send_async_email,
                    args=(
                        current_app._get_current_object(),
                        msg
                    ),
                    daemon=True
                ).start()

            # ADMIN REDIRECT
            if user.role == 'admin':
                return redirect(
                    url_for('admin.dashboard')
                )

            # USER REDIRECT
            return redirect(
                url_for('user.dashboard')
            )

        else:
            flash(
                'Invalid email or password',
                'error'
            )

    response = make_response(
        render_template('auth/login.html')
    )

    response.headers['Cache-Control'] = (
        'no-store, no-cache, must-revalidate, max-age=0'
    )
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


# ==========================================
# SIGNUP
# ==========================================
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():

    if current_user.is_authenticated:
        return redirect(
            url_for('user.dashboard')
        )

    if request.method == 'POST':

        name = request.form.get('name')
        email = request.form.get(
            'email',
            ''
        ).strip().lower()

        phone = request.form.get('phone')
        password = request.form.get('password')

        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            flash(
                'Email already exists',
                'error'
            )

            return redirect(
                url_for('auth.signup')
            )

        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(
                password,
                method='pbkdf2:sha256'
            )
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)

        sender_email = current_app.config.get(
            'MAIL_USERNAME'
        )

        if sender_email:

            msg = Message(
                subject="Welcome to ScrapSutra",
                sender=sender_email,
                recipients=[new_user.email],
                body=(
                    f"Hello {new_user.name},\n\n"
                    f"Welcome to ScrapSutra! "
                    f"Start recycling and earn rewards."
                )
            )

            threading.Thread(
                target=send_async_email,
                args=(
                    current_app._get_current_object(),
                    msg
                ),
                daemon=True
            ).start()

        return redirect(
            url_for('user.dashboard')
        )

    response = make_response(
        render_template('auth/signup.html')
    )

    response.headers['Cache-Control'] = (
        'no-store, no-cache, must-revalidate, max-age=0'
    )

    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


# ==========================================
# LOGOUT
# ==========================================
@auth_bp.route('/logout')
@login_required
def logout():

    # Remove any old notification
    session.pop('pickup_notification', None)

    logout_user()

    return redirect(
        url_for('index')
    )


# ==========================================
# GOOGLE LOGIN
# ==========================================
@auth_bp.route('/google-login', methods=['POST'])
def google_login():

    data = request.get_json()

    token = (
        data.get('id_token')
        if data
        else None
    )

    if not token:

        return jsonify({
            "success": False,
            "error": "No ID token provided"
        }), 400

    try:

        firebase_project_id = current_app.config.get(
            'FIREBASE_PROJECT_ID',
            'scarpsutra'
        )

        decoded_token = id_token.verify_firebase_token(
            token,
            requests.Request(),
            audience=firebase_project_id
        )

        email = decoded_token.get(
            'email',
            ''
        ).strip().lower()

        name = decoded_token.get(
            'name',
            'Google User'
        )

        if not email:

            return jsonify({
                "success": False,
                "error": "Token missing email"
            }), 400

    except Exception as e:

        return jsonify({
            "success": False,
            "error": f"Invalid token: {str(e)}"
        }), 401


    # ==========================================
    # FIND OR CREATE USER
    # ==========================================
    user = User.query.filter(
        db.func.lower(User.email) == email
    ).first()

    if not user:

        import secrets

        random_password = secrets.token_hex(16)

        user = User(
            name=name,
            email=email,
            phone="Not Provided",
            password=generate_password_hash(
                random_password,
                method='pbkdf2:sha256'
            )
        )

        db.session.add(user)
        db.session.commit()

        sender_email = current_app.config.get(
            'MAIL_USERNAME'
        )

        if sender_email:

            msg = Message(
                subject="Welcome to ScrapSutra via Google",
                sender=sender_email,
                recipients=[user.email],
                body=(
                    f"Hello {user.name},\n\n"
                    f"Welcome to ScrapSutra! "
                    f"Start recycling and earn rewards."
                )
            )

            threading.Thread(
                target=send_async_email,
                args=(
                    current_app._get_current_object(),
                    msg
                ),
                daemon=True
            ).start()


    # ==========================================
    # LOGIN GOOGLE USER
    # ==========================================
    login_user(user)

    # CHECK PICKUP NOTIFICATION
    if user.role != 'admin':
        check_pickup_notification(user.id)

    return jsonify({
        "success": True,
        "redirect": url_for('user.dashboard')
    })