import os
import uvicorn

if __name__ == "__main__":
    os.environ["LOAD_TEST_MODE"] = "true"
    os.environ["OTEL_ENABLED"] = "false"
    os.environ["GATEWAY_RATE_LIMIT_ENABLED"] = "false"

    from app.core.config import settings
    settings.LOAD_TEST_MODE = True
    settings.OTEL_ENABLED = False

    from app.middleware.ratelimit import limiter
    limiter.enabled = False

    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
