# Módulo de Tenancy e Gestão de Lojas (`apps/tenancy`)

## 1. Responsabilidade e Objetivo
O módulo `tenancy` gerencia o isolamento lógico das organizações clientes (Lojas/Inquilinos), o provisionamento de novas contas, a ativação/desativação de módulos funcionais via Feature Flags e a estrutura de perfis de usuário (`PerfilUsuario`).

## 2. Modelos e Escopo
- **`Loja`:** Entidade raiz de particionamento multi-tenant da aplicação. Armazena razão social, CNPJ com validação de unicidade numérica e estado operacional (`ativo`).
- **`ModuloLoja`:** Tabela associativa que controla a ativação de módulos (`catalogo`, `pedidos`, `marketplaces`, `financeiro`) por loja.
- **`PerfilUsuario`:** Extensão 1:1 do modelo `User` nativo, vinculando cada operador a um papel hierárquico (DEV, ADMIN, SUPERVISOR, USUARIO) e a uma `Loja` (obrigatória para papéis não-DEV).

## 3. RBAC e Governança de Acesso
- **DEV (Grupo 4):** Acesso global e irrestrito. Único perfil com permissão para provisionar e editar dados estruturais de lojas e alternar feature flags.
- **ADMIN (Grupo 3):** Gestão administrativa restrita à sua respectiva Loja. Cria e edita subordinados (SUPERVISOR e USUARIO).
- **SUPERVISOR (Grupo 1) & USUARIO (Grupo 0):** Perfis operacionais da loja.

## 4. Dependências
- `apps.core`
- `apps.accounts`
