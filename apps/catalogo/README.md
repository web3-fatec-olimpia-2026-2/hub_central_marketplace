# Módulo de Catálogo e Produtos (`apps/catalogo`)

## 1. Responsabilidade e Objetivo
O módulo `catalogo` atua como a Fonte Única da Verdade (Single Source of Truth) para inventário físico e precificação mestre no Hub de Marketplaces.

## 2. Modelos e Escopo de Tenancy
- **`Categoria`:** Taxonomia de produtos vinculada obrigatoriamente a uma `Loja` com unicidade composta `('loja', 'slug')`.
- **`Produto`:** Item físico do estoque mestre, custos de aquisição/embalagem e preço de venda. Possui FK para `Loja` e unicidade composta `('loja', 'sku')`.
- **`HistoricoPreco`:** Rastreabilidade temporal de alterações de preços por produto.

## 3. RBAC e Proteções contra BOLA/IDOR
- Todas as visualizações de catálogo herdam de `CatalogOwnershipCheckMixin` e `ModuloRequeridoMixin('catalogo')`.
- As consultas ao banco são filtradas pelo escopo da loja do usuário logado (`loja_id = request.user.perfil.loja_id`).
- Perfis DEV possuem visão global; ADMIN e SUPERVISOR têm acesso de escrita completo; USUARIO possui restrição contra alteração de preços e baixa geral de estoque.

## 4. Dependências
- `apps.core`
- `apps.tenancy`
