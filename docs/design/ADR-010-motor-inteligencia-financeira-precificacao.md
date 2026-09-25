# ADR 010 — Motor de Inteligência Financeira e Simulação de Margens Desacoplado do Catálogo Físico

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

Vender em múltiplos marketplaces exige estratégias complexas de precificação. Cada canal de venda aplica estruturas de comissão e taxas distintas:
- Comissões percentuais variáveis por categoria (ex.: 12% no Clássico e 17% no Premium no Mercado Livre).
- Tarifas fixas por unidade vendida para produtos de baixo ticket (ex.: taxa fixa de R$ 6,00 a R$ 6,50 para produtos com preço inferior a R$ 79,00).
- Custos operacionais variáveis: Custo da Mercadoria Vendida (CMV / aquisição), custos específicos de embalagem e frete.
- Diferenciação por modalidade logística: na modalidade *Full / Fulfillment*, o marketplace assume o armazenamento e envio, zerando o custo próprio de embalagem do lojista, mas cobrando taxas operacionais adicionais.

Lojistas frequentemente precificam produtos aplicando apenas uma margem bruta genérica e acabam operando no prejuízo por não contabilizarem as taxas em cascata e o impacto tributário. A equipe precisava de um motor de cálculo financeiro capaz de simular preços ideais, prever o lucro líquido real e viabilizar campanhas promocionais com segurança.

## 2. Decisão

A equipe decidiu projetar e implementar um **Motor de Inteligência Financeira e Simulação de Margens (`apps/financeiro`)** isolado do modelo físico de catálogo:
1. **Estrutura de Custos de Domínio (`Produto`)**:
   - `custo_aquisicao`: Valor de compra/fabricação unitária (CMV).
   - `custo_embalagem`: Custo específico de materiais de expedição (caixa, fita, plástico bolha).
   - `modalidade_full`: Flag booleana que zera dinamicamente o custo de embalagem própria quando a mercadoria está no armazém do marketplace.
2. **Desacoplamento em Serviços de Cálculo Puro**:
   - Implementação de classes de serviço que calculam a margem de contribuição líquida (R$) e percentual (%):
     $$\text{Margem Líquida} = \text{Preço Venda} - \left( \text{CMV} + \text{Embalagem} + \text{Comissão}(\%) + \text{Taxa Fixa} + \text{Impostos} \right)$$
3. **Simulador Interativo de Promoções e Mark-up Reverso**:
   - Permite ao gestor simular:
     - Dado um preço de venda promocional desejado, qual será a margem de lucro líquida final.
     - Dada a margem líquida desejada (ex.: 20%), qual deve ser o preço de venda mínimo a ser praticado no canal.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou duas abordagens arquiteturais inferiores**:

### Alternativa 1: Cálculo estático hardcoded diretamente na interface gráfica (JavaScript / Frontend)
- **Por que foi descartada (Justificativa Técnica)**: Se as fórmulas de comissões, mark-ups e faixas de preço fossem escritas apenas no código JavaScript do navegador do usuário:
  - O backend do Hub não teria capacidade de auditar se um preço cadastrado gera lucro ou prejuízo.
  - Rotinas automatizadas de precificação em lote, comandos de importação e endpoints de API ficariam desprovidos das regras financeiras.
  - Qualquer alteração na tabela de taxas do marketplace exigiria alterar código de front-end disperso em templates HTML.

### Alternativa 2: Poluir o modelo de dados de Produto com colunas para cada taxa de marketplace
- **Por que foi descartada (Justificativa Técnica Profunda)**: Adicionar dezenas de colunas em `Produto` (ex.: `taxa_mercadolivre_classico`, `taxa_shopee`, `taxa_magalu_fixa`) violaria o Princípio da Responsabilidade Única (SRP) e o desacoplamento de domínios. As regras e alíquotas de terceiros são voláteis e mudam com frequência regulatória dos marketplaces. O catálogo físico de um produto (nome, dimensões, peso, estoque) é perene e não deve sofrer alterações de schema relacional toda vez que um marketplace ajusta uma tarifa percentual.

## 4. Consequência

### Ganhos Reais:
- **Visibilidade Contábil Rigorosa**: O lojista enxerga exatamente o lucro líquido de cada produto antes de publicar ou sincronizar preços nos marketplaces.
- **Isolamento de Domínio**: Regras financeiras evoluem independentemente da estrutura física de inventário.
- **Suporte a Cenários Especiais**: Modela com precisão particularidades operacionais como produtos Full e produtos abaixo da faixa de isenção de taxa fixa.

### Custos e Limitações Assumidas:
- **Manutenção de Tabelas de Alíquotas**: Exige manter atualizadas as constantes e configurações das tabelas de comissão dos canais integrados.

## 5. Commit

- **Hash Principal**: `86a17d2` — `feat(financial): implementa motor de inteligencia financeira e simulador de promocoes`.
- **Hash de Atributos de Custo no Catálogo**: `apps/catalogo/models.py` integrado com campos `custo_aquisicao`, `custo_embalagem` e `modalidade_full` no commit `c2ae6bf`.
