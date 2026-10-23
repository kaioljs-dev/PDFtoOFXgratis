"""
Parser for Banco Bradesco (Code: 237).
Handles checking account statements with separate credit/debit columns or combined values.
"""
from decimal import Decimal
import re
from typing import List

from .base import BaseBankParser
from ..core.models import BankInfo, BankStatement, Transaction
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date


class BradescoParser(BaseBankParser):
    bank_id = "237"
    bank_name = "Banco Bradesco"

    def can_parse(self, first_page_text: str) -> bool:
        header = self.get_clean_header(first_page_text)
        return (
            "BRADESCO" in header or
            "237-2" in header
        )

    def extract_account_info(self, text: str) -> BankInfo:
        branch = "0001"
        account = "0000000-0"

        # Ex: "Agência: 1234 | Conta: 1234567-8" ou "Agência: 1234 Conta Corrente: 1234567-8"
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

        # 1. Tabelas
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
                if not tx_date or any(k in row_str.upper() for k in ["SALDO ANTERIOR", "TOTAL", "SALDO ATUAL"]):
                    continue

                # Identificar se há colunas de Crédito e Débito separadas:
                # Exemplo Bradesco: [Data, Histórico, Docto, Crédito, Débito, Saldo]
                # Ou: [Data, Histórico, Docto, Valor, Saldo]
                memo = clean_row[1] if len(clean_row) > 1 else ""
                doc_num = clean_row[2] if len(clean_row) > 2 and re.match(r"^\d+$", clean_row[2]) else None
                amount = None

                # Se a tabela tem 6 colunas, frequentemente col 3 é Crédito, col 4 é Débito
                if len(clean_row) >= 6:
                    cred_cell = clean_row[3]
                    deb_cell = clean_row[4]
                    if cred_cell and re.search(r"\d", cred_cell):
                        amount = parse_brl_amount(cred_cell)
                    elif deb_cell and re.search(r"\d", deb_cell):
                        amount = parse_brl_amount(deb_cell, is_debit=True)
                else:
                    # Procurar células de valor
                    for cell in clean_row[2:]:
                        if ("," in cell or "." in cell) and re.search(r"\d", cell):
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

                # Bradesco regex: 21/10/2026 TED RECEBIDA 12345 1.500,00 5.000,00
                # Ou: 21/10/2026 PAGTO ELETRON COBRANCA 67890 -350,00 4.650,00
                match = re.match(
                    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(?:(\d{4,8})\s+)?([-\d.,]+(?:\s*[CD])?)(?:\s+[-\d.,]+(?:\s*[CD])?)?$",
                    line
                )
                if match:
                    d_str, raw_memo, doc, raw_val = match.groups()
                    if any(k in raw_memo.upper() for k in ["SALDO ANTERIOR", "SALDO ATUAL", "SALDO"]):
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
