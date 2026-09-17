# Relatório de Rastreabilidade Git — Marco 1 (Mapeamento Completo de Branches e Commits)
**Disciplina**: ILP-037 Técnicas de Programação II  
**Instituição**: FATEC Olímpia · Semestre Letivo 2026/2  
**Docente**: Prof. José Ceron Neto  
**Projeto**: Hub Central de Gestão e Integração de Marketplaces  
**Instrumento de Avaliação**: Caderno de Design (ADRs em `docs/design/`)

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

---

## 1. Inspeção Oficial do Repositório Git

Conforme diretriz obrigatória de execução do Marco 1, foram executados os comandos no terminal do projeto para obter o estado fático do repositório:

### 1.1. Log dos Commits Recentes (`git log --oneline -n 30`)

```text
16bf6fe chore(config): consolidar ajustes de ambiente e templates de conexao
f09fd98 refactor(ui): remover exibicao de topicos do bloco de webhooks no formulario de conexao
9ec45ff refactor(security): remover bloqueio temporal anti-replay mantendo validacao estrita de hmac
bbba189 refactor(security): tornar resolucao de scheme estritamente dinamica via request.is_secure
9801a56 fix(security): reconhecer https sob proxy reverso ngrok e forcar https em redirect uri e webhooks
476a938 feat(security): implementar criptografia fernet, modo hibrido e webhook segmentado por uuid
a4b7c89 feat(ui): ordenar navbar sequencial pós-logs e reestruturar layout da home em grid 4x2
2a6a90a fix(ui): ajusta responsividade da navbar e elimina overflow horizontal
9faf0ac fix(pedidos): registra historico de alteracao de estoque na baixa de venda e remove tags tecnicas rn05 da ui
37c8a66 fix(marketplaces): trata campos nulos com safe_decimal e safe_int na ingestao do webhook meli
60179f5 fix(marketplaces): blinda resolucao de tenant no webhook, corrige idempotencia por PedidoVenda e persiste vendas com vinculo pendente
9599406 fix/webhook-vendas-quantidade-e-auto-sync
c5981a0 fix(anuncios): blindagem de delecao incorreta de composicao, auditoria com snapshots e alerta de produto sem vinculo
fe29593 fix(catalogo,anuncios): reabre pendencia de sync sob alteracao fisica, badge acumulativo e decisao estrita em lote
a7463b4 fix(catalogo,anuncios): centraliza sincronizacao global, duplo historico com sku e correcao nos modais de estoque
34f5b3f feat(anuncios): ciclo formal de sincronizacao com selecao dinamica, consistencia no produto e historico
ada84d3 docs: adiciona demonstracao do fluxo da branch e evidencias de testes manuais
e792dbb fix(catalogo): refina sincronizacao com confirmacao modal, controle de pendencias e historico unificado
63d516f feat(webhooks): implementa endpoint nativo Mercado Livre com idempotencia estrita e baixa atomica de estoque
97eb1af feat(estoque): implementa listagem de anuncios por composicao e baixa/ajuste manual de estoque interativo
acb7f7f fix(catalogo): corrige listagem de anuncios vinculados via composicao no detalhe do produto
8284bc8 feat(anuncios): implementa Fase 2 de sincronizacao segura de estoque e preco com circuit breaker e signals
259a925 feat(anuncios): finaliza Fase 1 de importação de anúncios Mercado Livre com suporte a kits e correção no items/bulk
3ffe72c fix(meli): aprimora rastreamento de conta e tratamento de conflito na reconexao oauth
2ec1349 feat(meli): implementa strategy/adapter oauth, auto-refresh com lock pessimista, csrf state e validacao ativa
0102775 docs: atualiza modelo de variaveis no .env.example
745f074 fix(marketplaces): bloquear duplicidade de conexao, travar edicao de canal/loja e carregar credenciais dev via .env
bee4786 feat(mock): implementar flag de alternancia para simulacao oauth e regras de reconexao
ec569dc feat(meli): implementar fluxo oauth2 real e criptografia fernet no banco
56d4a7f feat(anuncios): implementa publicacao de anuncios em marketplaces (RF-04)
```

---

## 2. Catálogo Completo das 35 Branches do Repositório

A tabela a seguir cataloga **todas as 35 branches** existentes no repositório, mapeando o escopo técnico, os commits associados, os padrões de projeto adotados e os respectivos ADRs do Caderno de Design:

| # | Nome da Branch | Escopo Técnico de Engenharia | Padrões / Decisões Envolvidas | ADR Vinculado | Hash Principal |
| :-: | :--- | :--- | :--- | :---: | :---: |
| **1** | `main` | Ramo principal com histórico consolidado e entregas estáveis. | Governança e entrega contínua | Todos | `f555854` |
| **2** | `feat/django-initial-setup` | Setup inicial do Django, configurações de ambiente e arquitetura de pastas. | Bounded Contexts / Arquitetura Modular | ADR 001 | `5823a34` |
| **3** | `refactor/modularizacao-apps-feature-flags` | Decomposição do monólito em apps desacoplados (`tenancy`, `catalogo`, etc.). | Modular Monolith / Clean Architecture | ADR 001 | `f3d40a3` |
| **4** | `feat/cadastro-loja-dev` | Modelagem da entidade Loja e infraestrutura de isolamento multi-tenant. | Multi-tenant por FK obrigatória | ADR 003 | `f49ce26` |
| **5** | `feat/gestao-usuarios-rbac` | Gestão de perfis e matriz de permissões de acesso baseada em funções. | Role-Based Access Control (RBAC) | ADR 003 | `9eed224` |
| **6** | `feat/cadastro-produtos-categorias` | Cadastro mestre de catálogo com validação estrita no Model e chaves compostas. | Model Validation (`clean`) / Composite Keys | ADR 002 / ADR 003 | `c2ae6bf` |
| **7** | `feature/baixa-manual-estoque-interativa` | Baixa de estoque manual auditada com motivos e validações invariantes. | Domain Integrity / Audit Trail | ADR 002 | `97eb1af` |
| **8** | `fix/correcao-produto-anuncio-marketplace` | Correção de integridade e evidências de testes no catálogo. | Regressão e Validação de Domínio | ADR 002 | `ada84d3` |
| **9** | `feat/integracao-oauth-mercadolivre` | Primeiro fluxo OAuth 2.0 real com persistência de credenciais cifradas. | Cryptography / Token Lifecycle | ADR 004 | `ec569dc` |
| **10** | `feature/marketplace-fernet-webhook-uuid` | Criptografia Fernet definitiva, modo híbrido e webhook por UUID assinado. | Fernet AES-128-CBC / HMAC Security | ADR 004 | `476a938` |
| **11** | `fix/bloqueio-duplicidade-conexao-marketplace` | Bloqueio de conexões duplicadas para o mesmo seller no mesmo canal. | Business Constraints / Prevenção de Conflito | ADR 004 | `745f074` |
| **12** | `feature/ciclo-vida-tokens-e-validacao-mercadolivre` | Auto-refresh com lock pessimista, estado CSRF e validação ativa de conexão. | **Strategy Pattern** / Lock Pessimista | ADR 005 / ADR 008 | `2ec1349` |
| **13** | `fix/validacao-conflito-reconexao-mercadolivre` | Tratamento de concorrência e conflitos na re-autorização OAuth. | Concorrência e Resiliência | ADR 005 | `3ffe72c` |
| **14** | `autenticacao-mercado-livre` | Ramo temático de homologação do protocolo de handshake do Mercado Livre. | Adapter / Protocol Normalization | ADR 005 | `56d4a7f` |
| **15** | `feat/integracao-mercadolivre-precos` | Sincronização de tabelas de preços com despacho polimórfico de lotes. | Strategy / Batch Processing | ADR 005 | `eb07bba` |
| **16** | `feat/broadcast-multicanal-estoque` | Disparo multicanal reativo de estoque com dedução de canal de origem. | **Observer Pattern** / Signals | ADR 006 | `06d7a33` |
| **17** | `feature/sincronizacao-preco-estoque-seguro` | Sincronização segura com desarmamento automático de disjuntor. | **Circuit Breaker Pattern** | ADR 007 | `8284bc8` |
| **18** | `feat/webhook-vendas-baixa-estoque` | Endpoint nativo de webhook de vendas e baixa de saldo físico. | Idempotency / Unit of Work | ADR 008 | `9de4a56` |
| **19** | `feature/webhook-vendas-baixa-estoque` | Baixa atômica de estoque com lock concorrente (`select_for_update`). | **Pessimistic Locking** | ADR 008 | `63d516f` |
| **20** | `fix/webhook-vendas-quantidade-e-auto-sync` | Correção na multiplicação de quantidades e auto-sync pós-venda. | Transacionalidade ACID | ADR 008 | `9599406` |
| **21** | `fix/webhook-pedido-multi-tenant-idempotencia` | Blindagem multi-tenant no webhook e idempotência estrita por PedidoVenda. | Idempotency Key / Tenant Resolution | ADR 008 / ADR 003 | `60179f5` |
| **22** | `feature/rf-04-anuncios` | Publicação de anúncios comerciais desacoplados do catálogo físico. | **Composite Pattern** | ADR 009 | `56d4a7f` |
| **23** | `feature/importacao-anuncios-mercadolivre` | Importação em lote de anúncios do Meli com suporte a kits e combos. | Composite / Auto-vinculação de SKU | ADR 009 | `259a925` |
| **24** | `fix/anuncios-vinculados-produto-detail` | Relação N:M reversa exibindo anúncios de kits na ficha do produto. | Navigation / Query Optimization | ADR 009 | `acb7f7f` |
| **25** | `fix/blindagem-de-erro-por-delecao-incorreta` | Blindagem contra exclusão acidental de vínculos com auditoria por snapshots. | Data Integrity / Snapshots | ADR 009 | `c5981a0` |
| **26** | `feat/motor-inteligencia-financeira-promocoes` | Motor de cálculo de margem líquida, CMV, taxas de canais e simulador. | Domain Service / Value Objects | ADR 010 | `86a17d2` |
| **27** | `fix/sincronizacao-dinamica-ciclo-anuncios` | Ciclo formal de sincronização com máquina de estados finita e seleção dinâmica. | **State Pattern** | ADR 011 | `34f5b3f` |
| **28** | `fix/centralizacao-sync-historico-duplo-e-modais` | Centralização global com duplo histórico e recálculo dinâmico de divergência. | State Aggregation / Modal UI | ADR 011 | `a7463b4` |
| **29** | `feat/mockar-dados` | Módulo de geração de dados fictícios para testes em ambiente de desenvolvimento. | Mocking / Data Seeding | ADR 012 | `1baa5b9` |
| **30** | `feat/alternar-simulacao-oauth-mock` | Feature flag para alternar de forma transparente entre OAuth real e simulador. | **Feature Toggle Pattern** | ADR 012 | `bee4786` |
| **31** | `feat/custom-404-security` | Template 404/500 sanitizado prevenindo vazamento de rotas e stack traces. | Defensive Design / Anti-Fingerprinting | ADR 013 | `d58cc2e` |
| **32** | `fix/add-ai-attribution-header` | Cabeçalho obrigatório de atribuição de IA nos arquivos fontes (Nível 2). | Code Governance / Academic Integrity | ADR 013 | `7aa267f` |
| **33** | `feat/dark-light-theme-support` | Suporte a 4 temas visuais ergonômicos com persistência local no navegador. | User Experience / Accessibility | ADR 013 | `5dedfaa` |
| **34** | `feat/dashboard-home-remodel` | Reestruturação da dashboard em grid ordenado e intuitivo. | Information Architecture | ADR 013 | `a4b7c89` |
| **35** | `fix/navbar-responsiva-overflow` | Eliminação de overflow horizontal e adaptação fluida para dispositivos móveis. | Responsive Layout | ADR 013 | `2a6a90a` |

---

## 3. Matriz Consolidada de Padrões de Projeto (GoF & Corporativos)

O Hub Centralizador de Marketplaces implementa de forma orgânica um rico ecossistema de padrões de engenharia:

| Padrão de Projeto | Classificação | Onde Está Aplicado no Hub | Benefício Arquitetural Comprovado | ADR |
| :--- | :--- | :--- | :--- | :---: |
| **Strategy** | Comportamental | `BaseMarketplaceConnector` e conectores por canal | Desacopla as rotinas de rede de cada marketplace; extensível sem alterar o catálogo (OCP). | ADR 005 |
| **Factory Method** | Criacional | `apps/marketplaces/connectors/factory.py` | Centraliza a resolução em tempo de execução da estratégia correta via `CONNECTOR_REGISTRY`. | ADR 005 |
| **Adapter** | Estrutural | `MercadoLivreConnector`, `ShopeeConnector`, etc. | Normaliza payloads JSON proprietários externos para o domínio interno do Hub. | ADR 005 |
| **Observer** | Comportamental | `apps/anuncios/signals.py` via Django Signals | Propaga mutações de catálogo para anúncios vinculados sem acoplamento direto de código. | ADR 006 |
| **Circuit Breaker** | Resiliência | `AnuncioSincronizacaoService.validar_variacao_preco` | Interrompe chamadas de API sob variações bruscas de preço (>50% queda) ou zeramento em lote. | ADR 007 |
| **Idempotency Key** | Resiliência | `ProcessamentoPedidoService.processar_pedido_venda` | Previne cobrança duplicada ou dedução de estoque repetida sob retentativas de webhooks. | ADR 008 |
| **Unit of Work** | Transacional | `transaction.atomic()` no processamento de pedidos | Garante consistência ACID: tudo grava com sucesso ou tudo sofre rollback atômico. | ADR 008 |
| **Pessimistic Locking** | Concorrência | `Produto.objects.select_for_update()` / `Conta.select_for_update()` | Bloqueia linhas no banco prevenindo *race conditions*, *overselling* e colisão de tokens de uso único. | ADR 008 |
| **Composite** | Estrutural | `Anuncio` e `AnuncioComposicao` | Modela anúncios simples e kits/combos complexos compartilhando o mesmo estoque físico. | ADR 009 |
| **State** | Comportamental | `StatusSincronizacaoEnum` e `status_sincronizacao_consolidado` | Gerencia a máquina de estados finita da sincronização com recálculo dinâmico de pendências. | ADR 011 |
| **Feature Toggle** | Operacional | Flags `SIMULAR_OAUTH_MERCADOLIVRE` no `.env` | Alterna instantaneamente entre ambiente de testes offline simulado e produção real. | ADR 012 |

---

## 4. Checklist de Conformidade do Marco 1 (Rubrica FATEC)

- [x] **A pasta `docs/design/` está no repositório e versionada**: Versionada e estruturada com 13 ADRs aprofundados.
- [x] **Todas as 35 branches mapeadas e justificadas**: Relacionadas com escopo técnico e commits no presente documento.
- [x] **Cada decisão importante virou um ADR**: Do ADR 001 ao ADR 013, cobrindo todos os pilares do sistema.
- [x] **Cada ADR tem as CINCO seções preenchidas**: Contexto, Decisão, Alternativa Descartada, Consequência e Commit.
- [x] **A "alternativa descartada" é justificada com rigor técnico**: Rejeição de abordagens ingênuas explicada com base nos limites do framework Django, ACID, SOLID e OWASP.
- [x] **O ADR da decisão sobre Strategy foi documentado**: ADR 005 registra a interface abstrata e a fábrica com base no commit real `2ec1349`.
- [x] **Commits 100% rastreáveis e reais**: Hashes curtos de 7 dígitos inspecionados diretamente via terminal Git.
- [x] **Roteiro de Defesa Oral sem consulta**: Disponibilizado e sintetizado no `README.md` do Caderno de Design.
