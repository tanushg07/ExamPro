"""
Services module for handling business logic related to validation.
This separates validation logic from models, improving maintainability.
"""
import json
import bleach
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Maximum size constants
MAX_JSON_SIZE = 10000
ALLOWED_HTML_TAGS = ['p', 'b', 'i', 'u', 'ul', 'ol', 'li', 'br', 'pre', 'code', 'span']
ALLOWED_HTML_ATTRS = {'span': ['class']}

def sanitize_html(html_text):
    """
    Sanitize HTML text to prevent XSS attacks
    
    Args:
        html_text: The HTML text to sanitize
        
    Returns:
        str: The sanitized HTML
    """
    if not html_text:
        return html_text
        
    return bleach.clean(
        html_text,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRS,
        strip=True
    )

def sanitize_code(code_text):
    """
    Sanitize code text to allow syntax highlighting but prevent XSS
    
    Args:
        code_text: The code text to sanitize
        
    Returns:
        str: The sanitized code
    """
    if not code_text:
        return code_text
        
    return bleach.clean(
        code_text,
        tags=['pre', 'code', 'span'],
        attributes={'span': ['class']},
        strip=True
    )

def validate_json_size(json_data, max_size=MAX_JSON_SIZE):
    """
    Validate and potentially truncate JSON data that's too large
    
    Args:
        json_data: The JSON data to validate
        max_size: Maximum allowed size in characters
        
    Returns:
        dict: The validated (potentially truncated) JSON data
    """
    if not json_data:
        return {}
        
    if isinstance(json_data, str):
        try:
            json_data = json.loads(json_data)
        except:
            return {'error': 'Invalid JSON format', 'truncated': True}
    
    # Convert to string to check size
    json_str = json.dumps(json_data)
    
    if len(json_str) > max_size:
        return {'error': 'JSON data too large', 'truncated': True, 'original_size': len(json_str)}
        
    return json_data

def validate_time_difference(client_time, server_time=None, max_diff_seconds=300):
    """
    Validate the difference between client and server time
    
    Args:
        client_time: The client-reported time
        server_time: The server time (defaults to now)
        max_diff_seconds: Maximum allowed difference in seconds
        
    Returns:
        tuple: (is_valid, difference_seconds)
    """
    if not client_time:
        return False, None
        
    if not server_time:
        server_time = datetime.utcnow()
        
    try:
        # Convert string to datetime if needed
        if isinstance(client_time, str):
            client_time = datetime.fromisoformat(client_time.replace('Z', '+00:00'))
            
        time_diff = abs((client_time - server_time).total_seconds())
        return time_diff <= max_diff_seconds, time_diff
    except Exception as e:
        logger.error(f"Error validating time difference: {str(e)}")
        return False, None
