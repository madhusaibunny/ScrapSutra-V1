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

import os
import resend
import threading

from google.oauth2 import id_token
from google.auth.transport import requests


auth_bp = Blueprint('auth', __name__)


# ==========================================
# SEND EMAIL USING RESEND
# ==========================================
def send_email(to_email, subject, html_content):

    try:

        api_key = os.environ.get("RESEND_API_KEY")

        if not api_key:
            print("RESEND ERROR: RESEND_API_KEY is missing")
            return

        resend.api_key = api_key

        sender_email = os.environ.get(
            "MAIL_SENDER",
            "onboarding@resend.dev"
        )

        response = resend.Emails.send({
            "from": sender_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })

        print(
            f"EMAIL SENT SUCCESSFULLY TO {to_email}"
        )

        print(response)

    except Exception as e:

        print(
            f"RESEND EMAIL ERROR: {str(e)}"
        )


# ==========================================
# SEND EMAIL IN BACKGROUND
# ==========================================
def send_async_email(to_email, subject, html_content):

    threading.Thread(
        target=send_email,
        args=(
            to_email,
            subject,
            html_content
        ),
        daemon=True
    ).start()


# ==========================================
# CHECK PICKUP STATUS FOR LOGIN POPUP
# ==========================================
def check_pickup_notification(user_id):

    pickup = (
        PickupRequest.query
        .filter(
            PickupRequest.user_id == user_id,
            PickupRequest.status.in_(
                ['approved', 'rejected']
            )
        )
        .order_by(
            PickupRequest.created_at.desc()
        )
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
@auth_bp.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    if current_user.is_authenticated:

        if current_user.role == 'admin':

            return redirect(
                url_for('admin.dashboard')
            )

        return redirect(
            url_for('user.dashboard')
        )


    if request.method == 'POST':

        email = request.form.get(
            'email',
            ''
        ).strip().lower()

        password = request.form.get(
            'password',
            ''
        )


        user = User.query.filter(
            db.func.lower(User.email) == email
        ).first()


        if user and check_password_hash(
            user.password,
            password
        ):

            # ==================================
            # LOGIN USER
            # ==================================
            login_user(user)


            # ==================================
            # CHECK PICKUP STATUS
            # ==================================
            if user.role != 'admin':

                check_pickup_notification(
                    user.id
                )


            # ==================================
            # SEND LOGIN NOTIFICATION EMAIL
            # ==================================
            send_async_email(

                user.email,

                "New Login Detected - ScrapSutra",

                f"""
                <html>

                <body>

                    <h2>Hello {user.name},</h2>

                    <p>
                        A new login was detected on your
                        <strong>ScrapSutra</strong> account.
                    </p>

                    <p>
                        If this was you, you can safely
                        ignore this email.
                    </p>

                    <br>

                    <p>
                        Thank you,<br>
                        <strong>ScrapSutra Team ♻️</strong>
                    </p>

                </body>

                </html>
                """

            )


            # ==================================
            # ADMIN REDIRECT
            # ==================================
            if user.role == 'admin':

                return redirect(
                    url_for('admin.dashboard')
                )


            # ==================================
            # USER REDIRECT
            # ==================================
            return redirect(
                url_for('user.dashboard')
            )


        else:

            flash(
                'Invalid email or password',
                'error'
            )


    response = make_response(

        render_template(
            'auth/login.html'
        )

    )


    response.headers['Cache-Control'] = (
        'no-store, no-cache, must-revalidate, max-age=0'
    )

    response.headers['Pragma'] = 'no-cache'

    response.headers['Expires'] = '0'
    
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'


    return response


# ==========================================
# SIGNUP
# ==========================================
@auth_bp.route(
    '/signup',
    methods=['GET', 'POST']
)
def signup():

    if current_user.is_authenticated:

        return redirect(
            url_for('user.dashboard')
        )


    if request.method == 'POST':

        name = request.form.get(
            'name'
        )

        email = request.form.get(
            'email',
            ''
        ).strip().lower()

        phone = request.form.get(
            'phone'
        )

        password = request.form.get(
            'password'
        )


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


        # ==================================
        # CREATE USER
        # ==================================
        new_user = User(

            name=name,

            email=email,

            phone=phone,

            password=generate_password_hash(
                password,
                method='pbkdf2:sha256'
            )

        )


        db.session.add(
            new_user
        )

        db.session.commit()


        # ==================================
        # LOGIN NEW USER
        # ==================================
        login_user(
            new_user
        )


        # ==================================
        # SEND WELCOME EMAIL
        # ==================================
        send_async_email(

            new_user.email,

            "Welcome to ScrapSutra ♻️",

            f"""
            <html>

            <body>

                <h2>
                    Welcome to ScrapSutra,
                    {new_user.name}! ♻️
                </h2>

                <p>
                    Your account has been successfully created.
                </p>

                <p>
                    You can now upload your scrap,
                    schedule pickups and start recycling.
                </p>

                <br>

                <p>
                    Happy Recycling! 🌱
                </p>

                <p>
                    <strong>
                        ScrapSutra Team
                    </strong>
                </p>

            </body>

            </html>
            """

        )


        return redirect(
            url_for('user.dashboard')
        )


    response = make_response(

        render_template(
            'auth/signup.html'
        )

    )


    response.headers['Cache-Control'] = (
        'no-store, no-cache, must-revalidate, max-age=0'
    )

    response.headers['Pragma'] = 'no-cache'

    response.headers['Expires'] = '0'
    
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'


    return response


# ==========================================
# LOGOUT
# ==========================================
@auth_bp.route('/logout')
@login_required
def logout():

    session.pop(
        'pickup_notification',
        None
    )

    logout_user()


    return redirect(
        url_for('index')
    )


# ==========================================
# GOOGLE LOGIN
# ==========================================
@auth_bp.route(
    '/google-login',
    methods=['POST']
)
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

            'ss-1-37011'

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

        print(
            f"GOOGLE LOGIN ERROR: {str(e)}"
        )

        return jsonify({

            "success": False,

            "error": f"Invalid token: {str(e)}"

        }), 401


    # ==========================================
    # FIND USER
    # ==========================================
    user = User.query.filter(

        db.func.lower(User.email) == email

    ).first()


    # ==========================================
    # CREATE USER IF NOT EXISTS
    # ==========================================
    if not user:

        import secrets


        random_password = secrets.token_hex(
            16
        )


        user = User(

            name=name,

            email=email,

            phone="Not Provided",

            password=generate_password_hash(

                random_password,

                method='pbkdf2:sha256'

            )

        )


        db.session.add(
            user
        )

        db.session.commit()


        # ==================================
        # WELCOME EMAIL
        # ==================================
        send_async_email(

            user.email,

            "Welcome to ScrapSutra ♻️",

            f"""
            <html>

            <body>

                <h2>
                    Hello {user.name}!
                </h2>

                <p>
                    Welcome to ScrapSutra.
                </p>

                <p>
                    Your account was successfully
                    created using Google Login.
                </p>

                <br>

                <p>
                    <strong>
                        ScrapSutra Team ♻️
                    </strong>
                </p>

            </body>

            </html>
            """

        )


    # ==========================================
    # LOGIN USER
    # ==========================================
    login_user(
        user
    )


    # ==========================================
    # CHECK PICKUP NOTIFICATION
    # ==========================================
    if user.role != 'admin':

        check_pickup_notification(
            user.id
        )


    return jsonify({

        "success": True,

        "redirect": url_for(
            'user.dashboard'
        )

    })