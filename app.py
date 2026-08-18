import os
from dotenv import load_dotenv
from flask import Flask, render_template
from database.models import db, User
from flask_login import LoginManager
from flask_mail import Mail

load_dotenv()

# Define mail globally to be imported everywhere
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scrapsutra.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')

    # Mail config (Using Brevo SMTP)
    app.config['MAIL_SERVER'] = 'smtp-relay.brevo.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'test@example.com')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'password')

    # Make sure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    mail.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'
    login_manager.init_app(app)

    @app.context_processor
    def inject_firebase_config():
        return dict(
            firebase_api_key=os.environ.get('FIREBASE_API_KEY', ''),
            firebase_auth_domain=os.environ.get('FIREBASE_AUTH_DOMAIN', ''),
            firebase_project_id=os.environ.get('FIREBASE_PROJECT_ID', ''),
            firebase_storage_bucket=os.environ.get('FIREBASE_STORAGE_BUCKET', ''),
            firebase_messaging_sender_id=os.environ.get('FIREBASE_MESSAGING_SENDER_ID', ''),
            firebase_app_id=os.environ.get('FIREBASE_APP_ID', '')
        )

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.user import user_bp
    from routes.admin import admin_bp
    from routes.auth import auth_bp
    
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/pricing')
    def pricing():
        rates = [
            {'category': 'Plastic', 'price': 15, 'icon': 'fa-bottle-water', 'color': '#10b981'},
            {'category': 'Metal', 'price': 40, 'icon': 'fa-gear', 'color': '#9ca3af'},
            {'category': 'Paper', 'price': 10, 'icon': 'fa-newspaper', 'color': '#facc15'},
            {'category': 'Cardboard', 'price': 8, 'icon': 'fa-box-open', 'color': '#f59e0b'},
            {'category': 'Glass', 'price': 5, 'icon': 'fa-wine-glass', 'color': '#60a5fa'},
            {'category': 'E-Waste', 'price': 50, 'icon': 'fa-microchip', 'color': '#a78bfa'}
        ]
        return render_template('pricing.html', rates=rates)

    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)