import os
# Ensure Secret key is set before the app gets imported.
os.environ["SECRET_KEY"]="test-secret-key"
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

