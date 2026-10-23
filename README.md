# pdf2ofx - Conversor de Extratos Bancários em PDF para OFX

Conversor de extratos bancários em PDF para arquivos OFX 1.0.2 padrão SGML, desenvolvido em Python com precisão contábil (`Decimal`), extração via `pdfplumber`, geração de FITID determinístico (hash SHA-256) e pipeline de testes em etapas à prova de regressão.

---

## 🏦 Bancos Suportados

| Banco | Código Febraban | Módulo Parser |
|---|---|---|
| **Banco do Brasil** | `001` | `src.parsers.bb.BancoDoBrasilParser` |
| **Caixa Econômica Federal** | `104` | `src.parsers.caixa.CaixaParser` |
| **Banco Bradesco** | `237` | `src.parsers.bradesco.BradescoParser` |
| **Banco Santander** | `033` | `src.parsers.santander.SantanderParser` |
| **Banco Itaú** | `341` | `src.parsers.itau.ItauParser` |
| **Nubank (Nu Pagamentos S.A.)** | `260` | `src.parsers.nubank.NubankParser` |
| **Outros Bancos Brasileiros** | - | `src.parsers.factory.GenericBankParser` (Fallback Heurístico) |

---

## 📂 Estrutura do Projeto

```text
pdf2ofx/
├── main.py                     # Script CLI executável principal
├── run_tests.py                # Pipeline de testes automatizados com bloqueio em etapas
├── generate_samples.py         # Gerador de extratos PDF de exemplo com ReportLab
├── requirements.txt            # Dependências (pdfplumber, reportlab)
├── .gitignore                  # Proteção de dados bancários confidenciais
├── src/
│   ├── core/
│   │   └── models.py           # Modelos de dados (BankInfo, Transaction, BankStatement)
│   ├── utils/
│   │   ├── currency.py         # Tratamento de moeda brasileira e precisão Decimal
│   │   ├── dates.py            # Tratamento e conversão de formatos de datas
│   │   └── hashing.py          # FITID determinístico e idempotente via SHA-256
│   ├── generators/
│   │   └── ofx.py              # Gerador OFX SGML/XML padrão 1.0.2
│   └── parsers/
│       ├── base.py             # Classe base e isolamento anti-falso positivo de cabeçalho
│       ├── bb.py               # Parser Banco do Brasil
│       ├── caixa.py            # Parser Caixa Econômica Federal
│       ├── bradesco.py         # Parser Bradesco
│       ├── santander.py        # Parser Santander
│       ├── itau.py             # Parser Itaú
│       ├── nubank.py           # Parser Nubank
│       └── factory.py          # Auto-detecção de banco e fallback genérico
└── tests/
    ├── fixtures/               # Extratos reais de teste (.gitignored)
    └── test_regression_pipeline.py # Casos de teste de regressão em 5 portões
```

---

## 🚀 Como Executar

### 1. Instalação das Dependências
```bash
python -m pip install -r requirements.txt
```

### 2. Gerar Extratos de Exemplo para Teste Rápido
```bash
python generate_samples.py
```

### 3. Converter Extrato Individual
```bash
python main.py samples/extrato_bb.pdf
# Ou especificando o nome do arquivo de saída:
python main.py samples/extrato_bb.pdf -o extrato_bb.ofx --verbose
```

### 4. Converter em Lote (Diretório)
```bash
python main.py samples/ -o samples/ofx_output/ --verbose
```

---

## 🛡️ Pipeline de Testes Automatizados em Portões (Phased Gate Runner)

Para executar a validação estrita onde uma etapa **só avança se a anterior for aprovada**:

```bash
python run_tests.py
```

### Portões de Validação:
1. **Etapa 1/5 - Utilitários Financeiros**: Precisão contábil `Decimal`, tratamento de prefixos/sufixos (`R$ -120,00`, `120,00 D`, `(120,00)`), datas e FITIDs determinísticos.
2. **Etapa 2/5 - Detecção Anti-Falso Positivo**: Impede que menções de outros bancos em Pix/TED ativem o parser incorreto.
3. **Etapa 3/5 - Regex de Saldo**: Impede que expressões como `Saldo em 21/10/2026: R$ 4.494,30` capturem o dia como saldo.
4. **Etapa 4/5 - Padrão OFX SGML 1.0.2**: Validação de cabeçalhos, nós folha, escape de caracteres especiais e tags `<STMTTRN>` / `<LEDGERBAL>`.
5. **Etapa 5/5 - Diretórios CLI e Reconciliação Contábil Real**: Impede erros de criação de pasta (`[Errno 22]`) e valida a reconciliação dos extratos.
