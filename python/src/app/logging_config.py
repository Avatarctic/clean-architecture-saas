import logging
import warnings

import structlog

# Suppress a noisy, non-fatal passlib bcrypt metadata warning that appears in some
# environments (passlib tries to read bcrypt.__about__ and may log a warning).
# We keep bcrypt functionality but avoid the confusing startup message.
# Ensure bcrypt module exposes a minimal __about__ object so passlib won't
# raise AttributeError when probing for version metadata in some installs.
# This must happen at module import time, before passlib tries to use bcrypt.
import bcrypt as _bcrypt  # type: ignore  # isort: skip
from types import SimpleNamespace  # isort: skip

if not hasattr(_bcrypt, "__about__"):
    _bcrypt.__about__ = SimpleNamespace(__version__="4.0.1")  # type: ignore[attr-defined]
elif not hasattr(_bcrypt.__about__, "__version__"):
    _bcrypt.__about__.__version__ = "4.0.1"  # type: ignore[attr-defined]


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    # suppress the specific handler and the broader passlib namespaces
    logging.getLogger("passlib").setLevel(logging.ERROR)
    logging.getLogger("passlib.handlers").setLevel(logging.ERROR)
    logging.getLogger("passlib.handlers.bcrypt").setLevel(logging.ERROR)

    # Suppress a known PendingDeprecationWarning from starlette.formparsers about
    # `multipart` import; it's noisy in test output and not actionable for us.
    warnings.filterwarnings(
        "ignore",
        category=PendingDeprecationWarning,
        module=r"starlette\.formparsers",
    )


def get_logger(name: str | None = None):
    if not structlog.get_config():
        configure_logging()
    return structlog.get_logger(name)
