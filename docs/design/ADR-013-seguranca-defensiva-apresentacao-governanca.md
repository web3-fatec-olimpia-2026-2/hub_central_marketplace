# ADR 013 — Segurança Defensiva na Camada de Apresentação, Prevenção de Information Leakage e Governança de Código

> **Declaração de Integridade Acadêmica:** Este conteúdo foi produzido com auxílio de IA.

## 1. Contexto

A segurança e a maturidade de um sistema corporativo de integração de e-commerce não se limitam à criptografia de banco e ao controle de acesso transacional; elas devem estender-se à camada de apresentação e à governança do código-fonte:
1. **Vazamento de Informações Sensíveis (*Information Leakage / Fingerprinting*)**: No Django, quando rotas inexistentes são acessadas ou erros inesperados acontecem, as telas padrão de depuração revelam a lista completa de URLs do sistema (`urls.py`), versões exatas do framework e de bibliotecas, caminhos físicos do sistema operacional e configurações internas. Em ambientes de produção, atacantes utilizam essas páginas de erro para mapear vetores de invasão e descobrir endpoints administrativos restritos.
2. **Diretrizes de Governança de IA da FATEC (Uso Nível 2)**: Conforme os critérios éticos e pedagógicos do Prof. José Ceron Neto para a disciplina ILP-037, o auxílio de ferramentas de IA generativa é categorizado como Nível 2 (permitido mediante declaração e rastreabilidade explícita). A equipe precisava instituir um padrão compulsório de governança no código-fonte para garantir conformidade acadêmica e transparência profissional.
3. **Ergonomia Operacional e Acessibilidade**: Operadores de armazém e gestores de e-commerce trabalham em ambientes variados (telas industriais de baixa luminosidade, dispositivos móveis em estoque e desktops de escritório), demandando interface com suporte a temas visuais ergonômicos e responsividade estrita sem quebra de layout.

## 2. Decisão

A equipe adotou um conjunto de medidas de **Hardening Defensivo de Apresentação e Governança de Engenharia**:

1. **Páginas Customizadas de Erro e Prevenção de Information Leakage (`templates/404.html` e `templates/500.html`)**:
   - Sob `DEBUG=False`, o sistema renderiza uma página de erro 404/500 customizada, visualmente limpa e integrada à identidade do Hub.
   - Nenhuma informação interna de rotas, nomes de classes, parâmetros de URL, exceções Python ou versões de dependências é exposta ao cliente HTTP.
   - Foram implementados testes automatizados em `core/tests.py` assegurando que rotas inexistentes retornem estritamente status `404` sanitizado.

2. **Governança de Código e Padrão Ético de IA (Cabeçalho Compulsorio)**:
   - Introdução padronizada do cabeçalho de conformidade acadêmica em todos os arquivos de código-fonte (`.py`) do projeto:
     ```python
     # Os códigos foram gerados com auxilio de I.A.
     ```
   - Esse padrão assegura total conformidade com a declaração de autoria híbrida e ética da FATEC, garantindo que a equipe mantenha a responsabilidade de domínio e saiba defender oralmente cada linha de código implementada.

3. **Arquitetura de Apresentação com Suporte a Temas e Grid Responsivo**:
   - Criação de layout em grid ordenado e intuitivo na página inicial (`grid 4x2`) e barra de navegação sequencial sem *overflow* horizontal.
   - Mecanismo de persistência local (`localStorage`) suportando 4 modos visuais: Padrão, Claro (*Light*), Escuro (*Dark*) e Automático (*Sistema*), garantindo conforto visual a operadores de expedição.

## 3. Alternativa Descartada

A equipe avaliou e **rejeitou as seguintes alternativas**:

### Alternativa 1: Manter as páginas padrão de erro do Django
- **Por que foi descartada (Justificativa Técnica)**: Viola diretamente a diretriz OWASP Top 10 A05:2021 (*Security Misconfiguration*). As páginas padrão do Django exibem detalhes internos de schema de roteamento e pistas técnicas que auxiliam atacantes em varreduras automatizadas (*fuzzing* e *directory traversal*).

### Alternativa 2: Omitir a declaração de auxílio de IA no código-fonte
- **Por que foi descartada (Justificativa Técnica e Ética)**: Contraria o regulamento da disciplina ILP-037. A transparência na atribuição de código assistido por IA reforça a maturidade dos alunos como futuros Engenheiros de Software, destacando que a inteligência artificial serviu como acelerador de produtividade, enquanto a arquitetura, a justificativa das alternativas descartadas e a defesa técnica residem integralmente na capacidade cognitiva dos integrantes da equipe.

## 4. Consequência

### Ganhos Reais:
- **Blindagem Contra Reconhecimento de Superfície de Ataque**: Superfície de ataque externa reduzida a zero vazamento de metadados.
- **Conformidade Normativa e Acadêmica**: Transparência e integridade perante a banca examinadora da FATEC Olímpia.
- **Experiência do Usuário (UX) Profissional**: Navegação fluida, sem quebras de layout em celulares ou coletores de estoque e adaptável à iluminação ambiente.

### Custos e Limitações Assumidas:
- **Disciplina Contínua de Revisão de Código**: Necessidade de validar se novos arquivos criados mantêm o cabeçalho padronizado de governança e não quebram o grid de navegação.

## 5. Commit

- **Hash de Hardening e Template 404**: `d58cc2e` — `feat(templates): adiciona template customizado templates/404.html e testes`.
- **Hash de Governança de Cabeçalho de IA**: `7aa267f` — `fix(code-standard): introduz cabecalho obrigatorio de atribuicao de I.A. nos arquivos fontes`.
- **Hash de Temas Visuais (Dark/Light/Sistema)**: `5dedfaa` — `feat(ui): adiciona suporte a 4 temas (padrao, claro, escuro e sistema) com persistencia local`.
- **Hash de Remodelagem da Home em Grid e Navbar**: `a4b7c89` — `feat(ui): ordenar navbar sequencial pós-logs e reestruturar layout da home em grid 4x2`.
- **Hash de Responsividade e Correção de Overflow**: `2a6a90a` — `fix(ui): ajusta responsividade da navbar e elimina overflow horizontal`.
