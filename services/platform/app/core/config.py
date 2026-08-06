import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]

DATABASE_URL=os.environ["DATABASE_URL"]

ALGORITHM ="HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30

REFRESH_TOKEN_EXPIRE_DAYS = 7

#Set to true only when the service runs behind a reverse proxy / load balancer
# that sets X-Forwarded-For itself.
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"
      