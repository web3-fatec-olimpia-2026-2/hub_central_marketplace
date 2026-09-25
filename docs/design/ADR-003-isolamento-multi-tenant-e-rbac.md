# ADR 003 — Arquitetura de Isolamento Multi-tenant e Controle de Acesso Baseado em Funções (RBAC Granular)

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

O Hub Inteligente de Marketplaces foi concebido como uma plataforma de software como serviço (SaaS Multi-tenant). Nesse modelo, diferentes empresas/lojistas (*Tenants*) compartilham a mesma aplicação e banco de dados para gerenciar seus estoques, conexões e pedidos de marketplaces. 

O vazamento acidental de dados entre lojas (vazamento *cross-tenant*) — como um lojista visualizar o catálogo, as credenciais OAuth privadas de marketplaces ou o faturamento de outro concorrente — causaria danos catastróficos de privacidade, violação severa da LGPD e quebra irreparável de confiança comercial. Simultaneamente, dentro da organização de uma mesma loja, múltiplos colaboradores exercem funções distintas: enquanto administradores e supervisores precisam configurar chaves de API e gerenciar categorias, operadores operacionais de estoque devem registrar apenas baixas por avaria, sem autorização para reajustar tabelas de preços ou excluir registros mestres.

## 2. Decisão

A equipe decidiu implementar uma **arquitetura de isolamento multi-tenant lógico orientada a banco de dados compartilhado com segregação por chave estrangeira e restrições compostas**, complementada por um sistema de **Controle de Acesso Baseado em Funções (RBAC Granular)**:
1. **Chave Estrangeira Obrigatória**: Todas as entidades do domínio (`Categoria`, `Produto`, `ContaMarketplace`, `PedidoVenda`, `LogAuditoria`) possuem uma `ForeignKey` obrigatória não-nula para o modelo `Loja` (`apps.tenancy.models.Loja`).
2. **Unicidade Composta por Tenant**: Criação de índices e restrições de unicidade a nível de banco de dados (`unique_together = [['loja', 'sku']]` e `[['loja', 'slug']]`), garantindo que o mesmo SKU possa existir legitimamente em lojas diferentes sem conflito ou sobreposição.
3. **RBAC com Roles e Decorators Customizados**: Definição de perfis hierárquicos de acesso (`DEV`, `ADMIN`, `SUPERVISOR`, `USUARIO`) validados centralizadamente através de decorators de view (`@role_required`, `@tenant_required`) e checagem de permissões na camada de formulários e templates.
4. **Validação Cruzada de Integridade no `clean()`**: Os modelos validam programaticamente se entidades relacionadas pertencem estritamente à mesma loja (ex.: um `Produto` não pode ser associado a uma `Categoria` de outra loja).

## 3. Alternativa Descartada

A equipe avaliou e **descartou duas alternativas estruturais**:

### Alternativa 1: Arquitetura de Banco de Dados Separado por Tenant (*Database-per-tenant*) ou Schemas Separados (*PostgreSQL Schema-per-tenant* via `django-tenants`)
- **Por que foi descartada (Justificativa Técnica Profunda)**: A separação física por schemas dinâmicos ou bancos de dados isolados traria uma complexidade de infraestrutura desproporcional para o Marco 1 do projeto:
  - Exigiria roteamento dinâmico complexo de conexões no Django (`DATABASE_ROUTERS`).
  - Cada migração de schema (`migrate`) precisaria ser executada sequencialmente para cada tenant cadastrado, tornando o deploy e os testes automatizados excessivamente lentos.
  - O overhead de conexões simultâneas esgotaria os limites de recursos em ambientes de desenvolvimento e servidores em nuvem de menor porte.
  - Para o objetivo pedagógico de demonstrar modularidade, segurança e padrões de software, o isolamento lógico no mesmo banco de dados com chaves compostas oferece a mesma garantia de segurança lógica com muito maior manutenibilidade e agilidade de entrega.

### Alternativa 2: Confiar exclusivamente em filtros manuais nas Views (`.filter(loja=...)`) sem constraints no banco
- **Por que foi descartada (Justificativa Técnica)**: Deixar a responsabilidade de isolamento exclusivamente a cargo de filtros manuais escritos pelos desenvolvedores em cada view (`views.py`) é uma receita para falhas humanas críticas. Se uma única view esquecer o filtro `.filter(loja=...)` em uma consulta, ocorreria vazamento imediato de dados entre tenants. Além disso, sem as restrições compostas de unicidade no banco (`unique_together`), o banco permitiria colisões acidentais de SKU e slugs entre lojas.

## 4. Consequência

### Ganhos Reais:
- **Alta Performance e Simplicidade Operacional**: Um único schema de banco de dados, migrações atômicas instantâneas (`python manage.py migrate`) e suporte nativo em qualquer banco relacional (SQLite em desenvolvimento, PostgreSQL em produção).
- **Segurança em Profundidade**: O isolamento é garantido tanto no banco de dados (chaves compostas), quanto na camada de domínio (`clean()`) e na camada de controle (decorators de autorização).
- **Granularidade Operacional**: Perfis bem delimitados evitam que operadores comuns realizem ações destrutivas ou acessem credenciais sensíveis.

### Custos e Limitações Assumidas:
- **Disciplina Rigorosa de QuerySets**: Todos os serviços e consultas de listagem precisam ser estritamente filtrados pelo tenant ativo da sessão (`request.user.perfil.loja`), mitigado pelo uso padronizado de mixins e queries encapsuladas.

## 5. Commit

- **Hash Principal**: `f49ce26` — `feat(core): implementar cadastro e gestao multi-tenant de lojas com rbac` (Criação do modelo de Lojas, permissões RBAC e isolamento multi-tenant base).
- **Hash de Extensão ao Catálogo**: `c2ae6bf` — `feat: implementacao do modulo de cadastro de produtos e categorias (RF-03) com isolamento multi-tenant e RBAC granular` (Aplicação de chaves compostas e filtros multi-tenant em produtos e categorias).
