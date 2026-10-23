"""
Base Parser class defining the common interface and helpers for bank statement parsers.
"""
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
import re
from typing import List, Optional, Tuple

import pdfplumber

from ..core.models import BankInfo, BankStatement, Transaction, TransactionType
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date
from ..utils.hashing import generate_fitid


class BaseBankParser(ABC):
    """Abstract base class for bank statement parsers."""

    bank_id: str = "000"
    bank_name: str = "Banco Genérico"
    default_account_type: str = "CHECKING"

    @abstractmethod
    def can_parse(self, first_page_text: str) -> bool:
        """Determines if this parser handles the given PDF text."""
        pass

    @abstractmethod
    def parse(self, pdf_path: str) -> BankStatement:
        """Extracts BankStatement from PDF."""
        pass

    @classmethod
    def get_clean_header(cls, text: str, max_lines: int = 8) -> str:
        """
        Extracts top header lines ignoring transaction rows and counterparty mentions.
        Prevents false-positive bank identification when a Pix/TED cites another bank.
        """
        lines = []
        for line in text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            upper = line_str.upper()
            # Pular linhas que são transações
            if re.match(r"^\d{1,2}/\d{1,2}", line_str):
                continue
            if re.match(r"^\d{1,2}\s+[A-Z]{3}", upper):
                continue
            if any(term in upper for term in [
                "TRANSFERÊNCIA", "TRANSFERENCIA", "PAGAMENTO", "PAGTO", "BOLETO", "SAQUE", "COMPRA NO DÉBITO", "COMPRA NO DEBITO"
            ]):
                continue
            lines.append(upper)
            if len(lines) >= max_lines:
                break
        return "\n".join(lines)

    def extract_text_and_tables(self, pdf_path: str) -> Tuple[str, List[List[List[str]]]]:
        """
        Extracts full text and table structures across all pages using pdfplumber.
        Returns:
          full_text: concatenated string of all pages
          all_tables: list of tables extracted from each page
        """
        full_text_parts = []
        all_tables = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True) or page.extract_text() or ""
                full_text_parts.append(text)
                tables = page.extract_tables() or []
                all_tables.extend(tables)

        return "\n".join(full_text_parts), all_tables

    def extract_account_info(self, text: str) -> BankInfo:
        """Default heuristic extraction for branch and account numbers."""
        branch = "0001"
        account = "00000-0"

        # Tentar capturar Agência: 1234 / Conta: 56789-0
        branch_match = re.search(r"ag[êe]ncia[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if branch_match:
            branch = branch_match.group(1).strip()

        account_match = re.search(r"conta(?:\s+corrente)?[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if account_match:
            account = account_match.group(1).strip()

        return BankInfo(
            bank_id=self.bank_id,
            bank_name=self.bank_name,
            branch_id=branch,
            account_id=account,
            account_type=self.default_account_type,
        )

    def extract_final_balance(self, text: str) -> Decimal:
        """Extracts closing balance from statement text using common regex patterns."""
        patterns = [
            r"saldo\s+final(?:\s+dispon[ií]vel)?[:\s]+(?:R\$\s*)?([-\d.,]+(?:\s*[CD\-])?)",
            r"saldo\s+dispon[ií]vel[:\s]+(?:R\$\s*)?([-\d.,]+(?:\s*[CD\-])?)",
            r"saldo\s+em\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?[:\s]+(?:R\$\s*)?([-\d.,]+(?:\s*[CD\-])?)",
            r"saldo\s+(?:atual|do\s+dia)[:\s]+(?:R\$\s*)?([-\d.,]+(?:\s*[CD\-])?)",
            r"total\s+saldo[:\s]+(?:R\$\s*)?([-\d.,]+(?:\s*[CD\-])?)",
        ]
        for pattern in patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                # Pegar última ocorrência de saldo
                last_val_str = matches[-1].group(1).strip()
                val = parse_brl_amount(last_val_str)
                if val != Decimal("0.00"):
                    return val

        return Decimal("0.00")

    def build_statement(
        self,
        bank_info: BankInfo,
        transactions: List[Transaction],
        final_balance: Optional[Decimal] = None
    ) -> BankStatement:
        """Builds and validates a BankStatement from extracted data."""
        if not transactions:
            today = date.today()
            return BankStatement(
                bank_info=bank_info,
                start_date=today,
                end_date=today,
                transactions=[],
                balance=final_balance or Decimal("0.00"),
            )

        # Ordenar transações por data
        transactions.sort(key=lambda t: t.date)
        start_date = transactions[0].date
        end_date = transactions[-1].date

        # Gerar FITIDs determinísticos para transações que ainda não têm
        for idx, tx in enumerate(transactions):
            if not tx.fitid:
                tx.fitid = generate_fitid(
                    bank_id=bank_info.bank_id,
                    account_id=bank_info.account_id,
                    tx_date=tx.date,
                    amount=tx.amount,
                    memo=tx.memo,
                    sequence=idx,
                    checknum=tx.checknum,
                )

        balance = final_balance if final_balance is not None else sum(
            (t.amount for t in transactions), Decimal("0.00")
        )

        return BankStatement(
            bank_info=bank_info,
            start_date=start_date,
            end_date=end_date,
            transactions=transactions,
            balance=balance,
            balance_date=end_date,
        )
