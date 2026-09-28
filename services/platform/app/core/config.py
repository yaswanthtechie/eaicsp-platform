import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]

DATABASE_URL=os.environ["DATABASE_URL"]

ALGORITHM ="HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15

REFRESH_TOKEN_EXPIRE_DAYS = 7

#Set to true only when the service runs behind a reverse proxy / load balancer
# that sets X-Forwarded-For itself.
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"

# ---- MFA / SSO -----------------------------------------
MFA_ENABLED = os.environ.get("MFA_ENABLED", "false").strip().lower() == "true"

# Dev/demo only. When set, every OTP equals this value. Leave empty
# anywhere real, and a random OTP is generated instead.
MFA_MOCK_OTP = os.environ.get("MFA_MOCK_OTP") or None

MOCK_SSO_ENABLED = os.environ.get("MOCK_SSO_ENABLED", "false").strip().lower() == "true"

# Required only when mock SSO is on; fails loudly at startup if missing.
MOCK_SSO_SECRET = os.environ["MOCK_SSO_SECRET"] if MOCK_SSO_ENABLED else None