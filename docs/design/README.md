# Caderno de Design — Marco 1 (Consolidado da Equipe)
**Disciplina**: ILP-037 Técnicas de Programação II  
**Instituição**: FATEC Olímpia · Semestre Letivo 2026/2  
**Docente**: Prof. José Ceron Neto  
**Projeto**: Hub Central de Gestão e Integração de Marketplaces  
**Instrumento de Avaliação**: Caderno de Design (ADRs em `docs/design/`)

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

---

## 1. Visão Geral e Filosofia do Caderno

O **Marco 1** da disciplina avalia com exclusividade a **qualidade e a maturidade das decisões de design de software** tomadas pela equipe de engenharia. O objetivo primordial não é demonstrar se o código compila ou renderiza telas (escopo de disciplinas de desenvolvimento web), mas **fundamentar por que a arquitetura do sistema foi desenhada dessa maneira**.

Nosso Caderno de Design reúne as decisões estruturantes implementadas ao longo das **35 branches** do repositório Git. Cada decisão foi modelada segundo o formato rigoroso de **ADR (Architecture Decision Record)** em 5 seções obrigatórias, com ênfase máxima na **Alternativa Descartada**, demonstrando o porquê técnico de rejeitar soluções ingênuas ou mal projetadas.

---

## 2. Índice Mestre de ADRs (Architecture Decision Records)

| Identificador | Título da Decisão de Arquitetura | Padrão / Tema Central | Hash de Commit | Arquivo Markdown |
| :---: | :--- | :--- | :---: | :--- |
| **ADR 001** | Definição da Arquitetura do Sistema e Escopo de Domínio | Bounded Contexts / Modular Monolith | `04d3422` | [ADR-001-decisao-de-projeto.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-001-decisao-de-projeto.md) |
| **ADR 002** | Localização e Validação de Invariantes de Domínio no Model | Model Validation (`clean`) vs @property vs Forms | `4a4bbda` | [ADR-002-validacao-regras-de-negocio.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-002-validacao-regras-de-negocio.md) |
| **ADR 003** | Arquitetura de Isolamento Multi-tenant e RBAC Granular | Multi-tenancy Lógico e Controle de Acesso | `f49ce26` | [ADR-003-isolamento-multi-tenant-e-rbac.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-003-isolamento-multi-tenant-e-rbac.md) |
| **ADR 004** | Proteção Criptográfica de Tokens OAuth 2.0 em Repouso | Criptografia Simétrica Fernet vs Hashing | `476a938` | [ADR-004-seguranca-e-criptografia-de-credenciais-oauth.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-004-seguranca-e-criptografia-de-credenciais-oauth.md) |
| **ADR 005** | Adoção dos Padrões Strategy e Factory para Conectores | **Strategy Pattern** + **Factory Method** | `2ec1349` | [ADR-005-padrao-strategy-para-conectores-de-marketplaces.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-005-padrao-strategy-para-conectores-de-marketplaces.md) |
| **ADR 006** | Propagação Reativa de Estoque via Django Signals | **Observer Pattern** (Publish-Subscribe) | `06d7a33` | [ADR-006-padrao-observer-signals-sincronizacao-estoque.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-006-padrao-observer-signals-sincronizacao-estoque.md) |
| **ADR 007** | Resiliência contra Oscilações Anômalas de Preço e Zeramento | **Circuit Breaker Pattern** | `8284bc8` | [ADR-007-padrao-circuit-breaker-resiliencia-api.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-007-padrao-circuit-breaker-resiliencia-api.md) |
| **ADR 008** | Idempotência e Transações Atômicas em Webhooks de Vendas | Idempotency Key + **Pessimistic Locking** | `63d516f` | [ADR-008-idempotencia-transacoes-atomicas-webhooks.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-008-idempotencia-transacoes-atomicas-webhooks.md) |
| **ADR 009** | Modelagem de Kits de Produtos e Anúncios Comerciais | **Composite Pattern** (Composições N:M) | `56d4a7f` | [ADR-009-padrao-composite-anuncios-e-kits-produtos.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-009-padrao-composite-anuncios-e-kits-produtos.md) |
| **ADR 010** | Motor de Inteligência Financeira e Simulação de Margens | Domain Service / Separação de Custos | `86a17d2` | [ADR-010-motor-inteligencia-financeira-precificacao.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-010-motor-inteligencia-financeira-precificacao.md) |
| **ADR 011** | Máquina de Estados para Ciclo de Vida e Sincronização | **State Pattern** (Finite State Machine) | `34f5b3f` | [ADR-011-padrao-state-maquina-estados-ciclo-anuncios.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-011-padrao-state-maquina-estados-ciclo-anuncios.md) |
| **ADR 012** | Modo Híbrido, Simulação e Feature Flags de Ambiente | **Feature Toggle Pattern** / Mocking | `bee4786` | [ADR-012-mocking-modo-hibrido-feature-flags.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-012-mocking-modo-hibrido-feature-flags.md) |
| **ADR 013** | Segurança Defensiva de Apresentação e Governança de IA | Hardening Anti-Leakage / AI Governance | `d58cc2e` | [ADR-013-seguranca-defensiva-apresentacao-governanca.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/ADR-013-seguranca-defensiva-apresentacao-governanca.md) |

Consulte o mapeamento exaustivo de todas as 35 branches em:  
👉 [HISTORICO_GIT_MARCO1.md](file:///z:/home/oscar/projetos/django/hub_integracao_marketplaces/docs/design/HISTORICO_GIT_MARCO1.md)

---

## 3. As Cinco Seções Canônicas de Cada ADR

Todos os registros acima obedecem à estrutura obrigatória de cinco seções:
1. **Contexto**: O problema real de arquitetura ou regra de negócio enfrentado no Hub.
2. **Decisão**: A solução técnica adotada e como ela protege a regra invariante.
3. **Alternativa Descartada**: A solução que a equipe estudou e **rejeitou**, explicando tecnicamente por que ela seria inferior (limites do framework Django, segurança ou manutenção).
4. **Consequência**: O trade-off assumido (ganhos reais de engenharia vs custos e limitações).
5. **Commit**: O hash curto rastreável de 7 dígitos comprovando onde a decisão entrou no repositório.

---

## 4. Roteiro para a Arguição Oral do Marco 1 (Defesa Sem Consulta)

Para preparar os membros da equipe para as perguntas da banca examinadora (Prof. José Ceron Neto), este guia resume as defesas essenciais:

### 4.1. "Por que a validação de preço e estoque não pode usar `@property` com setter no Django?" (ADR 002)
> **Defesa**: *"O Django ORM depende de instâncias de `models.Field` para gerar migrations, inferir formulários automáticos (`ModelForm`), renderizar telas do Django Admin e montar queries SQL eficientes no banco via `.filter()`. O uso de `@property` substitui o descritor de campo por uma propriedade em memória Python: isso quebra o Django Admin e impede que o banco filtre registros por SQL na cláusula `WHERE`. Por isso, centralizamos a integridade no Model usando `validators=[MinValueValidator(...)]`, constraints no banco e validação composta no método `clean()`, garantindo proteção independente de o dado entrar por formulários, shell ou webhooks."*

### 4.2. "Onde e por que a equipe aplicou o padrão Strategy?" (ADR 005)
> **Defesa**: *"Aplicamos o padrão Strategy na comunicação com os canais externos através da classe abstrata `BaseMarketplaceConnector` (`apps/marketplaces/connectors/base.py`). Cada marketplace (Mercado Livre, Shopee, Amazon, Magalu) possui particularidades profundas de endpoints OAuth, schemas JSON e regras de paginação. Descartamos o uso de estruturas `if/elif` nas views porque violaria o Princípio Aberto/Fechado (OCP): para adicionar um quinto marketplace, teríamos que alterar arquivos já consolidados e arriscar quebrar integrações existentes. Com a Strategy combinada com a Factory (`get_connector_for_conta`), plugar um novo marketplace resume-se a criar uma nova classe derivada e registrá-la, mantendo o núcleo do sistema 100% intocado e altamente testável com Mocks."*

### 4.3. "Por que vocês usaram criptografia simétrica Fernet em vez de Hash para os tokens?" (ADR 004)
> **Defesa**: *"Porque funções de Hash (como SHA-256 ou Bcrypt) são matemáticas unidirecionais — ou seja, irreversíveis. O Hash é perfeito para senhas de login, mas completamente inviável para credenciais de integração com APIs. O Hub precisa enviar o token original legível no cabeçalho HTTP `Authorization: Bearer <token>` a cada chamada externa, além de enviar o `refresh_token` original para renovação. Se usássemos Hash, o token puro seria irrecuperável e nenhuma requisição funcionaria. Para evitar o risco inaceitável de salvar em texto puro, adotamos criptografia simétrica autenticada Fernet (AES-128 em modo CBC com HMAC-SHA256), decifrando os segredos estritamente na memória RAM no momento do despacho da requisição."*

### 4.4. "Como o sistema previne venda sem estoque (overselling) durante picos concorrentes?" (ADR 008)
> **Defesa**: *"Combinamos três mecanismos transacionais: (1) **Idempotência estrita** por chave composta `(loja, canal, pedido_id_externo)` para evitar que reenvios de webhook debitem estoque duas vezes; (2) **Unit of Work** via `transaction.atomic()` para que todas as alterações sejam ACID; e (3) **Lock pessimista concorrente** via `Produto.objects.select_for_update()`. Quando uma venda chega, a linha do produto no banco é travada até o commit da transação, serializando as deduções e eliminando condições de corrida (race conditions) mesmo sob centenas de requisições simultâneas."*

### 4.5. "Como um mesmo estoque físico pode atender a anúncios avulsos e kits promocionais?" (ADR 009)
> **Defesa**: *"Adotamos o padrão Composite desacoplando a entidade física `Produto` da entidade comercial `Anuncio` através da tabela intermediária `AnuncioComposicao`. O estoque anunciado é calculado em tempo de execução usando o algoritmo de gargalo, dividindo o saldo físico de cada componente pelo seu multiplicador e selecionando o menor valor inteiro. Quando uma venda de kit acontece, o webhook debita atômica e proporcionalmente cada produto físico, e o sinal do Observer recalcula e propaga a nova cota para todos os outros anúncios unitários e kits que compartilham aquele item."*
