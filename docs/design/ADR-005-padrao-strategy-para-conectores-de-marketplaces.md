# ADR 005 — Adoção do Padrão de Projeto Strategy e Factory para Conectores de Marketplaces

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

A proposta de valor central do Hub Inteligente de Marketplaces é unificar e automatizar a comunicação entre o catálogo mestre de produtos e múltiplos canais de venda externos (Mercado Livre, Shopee, Magazine Luiza, Amazon). 

Cada marketplace opera sob uma arquitetura própria e protocolos de comunicação amplamente divergentes:
- **Fluxos de Autorização e Renovação de Tokens**: Variações de parâmetros, headers e endpoints OAuth 2.0 (ex.: Mercado Livre exige `client_secret` no corpo da requisição POST, enquanto outros utilizam autenticação Basic).
- **Estruturas de Dados e Payloads de Catálogo**: Chaves JSON completamente diferentes para representar títulos, descrições, categorias externas e atributos obrigatórios de produtos.
- **Sincronização de Inventário e Preços**: Endpoints específicos para atualização pontual ou em lote (bulk) de preços e saldos físicos.
- **Tratamento de Rate Limits e Erros de API**: Códigos de status HTTP, estruturas de payload de erro e limites de requisição por segundo distintos.

Se os controladores (`views.py`) ou serviços de catálogo tentassem invocar diretamente as bibliotecas HTTP de cada marketplace, haveria uma proliferação de estruturas condicionais espalhadas por toda a base de código, tornando o sistema frágil, suscetível a erros de regressão e de manutenção proibitiva.

## 2. Decisão

A equipe decidiu implementar o padrão de projeto comportamental **Strategy** (GoF) em cooperação com o padrão criacional **Factory**:

1. **Definição da Interface Canônica da Estratégia (`BaseMarketplaceConnector`)**:
   - Localização: `apps/marketplaces/connectors/base.py`.
   - Criação de uma classe base abstrata derivada de `abc.ABC` que formaliza o contrato obrigatório universal de comunicação que qualquer conector de marketplace deve cumprir.
   - Métodos padronizados: `get_authorization_url()`, `exchange_code()`, `refresh_credentials()`, `get_valid_access_token()`, `test_connection()`, `atualizar_preco()`, `atualizar_estoque()`, `publicar_anuncio()`, `buscar_pedidos()` e `importar_anuncios()`.

2. **Implementação das Estratégias Concretas**:
   - Cada parceiro externo possui sua respectiva classe que herda de `BaseMarketplaceConnector` e implementa as particularidades de protocolo do canal:
     - `MercadoLivreConnector` (`apps/marketplaces/connectors/mercadolivre.py`)
     - `ShopeeConnector` (`apps/marketplaces/connectors/shopee.py`)
     - `MagaluConnector` (`apps/marketplaces/connectors/magalu.py`)
     - `AmazonConnector` (`apps/marketplaces/connectors/amazon.py`)

3. **Resolução Dinâmica via Factory Pattern (`get_connector_for_conta`)**:
   - Localização: `apps/marketplaces/connectors/factory.py`.
   - Utilização de um dicionário de mapeamento centralizado (`CONNECTOR_REGISTRY`), onde o conector adequado é instanciado em tempo de execução com base no enum `CanalMarketplaceEnum` da conta do lojista:
     ```python
     def get_connector_for_conta(conta: ContaMarketplace) -> BaseMarketplaceConnector:
         connector_cls = CONNECTOR_REGISTRY.get(conta.canal, MercadoLivreConnector)
         return connector_cls(conta=conta)
     ```
   - O restante do sistema (views de sincronização, webhooks e comandos de terminal) consome exclusivamente a interface polimórfica `BaseMarketplaceConnector`, desconhecendo completamente a implementação interna específica de cada canal.

## 3. Alternativa Descartada

A equipe analisou minuciosamente e **rejeitou duas abordagens arquiteturais inferiores**:

### Alternativa 1: Lógica procedural baseada em estruturas condicionais `if/elif/else` nas Views e Serviços
- **Por que foi descartada (Justificativa Técnica Profunda)**: Essa abordagem representa o clássico antipadrão de código acoplado e viola os princípios fundamentais do SOLID:
  - **Violação do Princípio Aberto/Fechado (OCP - *Open/Closed Principle*)**: Toda vez que a equipe precisasse plugar um novo marketplace (ex.: Shein ou TikTok Shop), seria mandatório abrir, alterar e retestar arquivos críticos de Views e serviços já consolidados. Qualquer modificação incorreta poderia derrubar as integrações do Mercado Livre ou Shopee que já estavam funcionando perfeitamente em produção.
  - **Violação do Princípio da Responsabilidade Única (SRP - *Single Responsibility Principle*)**: As views e serviços de sincronização ficariam sobrecarregados com conhecimentos de baixo nível sobre URLs, headers, payloads e peculiaridades de rede de quatro ou mais fornecedores externos distintos.
  - **Explosão da Complexidade Ciclomática**: O código se tornaria um emaranhado de blocos `if canal == 'mercadolivre': ... elif canal == 'shopee': ...`, tornando a escrita de testes unitários extremamente complexa e propensa a falhas.

### Alternativa 2: Modelagem por Herança Multi-tabela de Classes no Django ORM (`MercadoLivreConta`, `ShopeeConta`)
- **Por que foi descartada (Justificativa Técnica Profunda)**: Criar modelos Django separados via herança de classe (`models.Model`) para embutir métodos de integração de API diretamente nos modelos persistidos acopla indevidamente a camada de acesso a dados (Active Record) à camada de transporte e I/O de rede:
  - O Django ORM gera `JOINs` relacionais automáticos dispendiosos para herança de tabelas, degradando o tempo de resposta das consultas.
  - Polui o modelo de dados relacional com métodos de rede impuros (`requests.post`, retentativas de socket, parsing de JSON volátil).
  - Dificulta enormemente a injeção de Mocks e Stubs durante a execução de testes automatizados unitários, pois os métodos de rede ficariam atrelados às instâncias salvas no banco de dados.

## 4. Consequência

### Ganhos Reais:
- **Alta Extensibilidade (Plug-and-Play)**: O sistema está totalmente aberto para extensão e fechado para modificação. Para suportar um novo canal, basta criar uma nova subclasse de `BaseMarketplaceConnector` e registrá-la no `CONNECTOR_REGISTRY` em `factory.py`. Nenhuma linha do código de catálogo, estoque ou views precisa ser tocada.
- **Isolamento de Falhas e Manutenibilidade**: Bugs, mudanças de versão de API ou alterações de endpoints do Mercado Livre ficam estritamente contidos dentro do arquivo `mercadolivre.py`.
- **Testabilidade Excelente**: É possível criar implementações falsas (*MockConnectors*) em segundos para testar todo o fluxo de sincronização e transações de estoque do Hub sem realizar chamadas reais à internet.

### Custos e Limitações Assumidas:
- **Necessidade de Normalização de Contratos**: Exige esforço arquitetural contínuo para manter os contratos de entrada e saída (`LogSincronizacao`, dicionários normalizados) representativos de todos os canais, inclusive em cenários onde um marketplace específico não suporta determinada funcionalidade (ex.: kits compostos ou variação de atributos), resolvido através de retornos semânticos claros ou `NotImplementedError`.

## 5. Commit

- **Hash Principal**: `2ec1349` — `feat(meli): implementa strategy/adapter oauth, auto-refresh com lock pessimista, csrf state e validacao ativa` (Criação formal da classe base `BaseMarketplaceConnector`, implementações concretas e `factory.py`).
- **Hash de Consumo no Catálogo**: `8284bc8` — `feat(anuncios): implementa Fase 2 de sincronizacao segura de estoque e preco com circuit breaker e signals` (Consumo polimórfico das estratégias na sincronização em lote).
