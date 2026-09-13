# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Re-exporta a camada de campos criptografados de apps.core.security.
POR QUE FAZ: Preserva 100% de retrocompatibilidade com migrações históricas e importações em outros módulos.
"""
from apps.core.security import get_fernet_instance, get_fernet_cipher, EncryptedTextField

__all__ = ['get_fernet_instance', 'get_fernet_cipher', 'EncryptedTextField']
