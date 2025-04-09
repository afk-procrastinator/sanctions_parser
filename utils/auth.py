from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

# Get password from environment variable or use a default
PASSWORD = os.getenv("APP_PASSWORD", "default_password")
HASHED_PASSWORD = generate_password_hash(PASSWORD)

def verify_password(password):
    """Verify if the provided password matches the stored hash"""
    return check_password_hash(HASHED_PASSWORD, password) 