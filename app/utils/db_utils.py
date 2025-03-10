"""Database utilities for handling special PostgreSQL types."""

from typing import Dict, Any, List
from datetime import date, datetime


def sanitize_for_json(data: Any) -> Any:
    """
    Recursively sanitize any data structure to make it JSON serializable.
    Handles PostgreSQL specific types like Range.
    """
    if data is None:
        return None
    elif isinstance(data, (str, int, float, bool)):
        return data
    elif isinstance(data, (datetime, date)):
        return data.isoformat()
    elif isinstance(data, Dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, List):
        return [sanitize_for_json(item) for item in data]
    elif hasattr(data, "__class__") and data.__class__.__name__ == "Range":
        # Handle PostgreSQL range types
        if hasattr(data, "isempty") and data.isempty:
            return None
        result = {}
        if hasattr(data, "lower") and data.lower is not None:
            result["lower"] = sanitize_for_json(data.lower)
        if hasattr(data, "upper") and data.upper is not None:
            result["upper"] = sanitize_for_json(data.upper)
        return result
    elif hasattr(data, "__dict__"):
        # Handle objects with __dict__ attribute
        return {k: sanitize_for_json(v) for k, v in data.__dict__.items()
                if not k.startswith("_")}
    elif hasattr(data, "keys") and callable(data.keys):
        # Handle dict-like objects
        return {k: sanitize_for_json(data[k]) for k in data.keys()}
    else:
        # Last resort, try string conversion
        try:
            return str(data)
        except Exception:
            return f"[Unserializable: {type(data).__name__}]"