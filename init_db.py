import os
from app import create_app, db
from database.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    
    # Check if admin exists
    admin = User.query.filter_by(email="admin@scrapsutra.com").first()
    if not admin:
        print("Creating admin user...")
        admin = User(
            name="Admin User",
            email="admin@scrapsutra.com",
            phone="0000000000",
            password=generate_password_hash("admin123", method="pbkdf2:sha256"),
            role="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully (email: admin@scrapsutra.com, password: admin123).")
    else:
        print("Admin already exists.")

    print("Database reset complete.")
