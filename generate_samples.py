"""
Gera PDFs de extratos bancários simulados para Banco do Brasil, Caixa, Bradesco, Santander e Itaú.
Permite testar a conversão imediatamente sem expor dados financeiros reais.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_bb_sample(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "BANCO DO BRASIL - Extrato de Conta Corrente")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Agência: 1234-5   Conta corrente: 98765-4   Cliente: EMPRESA TESTE LTDA")
    c.drawString(50, 715, "Período: 01/10/2026 a 21/10/2026")
    c.line(50, 705, 550, 705)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 690, "Dt. mov.")
    c.drawString(110, 690, "Lote")
    c.drawString(150, 690, "Histórico")
    c.drawString(330, 690, "Documento")
    c.drawString(410, 690, "Valor (R$)")
    c.drawString(490, 690, "Saldo (R$)")
    c.line(50, 680, 550, 680)

    rows = [
        ("01/10/2026", "00000", "SALDO ANTERIOR", "", "", "10.000,00 C"),
        ("05/10/2026", "13105", "PIX TRANSF RECEBIDA", "123456", "2.500,00 C", "12.500,00 C"),
        ("08/10/2026", "13113", "PAGAMENTO BOLETO FORNECEDOR", "987654", "1.250,50 D", "11.249,50 C"),
        ("12/10/2026", "00123", "TARIFA PACOTE SERVICOS", "000123", "45,90 D", "11.203,60 C"),
        ("15/10/2026", "13105", "RECEBIMENTO CLIENTE XYZ", "445566", "3.800,00 C", "15.003,60 C"),
        ("19/10/2026", "13113", "PAGAMENTO ENERGIA ELETRICA", "332211", "680,20 D", "14.323,40 C"),
    ]

    y = 660
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r[0])
        c.drawString(110, y, r[1])
        c.drawString(150, y, r[2])
        c.drawString(330, y, r[3])
        c.drawString(410, y, r[4])
        c.drawString(490, y, r[5])
        y -= 20

    c.line(50, y + 10, 550, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - 10, "Saldo final disponível: R$ 14.323,40 C")
    c.save()


def create_caixa_sample(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "CAIXA ECONÔMICA FEDERAL")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 730, "Extrato por período - Internet Banking Caixa")
    c.setFont("Helvetica", 10)
    c.drawString(50, 715, "Agência: 0234   Operação: 001   Conta: 00012345-6")
    c.line(50, 705, 550, 705)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 690, "Data Mov.")
    c.drawString(120, 690, "Nr. Doc.")
    c.drawString(190, 690, "Histórico")
    c.drawString(410, 690, "Valor (R$)")
    c.drawString(490, 690, "Saldo (R$)")
    c.line(50, 680, 550, 680)

    rows = [
        ("02/10/2026", "000001", "CRED TEV", "1.500,00 C", "7.500,00 C"),
        ("06/10/2026", "123456", "PAG BOLETO", "350,00 D", "7.150,00 C"),
        ("10/10/2026", "789101", "DEB PREST HAB", "1.120,00 D", "6.030,00 C"),
        ("16/10/2026", "000104", "TAR MANUT CTA", "39,00 D", "5.991,00 C"),
        ("20/10/2026", "554433", "CRED PIX", "4.200,00 C", "10.191,00 C"),
    ]

    y = 660
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r[0])
        c.drawString(120, y, r[1])
        c.drawString(190, y, r[2])
        c.drawString(410, y, r[3])
        c.drawString(490, y, r[4])
        y -= 20

    c.line(50, y + 10, 550, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - 10, "Saldo Atual: R$ 10.191,00 C")
    c.save()


def create_bradesco_sample(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Banco Bradesco S.A. - 237")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Extrato de: Agência: 1234 | Conta Corrente: 1234567-8")
    c.drawString(50, 715, "Período: 01/10/2026 a 21/10/2026")
    c.line(50, 705, 550, 705)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 690, "Data")
    c.drawString(120, 690, "Histórico")
    c.drawString(330, 690, "Docto.")
    c.drawString(410, 690, "Valor (R$)")
    c.drawString(490, 690, "Saldo (R$)")
    c.line(50, 680, 550, 680)

    rows = [
        ("03/10/2026", "TED RECEBIDA", "12345", "5.000,00", "15.000,00"),
        ("07/10/2026", "PAGTO ELETRON COBRANCA", "67890", "-850,00", "14.150,00"),
        ("11/10/2026", "COMPRA CARTAO VISA DEB", "99887", "-120,50", "14.029,50"),
        ("17/10/2026", "PIX RECEBIDO FORNECEDOR", "11223", "2.100,00", "16.129,50"),
    ]

    y = 660
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r[0])
        c.drawString(120, y, r[1])
        c.drawString(330, y, r[2])
        c.drawString(410, y, r[3])
        c.drawString(490, y, r[4])
        y -= 20

    c.line(50, y + 10, 550, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - 10, "Saldo final: R$ 16.129,50")
    c.save()


def create_santander_sample(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Banco Santander (Brasil) S.A. - 033")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Extrato Conta Corrente   Agência: 4321   Conta: 01098765-4")
    c.line(50, 705, 550, 705)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 690, "Data")
    c.drawString(120, 690, "Descrição")
    c.drawString(330, 690, "Docto")
    c.drawString(410, 690, "Valor (R$)")
    c.drawString(490, 690, "Saldo (R$)")
    c.line(50, 680, 550, 680)

    rows = [
        ("04/10/2026", "PIX RECEBIDO OUTRA IF", "456789", "3.000,00", "8.000,00"),
        ("09/10/2026", "PAGAMENTO TITULO OUTRO BCO", "112233", "-450,00", "7.550,00"),
        ("14/10/2026", "TARIFA CONTA SMART", "334455", "-69,90", "7.480,10"),
        ("18/10/2026", "DOC TED RECEBIDA", "778899", "1.750,00", "9.230,10"),
    ]

    y = 660
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r[0])
        c.drawString(120, y, r[1])
        c.drawString(330, y, r[2])
        c.drawString(410, y, r[3])
        c.drawString(490, y, r[4])
        y -= 20

    c.line(50, y + 10, 550, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - 10, "Saldo disponível: R$ 9.230,10")
    c.save()


def create_itau_sample(output_path: str):
    c = canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "Itaú Unibanco S.A. - 341")
    c.setFont("Helvetica", 10)
    c.drawString(50, 730, "Extrato de Conta Corrente   agência: 0123   conta: 45678-9")
    c.drawString(50, 715, "Período: 01/10/2026 a 21/10/2026")
    c.line(50, 705, 550, 705)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 690, "Data")
    c.drawString(120, 690, "Lançamentos")
    c.drawString(330, 690, "Documento")
    c.drawString(410, 690, "Valor (R$)")
    c.drawString(490, 690, "Saldo (R$)")
    c.line(50, 680, 550, 680)

    rows = [
        ("03/10/2026", "PIX TRANSF RECEB CLIENTE", "332211", "1.800,00", "5.800,00"),
        ("08/10/2026", "COMPRA CARTAO MASTER DEBITO", "998877", "-240,00", "5.560,00"),
        ("13/10/2026", "PAGAMENTO TRIBUTOS SIMPLES", "445566", "-1.100,50", "4.459,50"),
        ("19/10/2026", "RENDIMENTO APLIC AUT", "771122", "34,80", "4.494,30"),
    ]

    y = 660
    c.setFont("Helvetica", 9)
    for r in rows:
        c.drawString(50, y, r[0])
        c.drawString(120, y, r[1])
        c.drawString(330, y, r[2])
        c.drawString(410, y, r[3])
        c.drawString(490, y, r[4])
        y -= 20

    c.line(50, y + 10, 550, y + 10)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y - 10, "Saldo em 21/10/2026: R$ 4.494,30")
    c.save()


def main():
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    os.makedirs(samples_dir, exist_ok=True)

    banks = [
        ("extrato_bb.pdf", create_bb_sample, "Banco do Brasil (001)"),
        ("extrato_caixa.pdf", create_caixa_sample, "Caixa Econômica Federal (104)"),
        ("extrato_bradesco.pdf", create_bradesco_sample, "Banco Bradesco (237)"),
        ("extrato_santander.pdf", create_santander_sample, "Banco Santander (033)"),
        ("extrato_itau.pdf", create_itau_sample, "Banco Itaú (341)"),
    ]

    print(f"📦 Gerando extratos de exemplo em: {samples_dir}\n")
    for filename, func, label in banks:
        filepath = os.path.join(samples_dir, filename)
        func(filepath)
        print(f"   ✓ {label:<35} -> {filename}")

    print("\n✨ Extratos de teste gerados com sucesso! Agora você pode converter rodando:")
    print("   python main.py samples/extrato_bb.pdf")
    print("   python main.py samples/ --verbose")


if __name__ == "__main__":
    main()
