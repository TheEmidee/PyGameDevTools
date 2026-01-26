from datetime import datetime


def get_date_formatted_name() -> str:
    """Return current date in yyyyMMdd format."""
    return datetime.now().strftime("%Y%m%d")
