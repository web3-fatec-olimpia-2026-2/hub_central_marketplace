# ADR 006 — Padrão Comportamental Observer via Django Signals para Propagação Reativa de Estoque

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

No **Hub Inteligente de Marketplaces**, o estoque físico de um produto no catálogo mestre (`Produto.estoque`) pode ser alterado por múltiplos eventos concorrentes:
- Entrada manual de mercadorias ou contagem de inventário pelo lojista.
- Registro de perda ou avaria física por operadores de expedição.
- Venda confirmada em um marketplace (ex.: Mercado Livre via Webhook) que exige dedução imediata.

Quando o estoque físico de um produto é alterado, **todos os anúncios vinculados a esse produto** em múltiplos canais (Mercado Livre, Shopee, Amazon) precisam tomar conhecimento do evento para:
1. Reabrir o status de sincronização para `PENDENTE` (para alterações manuais que exigem conferência de lote).
2. Ou disparar a propagação imediata (*broadcast multicanal*) da nova cota disponível para os canais externos, aplicando a política de dedução do canal de origem (RF-08 / RN-05).

Se a lógica de notificação dos anúncios fosse codificada de forma imperativa dentro de cada formulário, view ou serviço que mutaciona produtos, haveria forte acoplamento e alto risco de esquecimento, gerando divergência de estoque e *overselling* (vender sem ter produto físico).

## 2. Decisão

A equipe decidiu implementar o padrão de projeto comportamental **Observer (Publish-Subscribe)** utilizando os **Signals desacoplados do Django (`post_save` e `pre_save`)**:
1. **Subject (Publicador)**: O modelo `Produto` (`apps/catalogo/models.py`), cujas alterações de estado emitem eventos de ciclo de vida do Django.
2. **Observer (Assinante)**: O módulo `apps/anuncios/signals.py`, que escuta os eventos `pre_save` e `post_save` de `Produto`:
   - `identificar_alteracao_produto (pre_save)`: Compara os valores em memória com os valores previamente persistidos no banco de dados (`Produto.objects.filter(pk=...).values('estoque', 'preco')`), detectando com exatidão se houve mutação real de saldo ou preço antes de disparar qualquer processamento pesado.
   - `disparar_sincronizacao_anuncios_produto (post_save)`: Identifica todos os anúncios compostos vinculados ao produto (`Anuncio.objects.filter(composicoes__produto=instance)`), recalcula as cotas físicas disponíveis e atualiza o estado de sincronização.
3. **Mecanismo Anti-Reentrância e Muting**: Criação do context manager `mute_sincronizacao_signals()` utilizando `threading.local()`, permitindo silenciar os sinais durante cargas em massa, migrações de dados ou quando a sincronização já é gerenciada por uma transação controlada, evitando loops recursivos infinitos.

## 3. Alternativa Descartada

A equipe analisou e **rejeitou formalmente duas abordagens arquiteturais**:

### Alternativa 1: Chamadas imperativas síncronas manuais em cada View ou Controller
- **Por que foi descartada (Justificativa Técnica Profunda)**: Exigiria que todo desenvolvedor, ao escrever uma view de ajuste de estoque, uma rota de importação de planilha, um formulário de admin ou um serviço de webhook, lembrasse de invocar manualmente `sincronizar_anuncios(produto)`. Se um único endpoint esquecesse essa chamada, o catálogo ficaria dessincronizado dos marketplaces silenciosamente. Além disso, acopla diretamente o app de `catalogo` ao app de `anuncios`, violando a arquitetura em camadas e o Princípio de Inversão de Dependências (DIP).

### Alternativa 2: Polling contínuo agendado no banco de dados (Tarefas Cron periódicas)
- **Por que foi descartada (Justificativa Técnica)**: Executar uma rotina periódica a cada X minutos para varrer todo o catálogo buscando produtos com data de alteração recente geraria uma sobrecarga massiva de I/O no banco de dados (*busy waiting*) e introduziria uma latência inaceitável para o e-commerce. Durante o intervalo entre as execuções do Cron, clientes poderiam comprar itens já esgotados no Mercado Livre, gerando penalidades severas à reputação do vendedor. A propagação reativa orientada a eventos (Signals) entrega notificação em milissegundos sem polling inútil.

## 4. Consequência

### Ganhos Reais:
- **Desacoplamento Total**: O catálogo de produtos não conhece a estrutura interna dos anúncios nem os detalhes de rede dos marketplaces.
- **Confiabilidade Sistêmica**: Qualquer mutação de estoque ou preço gera automaticamente a atualização dos anúncios correspondentes, independente do ponto de entrada do sistema.
- **Controle Fino de Execução**: O context manager `mute_sincronizacao_signals` fornece proteção contra *signal storms* e recursão indesejada em lote.

### Custos e Limitações Assumidas:
- **Depuração Indireta**: Fluxos baseados em eventos desacoplados tornam a rastreabilidade do fluxo de execução menos linear do que código procedural síncrono.
- **Necessidade de Disciplina de Threads**: O uso de `threading.local()` exige atenção em ambientes concorrentes com async/await ou multi-threading.

## 5. Commit

- **Hash Principal**: `06d7a33` — `feat(estoque): implementa broadcast multi-canal com clamping e politica de canal de origem (RF-08)`.
- **Hash de Refinamento de Signals e Lote**: `8284bc8` — `feat(anuncios): implementa Fase 2 de sincronizacao segura de estoque e preco com circuit breaker e signals`.
- **Hash de Reabertura de Pendência**: `fe29593` — `fix(catalogo,anuncios): reabre pendencia de sync sob alteracao fisica, badge acumulativo e decisao estrita em lote`.
