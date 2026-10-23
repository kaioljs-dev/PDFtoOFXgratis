"""
Core data models for pdf2ofx converter.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class TransactionType(str, Enum):
    """OFX Standard transaction types."""
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    DEP = "DEP"      # Deposit
    XFER = "XFER"    # Transfer
    CHECK = "CHECK"  # Cheque
    FEE = "FEE"      # Tarifa/Taxa
    ATM = "ATM"      # Saque Caixa Eletrônico
    POS = "POS"      # Ponto de venda / Cartão de Débito
    PAYMENT = "PAYMENT"  # Pagamento
    OTHER = "OTHER"

    @classmethod
    def from_amount(cls, amount: Decimal) -> "TransactionType":
        return cls.CREDIT if amount > Decimal("0") else cls.DEBIT


@dataclass
class BankInfo:
    """Bank account metadata."""
    bank_id: str             # Código Febraban: 001 (BB), 104 (Caixa), 237 (Bradesco), 033 (Santander), 341 (Itaú)
    bank_name: str           # Nome amigável do banco
    branch_id: str = "0001"  # Agência
    account_id: str = "000000-0"  # Conta
    account_type: str = "CHECKING"  # CHECKING ou SAVINGS


@dataclass
class Transaction:
    """Represents a single bank statement entry."""
    date: date
    amount: Decimal
    memo: str
    trntype: TransactionType = TransactionType.OTHER
    fitid: str = ""
    checknum: Optional[str] = None
    refnum: Optional[str] = None

    def __post_init__(self):
        # Garantir tipo Decimal com 2 casas
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        
        # Atribuir tipo padrão se for OTHER
        if self.trntype == TransactionType.OTHER:
            self.trntype = TransactionType.from_amount(self.amount)
        
        # Limpar memo
        self.memo = " ".join(self.memo.split())


@dataclass
class BankStatement:
    """Full bank statement extracted from PDF."""
    bank_info: BankInfo
    start_date: date
    end_date: date
    transactions: List[Transaction] = field(default_factory=list)
    balance: Decimal = Decimal("0.00")
    balance_date: Optional[date] = None

    def __post_init__(self):
        if not isinstance(self.balance, Decimal):
            self.balance = Decimal(str(self.balance))
        if self.balance_date is None:
            self.balance_date = self.end_date

    @property
    def total_credits(self) -> Decimal:
        return sum(
            (t.amount for t in self.transactions if t.amount > Decimal("0")),
            Decimal("0.00")
        )

    @property
    def total_debits(self) -> Decimal:
        return sum(
            (t.amount for t in self.transactions if t.amount < Decimal("0")),
            Decimal("0.00")
        )

    @property
    def net_change(self) -> Decimal:
        return sum((t.amount for t in self.transactions), Decimal("0.00"))

    def add_transaction(self, transaction: Transaction) -> None:
        self.transactions.append(transaction)
        # Atualizar datas de início e fim se necessário
        if transaction.date < self.start_date:
            self.start_date = transaction.date
        if transaction.date > self.end_date:
            self.end_date = transaction.date
