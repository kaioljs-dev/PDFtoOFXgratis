"""
Deterministic FITID (Financial Institution Transaction ID) generator.
Guarantees idempotency and deduplication when re-importing statements.
"""
from datetime import date
from decimal import Decimal
import hashlib
from typing import Optional, Union


def generate_fitid(
    bank_id: str,
    account_id: str,
    tx_date: Union[date, str],
    amount: Decimal,
    memo: str,
    sequence: int = 0,
    checknum: Optional[str] = None
) -> str:
    """
    Generates a deterministic unique transaction ID (FITID) using SHA-256.
    
    Formula:
      hash = SHA256(bank_id:account_id:date:amount:memo:checknum:sequence)
    
    Returns a clean alphanumeric string suitable for OFX (max 32 chars).
    Format: {BANK_PREFIX}-{YYYYMMDD}-{HASH12}
    """
    date_str = tx_date.strftime("%Y%m%d") if isinstance(tx_date, date) else str(tx_date).replace("-", "")
    amt_str = f"{amount:.2f}"
    memo_clean = "".join(c for c in memo.upper() if c.isalnum() or c in " _-")[:40]
    check_str = str(checknum or "")

    raw_data = f"{bank_id}:{account_id}:{date_str}:{amt_str}:{memo_clean}:{check_str}:{sequence}"
    hash_hex = hashlib.sha256(raw_data.encode("utf-8")).hexdigest().upper()
    
    bank_prefix = bank_id.zfill(3)
    # Ex: 001-20261021-9F3A1B4C8D2E
    short_hash = hash_hex[:12]
    return f"{bank_prefix}-{date_str}-{short_hash}"
