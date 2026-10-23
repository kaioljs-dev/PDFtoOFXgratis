"""
Parser for Banco Itaú Unibanco (Code: 341).
Handles both standard DD/MM/YYYY dates and abbreviated DD/MM statements.
"""
from datetime import datetime
from decimal import Decimal
import re
from typing import List, Optional

from .base import BaseBankParser
from ..core.models import BankInfo, BankStatement, Transaction
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date


class ItauParser(BaseBankParser):
    bank_id = "341"
    bank_name = "Banco Itaú"

    def can_parse(self, first_page_text: str) -> bool:
        header = self.get_clean_header(first_page_text)
        return (
            "ITAÚ" in header or
            "ITAU" in header or
            "341-7" in header
        )

    def extract_account_info(self, text: str) -> BankInfo:
        branch = "0001"
        account = "00000-0"

        # Ex: "agência 1234 conta 12345-6" ou "Ag.: 1234 C/C: 12345-6"
        branch_match = re.search(r"ag(?:[êe]ncia|\.)?[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if branch_match:
            branch = branch_match.group(1).strip()

        acct_match = re.search(r"c(?:onta)?(?:/c)?[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if acct_match:
            account = acct_match.group(1).strip()

        return BankInfo(
            bank_id=self.bank_id,
            bank_name=self.bank_name,
            branch_id=branch,
            account_id=account,
            account_type=self.default_account_type,
        )

    def detect_reference_year(self, text: str) -> int:
        """Finds statement year from header, e.g. 2026."""
        # Procurar ano explícito: "outubro/2026", "2026", "01/10/2026"
        m = re.search(r"/\s*(20\d{2})\b", text)
        if m:
            return int(m.group(1))
        m2 = re.search(r"\b(20\d{2})\b", text)
        if m2:
            return int(m2.group(1))
        return datetime.now().year

    def parse(self, pdf_path: str) -> BankStatement:
        full_text, all_tables = self.extract_text_and_tables(pdf_path)
        bank_info = self.extract_account_info(full_text)
        ref_year = self.detect_reference_year(full_text)
        transactions: List[Transaction] = []

        # 1. Tabelas estruturadas
        for table in all_tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                clean_row = [str(c).strip() if c else "" for c in row]
                row_str = " ".join(clean_row)

                # Verificar se linha começa com DD/MM/YYYY ou DD/MM
                m_date = re.match(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", clean_row[0])
                if not m_date:
                    continue

                tx_date = parse_statement_date(m_date.group(1), default_year=ref_year)
                if not tx_date or any(k in row_str.upper() for k in ["SALDO ANTERIOR", "SALDO TOTAL", "SALDO DO DIA"]):
                    continue

                # Colunas comuns Itaú:
                # [Data, Lançamentos, Razão, Documento, Valor, Saldo]
                # Ou: [Data, Lançamento, Valor, Saldo]
                memo = clean_row[1] if len(clean_row) > 1 else ""
                doc_num = None
                amount = None

                for cell in clean_row[2:]:
                    if re.match(r"^\d{4,8}$", cell) and not doc_num:
                        doc_num = cell
                    elif ("," in cell or "." in cell) and re.search(r"\d", cell):
                        val = parse_brl_amount(cell)
                        if val != Decimal("0.00") and amount is None:
                            amount = val

                if amount is not None and memo:
                    transactions.append(Transaction(
                        date=tx_date,
                        amount=amount,
                        memo=memo,
                        checknum=doc_num,
                    ))

        # 2. Fallback linha por linha via regex
        if not transactions:
            lines = full_text.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Padrão Itaú: 21/10/2026 PIX TRANSF RECEB 123456 800,00 4.800,00
                # Ou: 21/10 PIX TRANSF RECEB -150,00 4.650,00
                match = re.match(
                    r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(?:(\d{4,8})\s+)?([-\d.,]+(?:\s*[CD\-])?)(?:\s+[-\d.,]+(?:\s*[CD\-])?)?$",
                    line
                )
                if match:
                    d_str, raw_memo, doc, raw_val = match.groups()
                    if any(k in raw_memo.upper() for k in ["SALDO ANTERIOR", "SALDO ATUAL", "SALDO DO DIA", "SALDO EM"]):
                        continue

                    tx_date = parse_statement_date(d_str, default_year=ref_year)
                    tx_amt = parse_brl_amount(raw_val)
                    if tx_date and tx_amt != Decimal("0.00"):
                        transactions.append(Transaction(
                            date=tx_date,
                            amount=tx_amt,
                            memo=raw_memo.strip(),
                            checknum=doc,
                        ))

        balance = self.extract_final_balance(full_text)
        return self.build_statement(bank_info, transactions, balance)
