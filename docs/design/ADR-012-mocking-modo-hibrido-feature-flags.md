# ADR 012 — Camada de Mocking, Modo Híbrido e Feature Flags para Simulação de Ambiente e Alternância OAuth

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

Durante o ciclo de desenvolvimento, testes contínuos (CI) e demonstrações acadêmicas do **Hub Inteligente de Marketplaces**, a dependência de chamadas HTTP ativas a servidores externos de terceiros (como o Mercado Livre) impõe obstáculos severos:
- Os servidores de autorização OAuth do Mercado Livre exigem domínios com certificado SSL HTTPS público válido para redirecionamento do callback (`redirect_uri`), o que exige túneis reversos (como `ngrok`) que expiram frequentemente e dependem de conexão com a internet.
- Limites de taxa de requisição (*Rate Limits*) e instabilidades das APIs de sandbox de marketplaces podem paralisar a esteira de testes automatizados unitários da equipe.
- Integrantes da equipe ou avaliadores da banca precisam testar a aplicação em ambientes locais offline ou sem credenciais comerciais reais de produção.

A equipe necessitava de uma estratégia arquitetural que permitisse alternar de forma transparente entre o modo de integração real com a nuvem e um modo de simulação em memória (*Mock/Hybrid Mode*), sem contaminar o código de negócio com código de teste.

## 2. Decisão

A equipe decidiu implementar uma arquitetura de **Simulação de Ambiente baseada no padrão Feature Toggle (Feature Flags) e Conectores Mock**:
1. **Feature Flags de Simulação via `.env`**:
   - `SIMULAR_OAUTH_MERCADOLIVRE`: Quando ativado (`True`), o sistema redireciona o fluxo de autorização OAuth para um formulário de consentimento interno simulado, gerando tokens sintéticos válidos com criptografia Fernet sem disparar requisições para a internet.
   - `MELI_SIMULATION_MODE`: Ativa geradores de payloads sintéticos de anúncios e webhooks de pedidos para validação completa de ponta a ponta.
2. **Conector Mock e Injeção de Dados de Homologação (`apps/core/mockar_dados.py`)**:
   - Módulo isolado e restrito ao modo de desenvolvimento (`DEBUG=True`), responsável por semear o banco com categorias realistas, produtos mestres e lojas de demonstração para testes rápidos de interface e carga.
3. **Modo Híbrido de Credenciais (`ContaMarketplace.modo_hibrido`)**:
   - Permite que uma mesma instância da aplicação gerencie contas reais conectadas à API do Mercado Livre e contas de homologação simuladas em paralelo, garantindo testes de concorrência sem custos operacionais.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou formalmente duas alternativas**:

### Alternativa 1: Dependência estrita e obrigatória de conexão real com o Mercado Livre em todos os ambientes
- **Por que foi descartada (Justificativa Técnica)**: Tornaria impossível a execução de testes automatizados (`python manage.py test`) em pipelines de Integração Contínua (GitHub Actions) ou em laptops sem conexão estável com a internet. Qualquer indisponibilidade momentânea nos servidores do Mercado Livre impediria os desenvolvedores de trabalhar no catálogo ou na inteligência financeira.

### Alternativa 2: Espalhar blocos `if settings.DEBUG: return mock_data` dentro das views de negócio
- **Por que foi descartada (Justificativa Técnica Profunda)**: Essa prática representa o antipadrão de contaminação de código de produção com código de teste. Se um desenvolvedor cometer um erro de lógica, código de mock poderia ser executado inadvertidamente em ambiente de produção, ignorando validações reais de segurança. A decisão adotada encapsula a alternância no padrão Factory e em rotas controladas por Feature Flags centralizadas, mantendo os serviços de aplicação limpos e agnósticos sobre se o canal é real ou simulado.

## 4. Consequência

### Ganhos Reais:
- **Autonomia de Desenvolvimento e Testes Offline**: A equipe pode desenvolver, refatorar e executar 100% da suíte de testes unitários sem depender de internet ou túneis ngrok.
- **Segurança e Privacidade**: Não há necessidade de compartilhar credenciais reais de contas corporativas de lojistas entre todos os desenvolvedores da equipe.
- **Demonstração Acadêmica Confiável**: A apresentação do projeto na banca avaliadora é imune a falhas de conectividade ou alterações inesperadas de API de terceiros.

### Custos e Limitações Assumidas:
- **Disciplina de Manutenção de Mocks**: Os mocks precisam ser atualizados sempre que a especificação da API real sofrer alterações estruturais relevantes.

## 5. Commit

- **Hash de Módulo Isolado de Mock de Dados**: `1baa5b9` — `feat(mockar_dados): adiciona modulo isolado de mock de dados e injecao de credenciais em modo debug`.
- **Hash de Flag de Alternância e Simulação OAuth**: `bee4786` — `feat(mock): implementar flag de alternancia para simulacao oauth e regras de reconexao`.
- **Hash de Bloqueio de Duplicidade e Credenciais Dev**: `745f074` — `fix(marketplaces): bloquear duplicidade de conexao, travar edicao de canal/loja e carregar credenciais dev via .env`.
