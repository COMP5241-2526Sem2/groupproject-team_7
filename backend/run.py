import os
import sys

# Add backend directory to path for Vercel serverless functions
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app

config_name = os.environ.get("FLASK_ENV", "production")
app = create_app(config_name)

# Export app for Vercel serverless function
application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
