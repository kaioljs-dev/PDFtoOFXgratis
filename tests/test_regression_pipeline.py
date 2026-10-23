"""
Pipeline Automatizado de Testes de Regressão em Etapas (Phased Gate Test Suite).
Garante que todos os erros anteriores permaneçam corrigidos antes de permitir
o avanço para as etapas subsequentes.
"""
from datetime import date
from decimal import Decimal
import os
import shutil
import sys
import unittest

# Adicionar raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.models import BankInfo, BankStatement, Transaction, TransactionType
from src.generators.ofx import OFXGenerator
from src.parsers.base import BaseBankParser
from src.parsers.bb import BancoDoBrasilParser
from src.parsers.bradesco import BradescoParser
from src.parsers.caixa import CaixaParser
from src.parsers.factory import GenericBankParser, ParserFactory
from src.parsers.itau import ItauParser
from src.parsers.nubank import NubankParser
from src.parsers.santander import SantanderParser
from src.utils.currency import format_brl, format_ofx_amount, parse_brl_amount
from src.utils.dates import format_ofx_date, parse_statement_date
from src.utils.hashing import generate_fitid
from src.utils.text import remove_accents, sanitize_memo


class Stage1CoreAndCurrencyTests(unittest.TestCase):
    """
    ETAPA 1: Utilitários Financeiros, Decimal, Datas, FITID e Sanitização de Acentos
    """

    def test_accent_and_text_sanitization(self):
        """Garante que acentos e cedilhas sejam convertidos em ASCII para compatibilidade com ERPs."""
        cases = [
            ("Transferência", "Transferencia"),
            ("Débito", "Debito"),
            ("Simões", "Simoes"),
            ("Atenção e Configuração", "Atencao e Configuracao"),
            ("Cartão Elo Débito", "Cartao Elo Debito"),
        ]
        for raw, expected in cases:
            self.assertEqual(remove_accents(raw), expected)
            self.assertEqual(sanitize_memo(raw), expected)

    def test_decimal_currency_parsing(self):
        """Garante que formatos monetários brasileiros convertam com precisão para Decimal."""
        cases = [
            ("1.250,50", Decimal("1250.50")),
            ("-1.250,50", Decimal("-1250.50")),
            ("1.250,50 D", Decimal("-1250.50")),
            ("1.250,50 C", Decimal("1250.50")),
            ("1.250,50-", Decimal("-1250.50")),
            ("(1.250,50)", Decimal("-1250.50")),
            ("R$ 40,79", Decimal("40.79")),
            ("R$ -7.411,91", Decimal("-7411.91")),
            ("+7.448,40", Decimal("7448.40")),
            ("0,00", Decimal("0.00")),
            ("", Decimal("0.00")),
        ]
        for raw, expected in cases:
            res = parse_brl_amount(raw)
            self.assertEqual(res, expected, f"Falha ao converter '{raw}': esperado {expected}, obtido {res}")

    def test_fitid_determinism_and_uniqueness(self):
        """Garante que o FITID seja idempotente (reprodutível) e único para transações distintas."""
        tx_date = date(2026, 9, 1)
        amt = Decimal("1949.00")
        memo = "Transferência recebida pelo Pix TARGET CONTABILIDADE"

        fitid_1 = generate_fitid("260", "71578973-8", tx_date, amt, memo, sequence=0)
        fitid_2 = generate_fitid("260", "71578973-8", tx_date, amt, memo, sequence=0)
        # Mesmos dados = mesmo FITID (evita duplicações em reimportações)
        self.assertEqual(fitid_1, fitid_2, "FITID deve ser determinístico!")

        # Mudança de valor ou sequência gera FITID diferente
        fitid_diff_amt = generate_fitid("260", "71578973-8", tx_date, Decimal("1950.00"), memo, sequence=0)
        fitid_diff_seq = generate_fitid("260", "71578973-8", tx_date, amt, memo, sequence=1)
        self.assertNotEqual(fitid_1, fitid_diff_amt)
        self.assertNotEqual(fitid_1, fitid_diff_seq)
        self.assertTrue(fitid_1.startswith("260-20260901-"))

    def test_date_parsing_variations(self):
        """Garante suporte a formatos de data de extratos brasileiros."""
        self.assertEqual(parse_statement_date("01/09/2026"), date(2026, 9, 1))
        self.assertEqual(parse_statement_date("21/10/26"), date(2026, 10, 21))
        self.assertEqual(parse_statement_date("2026-10-21"), date(2026, 10, 21))
        self.assertEqual(parse_statement_date("15/10", default_year=2026), date(2026, 10, 15))


class Stage2BankDetectionAntiFalsePositiveTests(unittest.TestCase):
    """
    ETAPA 2: Resolução de Conflitos e Falsos Positivos na Detecção de Bancos
    (Impede o erro onde menções de outros bancos no Pix ativavam o parser errado).
    """

    def test_nubank_with_santander_pix_does_not_trigger_santander(self):
        """
        Extrato do Nubank contendo Pix para Santander DEVE ser detectado como Nubank,
        NUNCA como Santander.
        """
        text_page_1 = """Kaio Luiz Jacintho da Silva
CPF •••.462.487-•• Agência 0001 Conta
71578973-8
01 DE SETEMBRO DE 2026 a 30 DE SETEMBRO DE 2026 VALORES EM R$
Saldo inicial 4,30
Saldo final do período R$ 40,79
01 SET 2026 Total de saídas - 207,46
Transferência enviada pelo Pix UNIVERSIDADE ESTACIO DE SA - 34.075.739/0001- 84 - BCO SANTANDER (BRASIL) S.A. (0033)
"""
        santander_parser = SantanderParser()
        nubank_parser = NubankParser()

        self.assertFalse(
            santander_parser.can_parse(text_page_1),
            "ERRO DE REGRESSÃO: SantanderParser aceitou um extrato do Nubank por conter menção ao Santander no Pix!"
        )
        self.assertTrue(
            nubank_parser.can_parse(text_page_1),
            "NubankParser deveria ter reconhecido o extrato do Nubank."
        )

    def test_banco_do_brasil_with_bradesco_transfer(self):
        """Extrato do BB com TED para Bradesco DEVE ativar BBParser e não BradescoParser."""
        text_page_1 = """BANCO DO BRASIL - Autoatendimento BB
Agência: 1234-5  Conta corrente: 98765-4
Extrato de Conta Corrente
05/10/2026 13105 TED TRANSF BRADESCO S.A. 1.500,00 D
"""
        bb_parser = BancoDoBrasilParser()
        bradesco_parser = BradescoParser()

        self.assertTrue(bb_parser.can_parse(text_page_1))
        self.assertFalse(bradesco_parser.can_parse(text_page_1))

    def test_caixa_with_itau_payment(self):
        """Extrato da Caixa com pagamento para o Itaú DEVE ativar CaixaParser."""
        text_page_1 = """CAIXA ECONÔMICA FEDERAL
Extrato por período - Internet Banking Caixa
Agência: 0234 Conta: 00012345-6
10/10/2026 123456 PAGAMENTO BOLETO BANCO ITAU 350,00 D
"""
        caixa_parser = CaixaParser()
        itau_parser = ItauParser()

        self.assertTrue(caixa_parser.can_parse(text_page_1))
        self.assertFalse(itau_parser.can_parse(text_page_1))


class Stage3BalanceRegexTests(unittest.TestCase):
    """
    ETAPA 3: Regex de Extração de Saldo (Prevenção de Captura de Números de Data)
    (Impede o erro onde 'Saldo em 21/10/2026' capturava '21' em vez do saldo real).
    """

    class DummyParser(BaseBankParser):
        def can_parse(self, text: str) -> bool:
            return True
        def parse(self, pdf_path: str) -> BankStatement:
            pass

    def setUp(self):
        self.parser = self.DummyParser()

    def test_balance_date_pattern_does_not_capture_day_number(self):
        """Garante que 'Saldo em 21/10/2026: R$ 4.494,30' extraia 4494.30 e não 21.00."""
        text = "Extrato Itaú\nSaldo em 21/10/2026: R$ 4.494,30"
        bal = self.parser.extract_final_balance(text)
        self.assertEqual(
            bal, Decimal("4494.30"),
            f"ERRO DE REGRESSÃO: Capturou {bal} em vez do saldo real 4494.30!"
        )

    def test_balance_final_disponivel_pattern(self):
        text = "Saldo final disponível: R$ 14.323,40 C"
        bal = self.parser.extract_final_balance(text)
        self.assertEqual(bal, Decimal("14323.40"))

    def test_balance_final_do_periodo_pattern(self):
        text = "Saldo final do período\nR$ 40,79"
        nubank_parser = NubankParser()
        bal = nubank_parser.extract_final_balance(text)
        self.assertEqual(bal, Decimal("40.79"))


class Stage4OFXGeneratorStandardsTests(unittest.TestCase):
    """
    ETAPA 4: Validação do Gerador OFX SGML 1.0.2
    Garante conformidade estrita com o padrão bancário aceito por ERPs.
    """

    def test_ofx_header_and_transaction_structure(self):
        bank_info = BankInfo(
            bank_id="260",
            bank_name="Nu Pagamentos S.A.",
            branch_id="0001",
            account_id="71578973-8",
            account_type="CHECKING",
        )
        tx1 = Transaction(
            date=date(2026, 9, 1),
            amount=Decimal("1949.00"),
            memo="Transferência Pix Recebida & Confirmada",
            fitid="260-20260901-ABC123",
            trntype=TransactionType.XFER,
        )
        tx2 = Transaction(
            date=date(2026, 9, 2),
            amount=Decimal("-85.31"),
            memo="Compra no débito Loja <XYZ>",
            fitid="260-20260902-DEF456",
            trntype=TransactionType.POS,
        )
        statement = BankStatement(
            bank_info=bank_info,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            transactions=[tx1, tx2],
            balance=Decimal("1863.69"),
        )

        gen = OFXGenerator()
        ofx_text = gen.generate(statement)

        # 1. Cabeçalho SGML padrão OFX 1.0.2
        self.assertIn("OFXHEADER:100", ofx_text)
        self.assertIn("DATA:OFXSGML", ofx_text)
        self.assertIn("VERSION:102", ofx_text)
        self.assertIn("CHARSET:1252", ofx_text)

        # 2. Dados bancários
        self.assertIn("<BANKID>260", ofx_text)
        self.assertIn("<BRANCHID>0001", ofx_text)
        self.assertIn("<ACCTID>71578973-8", ofx_text)
        self.assertIn("<ACCTTYPE>CHECKING", ofx_text)

        # 3. Transações e Escapamento SGML com remoção de acentos para compatibilidade com ERPs
        self.assertIn("<TRNAMT>1949.00", ofx_text)
        self.assertIn("<TRNAMT>-85.31", ofx_text)
        self.assertIn("<FITID>260-20260901-ABC123", ofx_text)
        # '&' e '<' devem ser escapados e acentos convertidos para ASCII (Transferência -> Transferencia, Débito -> Debito)
        self.assertIn("Transferencia Pix Recebida &amp; Confirmada", ofx_text)
        self.assertIn("Compra no debito Loja &lt;XYZ&gt;", ofx_text)

        # 4. Saldo
        self.assertIn("<BALAMT>1863.69", ofx_text)


class Stage5CLIAndDirectoryHandlingTests(unittest.TestCase):
    """
    ETAPA 5: I/O de Diretórios no CLI e Conversão Ponta a Ponta
    (Impede o erro [Errno 22] em pastas que não existiam previamente).
    """

    def test_output_directory_auto_creation_without_errno22(self):
        """Garante que salvar em diretório inexistente crie o diretório automaticamente."""
        test_dir = os.path.join(os.path.dirname(__file__), "tmp_output_test", "subdir")
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        test_file = os.path.join(test_dir, "test_output.ofx")
        statement = BankStatement(
            bank_info=BankInfo(bank_id="001", bank_name="BB"),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 2),
            transactions=[],
            balance=Decimal("0.00"),
        )
        gen = OFXGenerator()
        # Não deve levantar OSError / Errno 22
        saved_path = gen.save(statement, test_file)
        self.assertTrue(os.path.isfile(saved_path))
        self.assertTrue(os.path.exists(test_dir))

        # Limpeza
        shutil.rmtree(os.path.dirname(test_dir))

    def test_real_nubank_file_end_to_end_if_present(self):
        """Se o arquivo real do Nubank estiver presente em tests/fixtures, valida reconciliação contábil."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "NU_715789738_01SET2026_30SET2026.pdf")
        if not os.path.isfile(fixture_path):
            self.skipTest("Arquivo de fixture real não encontrado no ambiente local.")

        parser = ParserFactory.get_parser(fixture_path)
        self.assertEqual(parser.bank_id, "260")
        statement = parser.parse(fixture_path)

        # Validação contábil estrita
        self.assertEqual(len(statement.transactions), 53)
        self.assertEqual(statement.total_credits, Decimal("7448.40"))
        self.assertEqual(statement.total_debits, Decimal("-7411.91"))
        self.assertEqual(statement.balance, Decimal("40.79"))
        self.assertEqual(statement.bank_info.account_id, "71578973-8")
