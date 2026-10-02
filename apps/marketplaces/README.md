# Módulo de Conectores de Marketplaces (`apps/marketplaces`)

## 1. Responsabilidade e Objetivo
O módulo `marketplaces` implementa a camada de integração externa com plataformas de comércio eletrônico (Mercado Livre, Shopee, Amazon, Magalu), gerenciando fluxo OAuth 2.0, renovação de tokens, endpoints de webhook e logs de auditoria.

## 2. Modelos e Segurança
- **`ContaMarketplace`:** Gerencia credenciais e tokens de acesso por loja. Armazena `access_token` e `refresh_token` criptografados em repouso com `EncryptedTextField` (Fernet). Possui `webhook_uuid` único (UUIDv4) para evitar enumeração de endpoints de notificação.
- **`LogAuditoria`:** Registro auditável de eventos de sincronização e transações com os canais parceiros.

## 3. RBAC e Tenancy
- Conexões e contas pertencem estritamente à respectiva `Loja`.
- Exige módulo ativo `marketplaces` via `ModuloRequeridoMixin`.

## 4. Dependências
- `apps.core`
- `apps.tenancy`
