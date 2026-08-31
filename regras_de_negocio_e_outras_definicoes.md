# regras_de_negocio_e_outras_definicoes.md — Regras de Negócio, Multi-Tenant, RBAC e Definições Funcionais

**Projeto:** Hub Central de Gestão e Integração de Marketplaces
**Versão:** 1.0 (MVP)
**Ambiente:** WSL 2 (Ubuntu) em `~/projetos/django/<nome_do_projeto>/`
**Diretrizes Superiores:** `AGENT_INSTRUCTIONS_DJANGO.md` (padrão global de ambiente) → `PROJECT_SPEC.md` (arquitetura técnica) → **este documento** (domínio, RBAC, RF/RN)

---

## 0. Nota de Consolidação e Precedência

Este é o arquivo referenciado pela Seção 7 do `PROJECT_SPEC.md` como fonte **exclusiva** de escopo funcional, regras de negócio (RN), requisitos funcionais (RF) e modelagem de domínio. Ele consolida em uma única fonte:

- A visão de arquitetura e o escopo de MVP descritos em `Documentacao_Alinhamento_Hub.txt`;
- O rascunho técnico de domínio (matriz RBAC, RF, RN, modelagem preliminar) previamente esboçado como `regras_de_negocio.md`;
- As definições adicionais de multi-tenancy e hierarquia de perfis de acesso fornecidas pela equipe.

**Regra de precedência:** este documento **não** define nada sobre ambiente, isolamento de máquina, Git, `.venv` ou segredos — isso é responsabilidade exclusiva do `AGENT_INSTRUCTIONS_DJANGO.md`. Também não redefine o padrão visual, a estrutura de pastas ou a Definition of Done — isso permanece em `PROJECT_SPEC.md`. Em caso de dúvida sobre "onde" algo deve ser implementado (camada, pasta, padrão de botão), consulte `PROJECT_SPEC.md`; em caso de dúvida sobre "o que" o sistema deve fazer e "quem" pode fazer o quê, a fonte é este arquivo.

---

## 1. Visão Geral do Negócio

O sistema é um **Hub Centralizador Multi-Tenant** para gestão de catálogo, preços e estoque, atuando como **Fonte Única da Verdade (Single Source of Truth)** para múltiplas lojas (tenants), sem depender de integração com ERP.

Cada loja cadastrada no Hub mantém seus próprios produtos, categorias, usuários e credenciais de integração com marketplaces, de forma isolada das demais lojas.

O canal de integração prioritário do MVP é o **Mercado Livre** ([developers.mercadolivre.com.br](https://developers.mercadolivre.com.br/pt_br)). A arquitetura de domínio, entretanto, é desenhada para comportar múltiplos canais simultaneamente (Shopee e Magalu estão no backlog — Seção 13), replicando o mesmo fluxo:

```text
                     ┌────────────────────────────┐
                     │        HUB CENTRAL          │
   Dados do Produto  │  (Fonte única da verdade)   │  Envio do fluxo de dados
   Atualização Preço │                              │─────────────────────────▶ Mercado Livre
   Estoque           │   Loja A · Loja B · Loja C   │─────────────────────────▶ Shopee (backlog)
                     │                              │─────────────────────────▶ Magalu (backlog)
                     └──────────────▲───────────────┘
                                    │
                     Webhook de venda / pedido (RF-06)
                                    │
                            Marketplace integrado
```

Sem ERP, **toda** manutenção de dados (preço, estoque, descrição) ocorre manualmente ou via automações internas do próprio Hub — não há sincronização automática com nenhum sistema externo de gestão.

---

## 2. Modelo Multi-Tenant (Lojas)

### 2.1. Conceito de Tenant

Cada **Loja** cadastrada é um tenant isolado. Nenhuma entidade de domínio (usuário, produto, categoria, log) pode ser lida, criada ou alterada fora do escopo da própria loja — exceto pelo perfil `DEV`, que possui visão global.

### 2.2. Exemplo Ilustrativo

O exemplo abaixo é apenas didático, para fixar o conceito de isolamento — não representa dados reais:

| Loja (Tenant) | Slug | Usuários vinculados (exemplos) | Visibilidade cruzada |
|---|---|---|---|
| Loja A | `loja-a` | 1 ADMIN, 1 SUPERVISOR, N USUÁRIO | Loja A não enxerga dados de B/C |
| Loja B | `loja-b` | 1 ADMIN, N USUÁRIO | Loja B não enxerga dados de A/C |
| Loja C | `loja-c` | 1 ADMIN, 1 SUPERVISOR, N USUÁRIO | Loja C não enxerga dados de A/B |
| — | — | Usuário(s) `DEV` | Enxerga e opera em A, B e C |

### 2.3. Isolamento de Dados (ver RN-01)

Toda consulta feita por managers/views deve filtrar obrigatoriamente por `loja=request.user.perfil.loja`, exceto quando `request.user.perfil.papel == 'DEV'`. Esse filtro é mandatório em produtos, categorias, histórico de preços e logs de sincronização/auditoria.

### 2.4. Escopo de Cadastro de Loja

O **cadastro, edição e ativação de uma nova Loja (tenant)** — incluindo o registro das credenciais de integração com o Mercado Livre (`meli_client_id`, `meli_client_secret`, tokens) — é uma operação restrita **exclusivamente ao perfil `DEV`**. Nenhum outro perfil, incluindo `ADMIN`, pode criar ou desativar uma loja. Isso é intencional: `ADMIN` administra o conteúdo *dentro* de uma loja já provisionada, mas o provisionamento do tenant em si é uma operação de escopo geral do sistema (RF-01).

---

## 3. Perfis de Usuário e RBAC (Grupos de Utilizadores)

### 3.1. Princípio de Exclusividade

Todo usuário do sistema (`auth.User`) **deve** estar vinculado a exatamente **um** registro de perfil (`PerfilUsuario`), com exatamente **um** papel entre `DEV`, `ADMIN`, `SUPERVISOR` e `USUARIO` (ver RN-03). Não existe usuário sem papel, nem usuário com mais de um papel simultâneo.

### 3.2. Definição dos Perfis

**DEV — Escopo Geral (todas as Lojas)**
Acesso irrestrito, tanto em definições de desenvolvimento (Django Admin, configuração técnica, criação de tenants) quanto em qualquer regra administrativa que venha a ser definida em qualquer loja. É o único perfil que enxerga e atua sobre múltiplas lojas simultaneamente. `loja` é `null` neste perfil, pois seu escopo não é vinculado a um único tenant.

**ADMIN — Escopo da Loja vinculada**
Acesso geral **dentro da sua própria loja**, incluindo qualquer regra administrativa definida para aquele tenant: gestão de usuários da loja (criar/editar `SUPERVISOR` e `USUARIO`, mas nunca `DEV`), CRUD completo de produtos e categorias, alteração de preço/estoque e disparo de sincronização/publicação de anúncios.

**SUPERVISOR — Escopo intermediário**
Acesso intermediário entre `ADMIN` e `USUÁRIO`, dentro da sua própria loja: pode visualizar usuários (mas não criar/editar/desativar), tem CRUD completo de produtos e categorias, altera preço e estoque, e pode disparar sincronização e publicação de anúncios. Não gerencia usuários nem configura credenciais de integração da loja.

**USUÁRIO — Escopo restrito**
O perfil com maiores restrições, dentro da sua própria loja: sem qualquer acesso à gestão de usuários; pode criar e editar produtos e categorias, porém com restrições (ver 3.3 e Seção 5); não altera preço de venda (apenas visualiza); pode realizar apenas uma baixa pontual de estoque (ex.: registro de avaria/perda), não ajustes gerais; visualiza logs de sincronização, mas não os dispara.

### 3.3. Matriz de Permissões por Ação

| Ação | DEV | ADMIN | SUPERVISOR | USUÁRIO |
|---|:---:|:---:|:---:|:---:|
| Criar / editar / desativar Loja (Tenant) | ✅ (global) | ❌ | ❌ | ❌ |
| Configurar credenciais de integração (Mercado Livre) da loja | ✅ | ✅ (só a própria) | ❌ | ❌ |
| Criar / editar usuário `ADMIN` | ✅ | ❌ | ❌ | ❌ |
| Criar / editar usuário `SUPERVISOR` ou `USUARIO` | ✅ | ✅ (só na própria loja) | ❌ | ❌ |
| Visualizar lista de usuários da loja | ✅ | ✅ | ✅ (view only) | ❌ |
| Criar / editar Categoria de Produto | ✅ | ✅ | ✅ | ✅ (com restrições, §5.3) |
| Criar / editar Produto (dados descritivos: nome, SKU, descrição, categoria) | ✅ | ✅ | ✅ | ✅ (com restrições, §5.3) |
| Excluir Produto / Categoria | ✅ | ✅ | ✅ | ❌ |
| Alterar Preço de Venda | ✅ | ✅ | ✅ | ❌ (visualiza apenas) |
| Ajustar Estoque (entrada/correção geral) | ✅ | ✅ | ✅ | ❌ (visualiza apenas) |
| Baixa pontual de estoque (avaria/perda) | ✅ | ✅ | ✅ | ✅ |
| Disparar publicação de anúncio no marketplace | ✅ | ✅ | ✅ | ❌ |
| Disparar sincronização manual (preço/estoque) | ✅ | ✅ | ✅ | ❌ |
| Visualizar Logs de Sincronização / Auditoria | ✅ (todas as lojas) | ✅ (própria loja) | ✅ (própria loja) | ✅ (própria loja, view only) |
| Acessar Django Admin | ✅ | ❌ | ❌ | ❌ |

> Esta matriz é a fonte oficial de decisão para `@login_required` + checagem de papel em views, e para os testes de **Ownership Check** exigidos em `PROJECT_SPEC.md` (Seção 5).

### 3.4. Regras de Atribuição de Papel

- Somente `DEV` pode atribuir o papel `DEV` a um usuário.
- `ADMIN` só pode criar/editar usuários com papel `SUPERVISOR` ou `USUARIO`, e apenas dentro da própria loja.
- Nenhum usuário pode alterar o próprio papel.
- A troca de papel de um usuário deve gerar registro em `LogAuditoria`.

---

## 4. Cadastro de Usuários — Regras Específicas (RF-02)

- Toda conta de usuário é obrigatoriamente vinculada a **uma única Loja** e a **um único papel**, exceto o papel `DEV`, cuja `loja` é `null` (escopo global).
- `PerfilUsuario` possui relação `OneToOne` com `auth.User` — um usuário Django nunca pode ter mais de um perfil ativo (RN-03).
- O cadastro de usuário dentro de uma loja é permitido a `DEV` (qualquer loja) e a `ADMIN` (apenas a sua própria loja), conforme a matriz da Seção 3.3.
- `SUPERVISOR` e `USUÁRIO` não possuem, em nenhuma hipótese, acesso à criação ou edição de outros usuários.

---

## 5. Cadastro de Produtos e Categorias — Regras Específicas (RF-03)

### 5.1. Campos Mínimos do Produto

`id` (interno), `sku`, `nome`, `descricao`, `preco` (base), `estoque` (saldo), `status`, `categoria` (FK), `loja` (FK), `meli_item_id` (ID do anúncio vinculado no Mercado Livre), `status_sincronizacao`.

### 5.2. Regras de Unicidade e Validação

- **RN-02:** `sku` é único por loja (`unique_together = ['loja', 'sku']`) — lojas diferentes podem reutilizar o mesmo SKU sem conflito.
- **RN-06:** nenhum produto pode ser salvo ou sincronizado com `preco <= 0` ou `estoque < 0`.

### 5.3. Restrições do Perfil `USUÁRIO` sobre Produtos/Categorias

O perfil `USUÁRIO` pode criar e editar os campos **descritivos** do produto (nome, SKU, descrição, categoria, status), mas:

- **não** pode alterar `preco` (campo somente leitura para este perfil);
- **não** pode fazer ajuste geral de `estoque`, apenas registrar uma baixa pontual (ex.: perda/avaria), sempre com motivo obrigatório e registro em `LogAuditoria`;
- **não** pode excluir produtos ou categorias.

---

## 6. Integração com Marketplaces — Mercado Livre (Prioridade do MVP)

### 6.1. Ordem de Prioridade Funcional

A **primeira função ativa de integração** a ser implementada é a **Atualização de Preços** (RF-05) via API do Mercado Livre — ou seja, o fluxo de "Hub → Marketplace" (preço local mudou → `PUT /items/{item_id}`) tem prioridade de desenvolvimento sobre a publicação automatizada de novos anúncios (RF-04). A documentação oficial de referência é a [API do Mercado Livre](https://developers.mercadolivre.com.br/pt_br).

### 6.2. Credenciais por Loja

Cada Loja mantém suas próprias credenciais Mercado Livre (`meli_client_id`, `meli_client_secret`, `meli_access_token`, `meli_refresh_token`), reforçando o isolamento multi-tenant: nenhuma loja compartilha ou reutiliza credenciais de outra.

### 6.3. Publicação de Anúncios (RF-04)

Após a atualização de preços estar estável, o sistema deve automatizar o disparo e a criação de anúncios no(s) marketplace(s) integrados a partir do cadastro do produto no Hub.

### 6.4. Extensibilidade Futura

A camada de integração deve ser desenhada de forma desacoplada (ex.: um serviço por canal) para permitir a adição de Shopee e Magazine Luiza no futuro (Seção 13) sem reescrever a lógica central de preço/estoque.

---

## 7. Sincronização de Estoque (Event-Driven)

### 7.1. Webhook de Vendas (RF-06)

Endpoint público `/webhook/mercadolivre/` recebe notificações (`orders_v2` / `shipments`) do Mercado Livre. `services.processar_webhook_venda(payload)` valida autenticidade e identifica a Loja/Item correspondente.

### 7.2. Baixa Automática de Estoque (RF-07 / RN-05)

O abatimento do saldo deve ocorrer sob `transaction.atomic()` com `select_for_update()` para evitar condição de corrida:

```
Estoque Final = Estoque Atual − Quantidade Vendida
```

Se `Estoque Final < 0`, o sistema grava log com flag de alerta e **impede** a inconsistência no banco local (a operação não deve resultar em saldo negativo).

### 7.3. Broadcast Multi-Canal (RF-08)

Após a baixa local, o Hub dispara imediatamente a atualização do saldo remanescente para os demais marketplaces integrados àquele produto, evitando furos de estoque. No MVP, com apenas o Mercado Livre ativo, este passo é preparado arquiteturalmente, mas só terá efeito prático quando um segundo canal for integrado (backlog).

---

## 8. Regras de Negócio (RN) — Lista Consolidada

| ID | Regra |
|---|---|
| RN-01 | Isolamento multi-tenant rigoroso: toda entidade de domínio (Categoria, Produto, Variação, HistoricoPreco, LogSincronizacao, LogAuditoria) possui FK obrigatória para Loja; consultas filtram por `loja=request.user.perfil.loja`, salvo papel `DEV`. |
| RN-02 | Unicidade de SKU por loja: `unique_together = ['loja', 'sku']`. |
| RN-03 | Unicidade de perfil por usuário: um `auth.User` possui no máximo um `PerfilUsuario` ativo, com papel exclusivo entre `DEV`, `ADMIN`, `SUPERVISOR`, `USUARIO`. |
| RN-04 | Fonte única da verdade (sem ERP): nenhuma alteração de estoque/preço é aceita de fontes externas não autenticadas; toda alteração manual gera `LogAuditoria`. |
| RN-05 | Atomicidade na baixa de estoque via webhook, com `select_for_update()`; saldo negativo é bloqueado e logado como alerta. |
| RN-06 | Bloqueio de dados inválidos: nenhum produto é salvo/sincronizado com `preco <= 0` ou `estoque < 0`. |
| RN-07 | Criação de Loja (tenant) é operação exclusiva do perfil `DEV`. |
| RN-08 | Atribuição do papel `DEV` a um usuário é operação exclusiva de outro usuário `DEV`. |
| RN-09 | O perfil `USUÁRIO` não altera `preco` de produto nem faz ajuste geral de `estoque` — apenas baixa pontual justificada. |

---

## 9. Requisitos Funcionais (RF) — Lista Consolidada

| ID | Funcionalidade | Perfil Mínimo |
|---|---|---|
| RF-01 | Gestão de Tenants (Lojas): cadastro, edição e credenciais de integração Mercado Livre. | DEV |
| RF-02 | Gestão de Usuários: criação de contas vinculadas a uma loja e a um único papel. | ADMIN (loja) / DEV (global) |
| RF-03 | CRUD de Categorias e Produtos. | USUÁRIO (loja), com restrições — §5.3 |
| RF-04 | Publicação / criação automatizada de anúncios no Mercado Livre. | SUPERVISOR (loja) |
| RF-05 | Atualização de Preços no marketplace (primeira função ativa — §6.1). | SUPERVISOR (loja) |
| RF-06 | Webhook de Vendas: endpoint público para eventos `orders_v2` / `shipments`. | Sistema / Externo |
| RF-07 | Baixa automática de estoque após evento de venda. | Sistema / Services |
| RF-08 | Sincronização multi-canal (broadcast) de saldo remanescente. | Sistema / Services |

---

## 10. Modelagem de Dados Preliminar (models.py)

**Loja (Tenant)**
`nome` (CharField), `slug` (SlugField, unique), `ativo` (BooleanField), `criado_em` (DateTimeField), `meli_client_id`, `meli_client_secret`, `meli_access_token`, `meli_refresh_token`.

**PerfilUsuario**
`usuario` (OneToOneField → `auth.User`, cascade), `loja` (ForeignKey → Loja, `null=True` apenas para papel `DEV`), `papel` (CharField, choices: `DEV`, `ADMIN`, `SUPERVISOR`, `USUARIO`).

**Categoria**
`loja` (FK), `nome` (CharField), `slug` (SlugField).

**Produto**
`loja` (FK), `categoria` (FK), `sku` (CharField), `nome` (CharField), `descricao` (TextField), `preco` (DecimalField), `estoque` (IntegerField), `meli_item_id` (CharField), `status_sincronizacao` (CharField, choices).

**LogSincronizacao / LogAuditoria**
`loja` (FK), `produto` (FK), `evento` (CharField), `payload` (JSONField), `status` (CharField), `criado_em` (DateTimeField).

---

## 11. Fluxos de Serviços (services.py)

**Atualização Manual de Preço**
1. `ADMIN`/`SUPERVISOR` edita o preço via formulário validado (`forms.py`).
2. `services.atualizar_preco_produto(produto, novo_preco, usuario)` grava histórico sob transação atômica.
3. Dispara `PUT /items/{item_id}` para a API do Mercado Livre.
4. Registra retorno em `LogSincronizacao` e atualiza status na interface.

**Webhook de Vendas (Event-Driven)**
1. Endpoint `/webhook/mercadolivre/` recebe notificação JSON.
2. `services.processar_webhook_venda(payload)` valida autenticidade e identifica Loja/Item.
3. Executa `Produto.objects.select_for_update()` sob `transaction.atomic()` e abate a quantidade vendida.
4. Dispara atualização de estoque para os demais anúncios/marketplaces vinculados (RF-08).

---

## 12. Ordem de Prioridade de Implementação (Roadmap do MVP)

1. CRUD de Loja (Tenant) — escopo `DEV` (RF-01).
2. Cadastro de Usuários com RBAC (RF-02).
3. Cadastro de Produtos e Categorias (RF-03).
4. **Integração Mercado Livre — Atualização de Preços** (RF-05) — primeira função ativa de integração externa.
5. Publicação automatizada de Anúncios (RF-04).
6. Webhook de Vendas e Baixa Automática de Estoque (RF-06 / RF-07).
7. Broadcast Multi-Canal (RF-08) — efeito pleno apenas com um segundo marketplace integrado.

---

## 13. Backlog Futuro (Fora do Escopo do MVP)

- **Motor de Inteligência Financeira:** validação algorítmica de viabilidade de campanhas promocionais, cruzando preço de venda, taxas da plataforma, custos fixos/variáveis e margem líquida.
- **Integração com Novos Canais:** conectores para Shopee e Magazine Luiza, reutilizando a arquitetura desacoplada de integração (§6.4).
- **Módulo de Conciliação Financeira:** fechamento de repasses de marketplaces e taxas de envio.

---

## 14. Relação com Outros Documentos do Projeto

| Assunto | Onde consultar |
|---|---|
| Ambiente, Git, `.venv`, segredos, fluxo de branches/PR | `AGENT_INSTRUCTIONS_DJANGO.md` |
| Estrutura de pastas, `settings.py`, padrão visual (Bootstrap), Estratégia de Testes, Definition of Done | `PROJECT_SPEC.md` |
| Domínio, RBAC, multi-tenant, RF/RN, modelagem, fluxos de serviço | Este documento |

---

## 15. Registro de Alterações

### v1.0
- Consolidação inicial a partir de `Documentacao_Alinhamento_Hub.txt`, do rascunho técnico anterior (`regras_de_negocio.md`) e das definições adicionais de multi-tenancy e hierarquia de perfis (`DEV`, `ADMIN`, `SUPERVISOR`, `USUARIO`).
- Adicionada Matriz de Permissões por Ação (§3.3).
- Adicionada Ordem de Prioridade de Implementação (§12), definindo a Atualização de Preços via Mercado Livre como primeira função ativa de integração.
- Explicitada a restrição de criação de Loja (tenant) ao perfil `DEV` (RN-07) e de atribuição do papel `DEV` a outro `DEV` (RN-08).
