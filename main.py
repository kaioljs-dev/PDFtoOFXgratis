#!/usr/bin/env python3
"""
pdf2ofx - Conversor de Extratos Bancários em PDF para OFX.
Suporte: Banco do Brasil, Caixa, Bradesco, Santander, Itaú e Nubank.
Salva por padrão na pasta 'output_ofx/'.
"""
import argparse
import glob
import os
import sys
from decimal import Decimal
from typing import Optional

# Garantir importação do módulo src
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output_ofx")
sys.path.insert(0, PROJECT_ROOT)

from src.generators.ofx import OFXGenerator
from src.parsers.factory import ParserFactory
from src.utils.currency import format_brl


def print_banner():
    banner = r"""
  ╔══════════════════════════════════════════════════════════════════╗
  ║                     pdf2ofx (Extrato -> OFX)                     ║
  ║  Suporte: Banco do Brasil, Caixa, Bradesco, Santander, Itaú, Nu  ║
  ╚══════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def convert_single_pdf(
    pdf_path: str,
    output_path: Optional[str] = None,
    bank: Optional[str] = None,
    only_info: bool = False,
    verbose: bool = False,
    is_batch: bool = False
) -> bool:
    if not os.path.isfile(pdf_path):
        print(f"❌ Erro: Arquivo PDF não encontrado: {pdf_path}")
        return False

    print(f"\n📄 Processando: {os.path.basename(pdf_path)}")
    try:
        parser = ParserFactory.get_parser(pdf_path, forced_bank=bank)
        if verbose:
            print(f"   🔍 Parser selecionado: {parser.bank_name} (ID: {parser.bank_id})")

        statement = parser.parse(pdf_path)

        # Determinar caminho de saída (padrão: output_ofx/<nome_base>.ofx)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        if not output_path:
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
            output_ofx = os.path.join(DEFAULT_OUTPUT_DIR, f"{base_name}.ofx")
        elif is_batch or os.path.isdir(output_path) or output_path.endswith(("/", "\\")):
            os.makedirs(output_path, exist_ok=True)
            output_ofx = os.path.join(output_path, f"{base_name}.ofx")
        else:
            output_ofx = output_path

        # Exibir resumo detalhado
        print(f"   🏦 Banco:      {statement.bank_info.bank_name} (Cód: {statement.bank_info.bank_id})")
        print(f"   🏢 Agência:    {statement.bank_info.branch_id} | Conta: {statement.bank_info.account_id}")
        print(f"   📅 Período:    {statement.start_date.strftime('%d/%m/%Y')} até {statement.end_date.strftime('%d/%m/%Y')}")
        print(f"   🔢 Lançamentos: {len(statement.transactions)}")
        print(f"   🟢 Total Créditos: {format_brl(statement.total_credits)}")
        print(f"   🔴 Total Débitos:  {format_brl(statement.total_debits)}")
        print(f"   ⚖️  Variação:       {format_brl(statement.net_change)}")
        print(f"   💰 Saldo Final:    {format_brl(statement.balance)}")

        if verbose and statement.transactions:
            print("\n   ── Primeiros lançamentos ──")
            for tx in statement.transactions[:5]:
                sign = "+" if tx.amount > Decimal("0") else ""
                print(f"   • {tx.date.strftime('%d/%m/%Y')} | {tx.memo:<30} | {sign}{format_brl(tx.amount):>12} | FITID: {tx.fitid}")
            if len(statement.transactions) > 5:
                print(f"   ... e mais {len(statement.transactions) - 5} transações.")

        if only_info:
            print("   ℹ️  Modo --info ativo. Nenhum arquivo OFX foi gerado.")
            return True

        if not statement.transactions:
            print("   ⚠️  Aviso: Nenhuma transação financeira foi encontrada no PDF.")

        # Gerar OFX
        generator = OFXGenerator()
        abs_output_ofx = os.path.abspath(output_ofx)
        generator.save(statement, abs_output_ofx)
        file_size_kb = os.path.getsize(abs_output_ofx) / 1024.0
        
        print(f"\n   ✅ Sucesso! Arquivo gerado em:")
        print(f"      {abs_output_ofx} ({file_size_kb:.1f} KB)")
        print(f"   🔗 Link direto: file:///{abs_output_ofx.replace(os.sep, '/')}")
        return True

    except Exception as e:
        print(f"   ❌ Erro ao converter '{pdf_path}': {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="pdf2ofx: Conversor de extratos bancários em PDF para OFX padrão SGML 1.0.2.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python main.py input_extratos/extrato.pdf
  python main.py input_extratos/extrato.pdf -o output_ofx/meu_extrato.ofx
  python main.py input_extratos/
  python main.py input_extratos/extrato.pdf -b nubank --verbose
  python main.py input_extratos/extrato.pdf --info
"""
    )
    parser.add_argument("input", help="Caminho do arquivo PDF ou pasta com múltiplos PDFs.")
    parser.add_argument("-o", "--output", help="Caminho do arquivo ou diretório de saída para o OFX (padrão: output_ofx/).")
    parser.add_argument("-b", "--bank", choices=["auto", "bb", "caixa", "bradesco", "santander", "itau", "nubank"], default="auto",
                        help="Forçar banco específico (padrão: auto-detecção).")
    parser.add_argument("--info", action="store_true", help="Apenas exibe os dados e saldo do extrato sem gerar OFX.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Exibe detalhes adicionais do processo.")

    args = parser.parse_args()
    print_banner()

    # Verificar se entrada é diretório (lote) ou arquivo único
    if os.path.isdir(args.input):
        raw_files = glob.glob(os.path.join(args.input, "*.pdf")) + glob.glob(os.path.join(args.input, "*.PDF"))
        unique_paths = {}
        for f in raw_files:
            unique_paths[os.path.normcase(os.path.abspath(f))] = f
        pdf_files = sorted(list(unique_paths.values()))

        if not pdf_files:
            print(f"⚠️  Nenhum arquivo PDF encontrado no diretório: {args.input}")
            sys.exit(1)

        print(f"📂 Modo lote: {len(pdf_files)} extrato(s) encontrado(s).")
        success_count = 0
        for pdf_path in pdf_files:
            ok = convert_single_pdf(
                pdf_path=pdf_path,
                output_path=args.output,
                bank=args.bank,
                only_info=args.info,
                verbose=args.verbose,
                is_batch=True
            )
            if ok:
                success_count += 1

        print(f"\n🎉 Concluído: {success_count}/{len(pdf_files)} extratos processados com sucesso.")
        sys.exit(0 if success_count > 0 else 1)
    else:
        ok = convert_single_pdf(
            pdf_path=args.input,
            output_path=args.output,
            bank=args.bank,
            only_info=args.info,
            verbose=args.verbose,
            is_batch=False
        )
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
