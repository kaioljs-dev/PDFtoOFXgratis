"""
Text sanitization and accent stripping utilities for OFX compliance.
"""
import re
import unicodedata


def remove_accents(text: str) -> str:
    """
    Converte caracteres acentuados para sua forma básica ASCII (US-ASCII / Latin-1).
    Exemplos:
      - 'Transferência' -> 'Transferencia'
      - 'Débito'        -> 'Debito'
      - 'Simões'        -> 'Simoes'
      - 'Atenção'       -> 'Atencao'
      - 'CRÉDITO'       -> 'CREDITO'
    """
    if not text:
        return ""
    # NFKD separa letras bases de seus modificadores diacríticos (acentos)
    nfkd = unicodedata.normalize("NFKD", str(text))
    # Remove marcas diacríticas (categoria 'Mn' do Unicode)
    clean_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Substituir caracteres residuais não-ASCII ou mantê-los seguros
    return clean_ascii.encode("ascii", "ignore").decode("ascii")


def sanitize_memo(text: str, max_length: int = 120) -> str:
    """
    Higieniza a descrição para o campo <MEMO> do OFX:
      1. Remove acentuação e cedilha
      2. Remove quebras de linha e tabs
      3. Remove espaços duplicados
      4. Limita tamanho máximo
    """
    if not text:
        return ""
    # Remover quebras de linha e tabs
    clean = re.sub(r"[\r\n\t]+", " ", str(text))
    # Remover acentuação
    clean = remove_accents(clean)
    # Remover múltiplos espaços
    clean = " ".join(clean.split()).strip()
    return clean[:max_length]
