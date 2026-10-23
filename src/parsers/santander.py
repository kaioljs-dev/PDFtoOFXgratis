"""
Parser for Banco Santander (Code: 033).
Handles checking and savings account PDF statements.
"""
from decimal import Decimal
import re
from typing import List

from .base import BaseBankParser
from ..core.models import BankInfo, BankStatement, Transaction
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date


class SantanderParser(BaseBankParser):
    bank_id = "033"
    bank_name = "Banco Santander"

    def can_parse(self, first_page_text: str) -> bool:
        header = self.get_clean_header(first_page_text)
        return (
            "SANTANDER" in header or
            "033-7" in header
        )

    def extract_account_info(self, text: str) -> BankInfo:
        branch = "0001"
        account = "00000000-0"

        # Ex: "Agência: 1234" ou "Agência / Conta: 1234 / 01023456-7"
        branch_match = re.search(r"ag[êe]ncia[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if branch_match:
            branch = branch_match.group(1).strip()

        acct_match = re.search(r"conta(?:\s+corrente)?[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if acct_match:
            account = acct_match.group(1).strip()

        return BankInfo(
            bank_id=self.bank_id,
            bank_name=self.bank_name,
            branch_id=branch,
            account_id=account,
            account_type=self.default_account_type,
        )

    def parse(self, pdf_path: str) -> BankStatement:
        full_text, all_tables = self.extract_text_and_tables(pdf_path)
        bank_info = self.extract_account_info(full_text)
        transactions: List[Transaction] = []

        # 1. Tabelas estruturadas
        for table in all_tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                clean_row = [str(c).strip() if c else "" for c in row]
                row_str = " ".join(clean_row)

                m_date = re.match(r"^(\d{2}/\d{2}/\d{4})", clean_row[0])
                if not m_date:
                    continue

                tx_date = parse_statement_date(m_date.group(1))
                if not tx_date or any(k in row_str.upper() for k in ["SALDO ANTERIOR", "SALDO DISPONIVEL"]):
                    continue

                # Santander padrão: [Data, Descrição, Docto, Valor, Saldo]
                memo = clean_row[1] if len(clean_row) > 1 else ""
                doc_num = None
                amount = None

                # Procurar documento e valor
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

                # Regex: 21/10/2026 PIX ENVIADO 123456 -150,00 4.850,00
                match = re.match(
                    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(?:(\d{4,8})\s+)?([-\d.,]+(?:\s*[CD])?)(?:\s+[-\d.,]+(?:\s*[CD])?)?$",
                    line
                )
                if match:
                    d_str, raw_memo, doc, raw_val = match.groups()
                    if any(k in raw_memo.upper() for k in ["SALDO ANTERIOR", "SALDO ATUAL", "SALDO DISPONÍVEL"]):
                        continue

                    tx_date = parse_statement_date(d_str)
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
