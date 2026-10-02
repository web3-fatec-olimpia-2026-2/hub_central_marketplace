# Módulo de Vendas e Pedidos Multicanal (`apps/pedidos`)

## 1. Responsabilidade e Objetivo
O módulo `pedidos` é responsável pelo ciclo de vida de compras, ingestão de webhooks de novos pedidos, baixa atômica e pessimista de inventário (`select_for_update`) e esteira de despacho.

## 2. Modelos e Escopo
- **`Pedido`:** Instância de venda vinculada à `Loja` e canal externo.
- **`ItemPedido`:** Itens que compõem o pedido e referenciam o produto de catálogo correspondente.
- **`HistoricoStatusPedido`:** Log temporal do ciclo de vida da compra (Aprovado, Faturado, Enviado, Entregue, Cancelado).

## 3. Concorrência e Isolamento
- Execução sob transações atômicas com mitigação de race condition no saldo de inventário.
- Escopo estritamente segregado por `Loja`.

## 4. Dependências
- `apps.core`
- `apps.catalogo`
- `apps.marketplaces`
- `apps.tenancy`
