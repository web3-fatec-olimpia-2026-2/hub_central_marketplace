# Módulo de Anúncios e Vínculos Multicanal (`apps/anuncios`)

## 1. Responsabilidade e Objetivo
O módulo `anuncios` gerencia as publicações nos canais externos, regras de precificação por canal, composições (anúncios simples vs kits) e histórico de sincronizações de status, estoque e preços.

## 2. Modelos e Escopo
- **`AnuncioMarketplace`:** Publicação atrelada a uma `ContaMarketplace` e a um ou mais produtos.
- **`ComposicaoAnuncio`:** Mapeia a proporção e quantidade de itens físicos que compõem o anúncio em um canal.
- **`HistoricoSincronizacao`:** Rastreia eventos de atualização disparados entre o Hub e as plataformas externas.

## 3. RBAC e Tenancy
- Todas as entidades são isoladas no escopo do tenant via vínculo com `ContaMarketplace` e `Loja`.
- Exige o módulo `marketplaces` e permissões operacionais do usuário logado.

## 4. Dependências
- `apps.core`
- `apps.catalogo`
- `apps.marketplaces`
- `apps.tenancy`
