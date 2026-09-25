# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o objetivo do arquivo como fachada de compatibilidade
"""
O QUE FAZ: Re-exporta a camada de campos criptografados de apps.core.security.
POR QUE FAZ: Preserva 100% de retrocompatibilidade com migrações históricas e importações em outros módulos.
"""
# Fim do bloco de docstring descritivo do módulo

# Importa as funções de recuperação da cifra Fernet e a classe do campo criptografado diretamente de apps.core.security
from apps.core.security import get_fernet_instance, get_fernet_cipher, EncryptedTextField

# Define a lista pública de símbolos exportados quando o módulo for importado via wildcard (from ... import *)
__all__ = ['get_fernet_instance', 'get_fernet_cipher', 'EncryptedTextField']
