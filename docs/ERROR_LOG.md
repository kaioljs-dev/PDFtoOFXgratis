# Registro de Erros e Prevenção de Regressão (Error Log & Regression Prevention)

**Versão do Projeto:** v1.02  
**Data de Atualização:** 24 de Outubro de 2026  
**Status do Pipeline:** 100% Aprovado (5/5 Portões)

---

## 📌 Visão Geral

Este documento registra o histórico de erros críticos identificados durante o ciclo de desenvolvimento e testes do **PDFtoOFXgratis**, descrevendo a causa raiz, a arquitetura da solução implementada e as regras de não-regressão vinculadas à suíte de testes automatizados em portões sequenciais (*Phased Gate Runner*).

---

## 🔍 Histórico de Casos e Regras de Não-Regressão

### Caso 1: Falso Positivo Santander x Nubank (Detecção de Layout)

- **Identificação do Erro:**  
  Ao processar um extrato bancário emitido pelo **Nubank**, o sistema identificava o documento indevidamente como pertencente ao **Banco Santander** (`SantanderParser`), gerando falha na extração de transações ou montagem de arquivo OFX incompatível.
- **Causa Raiz:**  
  O extrato do Nubank continha transações via Pix enviadas a favorecidos correntistas do Santander, com descrições textuais no corpo do documento como:  
  `"Transferência enviada pelo Pix UNIVERSIDADE ESTACIO DE SA - ... - BCO SANTANDER (BRASIL) S.A. (0033)"`.  
  O método `can_parse()` do `SantanderParser` realizava a busca de palavras-chave (`"SANTANDER"`) indiscriminadamente em todo o corpo da primeira página, capturando termos contidos no histórico de lançamentos.
- **Solução Técnica Aplicada:**  
  1. Implementação do método `get_clean_header(text, max_lines=8)` na classe abstrata `BaseBankParser` (`src/parsers/base.py`). O método isola exclusivamente as primeiras linhas de cabeçalho da página, ignorando linhas com formato de data/lançamento contábil e palavras-chave de transações (`TRANSFERÊNCIA`, `PAGAMENTO`, `BOLETO`, `SAQUE`, `COMPRA NO DÉBITO`).
  2. Ajuste do método `can_parse()` em todos os parsers bancários para consultar apenas o cabeçalho higienizado retornado por `get_clean_header()`.
- **Prevenção de Regressão:**  
  - **Portão Associado:** **Etapa 2/5 (Stage 2)** - *Detecção de Bancos e Proteção Anti-Falso Positivo*.
  - **Testes Unitários:**  
    - `Stage2BankDetectionAntiFalsePositiveTests.test_nubank_with_santander_pix_does_not_trigger_santander`
    - `Stage2BankDetectionAntiFalsePositiveTests.test_banco_do_brasil_with_bradesco_transfer`
    - `Stage2BankDetectionAntiFalsePositiveTests.test_caixa_with_itau_payment`

---

### Caso 2: Encoding e Acentuação de Caracteres no OFX

- **Identificação do Erro:**  
  Ocorrência de perda de caracteres com acentuação ou caracteres corrompidos nas tags `<MEMO>` dos arquivos OFX gerados (exemplo: `"Transfer ncia"`, `"d bito"`, `"Sim es"`). Isso causava rejeição de arquivos ou descrições ilegíveis ao importar os lançamentos em ERPs contábeis e fiscais (ex.: Domínio Sistemas, Omie, ContaAzul).
- **Causa Raiz:**  
  O padrão bancário OFX 1.0.2 baseado em SGML especifica `ENCODING:USASCII` e `CHARSET:1252` (Windows-1252). Softwares de conciliação bancária frequentemente rejeitam sequências UTF-8 com caracteres acentuados ou removem bytes com diacríticos sem converter para o caractere base ASCII correspondente.
- **Solução Técnica Aplicada:**  
  1. Criação do módulo `src/utils/text.py` com as funções `remove_accents()` e `sanitize_memo()`.
  2. Uso de normalização Unicode `unicodedata.normalize("NFKD", ...)` para decompor caracteres acentuados e cedilhas em seus caracteres ASCII base correspondentes (ex.: `é` $\rightarrow$ `e`, `ç` $\rightarrow$ `c`, `ã` $\rightarrow$ `a`).
  3. Integração direta no método `_escape_sgml()` do `OFXGenerator` (`src/generators/ofx.py`), que simultaneamente converte diacríticos para ASCII e escapa entidades reservadas do SGML (`&` $\rightarrow$ `&amp;`, `<` $\rightarrow$ `&lt;`, `>` $\rightarrow$ `&gt;`).
  4. Gravação física do arquivo OFX com charset `latin-1` (`errors="replace"`), garantindo conformidade com a especificação OFX 1.0.2.
- **Prevenção de Regressão:**  
  - **Portão Associado:** **Etapa 1/5 (Stage 1)** e **Etapa 4/5 (Stage 4)**.
  - **Testes Unitários:**  
    - `Stage1CoreAndCurrencyTests.test_accent_and_text_sanitization`
    - `Stage4OFXGeneratorStandardsTests.test_ofx_header_and_transaction_structure`

---

## 📊 Matriz de Validação Atual dos Bancos (v1.02)

A tabela abaixo detalha o status de homologação com extratos reais e testes sintéticos dos parsers bancários disponíveis:

| Banco | Código Febraban | Parser | Cobertura Real Homologada | Status |
|---|:---:|---|---|:---:|
| **Nubank** (Nu Pagamentos S.A.) | `260` | `NubankParser` | Extrato real de **6 páginas** homologado com reconciliação matemática exata de 53 transações (Créditos: R$ 7.448,40; Débitos: R$ -7.411,91; Saldo: R$ 40,79). | ✅ Homologado |
| **Banco do Brasil** | `001` | `BancoDoBrasilParser` | Extrato real homologado com suporte a cabeçalhos contábeis, tratamento de colunas de data/lote/documento e indicadores contábeis `C`/`D`. | ✅ Homologado |
| **Banco Santander** | `033` | `SantanderParser` | Extrato real de **8 páginas** homologado com extração de movimentações, débitos consolidados e isolamento anti-falso positivo. | ✅ Homologado |
| **Caixa Econômica Federal** | `104` | `CaixaParser` | Validação estrutural de extratos por período do Internet Banking Caixa e blindagem contra menções de outros bancos. | ✅ Homologado |
| **Banco Bradesco** | `237` | `BradescoParser` | Validação estrutural com layout clássico Bradesco e tratamento de débitos e créditos. | ✅ Homologado |
| **Banco Itaú** | `341` | `ItauParser` | Validação estrutural, suporte a tabelas e extração correta de saldo sem captura indevida de dias de data. | ✅ Homologado |
| **Fallback Heurístico** | `-` | `GenericBankParser` | Mecanismo genérico para processamento de extratos com layouts desconhecidos baseado em tabelas e regex de moeda. | ✅ Ativo |

---

## 🛡️ Arquitetura dos Portões de Teste (Phased Gate Runner)

O arquivo `run_tests.py` implementa uma arquitetura sequencial onde uma etapa só é executada se a anterior obtiver **100% de sucesso**:

1. **Portão 1/5 - Utilitários Financeiros:** Precisão contábil `Decimal`, parsing de quantias monetárias BRL, tratamento de datas e unicidade/idempotência determinística do `FITID` via SHA-256.
2. **Portão 2/5 - Detecção Anti-Falso Positivo:** Validação estrita do isolamento de cabeçalho (`get_clean_header()`), impedindo que menções a outros bancos em transferências Pix/TED desviem a seleção do parser.
3. **Portão 3/5 - Regex de Saldo:** Impede que expressões como `"Saldo em 21/10/2026: R$ 4.494,30"` capturem erroneamente o número do dia (21) no lugar do saldo real.
4. **Portão 4/5 - Padrão OFX SGML 1.0.2:** Verificação da conformidade com o cabeçalho SGML, nós folha obrigatórios, escape de caracteres especiais e sanitização ASCII.
5. **Portão 5/5 - Diretórios CLI e Reconciliação Contábil Ponta a Ponta:** Impede erros de criação de pasta (`[Errno 22]`) e executa a reconciliação matemática completa de arquivos de extrato reais.
