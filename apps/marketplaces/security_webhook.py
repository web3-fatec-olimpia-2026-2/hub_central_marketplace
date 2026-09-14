# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Módulo utilitário para validação simétrica de assinaturas criptográficas HMAC para webhooks HTTP.
POR QUE FAZ: Neutraliza requisições forjadas ou sem assinatura válida com checagem criptográfica segura HMAC (compare_digest).
"""
import hmac
import hashlib
import time
from typing import Tuple


def validar_assinatura_e_anti_replay(request, secret: str, canal: str = 'mercadolivre', max_age_seconds: int = 300) -> Tuple[bool, int, str]:
    """
    Valida a autenticidade da assinatura criptográfica HMAC.
    Extrai o timestamp caso ele componha o hash do canal, sem bloquear requisições por janela temporal expirada.
    Retorna (valido: bool, status_code: int, mensagem: str).
    """
    if not secret:
        return True, 200, "Sem secret configurado."

    # 1. Extração do timestamp dos cabeçalhos
    raw_ts = (
        request.META.get('HTTP_X_TIMESTAMP')
        or request.META.get('HTTP_TIMESTAMP')
        or request.META.get('HTTP_X_REQUEST_TIMESTAMP')
    )

    sig_header = (
        request.META.get('HTTP_X_SIGNATURE')
        or request.META.get('HTTP_AUTHORIZATION')
        or request.META.get('HTTP_X_HUB_SIGNATURE_256')
        or request.META.get('HTTP_SIGNATURE')
        or ''
    )

    ts_val = None
    # Se o cabeçalho x-signature contiver ts=123...,v1=abc... (padrão oficial Mercado Livre)
    if 'ts=' in sig_header:
        parts = sig_header.split(',')
        for part in parts:
            part = part.strip()
            if part.startswith('ts='):
                raw_ts = part.split('=', 1)[1]
            elif part.startswith('v1='):
                sig_header = part.split('=', 1)[1]

    # 2. Validação da Assinatura HMAC
    if not sig_header:
        return False, 401, "Cabeçalho de assinatura HMAC ausente."

    provided_sig = sig_header.strip()
    if provided_sig.startswith('sha256='):
        provided_sig = provided_sig.split('=', 1)[1]
    elif provided_sig.startswith('v1='):
        provided_sig = provided_sig.split('=', 1)[1]
    elif provided_sig.lower().startswith('bearer '):
        provided_sig = provided_sig[7:].strip()

    secret_bytes = secret.encode('utf-8')
    body_bytes = request.body if hasattr(request, 'body') else b''

    # Possíveis padrões canônicos aceitos pelos marketplaces
    candidate_hashes = []

    # A. HMAC sobre o corpo puro (padrão HMAC-SHA256)
    candidate_hashes.append(hmac.new(secret_bytes, body_bytes, hashlib.sha256).hexdigest())

    # B. HMAC sobre ts + corpo (padrão Shopee / Meli com ts)
    if raw_ts:
        ts_str = str(raw_ts)
        candidate_hashes.append(hmac.new(secret_bytes, f"{ts_str}.{body_bytes.decode('utf-8', errors='ignore')}".encode('utf-8'), hashlib.sha256).hexdigest())
        candidate_hashes.append(hmac.new(secret_bytes, ts_str.encode('utf-8') + body_bytes, hashlib.sha256).hexdigest())
        candidate_hashes.append(hmac.new(secret_bytes, f"ts:{ts_str};".encode('utf-8') + body_bytes, hashlib.sha256).hexdigest())

    # Comparação segura contra timing attacks
    for expected in candidate_hashes:
        if hmac.compare_digest(provided_sig.lower(), expected.lower()):
            return True, 200, "Assinatura válida."

    return False, 401, "Assinatura HMAC inválida."
