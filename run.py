import os
import sys

# Add project to path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

# Absolute paths for templates and static folders
BASE_DIR = PROJECT_DIR
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Import the app from dashboard.app
from dashboard.app import app

if __name__ == "__main__":
    print(f"DEBUG: Template dir = {TEMPLATE_DIR}")
    print(f"DEBUG: Static dir = {STATIC_DIR}")
    app.run(host="127.0.0.1", port=8080, debug=True)
