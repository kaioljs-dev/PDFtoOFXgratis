"""
Parser for Banco do Brasil (Code: 001).
Handles checking account and savings statements.
"""
from decimal import Decimal
import re
from typing import List

from .base import BaseBankParser
from ..core.models import BankInfo, BankStatement, Transaction, TransactionType
from ..utils.currency import parse_brl_amount
from ..utils.dates import parse_statement_date


class BancoDoBrasilParser(BaseBankParser):
    bank_id = "001"
    bank_name = "Banco do Brasil"

    def can_parse(self, first_page_text: str) -> bool:
        header = self.get_clean_header(first_page_text)
        return (
            "BANCO DO BRASIL" in header or
            "001-9" in header or
            "AUTOATENDIMENTO BB" in header
        )

    def extract_account_info(self, text: str) -> BankInfo:
        branch = "0001"
        account = "00000-0"

        # Ex: "Agência: 1234-5" ou "Agência 1234-X"
        branch_match = re.search(r"ag[êe]ncia[:\s]+(\d+[-\w]*)", text, re.IGNORECASE)
        if branch_match:
            branch = branch_match.group(1).strip()

        # Ex: "Conta corrente: 98765-4" ou "Conta: 12345-6"
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

        # 1. Tentar extração via tabelas estruturadas
        for table in all_tables:
            for row in table:
                if not row or len(row) < 3:
                    continue
                # Limpar células
                clean_row = [str(c).strip() if c else "" for c in row]
                row_str = " ".join(clean_row)

                # Verificar se começa com data DD/MM/YYYY
                m_date = re.match(r"^(\d{2}/\d{2}/\d{4})", clean_row[0])
                if not m_date:
                    continue

                tx_date = parse_statement_date(m_date.group(1))
                if not tx_date:
                    continue

                # Filtrar linhas de saldo que começam com data
                if any(k in row_str.upper() for k in ["SALDO ANTERIOR", "SALDO ATUAL", "S A L D O"]):
                    continue

                # Procurar valor monetário e documento nas colunas restantes
                # Geralmente: [Data, Lote, Histórico, Documento, Valor, Saldo]
                # Ou: [Data, Histórico, Documento, Valor]
                memo = ""
                doc_num = None
                amount = None

                # Analisar da direita para a esquerda procurando valores
                amounts_found = []
                for idx, cell in enumerate(clean_row[1:], start=1):
                    # Procura padrão monetário: 1.250,00 C ou -120,00
                    m_val = re.search(r"([-\d.,]+)\s*([CD])?", cell)
                    if m_val and ("," in cell or "." in cell):
                        parsed_val = parse_brl_amount(cell)
                        if parsed_val != Decimal("0.00"):
                            amounts_found.append((idx, parsed_val, cell))

                if amounts_found:
                    # Em extratos com [Valor, Saldo], o penúltimo valor é a transação e o último é o saldo
                    if len(amounts_found) >= 2:
                        val_idx, amount, _ = amounts_found[0]
                    else:
                        val_idx, amount, _ = amounts_found[0]

                    # Histórico são os campos entre a data e o valor
                    memo_parts = clean_row[1:val_idx]
                    memo = " ".join(p for p in memo_parts if p and not re.match(r"^\d{4,6}$", p))
                    # Procurar documento (geralmente numérico)
                    for p in memo_parts:
                        if re.match(r"^\d{5,10}$", p):
                            doc_num = p
                            break

                if amount is not None and memo:
                    transactions.append(Transaction(
                        date=tx_date,
                        amount=amount,
                        memo=memo or "Lançamento Banco do Brasil",
                        checknum=doc_num,
                    ))

        # 2. Se a extração por tabela não capturou transações, faz fallback regex linha por linha
        if not transactions:
            lines = full_text.splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Padrão BB: 21/10/2026 13105 PIX TRANSF RECEBIDA 123456 1.500,00 C 5.430,20 C
                # Ou: 21/10/2026 PIX TRANSF RECEBIDA 1.500,00 C
                match = re.match(
                    r"^(\d{2}/\d{2}/\d{4})\s+(?:(\d{4,6})\s+)?(.+?)\s+([-\d.,]+\s*[CD]?)(?:\s+[-\d.,]+\s*[CD]?)?$",
                    line
                )
                if match:
                    d_str, lote, raw_memo, raw_val = match.groups()
                    if any(k in raw_memo.upper() for k in ["SALDO ANTERIOR", "SALDO ATUAL", "S A L D O"]):
                        continue

                    tx_date = parse_statement_date(d_str)
                    tx_amt = parse_brl_amount(raw_val)
                    if tx_date and tx_amt != Decimal("0.00"):
                        # Extrair documento se estiver no final do memo
                        doc_match = re.search(r"(\d{5,10})$", raw_memo.strip())
                        doc_num = doc_match.group(1) if doc_match else None
                        memo_clean = re.sub(r"\s+\d{5,10}$", "", raw_memo).strip()

                        transactions.append(Transaction(
                            date=tx_date,
                            amount=tx_amt,
                            memo=memo_clean or raw_memo,
                            checknum=doc_num or lote,
                        ))

        balance = self.extract_final_balance(full_text)
        return self.build_statement(bank_info, transactions, balance)
