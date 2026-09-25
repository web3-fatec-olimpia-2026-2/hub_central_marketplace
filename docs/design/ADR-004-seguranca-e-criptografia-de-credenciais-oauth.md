# ADR 004 — Proteção Criptográfica de Tokens OAuth 2.0 e Segredos em Repouso

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

Para que o Hub Inteligente realize a sincronização automática de produtos, estoque e preços com os marketplaces parceiros (Mercado Livre, Shopee, Amazon, Magalu), o sistema necessita armazenar credenciais e segredos de autenticação fornecidos pelos lojistas e pelos servidores de autorização OAuth 2.0:
- `client_secret` e chaves de aplicação (`app_key`).
- `access_token` (tokens de autorização de curta duração).
- `refresh_token` (tokens de longa duração utilizados para renovação automática de acesso).

Se esses dados sensíveis fossem gravados em formato legível (texto puro) no banco de dados, qualquer incidente de segurança — como um vazamento de dump de banco de dados, injeção SQL, comprometimento de backup físico ou acesso indevido por operadores em painéis administrativos — resultaria no sequestro completo das contas de vendas dos lojistas, permitindo que cibercriminosos alterassem preços para zero, desviassem pedidos ou extraíssem dados fiscais de compradores.

## 2. Decisão

A equipe decidiu implementar **criptografia simétrica autenticada em repouso** utilizando o algoritmo **Fernet** (especificação da biblioteca `cryptography.fernet`), complementada por **identificadores efêmeros UUID v4 e assinatura HMAC**:
1. **Criptografia Simétrica Fernet**: O Fernet emprega criptografia AES-128 em modo CBC com derivação de chave segura e autenticação HMAC-SHA256 para garantia de integridade e timestamping contra adulterações.
2. **Encapsulamento nos Modelos e Serviços**: Os campos sensíveis do modelo `ContaMarketplace` (`access_token`, `refresh_token`, `client_secret`) são encriptados imediatamente antes da persistência no banco e descriptografados estritamente na memória volátil (`RAM`) no exato instante em que o conector precisa montar o cabeçalho HTTP `Authorization: Bearer <token>` para despachar requisições aos marketplaces (`apps.core.security` e `apps.marketplaces.security`).
3. **Gestão Segura de Chaves via Variáveis de Ambiente**: A chave mestra de criptografia (`FERNET_KEY`) nunca é commitada no repositório Git; ela é injetada em tempo de execução através do arquivo `.env`.
4. **Webhooks Segmentados por UUID com Validação HMAC**: Cada conta gera um identificador `webhook_secret_uuid` único e valida assinaturas digitais HMAC nas requisições recebidas de webhooks, mitigando ataques de personificação e replay.

## 3. Alternativa Descartada

A equipe analisou e **rejeitou formalmente duas alternativas**:

### Alternativa 1: Armazenamento em Texto Puro (*Plaintext*) no Banco de Dados
- **Por que foi descartada (Justificativa Técnica)**: Viola diretamente as diretrizes de segurança da informação (OWASP Top 10 A02:2021 — *Cryptographic Failures*), as normas de proteção de dados (LGPD Art. 46) e as políticas obrigatórias de segurança das APIs de marketplaces (ex.: Termos de Segurança da API do Mercado Livre). Em ambientes multi-tenant, credenciais em texto puro transformam qualquer vulnerabilidade de leitura em uma catástrofe de segurança sistêmica.

### Alternativa 2: Hashing Criptográfico Unidirecional (ex.: SHA-256, Argon2, PBKDF2 ou Bcrypt)
- **Por que foi descartada (Justificativa Técnica Profunda)**: Embora funções de Hash criptográfico sejam a solução correta para armazenamento de senhas de usuários, **elas são tecnicamente inviáveis para credenciais de integração de API**:
  - Funções de hash são matemáticas unidirecionais (*one-way functions*): após gerado o hash, é impossível recuperar a string original legível.
  - Para que o Hub possa se comunicar com as APIs externas dos marketplaces, ele precisa obrigatoriamente enviar o valor exato e original do `access_token` no cabeçalho HTTP `Authorization: Bearer <token_original>`.
  - Da mesma forma, para renovar um token expirado, o conector precisa submeter o `refresh_token` original legível ao endpoint `/oauth/token`.
  - Como o Hash torna o valor original irrecuperável, o sistema não conseguiria autenticar nenhuma chamada de API, tornando a integração inoperante. Apenas a criptografia simétrica reversível e autenticada atende simultaneamente aos requisitos de segurança e viabilidade operacional.

## 4. Consequência

### Ganhos Reais:
- **Blindagem Contra Vazamentos**: Mesmo se a base de dados for totalmente extraída em um ataque de dump, os invasores terão acesso apenas a strings cifradas ilegíveis e indecifráveis sem a chave mestra.
- **Conformidade Normativa**: O projeto atende aos mais rigorosos padrões de segurança exigidos por parceiros de comércio eletrônico corporativos.
- **Integridade Garantida**: Qualquer modificação manual maliciosa no banco de dados corrompe a assinatura HMAC do Fernet, fazendo com que o sistema rejeite a credencial adulterada imediatamente.

### Custos e Limitações Assumidas:
- **Dependência Crítica da Chave Mestra**: A perda da variável de ambiente `FERNET_KEY` torna os dados cifrados irrecuperáveis permanentemente, exigindo que os lojistas refaçam a autorização OAuth de suas contas.
- **Overhead Computacional**: Custo adicional de CPU para encriptar e decriptar tokens a cada operação de sincronização (mitigado pelo baixo volume de bytes de strings de token).

## 5. Commit

- **Hash Principal**: `476a938` — `feat(security): implementar criptografia fernet, modo hibrido e webhook segmentado por uuid` (Implementação do módulo Fernet, modo híbrido e segurança de webhooks).
- **Hash de Origem OAuth**: `ec569dc` — `feat(meli): implementar fluxo oauth2 real e criptografia fernet no banco` (Primeira versão do fluxo OAuth com persistência segura).
