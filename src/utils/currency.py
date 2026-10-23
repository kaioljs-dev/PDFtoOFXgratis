"""
Utilities for parsing Brazilian financial currency amounts into Python Decimal.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Union


def parse_brl_amount(val_str: Union[str, float, int, Decimal], is_debit: bool = False) -> Decimal:
    """
    Parses Brazilian currency format string into Decimal.
    Supports formats:
      - '1.250,50'      -> Decimal('1250.50')
      - '-1.250,50'     -> Decimal('-1250.50')
      - '1.250,50 D'    -> Decimal('-1250.50')
      - '1.250,50 C'    -> Decimal('1250.50')
      - '1.250,50-'     -> Decimal('-1250.50')
      - '(1.250,50)'    -> Decimal('-1250.50')
      - 'R$ -350,00'    -> Decimal('-350.00')
      - '1250.50'       -> Decimal('1250.50')
    """
    if isinstance(val_str, Decimal):
        return -abs(val_str) if is_debit else val_str
    if isinstance(val_str, (int, float)):
        dec = Decimal(str(val_str))
        return -abs(dec) if is_debit else dec

    s = str(val_str).strip()
    if not s:
        return Decimal("0.00")

    # Detectar sinal negativo ou indicador de débito (D)
    force_negative = False
    
    # Parênteses indicam valor negativo contábil: (120,00)
    if s.startswith("(") and s.endswith(")"):
        force_negative = True
        s = s[1:-1].strip()

    # Remover prefixos de moeda e caracteres invisíveis primeiro
    s = re.sub(r"[R$\s\xa0]", "", s)

    # Indicador sufixo ou prefixo: 'D', 'DEB', '-'
    upper_s = s.upper()
    if upper_s.endswith("D") or upper_s.endswith("DEB") or upper_s.endswith("-"):
        force_negative = True
        s = re.sub(r"[dD\-\s]+$", "", s).strip()
    elif upper_s.endswith("C") or upper_s.endswith("CRED") or upper_s.endswith("+"):
        s = re.sub(r"[cC\+\s]+$", "", s).strip()

    if s.startswith("-") or "-" in s:
        force_negative = True
        s = s.replace("-", "").strip()
    elif s.startswith("+"):
        s = s.replace("+", "").strip()

    if is_debit:
        force_negative = True

    # Lidar com separadores brasileiro vs internacional:
    # Caso 1: tem ponto e vírgula -> 1.250,50 -> remove ponto, troca vírgula por ponto
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    # Caso 2: só tem vírgula -> 1250,50 -> troca vírgula por ponto
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    # Caso 3: só tem ponto -> pode ser 1250.50 ou 1.250 (sem centavos)
    # Se tiver múltiplos pontos: 1.250.000 -> remove pontos
    elif s.count(".") > 1:
        s = s.replace(".", "")
    elif "." in s:
        # Se tem 1 ponto e 3 dígitos após, pode ser milhar: 1.250 -> 1250.00
        parts = s.split(".")
        if len(parts[1]) == 3 and not parts[1].endswith("00"):
            # Ex: 1.250 sem casas decimais
            s = parts[0] + parts[1]
        # Caso contrário, trata como decimal 1250.50

    # Remover qualquer outro caracter que não seja dígito ou ponto
    s = re.sub(r"[^0-9.]", "", s)

    if not s:
        return Decimal("0.00")

    try:
        amount = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        amount = Decimal("0.00")

    return -amount if force_negative else amount


def format_ofx_amount(amount: Decimal) -> str:
    """Formats Decimal to standard OFX format (e.g., -1234.56 or 1234.56)."""
    return f"{amount:.2f}"


def format_brl(amount: Decimal) -> str:
    """Formats Decimal to Brazilian currency string (e.g., R$ 1.234,56)."""
    sign = "-" if amount < Decimal("0") else ""
    abs_amt = abs(amount)
    parts = f"{abs_amt:,.2f}".split(".")
    # parts[0] tem vírgula como separador de milhar americano, trocamos por ponto
    integer_part = parts[0].replace(",", ".")
    decimal_part = parts[1]
    return f"{sign}R$ {integer_part},{decimal_part}"
