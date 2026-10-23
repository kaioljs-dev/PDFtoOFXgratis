"""
Parser factory and auto-detector for Brazilian bank statement PDFs.
"""
from decimal import Decimal
import re
from typing import Dict, List, Optional, Type

import pdfplumber

from .base import BaseBankParser
from .bb import BancoDoBrasilParser
from .bradesco import BradescoParser
from .caixa import CaixaParser
from .itau import ItauParser
from .nubank import NubankParser
from .santander import SantanderParser
from ..core.models import BankInfo, BankStatement, Transaction
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date


class GenericBankParser(BaseBankParser):
    """Fallback parser that detects standard Brazilian statement transaction rows."""
    bank_id = "000"
    bank_name = "Extrato Bancário"

    def can_parse(self, first_page_text: str) -> bool:
        return True

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

                m_date = re.match(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", clean_row[0])
                if not m_date:
                    continue

                tx_date = parse_statement_date(m_date.group(1))
                if not tx_date or any(k in row_str.upper() for k in ["SALDO ANTERIOR", "SALDO TOTAL", "SALDO DO DIA", "SALDO ATUAL"]):
                    continue

                memo = clean_row[1] if len(clean_row) > 1 else ""
                amount = None
                doc_num = None

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

        # 2. Fallback linha por linha
        if not transactions:
            lines = full_text.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Regex genérica para linhas de extrato: Data Descrição [Doc] Valor [Saldo]
                match = re.match(
                    r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+?)\s+(?:(\d{4,8})\s+)?([-\d.,]+(?:\s*[CD\-])?)(?:\s+[-\d.,]+(?:\s*[CD\-])?)?$",
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


class ParserFactory:
    """Factory to resolve appropriate parser by bank code, name or auto-detection."""

    PARSERS: List[Type[BaseBankParser]] = [
        BancoDoBrasilParser,
        CaixaParser,
        BradescoParser,
        SantanderParser,
        ItauParser,
        NubankParser,
    ]

    BANK_ALIASES: Dict[str, Type[BaseBankParser]] = {
        "bb": BancoDoBrasilParser,
        "001": BancoDoBrasilParser,
        "bancodobrasil": BancoDoBrasilParser,
        "banco_do_brasil": BancoDoBrasilParser,

        "caixa": CaixaParser,
        "104": CaixaParser,
        "cef": CaixaParser,
        "caixaeconomica": CaixaParser,

        "bradesco": BradescoParser,
        "237": BradescoParser,

        "santander": SantanderParser,
        "033": SantanderParser,
        "33": SantanderParser,

        "itau": ItauParser,
        "itaú": ItauParser,
        "341": ItauParser,

        "nubank": NubankParser,
        "nu": NubankParser,
        "260": NubankParser,
        "nupagamentos": NubankParser,
    }

    @classmethod
    def get_parser(cls, pdf_path: str, forced_bank: Optional[str] = None) -> BaseBankParser:
        """
        Returns parser instance based on user selection or auto-detects from PDF content.
        """
        # 1. Se o banco foi explicitamente passado pelo usuário
        if forced_bank and forced_bank.lower() != "auto":
            key = forced_bank.lower().replace("-", "").replace(" ", "").replace("_", "")
            if key in cls.BANK_ALIASES:
                return cls.BANK_ALIASES[key]()
            raise ValueError(
                f"Banco '{forced_bank}' desconhecido. Bancos suportados: "
                "bb (001), caixa (104), bradesco (237), santander (033), itau (341)."
            )

        # 2. Auto-detecção lendo a primeira página do PDF
        first_page_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text() or ""
        except Exception as e:
            # Em caso de erro na abertura preliminar, fallback genérico
            first_page_text = ""

        for parser_cls in cls.PARSERS:
            parser_instance = parser_cls()
            if parser_instance.can_parse(first_page_text):
                return parser_instance

        # 3. Fallback para parser genérico
        return GenericBankParser()
