from django import template
from datetime import datetime

register = template.Library()

@register.filter
def to_time(value):
    """Convert '14:00' to a datetime.time object."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except Exception:
        return None
