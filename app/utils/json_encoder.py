"""Custom JSON encoder for handling special types."""

import json
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from typing import Any


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that can handle special types like UUIDs, dates, datetimes, etc.
    """
    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            # Convert UUID to string
            return str(obj)
        elif isinstance(obj, (datetime, date)):
            # ISO format for dates and datetimes
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            # Convert Decimal to float
            return float(obj)
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Range':
            # Handle PostgreSQL range types (including daterange)
            if obj.isempty:
                return None
            # Convert range to a dictionary with lower and upper bounds
            result = {}
            if obj.lower is not None:
                result['lower'] = obj.lower.isoformat() if hasattr(obj.lower, 'isoformat') else obj.lower
            if obj.upper is not None:
                result['upper'] = obj.upper.isoformat() if hasattr(obj.upper, 'isoformat') else obj.upper
            return result
        # Let the base class handle everything else
        return super().default(obj)