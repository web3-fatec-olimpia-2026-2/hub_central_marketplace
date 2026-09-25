# ADR 011 — Padrão Comportamental State (Máquina de Estados) para Ciclo de Vida e Sincronização Dinâmica de Anúncios

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

A sincronização de anúncios entre o Hub e os marketplaces é um processo que passa por múltiplos estágios operacionais:
1. O anúncio é cadastrado ou importado, mas ainda não foi validado ou submetido (`NAO_SINCRONIZADO`).
2. O preço ou estoque físico sofre alteração no catálogo mestre, colocando o anúncio em fila de auditoria (`PENDENTE`).
3. O operador revisa e despacha os dados via API externa com sucesso (`ENVIADO`).
4. A API do canal rejeita os dados (ex.: token expirado, categoria inválida), exigindo correção manual (`ERRO`).
5. O lojista decide descartar a sincronização de determinado anúncio (ex.: produto descontinuado naquele canal específico) (`CANCELADO`).

Além disso, um mesmo `Produto` pode possuir múltiplos anúncios vinculados (ex.: 1 no Mercado Livre, 1 na Shopee, 1 Kit no Magalu). Se a equipe utilizasse uma simples flag booleana `sincronizado: bool`, a interface gráfica apresentaria informações conflitantes: se o produto estivesse sincronizado na Shopee mas desatualizado no Mercado Livre, qual estado exibir na tela principal? A equipe precisava de uma máquina de estados consistente que consolidasse o ciclo de vida individual e agregado dos anúncios.

## 2. Decisão

A equipe decidiu modelar o ciclo de vida da sincronização adotando o padrão **State (Máquina de Estados Finita)** complementado por **agregação dinâmica de estados no Produto mestre**:

1. **Enum Formal de Estados de Sincronização (`StatusSincronizacaoEnum`)**:
   - `NAO_SINCRONIZADO`: Estado inicial de onboarding.
   - `PENDENTE`: Divergência detectada entre o catálogo físico e o canal externo.
   - `ENVIADO`: Alinhamento confirmado e telemetria atualizada com sucesso.
   - `CANCELADO`: Sincronização descartada deliberadamente pelo lojista.
   - `ERRO`: Falha de comunicação ou rejeição de payload pela API parceira.

2. **Detecção Dinâmica de Divergência (`esta_pendente`)**:
   - O método `Anuncio.esta_pendente(preco_mestre)` avalia em tempo real se o preço comercial gravado diverge do preço do produto mestre ou se o estoque publicado diverge da cota física calculada, evitando estados defasados em cache.

3. **Propriedade de Estado Consolidado no Produto (`status_sincronizacao_consolidado`)**:
   - Em `apps/catalogo/models.py`, o modelo `Produto` inspeciona dinamicamente a coleção de todos os seus anúncios ativos:
     - Se todos os anúncios estão `CANCELADO` $\rightarrow$ *"Sincronização Descartada"*.
     - Se qualquer anúncio ativo estiver com divergência de preço ou `PENDENTE` $\rightarrow$ *"Pendente de Sincronização"* (gera badge de atenção amarelo).
     - Se todos os anúncios ativos estiverem `ENVIADO` sem pendências $\rightarrow$ *"Sincronizado com Sucesso"* (gera badge verde).
     - Se não possuir vínculos $\rightarrow$ *"Sem Anúncios"*.
   - Acompanhado de histórico de transições com snapshots antes/depois (`HistoricoSincronizacaoAnuncio`).

## 3. Alternativa Descartada

A equipe analisou e **rejeitou duas abordagens arquiteturais inferiores**:

### Alternativa 1: Campo booleano simples `is_sincronizado = models.BooleanField(default=False)`
- **Por que foi descartada (Justificativa Técnica)**: Uma flag booleana é um antipadrão para fluxos de integração complexos. Ela é incapaz de expressar nuances operacionais vitais (diferenciar uma falha de rede temporária de uma rejeição de dados por schema inválido; ou diferenciar um anúncio intencionalmente pausado de um que ainda não foi revisado). Além disso, não resolve a ambiguidade quando um produto possui múltiplos anúncios em canais diferentes.

### Alternativa 2: Confiar exclusivamente em status gravados estaticamente no banco sem cálculo dinâmico
- **Por que foi descartada (Justificativa Técnica Profunda)**: Se o estado dependesse unicamente de um campo estático na tabela `Produto`, qualquer mutação física no estoque exigiria varrer e atualizar a coluna em todos os produtos da base. Se uma rotina externa falhasse ao atualizar a coluna estática, haveria divergência entre o que a tela principal exibe ("Sincronizado") e a realidade dos anúncios na tabela detalhada ("Pendente"). A propriedade dinâmica avalia a verdade matemática das composições em tempo de execução.

## 4. Consequência

### Ganhos Reais:
- **Consistência Visual e Operacional Absoluta**: Elimina totalmente divergências entre o card de resumo de produtos e as tabelas de anúncios vinculados.
- **Rastreabilidade por Snapshots**: O lojista audita exatamente quem aprovou ou cancelou cada transição de estado e quais eram os valores de preço e estoque anteriores e posteriores.
- **Ações em Lote Seguras**: A tela de catálogo permite filtrar apenas anúncios no estado `PENDENTE` para despacho em lote com um único clique.

### Custos e Limitações Assumidas:
- **Avaliação em Memória**: O recálculo de estados dinâmicos para listagens extensas de produtos requer queries otimizadas com `prefetch_related('itens_composicao')` para prevenir o problema de consultas $N+1$.

## 5. Commit

- **Hash de Formalização do Ciclo de Sincronização**: `34f5b3f` — `feat(anuncios): ciclo formal de sincronizacao com selecao dinamica, consistencia no produto e historico`.
- **Hash de Centralização Global e Histórico com SKU**: `a7463b4` — `fix(catalogo,anuncios): centraliza sincronizacao global, duplo historico com sku e correcao nos modais de estoque`.
- **Hash de Badge Acumulativo e Reabertura de Pendência**: `fe29593` — `fix(catalogo,anuncios): reabre pendencia de sync sob alteracao fisica, badge acumulativo e decisao estrita em lote`.
