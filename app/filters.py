from datetime import datetime, timezone

def format_datetime(dt, format="%b %d, %Y %I:%M %p"):
    """
    Format a datetime object according to the given format
    
    Args:
        dt: A datetime object
        format: The format to use (default: "%b %d, %Y %I:%M %p")
        
    Returns:
        A formatted string representing the datetime
    """
    if dt is None:
        return "Not completed"
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return dt
    return dt.strftime(format)

def timesince(dt, default="just now"):
    """
    Returns a human-friendly string representing time passed since dt
    
    Args:
        dt: A datetime object
        default: String to return if dt is in the future
        
    Returns:
        A string like "2 minutes ago" or "3 days ago"
    """
    now = datetime.now(timezone.utc)
    
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return default
    
    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    if seconds < 3600:
        minutes = seconds / 60
        return f"{int(minutes)} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds / 3600
        return f"{int(hours)} hour{'s' if hours != 1 else ''} ago"
    if seconds < 604800:
        days = seconds / 86400
        return f"{int(days)} day{'s' if days != 1 else ''} ago"
    if seconds < 2592000:
        weeks = seconds / 604800
        return f"{int(weeks)} week{'s' if weeks != 1 else ''} ago"
    if seconds < 31536000:
        months = seconds / 2592000
        return f"{int(months)} month{'s' if months != 1 else ''} ago"
    
    years = seconds / 31536000
    return f"{int(years)} year{'s' if years != 1 else ''} ago"

def format_timedelta(start, end):
    """Format the time difference between two datetime objects"""
    if start is None or end is None:
        return "Not available"
    delta_seconds = (end - start).total_seconds()
    minutes = int(delta_seconds // 60)
    return f"{minutes} minutes"
