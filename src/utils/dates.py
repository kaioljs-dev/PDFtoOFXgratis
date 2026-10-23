"""
Date parsing and formatting utilities for bank statements and OFX output.
"""
from datetime import date, datetime
import re
from typing import Optional, Union


def parse_statement_date(date_str: str, default_year: Optional[int] = None) -> Optional[date]:
    """
    Parses various date formats commonly found in Brazilian bank statements:
      - '21/10/2026'
      - '21/10/26'
      - '21/10' (uses default_year or current year)
      - '2026-10-21'
      - '21.10.2026'
    """
    if not date_str:
        return None

    cleaned = date_str.strip().replace(".", "/")
    
    # 1. DD/MM/YYYY
    m1 = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", cleaned)
    if m1:
        d, m, y = map(int, m1.groups())
        try:
            return date(y, m, d)
        except ValueError:
            return None

    # 2. DD/MM/YY
    m2 = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", cleaned)
    if m2:
        d, m, yy = map(int, m2.groups())
        y = 2000 + yy if yy < 70 else 1900 + yy
        try:
            return date(y, m, d)
        except ValueError:
            return None

    # 3. DD/MM (sem ano)
    m3 = re.match(r"^(\d{1,2})/(\d{1,2})$", cleaned)
    if m3:
        d, m = map(int, m3.groups())
        y = default_year or datetime.now().year
        try:
            return date(y, m, d)
        except ValueError:
            return None

    # 4. YYYY-MM-DD
    m4 = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", cleaned)
    if m4:
        y, m, d = map(int, m4.groups())
        try:
            return date(y, m, d)
        except ValueError:
            return None

    return None


def format_ofx_date(d: Union[date, datetime], timezone_offset: str = "[-03:EST]") -> str:
    """
    Formats date into OFX 1.0.2 format: YYYYMMDDHHMMSS[offset]
    Example: 20261021120000[-03:EST]
    """
    if isinstance(d, datetime):
        base = d.strftime("%Y%m%d%H%M%S")
    elif isinstance(d, date):
        base = f"{d.strftime('%Y%m%d')}120000"
    else:
        now = datetime.now()
        base = f"{now.strftime('%Y%m%d')}120000"

    return f"{base}{timezone_offset}" if timezone_offset else base
