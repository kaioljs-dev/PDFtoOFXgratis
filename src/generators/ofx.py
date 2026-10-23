"""
OFX (Open Financial Exchange) Generator - Version 1.0.2 (SGML Standard).
Sanitizes accents to ASCII and outputs Latin-1 encoded files for full ERP compatibility.
"""
from datetime import datetime
import os
from typing import Optional

from ..core.models import BankStatement, Transaction
from ..utils.currency import format_ofx_amount
from ..utils.dates import format_ofx_date
from ..utils.text import remove_accents, sanitize_memo


class OFXGenerator:
    """Generates standard OFX 1.0.2 SGML documents from BankStatement models."""

    def __init__(self, timezone_offset: str = "[-03:EST]"):
        self.timezone_offset = timezone_offset

    def _escape_sgml(self, text: Optional[str], is_memo: bool = False) -> str:
        """Sanitizes accents to ASCII and escapes special SGML characters."""
        if not text:
            return ""
        
        # 1. Remover acentuação (Transferência -> Transferencia, Débito -> Debito, Simões -> Simoes)
        clean = sanitize_memo(text) if is_memo else remove_accents(str(text).strip())
        
        # 2. Escapar caracteres proibidos em SGML/XML
        clean = (
            clean.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
        )
        return clean

    def generate(self, statement: BankStatement) -> str:
        """Builds full OFX 1.0.2 SGML content as string."""
        now = datetime.now()
        dt_server = format_ofx_date(now, self.timezone_offset)
        dt_start = format_ofx_date(statement.start_date, self.timezone_offset)
        dt_end = format_ofx_date(statement.end_date, self.timezone_offset)
        dt_asof = format_ofx_date(statement.balance_date or statement.end_date, self.timezone_offset)

        lines = [
            "OFXHEADER:100",
            "DATA:OFXSGML",
            "VERSION:102",
            "SECURITY:NONE",
            "ENCODING:USASCII",
            "CHARSET:1252",
            "COMPRESSION:NONE",
            "OLDFILEKEY:NONE",
            "NEWFILEKEY:NONE",
            "",
            "<OFX>",
            "  <SIGNONMSGSRSV1>",
            "    <SONRS>",
            "      <STATUS>",
            "        <CODE>0",
            "        <SEVERITY>INFO",
            "      </STATUS>",
            f"      <DTSERVER>{dt_server}",
            "      <LANGUAGE>POR",
            "      <FI>",
            f"        <ORG>{self._escape_sgml(statement.bank_info.bank_name)}",
            f"        <FID>{statement.bank_info.bank_id}",
            "      </FI>",
            "    </SONRS>",
            "  </SIGNONMSGSRSV1>",
            "  <BANKMSGSRSV1>",
            "    <STMTTRNRS>",
            "      <TRNUID>1001",
            "      <STATUS>",
            "        <CODE>0",
            "        <SEVERITY>INFO",
            "      </STATUS>",
            "      <STMTRS>",
            "        <CURDEF>BRL",
            "        <BANKACCTFROM>",
            f"          <BANKID>{statement.bank_info.bank_id}",
            f"          <BRANCHID>{self._escape_sgml(statement.bank_info.branch_id)}",
            f"          <ACCTID>{self._escape_sgml(statement.bank_info.account_id)}",
            f"          <ACCTTYPE>{statement.bank_info.account_type}",
            "        </BANKACCTFROM>",
            "        <BANKTRANLIST>",
            f"          <DTSTART>{dt_start}",
            f"          <DTEND>{dt_end}",
        ]

        # Inserir cada transação sanitizada
        for tx in statement.transactions:
            lines.append("          <STMTTRN>")
            lines.append(f"            <TRNTYPE>{tx.trntype.value}")
            lines.append(f"            <DTPOSTED>{format_ofx_date(tx.date, self.timezone_offset)}")
            lines.append(f"            <TRNAMT>{format_ofx_amount(tx.amount)}")
            lines.append(f"            <FITID>{tx.fitid}")
            if tx.checknum:
                lines.append(f"            <CHECKNUM>{self._escape_sgml(tx.checknum)}")
            if tx.refnum:
                lines.append(f"            <REFNUM>{self._escape_sgml(tx.refnum)}")
            lines.append(f"            <MEMO>{self._escape_sgml(tx.memo, is_memo=True)}")
            lines.append("          </STMTTRN>")

        # Fechar lista e inserir saldo
        lines.extend([
            "        </BANKTRANLIST>",
            "        <LEDGERBAL>",
            f"          <BALAMT>{format_ofx_amount(statement.balance)}",
            f"          <DTASOF>{dt_asof}",
            "        </LEDGERBAL>",
            "      </STMTRS>",
            "    </STMTTRNRS>",
            "  </BANKMSGSRSV1>",
            "</OFX>",
            "",
        ])

        return "\r\n".join(lines)

    def save(self, statement: BankStatement, output_path: str) -> str:
        """
        Writes OFX content to specified file path with Latin-1 (ISO-8859-1) encoding,
        ensuring 100% compatibility with accounting ERPs (Domínio, Omie, ContaAzul).
        """
        content = self.generate(statement)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="latin-1", errors="replace") as f:
            f.write(content)
        return output_path
