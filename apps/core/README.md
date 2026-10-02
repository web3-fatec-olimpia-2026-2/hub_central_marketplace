# Módulo Core e Governança (`apps/core`)

## 1. Responsabilidade e Objetivo
O módulo `core` centraliza utilitários transversais, serviços de integridade criptográfica, contrato neutro de resolução de tenancy (`get_tenant`), testes de carga/concorrência e classes base reutilizáveis por todo o ecossistema Django.

## 2. Modelos e Escopo de Tenancy
- **Contrato Neutro de Tenancy:** Implementado em `apps/core/tenancy.py` via `get_tenant(request)`. Opera em conformidade com a configuração `TENANCY_MODE = env('TENANCY_MODE', default='single')`.
  - Modo `single`: devolve o tenant padrão (primeira loja ativa).
  - Modo `row`: resolve o tenant através do perfil do usuário autenticado (`request.user.perfil.loja`) ou contexto de sessão.
- **Campos Criptografados:** `EncryptedTextField` em `apps/core/security.py`, utilizando criptografia simétrica Fernet (AES-128-CBC + HMAC-SHA256) em repouso.

## 3. Dependências
- Biblioteca `cryptography`
- Framework nativo Django (`django.db`, `django.conf`)

## 4. RBAC e Permissões
- Não possui modelos próprios de usuário; fornece decorators e utilitários consumidos pelos demais módulos.

## 5. Interfaces Públicas
- `get_tenant(request=None, explicit_tenant=None)`: Ponto único contratual para resolução de tenant (Doc ① §10.6).
- `get_fernet_instance()`: Instância de cifrador simétrico Fernet.
- `EncryptedTextField`: Campo de modelo para persistência cifrada.
