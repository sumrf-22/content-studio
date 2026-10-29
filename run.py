import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Absolute paths for templates and static folders
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Import the app from dashboard.app
from dashboard.app import app

if __name__ == "__main__":
    print(f"DEBUG: Template dir = {TEMPLATE_DIR}")
    print(f"DEBUG: Static dir = {STATIC_DIR}")
    app.run(host="127.0.0.1", port=8080, debug=True)
