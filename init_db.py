import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from app import app
from database.models import db, User


def initialize_database():
    with app.app_context():
        db.create_all()

        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not admin_email or not admin_password:
            print("ERROR: ADMIN_EMAIL or ADMIN_PASSWORD is missing in .env")
            return

        admin_email = admin_email.strip().lower()

        admin = User.query.filter_by(email=admin_email).first()

        if admin:
            admin.role = "admin"
            db.session.commit()
            print("Admin already exists. Admin role updated!")
            print(f"Email: {admin_email}")

        else:
            admin = User(
                name="ScrapSutra Admin",
                email=admin_email,
                phone="0000000000",
                password=generate_password_hash(admin_password),
                role="admin",
                eco_score=0
            )

            db.session.add(admin)
            db.session.commit()

            print("Admin created successfully!")
            print(f"Email: {admin_email}")


if __name__ == "__main__":
    initialize_database()