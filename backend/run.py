import os
from app import create_app, db

config_name = os.environ.get("FLASK_ENV", "development")
app = create_app(config_name)

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
