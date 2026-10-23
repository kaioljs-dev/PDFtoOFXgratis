#!/usr/bin/env python3
"""
Pipeline Automatizado de Testes em Portões (Phased Gate Test Runner).

Executa as etapas em sequência estrita:
  Etapa 1 -> Etapa 2 -> Etapa 3 -> Etapa 4 -> Etapa 5

REGRA DE BLOQUEIO (GATE): Se qualquer etapa falhar, a execução é interrompida
imediatamente e NÃO avança para a próxima etapa até que o erro seja corrigido.
"""
import io
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_regression_pipeline import (
    Stage1CoreAndCurrencyTests,
    Stage2BankDetectionAntiFalsePositiveTests,
    Stage3BalanceRegexTests,
    Stage4OFXGeneratorStandardsTests,
    Stage5CLIAndDirectoryHandlingTests,
)

STAGES = [
    {
        "number": 1,
        "title": "Utilitários Financeiros (Decimal, Datas e FITID Idempotente)",
        "description": "Garante precisão contábil Decimal, hashes determinísticos e formatos de datas.",
        "test_class": Stage1CoreAndCurrencyTests,
    },
    {
        "number": 2,
        "title": "Detecção de Bancos e Proteção Anti-Falso Positivo",
        "description": "Impede que menções de outros bancos no Pix ativem o parser incorreto.",
        "test_class": Stage2BankDetectionAntiFalsePositiveTests,
    },
    {
        "number": 3,
        "title": "Extração de Saldo e Prevenção de Captura de Datas",
        "description": "Impede que 'Saldo em 21/10/2026' capture erroneamente o dia 21 como saldo.",
        "test_class": Stage3BalanceRegexTests,
    },
    {
        "number": 4,
        "title": "Validação de Estrutura OFX SGML 1.0.2",
        "description": "Garante cabeçalhos SGML válidos, nós folha corretos e escape de caracteres (&, <, >).",
        "test_class": Stage4OFXGeneratorStandardsTests,
    },
    {
        "number": 5,
        "title": "I/O de Diretórios CLI e Reconciliação Contábil Ponta a Ponta",
        "description": "Impede [Errno 22] em pastas novas e valida os totais exatos do extrato real.",
        "test_class": Stage5CLIAndDirectoryHandlingTests,
    },
]


def print_header():
    print("""
╔═════════════════════════════════════════════════════════════════════════╗
║          PIPELINE DE TESTES EM PORTÕES (PHASED GATE RUNNER)             ║
║  Cada etapa anterior DEVE passar antes de permitir o avanço à seguinte  ║
╚═════════════════════════════════════════════════════════════════════════╝
""")


def run_stage(stage_info: dict) -> bool:
    num = stage_info["number"]
    title = stage_info["title"]
    desc = stage_info["description"]
    test_class = stage_info["test_class"]

    print(f"\n▶ ETAPA {num}/5: {title}")
    print(f"  ℹ️  {desc}")
    print("  " + "─" * 65)

    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    if result.wasSuccessful():
        print(f"  ✅ [APROVADO] {result.testsRun} teste(s) passaram em {elapsed:.3f}s.")
        return True
    else:
        print(f"  ❌ [BLOQUEADO NA ETAPA {num}] Falha detectada!")
        print("\n  Detalhes do erro que interrompeu o pipeline:")
        for failure in result.failures + result.errors:
            test_name = failure[0]
            err_trace = failure[1]
            print(f"\n  • Teste: {test_name}")
            for line in err_trace.strip().splitlines()[-6:]:
                print(f"    {line}")

        print(f"\n⛔ PIPELINE INTERROMPIDO: O código NÃO avançará para a Etapa {num + 1} até que a Etapa {num} seja corrigida.")
        return False


def main():
    print_header()
    all_passed = True

    for stage in STAGES:
        passed = run_stage(stage)
        if not passed:
            all_passed = False
            break

    print("\n" + "═" * 73)
    if all_passed:
        print("🎉 SUCESSO TOTAL: TODAS AS 5 ETAPAS PASSARAM COM 100% DE APROVAÇÃO!")
        print("   O código está blindado contra regressões e pronto para produção.")
        print("═" * 73 + "\n")
        sys.exit(0)
    else:
        print("⚠️  PIPELINE FALHOU: Corrija a etapa indicada acima e execute novamente.")
        print("═" * 73 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
