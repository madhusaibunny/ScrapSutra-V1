import os
from app import create_app, db
from database.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("Tables created successfully.")
    
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
        print("Admin user created successfully.")
        print("⚠️  DEFAULT CREDENTIALS: Email: admin@scrapsutra.com | Password: admin123")
        print("⚠️  CHANGE THE ADMIN PASSWORD AFTER FIRST LOGIN!")
    else:
        print("Admin user already exists.")

    print("Database initialization complete.")
