import os
from app import create_app, db

config_name = os.environ.get("FLASK_ENV", "production")
app = create_app(config_name)

try:
    with app.app_context():
        db.create_all()
except Exception as e:
    app.logger.warning(f"Could not create database tables: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
