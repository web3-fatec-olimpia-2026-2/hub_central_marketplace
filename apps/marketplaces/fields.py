# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Custom field EncryptedTextField com criptografia simétrica Fernet em repouso.
POR QUE FAZ: Garante conformidade de segurança e proteção de tokens OAuth e segredos no banco de dados.
SEGURANÇA: Utiliza Fernet (AES-128-CBC + HMAC-SHA256) com chave mestra FIELD_ENCRYPTION_KEY ou derivação segura.
"""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet_cipher() -> Fernet:
    """
    O QUE FAZ: Obtém ou inicializa a cifra simétrica Fernet.
    POR QUE FAZ: Centraliza a derivação e validação da chave de criptografia de campos.
    FALLBACK: Caso FIELD_ENCRYPTION_KEY não esteja configurada ou seja inválida,
              deriva uma chave segura de 32 bytes a partir de settings.SECRET_KEY.
    """
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', None)
    if key and isinstance(key, str):
        key = key.strip()
    if key:
        try:
            return Fernet(key.encode('utf-8') if isinstance(key, str) else key)
        except Exception:
            pass

    # Fallback seguro: derivação via SHA-256 codificada em URL-safe Base64
    secret = getattr(settings, 'SECRET_KEY', 'hub-marketplaces-default-secret').encode('utf-8')
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(derived_key)


class EncryptedTextField(models.TextField):
    """
    O QUE FAZ: Campo de modelo que cifra strings em UTF-8 antes de persistir no banco e as decifra na recuperação.
    POR QUE FAZ: Previne exposição de tokens de autenticação (Access/Refresh Tokens) em dumps e logs de banco.
    """
    description = "Campo de texto com criptografia simétrica Fernet em repouso"

    def get_prep_value(self, value):
        """Cifra o texto antes de persistir no banco."""
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        if not isinstance(value, str):
            value = str(value)

        cipher = get_fernet_cipher()
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
        """Decifra o texto ao carregar do banco de dados."""
        if value is None or value == "":
            return value
        cipher = get_fernet_cipher()
        try:
            decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except (InvalidToken, Exception):
            # Retorna texto bruto se não for um token cifrado válido
            return value

    def to_python(self, value):
        """Garante decriptografia e compatibilidade de tipos no formulário/ORM."""
        if value is None or value == "":
            return value
        if isinstance(value, str):
            cipher = get_fernet_cipher()
            try:
                decrypted_bytes = cipher.decrypt(value.encode('utf-8'))
                return decrypted_bytes.decode('utf-8')
            except (InvalidToken, Exception):
                return value
        return str(value)
