# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo de logging para emissão de mensagens operacionais e diagnósticos
import logging

# Importa a classe Decimal e a exceção InvalidOperation para manipulação e validações numéricas seguras
from decimal import Decimal, InvalidOperation

# Importa o tipo Any da biblioteca typing para tipagem dinâmica genérica das entradas aceitas
from typing import Any

# Obtém a instância do logger nomeada conforme o namespace do módulo atual
logger = logging.getLogger(__name__)


# Função utilitária defensiva para conversão robusta de valores arbitrários para instâncias Decimal
def safe_decimal(val: Any, default: Any = Decimal('0.00')) -> Decimal:
    # Início do bloco de docstring que documenta o objetivo e as exceções prevenidas por esta rotina
    """
    O QUE FAZ: Converte com segurança qualquer valor (int, float, str, None, etc.) para Decimal.
    POR QUE FAZ: Evita quebras críticas em webhooks e replays causadas por valores `null`/`None`,
                 strings vazias, ou exceções `decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]`.
    """
    # Fim do bloco de documentação estrutural da função

    # Garante que o valor de fallback padrão fornecido seja convertido para uma instância válida de Decimal
    default_dec = default if isinstance(default, Decimal) else Decimal(str(default or '0.00'))

    # Se a entrada for estritamente nula (None), retorna imediatamente o fallback padrão
    if val is None:
        return default_dec

    # Se a entrada já for uma instância de Decimal, retorna o próprio objeto sem reprocessamento
    if isinstance(val, Decimal):
        return val

    # Se for tipo numérico nativo, converte via str
    # Trata tipos numéricos nativos primitivos (inteiro e ponto flutuante) convertendo via string
    if isinstance(val, (int, float)):
        try:
            return Decimal(str(val))
        # Em caso de falha de conversão numérica, retorna o fallback padrão de forma segura
        except (InvalidOperation, TypeError, ValueError):
            return default_dec

    # Converte o valor para string e remove eventuais espaços em branco nas extremidades
    val_str = str(val).strip()

    # Valida strings vazias ou representações literais textuais de nulo/indefinido (JSON e JavaScript)
    if not val_str or val_str.lower() in ('none', 'null', 'nan', 'undefined'):
        return default_dec

    # 1. Tentativa de conversão direta (ex: "120.50", "0.00")
    # Tenta instanciar Decimal diretamente da string no padrão internacional de ponto decimal
    try:
        return Decimal(val_str)
    # Se a sintaxe direta falhar (ex.: presença de vírgula ou múltiplos separadores), segue para tratamento avançado
    except (InvalidOperation, TypeError, ValueError):
        pass

    # 2. Tratamento de formatações de moeda com vírgula (ex: "120,50" ou "1.250,50")
    # Bloco protegido para normalização de pontuação monetária
    try:
        cleaned = val_str
        # Se contiver simultaneamente ponto e vírgula, determina qual é o separador decimal baseado na última posição
        if ',' in cleaned and '.' in cleaned:
            # Se a vírgula aparecer depois do ponto (última ocorrência)
            if cleaned.rfind(',') > cleaned.rfind('.'):
                # Formato brasileiro: 1.250,50 -> 1250.50
                # Remove os pontos de milhar e substitui a vírgula decimal por ponto
                cleaned = cleaned.replace('.', '').replace(',', '.')
            # Se o ponto aparecer depois da vírgula
            else:
                # Formato internacional: 1,250.50 -> 1250.50
                # Remove as vírgulas de milhar mantendo o ponto decimal
                cleaned = cleaned.replace(',', '')
        # Se contiver apenas vírgula (ex.: "150,50")
        elif ',' in cleaned:
            # Substitui a vírgula pelo ponto decimal padrão
            cleaned = cleaned.replace(',', '.')

        # Retorna o Decimal construído a partir da string sanitizada
        return Decimal(cleaned)
    # Em caso de erro na sanitização ou texto irreconhecível, devolve o fallback padrão
    except (InvalidOperation, TypeError, ValueError):
        return default_dec


# Função utilitária defensiva para conversão de valores arbitrários para números inteiros (int)
def safe_int(val: Any, default: int = 1) -> int:
    # Início do bloco de docstring que documenta o objetivo e a proteção contra falhas de tipo
    """
    O QUE FAZ: Converte com segurança qualquer valor para inteiro.
    POR QUE FAZ: Evita exceções `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`.
    """
    # Fim do bloco descritivo da função

    # Se a entrada for nula, retorna o valor padrão fornecido
    if val is None:
        return default

    # Bloco protegido para extração e coerção para número inteiro
    try:
        # Se a entrada já for número inteiro ou ponto flutuante, executa coerção direta
        if isinstance(val, (int, float)):
            return int(val)

        # Converte para string e elimina espaços laterais
        val_str = str(val).strip()

        # Rejeita strings vazias ou palavras-chave de nulidade
        if not val_str or val_str.lower() in ('none', 'null', 'nan', 'undefined'):
            return default

        # Converte primeiro para float e depois para int (suporta strings como "5.0")
        return int(float(val_str))
    # Captura erros de valor ou tipo incompatível e devolve o fallback com segurança
    except (ValueError, TypeError):
        return default
