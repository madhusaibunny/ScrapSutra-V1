# ScrapSutra V1 - Render Deployment Guide

## Overview
This guide provides step-by-step instructions to deploy ScrapSutra V1 to Render.com, a modern cloud platform for hosting web applications.

## Prerequisites
- GitHub account with the repository pushed
- Render account (https://render.com)
- Environment variables ready (API keys, credentials, etc.)

---

## Deployment Steps

### 1. Prepare Your Repository

#### Ensure all files are committed:
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

#### Verify `.env.example` is present and `.env` is in `.gitignore`:
- ✅ `.env.example` contains all environment variable templates
- ✅ `.env` is listed in `.gitignore` (secrets are not committed)

---

### 2. Create a Render Account & Connect GitHub

1. Go to https://render.com
2. Sign up using GitHub account
3. Authorize Render to access your GitHub repositories

---

### 3. Create a New Web Service on Render

1. Click **"New +"** in the Render Dashboard
2. Select **"Web Service"**
3. Connect your GitHub repository (ScrapSutra_V1_Final)
4. Fill in the service details:
   - **Name**: `scrapsutra-v1`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt && python init_db.py`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Start with Basic (scalable as needed)

---

### 4. Create PostgreSQL Database on Render

1. Click **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name**: `scrapsutra-db`
   - **Database**: `scrapsutra`
   - **User**: `scrapsutra`
   - **Instance Type**: Free or Starter (choose based on needs)
3. Create the database
4. Copy the internal database URL for later

---

### 5. Configure Environment Variables

In the Render Dashboard for your Web Service, go to **Environment**:

Add the following environment variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `SECRET_KEY` | Generate a strong random string | Use `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | PostgreSQL internal URL from step 4 | Format: `postgresql://user:password@host:5432/database` |
| `GEMINI_API_KEY` | Your Google Gemini API key | Get from Google Cloud Console |
| `FLASK_DEBUG` | `False` | Keep as False in production |
| `PYTHON_VERSION` | `3.10.11` | Matches requirements |
| `MAIL_USERNAME` | Your Brevo SMTP email | Email service for notifications |
| `MAIL_PASSWORD` | Your Brevo SMTP password | Get from Brevo account settings |
| `FIREBASE_API_KEY` | Your Firebase API key | Frontend Firebase config |
| `FIREBASE_AUTH_DOMAIN` | Your Firebase auth domain | e.g., `project.firebaseapp.com` |
| `FIREBASE_PROJECT_ID` | Your Firebase project ID | From Firebase Console |
| `FIREBASE_STORAGE_BUCKET` | Your Firebase storage bucket | e.g., `project.appspot.com` |
| `FIREBASE_MESSAGING_SENDER_ID` | Firebase sender ID | From Firebase Console |
| `FIREBASE_APP_ID` | Your Firebase app ID | From Firebase Console |

---

### 6. Create the Render Service

1. Review all settings
2. Click **"Create Web Service"**
3. Render will automatically:
   - Deploy from your GitHub repository
   - Install dependencies from `requirements.txt`
   - Run database initialization (`init_db.py`)
   - Start the application with Gunicorn

---

### 7. Monitor Deployment

1. Check the **Logs** tab in Render Dashboard for deployment progress
2. Look for successful messages:
   - `Database initialization complete.`
   - Application running on Render's URL

---

### 8. Connect PostgreSQL Database to Web Service

In Render Dashboard:

1. Go to your Web Service
2. Go to **Environment** section
3. The `DATABASE_URL` should already be set to your PostgreSQL instance

---

## Post-Deployment

### First Login
- **Admin Email**: `admin@scrapsutra.com`
- **Admin Password**: `admin123`

⚠️ **IMPORTANT**: Change the admin password immediately after first login!

### Useful Commands

#### Connect to your Render database (for debugging):
```bash
psql "postgresql://user:password@your-render-db-host:5432/scrapsutra"
```

#### View Render logs:
- Check "Logs" tab in Render Dashboard
- Real-time application output

#### Restart the service:
- Click "Manual Deploy" → "Deploy latest commit" in Render Dashboard

---

## Troubleshooting

### Database Connection Errors
- Verify `DATABASE_URL` is correct in Environment variables
- Ensure PostgreSQL instance is running
- Check that the database user has proper permissions

### Missing Environment Variables
- Check Render Environment tab
- Ensure all variables from `.env.example` are configured
- Redeploy after adding/updating variables

### Build Failures
- Check Logs for specific error messages
- Verify `requirements.txt` has all dependencies
- Ensure `init_db.py` runs without errors

### Static Files Not Loading
- Confirm Flask app serves static files correctly
- Check `static/` folder structure
- Verify UPLOAD_FOLDER path in app.py

---

## File Structure Required

```
ScrapSutra_V1_Final/
├── app.py                    # Flask application
├── init_db.py               # Database initialization
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── .gitignore              # Git ignore rules
├── render.yaml             # Render configuration
├── database/
│   ├── __init__.py
│   └── models.py           # Database models
├── routes/
│   ├── auth.py
│   ├── user.py
│   └── admin.py
├── models/
│   └── ai_module.py
├── templates/              # HTML templates
│   ├── base.html
│   ├── index.html
│   └── ...
└── static/                 # Static files
    ├── css/
    ├── uploads/
    └── ...
```

---

## Production Best Practices

✅ **Implemented:**
- PostgreSQL database instead of SQLite
- Gunicorn WSGI server
- Environment variable configuration
- Database initialization script

✅ **Recommended Next Steps:**
1. Set up error monitoring (e.g., Sentry)
2. Configure custom domain
3. Set up automatic backups for PostgreSQL
4. Enable HTTPS/SSL (Render handles this by default)
5. Monitor application performance

---

## Additional Resources

- [Render Documentation](https://render.com/docs)
- [Flask Deployment Guide](https://flask.palletsprojects.com/deployment/)
- [Gunicorn Documentation](https://gunicorn.org/)
- [PostgreSQL Render Docs](https://render.com/docs/databases)

---

## Support

For issues specific to:
- **Render**: Use Render's support resources
- **Flask/Python**: Check Flask documentation
- **Database**: Refer to PostgreSQL documentation
