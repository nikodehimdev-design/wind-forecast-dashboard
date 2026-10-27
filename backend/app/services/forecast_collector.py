import logging
import os
import time

import requests

from app.services.elexon import capture_current_forecasts


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    poll_seconds = int(os.getenv("WIND_FORECAST_POLL_SECONDS", "900"))
    if poll_seconds < 60:
        raise ValueError("WIND_FORECAST_POLL_SECONDS must be at least 60.")

    while True:
        try:
            stored = capture_current_forecasts()
            logger.info("Captured %s WINDFOR forecast records.", stored)
        except requests.RequestException:
            logger.exception("Could not retrieve WINDFOR forecasts.")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
