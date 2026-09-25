# ADR 008 — Idempotência Estrita, Transações Atômicas (Unit of Work) e Lock Pessimista na Ingestão de Webhooks de Vendas

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

A integração de vendas com marketplaces é assíncrona e orientada a notificações HTTP (Webhooks). Provedores como o Mercado Livre operam sob a semântica de entrega **"pelo menos uma vez" (*At-least-once delivery*)**:
- Se a rede oscilar ou o servidor do Hub demorar mais de 3 segundos para responder `200 OK`, o marketplace reenvia a mesma notificação repetidamente.
- Eventos de atualização de status de pedido (ex.: pagamento aprovado, etiqueta emitida, envio em trânsito) chegam concorrentemente.
- Se duas notificações para o mesmo pedido forem processadas simultaneamente em threads ou workers distintos, o estoque de um produto poderia ser debitado duas vezes (*double spending* de inventário).
- Simultaneamente, clientes podem comprar a última unidade de um item ao mesmo tempo em que um operador realiza uma contagem física, gerando condições de corrida (*race conditions*) no saldo físico.

A equipe precisava garantir que cada notificação externa fosse processada de forma estritamente atômica, isolada e imune a repetições concorrentes.

## 2. Decisão

A equipe de engenharia implementou uma tríade de padrões de concorrência e consistência transacional (`apps/pedidos/services.py: ProcessamentoPedidoService` e `apps/marketplaces/services.py`):

1. **Padrão Idempotency Key (Chave de Idempotência Composta)**:
   - Toda notificação recebida é checada contra a base relacional com base na tupla única: `(loja, canal_origem, pedido_id_externo)`.
   - Se o pedido já tiver sido registrado, o sistema retorna sucesso imediato (`HTTP 200`), descartando o reprocessamento de regras de negócio ou mutações de estoque.
   - Em caso de requisições simultâneas em microssegundos que passem da checagem inicial, a restrição de banco captura `IntegrityError` sob transação atômica e recupera o registro já criado de forma segura.

2. **Padrão Unit of Work / Transação Atômica (`transaction.atomic`)**:
   - Todo o ciclo de vida da ingestão (gravação do `PedidoVenda`, criação dos `ItemPedidoVenda`, dedução de estoque mestre e emissão de logs de auditoria) é executado dentro de um bloco transacional atômico ACID. Qualquer falha intermediária reverte (*rollback*) todas as alterações, evitando pedidos órfãos com estoque baixado ou vice-versa.

3. **Lock Pessimista Concorrente (`select_for_update`)**:
   - Durante a dedução do inventário físico, a linha do produto no banco de dados é bloqueada a nível de banco de dados:
     ```python
     with transaction.atomic():
         prod_locked = Produto.objects.select_for_update().get(pk=produto.pk)
         estoque_ant = prod_locked.estoque
         prod_locked.estoque = estoque_ant - (quantidade * multiplicador)
         prod_locked.save(update_fields=['estoque', 'atualizado_em'])
     ```
   - O mesmo lock pessimista é utilizado na renovação de tokens OAuth do Mercado Livre (`ContaMarketplace.objects.select_for_update()`), pois no Mercado Livre o `refresh_token` é de **uso único**; duas requisições concorrentes tentando renovar o token ao mesmo tempo invalidariam irremediavelmente a integração da conta.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou formalmente duas abordagens alternativas**:

### Alternativa 1: Processamento não-idempotente sem verificação prévia de unicidade
- **Por que foi descartada (Justificativa Técnica)**: Aceitar requisições de webhook sem garantia estrita de idempotência geraria baixa duplicada ou triplicada de estoque a cada retentativa de rede do marketplace. Um lojista com 10 unidades em estoque que sofresse reenvios de webhook acabaria com o sistema marcando 7 ou 4 unidades indevidamente, gerando ruptura de inventário e cancelamentos compulsórios de pedidos.

### Alternativa 2: Concorrência otimista baseada apenas em campos de versão (`version_id`)
- **Por que foi descartada (Justificativa Técnica Profunda)**: A concorrência otimista detecta conflitos após o fato e dispara exceções de concorrência que exigem loops complexos de retentativa no código de aplicação. Em endpoints de webhook com limite de timeout severo imposto por marketplaces (como o Mercado Livre, que aborta requisições após 3 a 5 segundos), loops de retentativa otimista esgotariam a janela de conexão HTTP. O lock pessimista (`select_for_update`) serializa o acesso no banco por frações de milissegundo de forma determinística, garantindo resposta imediata com total integridade matemática.

## 4. Consequência

### Ganhos Reais:
- **Consistência Matemática Absoluta**: Impossibilidade física de duplicidade de pedidos ou dedução duplicada de estoque por reenvios de webhooks.
- **Isolamento de Concorrência**: Prevenção total de *race conditions* mesmo sob picos de tráfego de vendas (ex.: eventos sazonais como Black Friday).
- **Proteção do Ciclo de Vida de Tokens**: Elimina a invalidação acidental de credenciais OAuth de uso único por requisições paralelas.

### Custos e Limitações Assumidas:
- **Serialização Temporária de Linhas no Banco**: O lock pessimista bloqueia temporariamente a linha daquele produto específico no banco até o commit da transação (mitigado pela brevidade extrema das transações, durando poucos milissegundos).

## 5. Commit

- **Hash de Idempotência e Baixa Atômica**: `63d516f` — `feat(webhooks): implementa endpoint nativo Mercado Livre com idempotencia estrita e baixa atomica de estoque`.
- **Hash de Resolução Multi-tenant e Idempotência**: `60179f5` — `fix(marketplaces): blinda resolucao de tenant no webhook, corrige idempotencia por PedidoVenda e persiste vendas com vinculo pendente`.
- **Hash de Lock Pessimista em Tokens OAuth**: `2ec1349` — `feat(meli): implementa strategy/adapter oauth, auto-refresh com lock pessimista, csrf state e validacao ativa`.
- **Hash de Rastreabilidade de Histórico de Venda**: `9faf0ac` — `fix(pedidos): registra historico de alteracao de estoque na baixa de venda e remove tags tecnicas rn05 da ui`.
