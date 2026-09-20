import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        for name in ("category", "operation", "participant_id"):
            value = getattr(record, name, None)
            if value is not None:
                document[name] = str(value)
        if record.exc_info and record.exc_info[0] is not None:
            document["exception_type"] = record.exc_info[0].__name__
        return json.dumps(document, separators=(",", ":"), ensure_ascii=True)


def configure_json_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    exc_info = bool(fields.pop("exc_info", False))
    logger.log(level, message, extra=fields, exc_info=exc_info)
