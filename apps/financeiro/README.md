# Módulo de Inteligência Financeira e Margens (`apps/financeiro`)

## 1. Responsabilidade e Objetivo
O módulo `financeiro` processa comissões de canais, custos fixos e variáveis, tarifas de marketplace, impostos e margem de contribuição líquida.

## 2. Modelos e Escopo
- **`ParametroCanalFinanceiro`:** Alíquotas e taxas de comissionamento por marketplace vinculadas à `Loja`.
- **`DemonstrativoResultadoPedido`:** Reconciliação do valor bruto recebido contra deduções e CMV.

## 3. RBAC e Tenancy
- Dados financeiros altamente sensíveis acessíveis exclusivamente a perfis autorizados (DEV, ADMIN e SUPERVISOR).
- Vínculo direto e restrito à `Loja` do usuário.

## 4. Dependências
- `apps.core`
- `apps.catalogo`
- `apps.pedidos`
- `apps.tenancy`
