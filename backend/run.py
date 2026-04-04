import os
import sys
import time
from app import create_app, db

config_name = os.environ.get("FLASK_ENV", "production")
app = create_app(config_name)

try:
    with app.app_context():
        last_error = None
        for attempt in range(1, 11):
            try:
                db.create_all()
                break
            except Exception as exc:
                last_error = exc
                app.logger.warning(
                    "Database not ready for create_all, retry %s/10: %s",
                    attempt,
                    exc,
                )
                time.sleep(2)
        else:
            raise last_error
except Exception as e:
    app.logger.warning(f"Could not create database tables: {e}")

if __name__ == "__main__":
    # Get port from command line argument or environment variable, default to 5000
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
