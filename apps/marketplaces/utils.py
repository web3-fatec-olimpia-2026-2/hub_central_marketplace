# Os códigos foram gerados com auxilio de I.A.
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)


def safe_decimal(val: Any, default: Any = Decimal('0.00')) -> Decimal:
    """
    O QUE FAZ: Converte com segurança qualquer valor (int, float, str, None, etc.) para Decimal.
    POR QUE FAZ: Evita quebras críticas em webhooks e replays causadas por valores `null`/`None`,
                 strings vazias, ou exceções `decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]`.
    """
    default_dec = default if isinstance(default, Decimal) else Decimal(str(default or '0.00'))

    if val is None:
        return default_dec

    if isinstance(val, Decimal):
        return val

    # Se for tipo numérico nativo, converte via str
    if isinstance(val, (int, float)):
        try:
            return Decimal(str(val))
        except (InvalidOperation, TypeError, ValueError):
            return default_dec

    val_str = str(val).strip()
    if not val_str or val_str.lower() in ('none', 'null', 'nan', 'undefined'):
        return default_dec

    # 1. Tentativa de conversão direta (ex: "120.50", "0.00")
    try:
        return Decimal(val_str)
    except (InvalidOperation, TypeError, ValueError):
        pass

    # 2. Tratamento de formatações de moeda com vírgula (ex: "120,50" ou "1.250,50")
    try:
        cleaned = val_str
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                # Formato brasileiro: 1.250,50 -> 1250.50
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                # Formato internacional: 1,250.50 -> 1250.50
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        return Decimal(cleaned)
    except (InvalidOperation, TypeError, ValueError):
        return default_dec


def safe_int(val: Any, default: int = 1) -> int:
    """
    O QUE FAZ: Converte com segurança qualquer valor para inteiro.
    POR QUE FAZ: Evita exceções `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`.
    """
    if val is None:
        return default
    try:
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ('none', 'null', 'nan', 'undefined'):
            return default
        return int(float(val_str))
    except (ValueError, TypeError):
        return default
