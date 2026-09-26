# ADR 009 — Padrão Estrutural Composite e Modelagem de Kits de Produtos vs. Anúncios Comerciais Desacoplados

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

No comércio eletrônico, existe uma divergência conceitual fundamental entre o **Inventário Físico do Catálogo** e a **Estratégia Comercial de Anúncios nos Marketplaces**:
- No catálogo do armazém, o lojista controla produtos individuais pelo SKU físico (ex.: Camiseta Branca Tam M, Cerveja Artesanal IPA 500ml).
- Nos marketplaces, o mesmo produto físico pode ser anunciado de múltiplas maneiras simultâneas:
  1. Anúncio individual clássico (1 unidade).
  2. Kit promocional com multiplicador de quantidade (ex.: "Kit 3 Camisetas Brancas").
  3. Combo composto heterogêneo (ex.: "Kit Churrasco: 1 Avental + 1 Faca de Churrasco + 1 Tábua de Madeira").
  4. Anúncio com benefícios distintos de frete (Anúncio Clássico vs. Anúncio Premium com frete grátis para o mesmo item físico).

Se o sistema adotasse uma modelagem ingênua de 1:1 onde cada `Anuncio` fosse apenas uma cópia direta de um `Produto`, seria impossível vender kits e combos sem duplicar o estoque de forma fictícia, gerando risco fatal de vender o mesmo produto físico duas vezes em anúncios diferentes (*overselling*).

## 2. Decisão

A equipe decidiu implementar o padrão estrutural **Composite** desacoplando o modelo comercial de `Anuncio` do modelo físico de `Produto` através de uma entidade de composição de primeira classe (`apps/anuncios/models.py: AnuncioComposicao`):

1. **Entidade Comercial (`Anuncio`)**:
   - Representa a publicação no marketplace (título, preço comercial de venda, permalink externo, status no canal e cota publicada).
   - Possui identificador externo `item_id_externo` (ex.: `MLB123456789`).
2. **Entidade Fisiológica de Composição (`AnuncioComposicao`)**:
   - Tabela intermediária de relacionamento N:M com atributos ricos: `anuncio`, `produto` e `quantidade` (multiplicador).
   - Um anúncio simples possui 1 composição com quantidade = 1.
   - Um kit possui 1 ou mais composições com multiplicador $\ge 1$.
3. **Cálculo Dinâmico de Cota Disponível (Algoritmo de Gargalo / *Bottleneck*)**:
   - O estoque publicado de um anúncio é calculado dinamicamente em tempo de execução:
     $$\text{Cota do Anúncio} = \min_{i \in \text{Composições}} \left( \left\lfloor \frac{\text{Estoque Físico}(P_i)}{\text{Multiplicador}_i} \right\rfloor \right)$$
   - Se o lojista possui 10 cervejas e o anúncio é um "Kit com 3 cervejas", a cota máxima calculada é $\lfloor 10 / 3 \rfloor = 3$ kits.
4. **Baixa Proporcional e Blindagem de Deleção**:
   - A venda de 1 unidade do kit debita atômica e proporcionalmente a quantidade exata de cada produto físico componente (`quantidade_vendida * multiplicador`).
   - Implementação de proteção contra deleção acidental de vínculos com auditoria baseada em snapshots (`fix/blindagem-de-erro-por-delecao-incorreta`).

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou formalmente duas alternativas de modelagem**:

### Alternativa 1: Acoplamento rígido 1:1 entre Produto e Anúncio (ForeignKey direta única)
- **Por que foi descartada (Justificativa Técnica)**: Se a tabela `Anuncio` tivesse apenas uma coluna `produto_id` direta simples:
  - O lojista estaria proibido de criar kits ou combos no marketplace.
  - Para criar um anúncio de "Kit 3 Camisetas", o lojista seria forçado a cadastrar um produto falso no catálogo chamado "Kit 3 Camisetas" e dividir manualmente o estoque físico entre a camiseta avulsa e o kit. Isso causaria descompasso imediato: se as camisetas avulsas esgotassem, o sistema não saberia que o kit também deveria ser zerado, resultando em venda sem estoque.

### Alternativa 2: Modelagem de kits apenas como strings/JSON em campos não-relacionais
- **Por que foi descartada (Justificativa Técnica Profunda)**: Armazenar a composição de kits dentro de um campo de texto ou payload JSON (`JSONField`) no anúncio destrói a integridade referencial do banco de dados relacional. Seria impossível executar consultas SQL indexadas reversas (ex.: *"quais anúncios precisam ser atualizados quando o produto SKU-100 mudar de estoque?"*). O Django ORM exigiria deserializar o JSON de todos os anúncios da loja em memória Python, degradando severamente a performance. A tabela relacional `AnuncioComposicao` permite consultas indexadas em milissegundos (`Anuncio.objects.filter(composicoes__produto=instance)`).

## 4. Consequência

### Ganhos Reais:
- **Flexibilidade Comercial Ilimitada**: O lojista pode criar anúncios unitários, kits do mesmo produto ou combos heterogêneos sem duplicar estoque físico.
- **Sincronização Atômica Multicanal**: Uma única venda de kit recalcula e propaga imediatamente as novas cotas para todos os outros anúncios unitários e kits que compartilham os mesmos componentes.
- **Auditoria e Rastreabilidade Relacional**: Facilidade de auditar no detalhe do produto todos os anúncios em que ele está embutido.

### Custos e Limitações Assumidas:
- **Complexidade de Recálculo**: Exige cálculo de cotas matemáticas a cada movimentação de inventário, mitigado pelo isolamento em transações atômicas e consultas com `prefetch_related`.

## 5. Commit

- **Hash de Publicação de Anúncios e RF-04**: `56d4a7f` — `feat(anuncios): implementa publicacao de anuncios em marketplaces (RF-04)`.
- **Hash de Importação com Suporte a Kits**: `259a925` — `feat(anuncios): finaliza Fase 1 de importação de anúncios Mercado Livre com suporte a kits e correção no items/bulk`.
- **Hash de Listagem Reversa de Composições**: `acb7f7f` — `fix(catalogo): corrige listagem de anuncios vinculados via composicao no detalhe do produto`.
- **Hash de Blindagem de Deleção e Snapshots**: `c5981a0` — `fix(anuncios): blindagem de delecao incorreta de composicao, auditoria com snapshots e alerta de produto sem vinculo`.
