"""
Parser for Nubank / Nu Pagamentos S.A. (Code: 260).
Handles checking account (Conta Nubank) PDF statements.
"""
from datetime import date
from decimal import Decimal
import re
from typing import List, Optional

from .base import BaseBankParser
from ..core.models import BankInfo, BankStatement, Transaction, TransactionType
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date
from ..utils.text import remove_accents


class NubankParser(BaseBankParser):
    bank_id = "260"
    bank_name = "Nu Pagamentos S.A. (Nubank)"

    MONTHS = {
        "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
        "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12
    }

    SKIP_PATTERNS = [
        r"^CPF\s+[•\d.-]+",
        r"^Ag[êe]ncia\s+\d+\s+Conta",
        r"^\d+-\d+$",
        r"^\d{2}\s+DE\s+\w+\s+DE\s+\d{4}\s+a\s+\d{2}\s+DE\s+\w+\s+DE\s+\d{4}",
        r"^VALORES\s+EM\s+R\$",
        r"^Saldo\s+inicial",
        r"^Rendimento\s+l[íi]quido",
        r"^Saldo\s+final\s+do\s+per[íi]odo",
        r"^R\$\s*[\d.,]+",
        r"^Movimenta[çc][õo]es",
        r"Tem\s+alguma\s+d[úu]vida\?",
        r"Caso\s+a\s+solu[çc][ãa]o\s+fornecida",
        r"dispon[íi]veis\s+em\s+nubank",
        r"^Extrato\s+gerado\s+dia",
        r"^O\s+saldo\s+l[íi]quido\s+corresponde",
        r"^N[ãa]o\s+nos\s+responsabilizamos",
        r"^Asseguramos\s+a\s+autenticidade",
        r"^Nu\s+Financeira\s+S\.A\.",
        r"^CNPJ:",
        r"^Nu\s+Pagamentos\s+S\.A\.",
        r"^Atendimento\s+24h",
    ]

    def can_parse(self, first_page_text: str) -> bool:
        header = self.get_clean_header(first_page_text)
        t = first_page_text.upper()
        return (
            "NUBANK" in header or
            "NU PAGAMENTOS" in header or
            "NU FINANCEIRA" in header or
            ("AGÊNCIA 0001 CONTA" in header and "VALORES EM R$" in header) or
            ("AGENCIA 0001 CONTA" in header and "VALORES EM R$" in header) or
            ("NU PAGAMENTOS" in t and "NUBANK.COM.BR" in t)
        )

    def extract_account_info(self, text: str) -> BankInfo:
        branch = "0001"
        account = "00000000-0"

        # Capturar Agência e Conta: "Agência 0001 Conta\n71578973-8" ou "Agência 0001 Conta 71578973-8"
        m = re.search(r"Ag[êe]ncia\s+(\d+)\s+Conta[\s\n]+(\d+[-\w]*)", text, re.IGNORECASE)
        if m:
            branch = m.group(1).strip()
            account = m.group(2).strip()

        return BankInfo(
            bank_id=self.bank_id,
            bank_name=self.bank_name,
            branch_id=branch,
            account_id=account,
            account_type=self.default_account_type,
        )

    def extract_final_balance(self, text: str) -> Decimal:
        """Captura 'Saldo final do período R$ 40,79' ou 'Saldo final do período 40,79'."""
        patterns = [
            r"Saldo\s+final\s+do\s+per[íi]odo[\s\n]+(?:R\$\s*)?([-\d.,]+)",
            r"Saldo\s+final[:\s]+(?:R\$\s*)?([-\d.,]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = parse_brl_amount(m.group(1).strip())
                if val != Decimal("0.00"):
                    return val

        return Decimal("0.00")

    def _should_skip_line(self, line: str) -> bool:
        for pat in self.SKIP_PATTERNS:
            if re.search(pat, line, re.IGNORECASE):
                return True
        return False

    def parse(self, pdf_path: str) -> BankStatement:
        full_text, _ = self.extract_text_and_tables(pdf_path)
        bank_info = self.extract_account_info(full_text)
        balance = self.extract_final_balance(full_text)

        lines = full_text.splitlines()
        transactions: List[Transaction] = []

        current_date: Optional[date] = None
        current_flow: Optional[str] = None  # 'CREDIT' ou 'DEBIT'

        for raw_line in lines:
            line = raw_line.strip()
            if not line or self._should_skip_line(line):
                continue

            # Detectar cabeçalho de data diária: '01 SET 2026' ou '01 SET 2026 Total de entradas + 2.949,00'
            m_date = re.match(r"^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})(.*)$", line)
            if m_date:
                d_str, m_str, y_str, rest = m_date.groups()
                month = self.MONTHS.get(m_str.upper())
                if month:
                    current_date = date(int(y_str), month, int(d_str))
                    line = rest.strip()
                    if not line:
                        continue

            # Detectar início de bloco de entradas ou saídas
            if "Total de entradas" in line:
                current_flow = "CREDIT"
                continue
            elif "Total de saídas" in line or "Total de saidas" in line:
                current_flow = "DEBIT"
                continue

            # Detectar linha de transação terminando com valor monetário: 'Descricao ... 1.949,00'
            m_tx = re.match(r"^(.*?)\s+([-\d.,]+)$", line)
            if m_tx and current_date:
                desc = m_tx.group(1).strip()
                val_raw = m_tx.group(2).strip()

                # Ignorar números soltos ou linhas de total diário
                if desc and any(c in val_raw for c in [",", "."]):
                    amount = parse_brl_amount(val_raw)
                    if amount != Decimal("0.00"):
                        if current_flow == "DEBIT":
                            amount = -abs(amount)
                        elif current_flow == "CREDIT":
                            amount = abs(amount)

                        # Limpar descrição e remover caracteres de controle
                        desc_clean = re.sub(r"\s+", " ", desc).strip()
                        desc_sanitized = remove_accents(desc_clean)

                        # Identificar tipo de transação mais específico se possível
                        desc_upper = desc_sanitized.upper()
                        trntype = TransactionType.CREDIT if amount > Decimal("0") else TransactionType.DEBIT
                        if "PIX" in desc_upper:
                            trntype = TransactionType.XFER
                        elif "SAQUE" in desc_upper:
                            trntype = TransactionType.ATM
                        elif "COMPRA NO DEBITO" in desc_upper or "COMPRA NO DEBITO" in desc_upper:
                            trntype = TransactionType.POS
                        elif "PAGAMENTO" in desc_upper or "BOLETO" in desc_upper:
                            trntype = TransactionType.PAYMENT

                        transactions.append(Transaction(
                            date=current_date,
                            amount=amount,
                            memo=desc_sanitized,
                            trntype=trntype,
                        ))

        return self.build_statement(bank_info, transactions, balance)
