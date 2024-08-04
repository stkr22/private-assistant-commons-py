import re


def mqtt_pattern_to_regex(pattern: str) -> re.Pattern:
    """
    Converts MQTT topic pattern with wildcards to a regular expression.
    - '+' wildcard is replaced to match any string in a single topic level.
    - '#' wildcard is replaced to match any strings at multiple topic levels.
    """
    pattern = re.escape(pattern)
    pattern = pattern.replace(r"\+", r"[^/]+").replace(r"\#", r".*")
    return re.compile(f"^{pattern}$")
