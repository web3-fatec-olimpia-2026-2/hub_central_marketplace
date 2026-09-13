# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Camada criptográfica em repouso utilizando o padrão Fernet (AES-128-CBC + HMAC-SHA256).
POR QUE FAZ: Protege chaves de API, segredos de aplicação, tokens de sessão OAuth e chaves de validação de webhooks no banco de dados.
SEGURANÇA: Obtém a chave mestra de FIELD_ENCRYPTION_KEY ou deriva deterministicamente a partir de settings.SECRET_KEY via SHA-256.
"""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet_instance() -> Fernet:
    """
    O QUE FAZ: Obtém ou inicializa a cifra simétrica Fernet.
    POR QUE FAZ: Centraliza a derivação e validação da chave de criptografia de campos.
    FALLBACK: Caso FIELD_ENCRYPTION_KEY não esteja configurada ou seja inválida,
              deriva deterministicamente uma chave válida base64 URL-safe de 32 bytes aplicando SHA-256 sobre settings.SECRET_KEY.
    """
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if key and isinstance(key, str):
        key = key.strip()
    if key:
        try:
            return Fernet(key.encode('utf-8') if isinstance(key, str) else key)
        except Exception:
            pass

    # Derivação determinística: SHA-256 sobre SECRET_KEY codificada em URL-safe Base64 (32 bytes)
    secret = getattr(settings, 'SECRET_KEY', 'hub-marketplaces-default-secret')
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    key_bytes = hashlib.sha256(secret).digest()
    derived_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(derived_key)


# Alias para retrocompatibilidade
get_fernet_cipher = get_fernet_instance


class EncryptedTextField(models.TextField):
    """
    O QUE FAZ: Campo de modelo Django que criptografa strings em UTF-8 com Fernet antes de persistir no banco e decifra ao recuperar.
    POR QUE FAZ: Previne vazamento e exposição de tokens e segredos em repouso (banco de dados, dumps, logs SQL).
    """
    description = "Campo de texto com criptografia simétrica Fernet em repouso"

    def get_prep_value(self, value):
        """Criptografa o texto antes de persistir no banco de dados."""
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        if not isinstance(value, str):
            value = str(value)

        cipher = get_fernet_instance()
        try:
            # Verifica se já está cifrado para evitar dupla encriptação
            try:
                cipher.decrypt(value.encode('utf-8'))
                return value
            except (InvalidToken, Exception):
                encrypted_bytes = cipher.encrypt(value.encode('utf-8'))
                return encrypted_bytes.decode('utf-8')
        except Exception:
            return value

    def from_db_value(self, value, expression, connection):
        """Descriptografa o texto ao carregar do banco de dados."""
        if value is None or value == "":
            return value
        cipher = get_fernet_instance()
        try:
            decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except (InvalidToken, Exception):
            # Fallback gracioso para o valor original caso já esteja em texto plano ou legado
            return value

    def to_python(self, value):
        """Garante consistência de decriptografia e compatibilidade no formulário/ORM."""
        if value is None or value == "":
            return value
        if isinstance(value, str):
            cipher = get_fernet_instance()
            try:
                decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
                return decrypted_bytes.decode('utf-8')
            except (InvalidToken, Exception):
                return value
        return str(value)
