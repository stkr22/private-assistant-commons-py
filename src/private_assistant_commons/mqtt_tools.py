"""Utilities for MQTT topic pattern matching and processing."""
import re


def mqtt_pattern_to_regex(pattern: str) -> re.Pattern:
    """Convert MQTT topic pattern with wildcards to regular expression.
    
    Args:
        pattern: MQTT topic pattern with wildcards
                '+' matches single topic level (e.g., 'sensor/+/temperature')
                '#' matches multiple topic levels (e.g., 'sensor/#')
                
    Returns:
        Compiled regular expression pattern
        
    Examples:
        mqtt_pattern_to_regex('sensor/+/temp') matches 'sensor/kitchen/temp'
        mqtt_pattern_to_regex('sensor/#') matches 'sensor/kitchen/temp/reading'
    """
    pattern = re.escape(pattern)
    pattern = pattern.replace(r"\+", r"[^/]+").replace(r"\#", r".*")
    return re.compile(f"^{pattern}$")
