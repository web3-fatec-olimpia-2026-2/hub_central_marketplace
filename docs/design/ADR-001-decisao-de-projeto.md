# ADR 001 — Definição da Arquitetura do Sistema e Escopo de Domínio [Hub Inteligente de Marketplaces]

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

No início da disciplina ILP-037 (Técnicas de Programação II) na FATEC Olímpia, a equipe foi incumbida de conceber e estruturar uma solução de software orientada a objetos de alta maturidade arquitetural. Durante a fase de ideação, foram analisadas duas propostas de projeto viáveis:
1. **Gerenciador de Campanhas de Marketing Digital**: software voltado à alocação de orçamentos, monitoramento de métricas analíticas de tráfego pago (CTR, CPC, conversões) e disparo de campanhas em redes sociais.
2. **Hub Inteligente de Integração de Marketplaces**: plataforma SaaS multi-tenant responsável por centralizar o catálogo mestre de produtos, controlar estoque físico com prevenção de overselling, precificação dinâmica e sincronização bidirecional com canais externos de e-commerce (Mercado Livre, Shopee, Amazon, Magalu).

O desafio arquitetural consistia em selecionar um escopo de domínio que comportasse de forma natural, coesa e profunda os padrões de projeto estruturais e comportamentais do currículo de Engenharia de Software (Strategy, Factory, Adapter, Observer/Signals, RBAC e Multi-tenancy), permitindo o desenvolvimento modular e entregas incrementais bem definidas ao longo dos Marcos de avaliação.

## 2. Decisão

A equipe decidiu pela concepção e desenvolvimento do **Hub Inteligente de Integração de Marketplaces**, adotando uma arquitetura em camadas modular orientada a contextos delimitados (*Bounded Contexts*) no framework Django. 

O sistema foi particionado em submódulos de domínio independentes:
- `apps.tenancy`: isolamento lógico de contas multi-loja e permissões corporativas.
- `apps.catalogo`: fonte única da verdade (*Single Source of Truth*) para produtos, precificação e inventário físico.
- `apps.marketplaces`: gestão de credenciais OAuth 2.0 cifradas e conectores polimórficos de comunicação externa.
- `apps.anuncios`: ciclo de vida de publicação comercial, composição de anúncios simples e kits de produtos.
- `apps.pedidos`: ingestão assíncrona de vendas via webhooks com baixa atômica de estoque e tratamento de idempotência.
- `apps.financeiro`: simulação de margens de lucro, tarifas de intermediação e inteligência de promoções.

## 3. Alternativa Descartada

A equipe avaliou e **descartou o desenvolvimento do Gerenciador de Campanhas de Marketing Digital**.

### Por que esta alternativa foi descartada (Justificativa Técnica Profunda):
1. **Natureza do Domínio e Acoplamento com APIs Analíticas**: O Gerenciador de Campanhas é um domínio prioritariamente analítico (*Read-Heavy* e baseado em agregação estatística de relatórios de terceiros como Google Ads e Meta Graph API). Isso exigiria pipelines pesados de ingestão de dados em lote (*Big Data / ETL*) e armazenamento em data warehouses, desviando o foco da disciplina, que preconiza a modelagem de domínio transacional de alta confiabilidade (*OLTP*), integridade de estado e padrões de design orientados a objetos.
2. **Limitação para Aplicação de Padrões Clássicos de Projeto**: Em um gerenciador de campanhas, a lógica de negócio fica diluída em chamadas assíncronas para ler métricas de relatórios consolidados. No Hub de Marketplaces, por outro lado, a variabilidade dos canais externos impõe a necessidade mandatória de padrões como:
   - **Strategy e Adapter**: para normalizar os protocolos díspares de comunicação de cada marketplace.
   - **Observer / Signals**: para propagar mutações físicas de estoque do catálogo para múltiplos canais instantaneamente (*broadcast*).
   - **Locks Concorrentes e Idempotência**: para blindar o sistema contra vendas concorrentes e *overselling*.
3. **Inviabilidade de Decomposição Modular Incremental**: As regras do Gerenciador de Campanhas eram fortemente acopladas entre orçamentos e relatórios, dificultando uma divisão limpa de tarefas entre os membros da equipe. Já o Hub de Marketplaces possibilitou uma divisão em microsserviços lógicos/apps semi-independentes, garantindo que o catálogo pudesse ser implementado, testado e validado de forma autônoma antes da integração com os canais externos.

## 4. Consequência

### Ganhos Reais (O que o sistema ganhou):
- **Desacoplamento e Coesão**: Cada aplicativo Django (`apps.*`) possui responsabilidades bem definidas, facilitando a criação de suítes de testes unitários e de integração totalmente isoladas.
- **Entregas Incrementais por Marcos**: Permitiu cumprir os marcos acadêmicos com segurança estrutural (Marco 1 focado em Catálogo, Multi-tenancy, RBAC, Criptografia e Design Patterns).
- **Paralelização de Desenvolvimento**: A equipe trabalhou simultaneamente em branches temáticas com baixíssimo índice de conflitos de merge.

### Custos e Limitações Assumidas (O que custou):
- **Complexidade Inicial de Setup**: Exigiu um desenho arquitetural detalhado prévio para definição de contratos de dados, enums globais e eventos de integração entre os apps.
- **Consistência de Dados Distribuída**: Por integrar sistemas externos via HTTP, a aplicação precisa gerenciar cenários de falhas de rede, retentativas e concorrência na sincronização de inventário.

## 5. Commit

- **Hash Principal**: `04d3422` — `:books: Rename File` (Fixação formal do escopo do Hub Inteligente de Marketplaces e consolidação inicial da documentação de design).
- **Hash Complementar de Infraestrutura**: `5823a34` — `chore(core): configurar arquitetura inicial do django, ambiente e especificacoes`.
