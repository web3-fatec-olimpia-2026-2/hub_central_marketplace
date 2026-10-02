# AGENT_INSTRUCTIONS_DJANGO.md — Padrão Global do Ecossistema Django (Ambiente, Processo, Arquitetura e Segurança de Aplicação)

**Versão:** 3.1  
**Aplica-se a:** todos os projetos Django do ecossistema (`~/projetos/django/`), desenvolvidos em WSL 2 (Windows + Ubuntu).  
**Posição no padrão de projeto (3 documentos):**

| Nº | Documento | Papel |
| :-: | :--- | :--- |
| ① | `AGENT_INSTRUCTIONS_DJANGO.md` (este) | **Padrão global normativo** — vale para qualquer projeto Django do ecossistema. |
| ② | `PROJECT_SPEC.md` | **Mínimo geral do projeto/produto** — modelo a preencher; ponto de partida para as especificidades de cada aplicativo. |
| ③ | `DEV_ENVIRONMENT_GUIDELINES.txt` | Registro narrativo do ambiente (referência humana; não normativo). |

---

## 0. Escopo, Autoridade e Hierarquia Documental

### 0.1. Finalidade

Este documento estabelece as regras globais e mandatórias para:

- configuração do ambiente de desenvolvimento e isolamento do sistema;
- gerenciamento do ambiente Python e das dependências;
- proteção de credenciais e fluxo de trabalho Git;
- salvaguardas e protocolo de operação para agentes de IA;
- **arquitetura global de aplicação** (modularidade, camadas, identificadores, *tenancy-ready*, páginas públicas e **sistema de temas**);
- **baseline de segurança da aplicação Django** (HTTP, sessão, CSP, entrada, autenticação, autorização, criptografia, rate limiting, erros, auditoria).

Ele é o **padrão global do ecossistema Django**. Foi consolidado a partir de três sistemas já construídos sob este ecossistema, extraindo o que se repete (e deve ser decidido uma única vez) e deixando para o Doc ② somente o que depende de produto.

O documento não define regras de negócio, requisitos funcionais, marca, conteúdo, perfis nomeados nem a matriz de permissões concreta de nenhum produto.

---

### 0.2. Mapa de domínios

Este documento está dividido em quatro domínios. Cada domínio responde a uma pergunta diferente e tem um dono diferente para o *valor* final.

| Domínio | Seções | Pergunta que responde | Onde fica o valor específico |
| :--- | :--- | :--- | :--- |
| **A — Ambiente e Processo** | §1–§8 | Onde e como desenvolver, versionar e operar com segurança? | Não há: é igual em todo projeto. |
| **B — Arquitetura Global de Aplicação** | §9–§11 | Como estruturar apps, camadas, identificadores, tenancy, interface-base, navegação e temas? | Doc ② (apps, menus, tema padrão, modelo de tenancy). |
| **C — Segurança Global da Aplicação** | §12–§21 | Qual o piso de segurança de qualquer aplicação Django do ecossistema? | Doc ② §10 (parâmetros e exceções justificadas). |
| **D — Qualidade, Entrega e Governança** | §22–§29 | Como testar, listar dependências, validar e relacionar-se com os docs do projeto? | Doc ② §11–§13. |

Para uma visão por assunto (em vez de por seção), consulte a tabela da Seção 0.5.

---

### 0.3. O que este documento NÃO cobre

Permanecem em documentação específica de cada projeto ou ambiente:

- infraestrutura de produção (hospedagem, proxy reverso, certificados, balanceamento, WAF/CDN, containers e orquestração, CI/CD);
- SGBD de produção, backup e recuperação de desastres;
- modelos de dados, regras de negócio e requisitos funcionais;
- contratos de APIs e integrações de domínio;
- marca, conteúdo, telas e **escolhas de tema** (modelo padrão, paleta, layouts) do briefing de design; o *mecanismo* de temas é global (Seções 11.5 a 11.12);
- perfis nomeados, hierarquia e matriz RBAC concreta;
- modelo de tenancy do produto (o contrato neutro é global, Seção 10.6);
- valores finais de parâmetros (limites de rate limit, tempo de sessão, hosts adicionais de CSP etc.);
- estratégia de testes específica do projeto;
- qualquer outra característica exclusiva de um projeto individual.

> **Mudança na v3.0:** HSTS, CSP, CSRF, cabeçalhos de segurança, autenticação, autorização, JWT/HMAC e rate limiting **deixaram** a lista de itens "não cobertos". Agora este documento define o **baseline** (valor-padrão seguro e mecanismo); o projeto só registra valores próprios ou exceções justificadas no Doc ②.

---

### 0.4. Hierarquia de documentos e Estrutura de Contexto

```text
~/projetos/
├── django/                                     <-- Diretório do Ecossistema Django
│   ├── AGENT_INSTRUCTIONS_DJANGO.md           <-- ① PADRÃO GLOBAL NORMATIVO DJANGO
│   ├── DEV_ENVIRONMENT_GUIDELINES.txt         <-- ③ Referência narrativa de ambiente (não normativa)
│   │
│   ├── <nome_do_projeto_A>/                    <-- Raiz do Repositório Git do Projeto A
│   │   ├── .venv/                             <-- Ambiente virtual isolado (ignorado no Git)
│   │   ├── .env                               <-- Credenciais locais (ignorado no Git)
│   │   ├── .env.example
│   │   ├── .gitignore
│   │   ├── requirements.txt
│   │   ├── manage.py
│   │   ├── PROJECT_SPEC.md                    <-- ② PRD + TRD mínimo do projeto/produto
│   │   ├── regras_de_negocio.md               <-- RF/RN detalhados
│   │   ├── apps/<app>/README.md               <-- Documentação individual de cada app (§9.3)
│   │   └── (opcionais) ARCHITECTURE.md · DATABASE.md · API.md · TESTING.md · SECURITY.md
│   │
│   └── <nome_do_projeto_B>/                    <-- Raiz do Repositório Git do Projeto B
│
├── nodejs/                                    <-- Outros Ecossistemas (Exemplo)
│   └── AGENT_INSTRUCTIONS_NODE.md
└── rust/
    └── AGENT_INSTRUCTIONS_RUST.md
```

Precedência de instrução:

```text
Padrões e instruções superiores da plataforma/agente
                    │
                    ▼
       ① AGENT_INSTRUCTIONS_DJANGO.md (../)
             PADRÃO GLOBAL
                    │
                    ▼
       ② PROJECT_SPEC.md (./)  ──►  regras_de_negocio.md · README de cada app
                    │
                    ▼
             Tarefa específica
```

**Mapa PRD / TRD:**

| Documento de requisitos | Onde vive |
| :--- | :--- |
| **TRD global** (requisitos técnicos comuns a todo projeto) | ① este documento |
| **PRD do produto** (visão, perfis, escopo, AppFlow, landing, design) | ② `PROJECT_SPEC.md` §1–§6, com RF/RN detalhados em `regras_de_negocio.md` |
| **TRD do projeto** (topologia, dados, integrações, parâmetros, testes) | ② `PROJECT_SPEC.md` §7–§11 |

Documentos de um projeto podem **acrescentar** regras. Não podem eliminar ou enfraquecer uma regra global; qualquer desvio é uma **exceção registrada e justificada** no Doc ② §10.

---

### 0.5. Critério de classificação: o que é Doc ① e o que é Doc ②

Regra de decisão:

> Se vale para **qualquer** projeto Django do ecossistema sem alteração, é Doc ①. Se depende de produto, público, marca, dados ou negócio, é Doc ②. Quando houver um padrão seguro com ajuste possível, o **padrão** fica no Doc ① e o **valor/ajuste** fica no Doc ②.

| Assunto | Doc ① define (padrão) | Doc ② define (projeto/produto) |
| :--- | :--- | :--- |
| **CSP** | Diretivas-base restritivas, allowlist, report-only → enforce, `frame-ancestors 'none'` | Hosts adicionais; relaxamentos (ex.: `frame-ancestors 'self'` / `SAMEORIGIN`) com justificativa |
| **Cookies e sessão** | `HttpOnly` + `Secure` + `SameSite`; tokens fora de `localStorage` | Tempo de vida da sessão; exceções documentadas |
| **UUIDv4** | Regra, modelo base e rotas `<uuid:id>` | Lista de entidades que expõem identificador |
| **Rate limiting** | Mecanismo, chaves, resposta 429, escopos mínimos, valores iniciais | Valores finais por rota |
| **RBAC** | Mecanismo, matriz como dado, regras de elevação, default deny | Perfis nomeados, ordem de privilégio, matriz concreta, segregação de funções |
| **401 / 403 / 404** | Política de respostas e padrão de queryset escopado (IDOR/BOLA) | Classificação por recurso |
| **Cripto e segredos** | Argon2id, Fernet, HMAC/JWT, assinatura de webhooks, chaves no `.env` | Campos cifrados, provedores OAuth, integrações |
| **Menus / NAVBAR** | Toda função na aplicação (não só no Admin), agrupada por assunto, visibilidade por RBAC | Estrutura concreta de menus |
| **Landing / páginas públicas** | Rota `/` pública quando a visibilidade estiver ativa (RBAC: `site.visibilidade_publica`); `/` é o login quando desativada; requisitos técnicos | Estado inicial da visibilidade, páginas controláveis, conteúdo, benefícios, características, tom |
| **Páginas de erro** | Handlers 400/403/404/500; `DEBUG=False`; sem vazar rotas | Texto, identidade e tom |
| **Modularidade** | Regras de app desacoplado e README por app | Catálogo de apps do projeto |
| **Design / temas** | Sistema de temas: 10 modelos, três cores (Fundos, Destaques, Escritas), seletor de cores, 20 paletas, eixos de estilo, variantes de layout, CSS gerado, `base.html` como casca fina | Modelos habilitados, tema padrão, paleta e cores de marca, layouts por tipo de página, quem altera |
| **AppFlow / Onboarding** | Exige que existam | Fluxos, jornadas e tour do produto |
| **Regras de negócio** | — | `regras_de_negocio.md` |
| **Login** | Ordem do formulário (Esqueci minha senha abaixo do botão Entrar); login local + OAuth | Provedores habilitados, tela de login do produto |
| **Tenancy** | Contrato neutro (`TENANCY_MODE`, resolvedor, regras de preparação); padrão `single` | Modo escolhido, resolução do tenant, entidades com escopo, ADR |

---

### 0.6. Linguagem normativa

- **DEVE / NÃO DEVE:** obrigação. Desvio só como exceção registrada (Doc ② §10).
- **RECOMENDADO:** prática esperada; desvio exige apenas justificativa curta.
- **PODE:** opcional.

Todos os agentes de IA comunicam decisões, planos e relatórios em **português**, salvo pedido diferente do usuário.

---

### 0.7. Precedência sobre o material de referência

O arquivo (Doc ③):

`DEV_ENVIRONMENT_GUIDELINES.txt`

(anteriormente nomeado `Ambiente_de_desenvolvimento_-_Django_-_Definição_do_fluxo_de_desenvolvimento_e_definições_de_segurança_e_escopo_básico.txt`)

é o documento de análise, referência técnica e registro do processo que deu origem ao domínio de ambiente deste padrão.

Ele pode ser consultado para:

- compreender o contexto das decisões;
- consultar explicações mais detalhadas;
- consultar o fluxo original;
- recuperar comandos e procedimentos de referência.

**O arquivo `.txt` não constitui fonte normativa de instruções operacionais para agentes de IA.**

Em caso de divergência entre o `.md` e o `.txt`, este documento prevalece.

Um agente de IA **não deve tratar a leitura do `.txt` como requisito obrigatório antes de executar uma tarefa**, quando as regras necessárias já estiverem definidas neste `.md`.

---

# PARTE A — DOMÍNIO: AMBIENTE E PROCESSO

*(§1–§8: válido para todo projeto, sem variação.)*

---

## 1. Bootstrap Único da Máquina Host

Esta seção deve ser executada **uma única vez por máquina**, antes de existir qualquer projeto Django.

Não repita estes passos a cada novo projeto.

---

### 1.1. Instalação de base no Windows

Executar o PowerShell como Administrador:

```powershell
# Instalar o WSL com Ubuntu
wsl --install -d Ubuntu
wsl --version

# Instalar o Git no Windows
# Utilizado para operações do host Windows quando necessário.
winget install --id Git.Git -e --source winget
git --version

# Instalar o VS Code
winget install --id Microsoft.VisualStudioCode -e --source winget
code --version

# Instalar a extensão oficial de conexão com WSL
code --install-extension ms-vscode-remote.remote-wsl
```

Ferramentas adicionais de CLI de terceiros são opcionais e permanecem fora do escopo mínimo deste documento.

Qualquer ferramenta adicional que venha a ser adotada como padrão global deverá ser avaliada e documentada separadamente.

---

### 1.2. Instalação de ferramentas nativas no Linux/WSL

No terminal Ubuntu/WSL:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv python3-dev build-essential git -y
```

---

### 1.3. Quando repetir esta seção

Esta seção deve ser executada novamente somente quando:

- uma nova máquina for configurada;
- o ambiente WSL precisar ser reconstruído;
- houver uma alteração deliberada no padrão global de infraestrutura do ambiente.

Ela **não deve ser repetida para cada novo projeto Django**.

---

## 2. Topologia de Isolamento e Arquitetura de Execução

### 2.1. Regra de localização dos arquivos

Todos os projetos Django, seus arquivos de código, bancos locais e ambientes virtuais DEVEM residir no sistema de arquivos nativo do WSL 2, alocados dentro da pasta dedicada ao ecossistema Django.

O caminho padrão obrigatório é:

```text
~/projetos/django/<nome_do_projeto>/
```

ou:

```text
/home/<usuario>/projetos/django/<nome_do_projeto>/
```

É terminantemente proibido:
1. Criar projetos Django soltos diretamente na raiz de `~/projetos/`.
2. Utilizar partições montadas do Windows como local de desenvolvimento (ex: `/mnt/c/Users/...`).

O código Django, o ambiente virtual e os arquivos de desenvolvimento devem permanecer no filesystem Linux nativo (`ext4`).

---

### 2.2. Papel de cada camada

#### Windows Host

O Windows atua principalmente como camada de interface e host das ferramentas visuais, incluindo:

- VS Code;
- Windows Terminal;
- PowerShell;
- demais ferramentas GUI.

#### WSL 2 / Ubuntu

O WSL 2 constitui o ambiente de desenvolvimento Linux, contendo:

- Python;
- compiladores;
- bibliotecas nativas;
- ambiente virtual Python;
- Git utilizado no desenvolvimento;
- código dos projetos;
- bancos de dados locais;
- demais dependências de desenvolvimento.

#### VS Code + WSL

O VS Code deve utilizar a integração oficial com WSL.

A abertura do projeto deve ser realizada a partir do diretório específico do projeto no terminal Linux:

```bash
cd ~/projetos/django/<nome_do_projeto>
code .
```

---

## 3. Gerenciamento do Ambiente Virtual Python e Dependências

### 3.1. Isolamento de pacotes com `.venv`

Todo projeto Django DEVE possuir seu próprio ambiente virtual Python contido em sua respectiva pasta raiz.

Antes de executar:

- `manage.py`;
- scripts Python;
- testes;
- linters;
- ferramentas Python;
- `pip`;

o ambiente virtual correspondente ao projeto deve estar ativo.

O prompt do terminal deve apresentar:

```text
(.venv)
```

Ativação:

```bash
source .venv/bin/activate
```

É proibida a instalação de dependências do projeto por `pip` fora do ambiente virtual.

Se o sistema impedir a instalação global devido a restrições de ambiente gerenciado, deve-se utilizar ou criar o `.venv`.

---

### 3.2. Gerenciamento e registro de dependências

O projeto deve manter um arquivo de dependências versionado e reproduzível.

O padrão global adotado neste ambiente utiliza:

```text
requirements.txt
```

como registro das dependências instaladas e das versões utilizadas no ambiente de desenvolvimento.

Quando a estratégia adotada pelo projeto utilizar congelamento completo do ambiente, o arquivo pode ser atualizado com:

```bash
pip freeze > requirements.txt
```

O objetivo é garantir que outro ambiente possa reproduzir as dependências utilizadas pelo projeto.

A estratégia específica de gerenciamento de dependências poderá ser refinada posteriormente em documentação do projeto, desde que preserve a reprodutibilidade do ambiente.

---

### 3.3. Fluxo para projetos clonados

Ao clonar um repositório Django existente, `.venv` e `.env` não devem estar no Git por design.

Eles devem ser recriados localmente.

Fluxo:

```bash
# 1. Ir para a pasta do ecossistema Django
cd ~/projetos/django

# 2. Clonar o repositório
git clone <URL_DO_REPOSITORIO>

# 3. Entrar na pasta do projeto recém-clonado
cd <nome_do_projeto>

# 4. Criar o ambiente virtual local
python3 -m venv .venv

# 5. Ativar o ambiente virtual
source .venv/bin/activate

# 6. Atualizar pip
pip install --upgrade pip

# 7. Instalar as dependências registradas pelo projeto
pip install -r requirements.txt
```

---

### 3.4. Criação e configuração do `.env` em projeto clonado

Antes de criar ou preencher o `.env`, verifique se existe:

```text
.env.example
```

Esse arquivo documenta as variáveis necessárias ao projeto.

Nunca adivinhe variáveis exigidas pela aplicação.

Nunca copie o `.env` de outro projeto.

Nunca utilize credenciais de produção em um ambiente local de desenvolvimento.

A `SECRET_KEY` deve ser exclusiva para o ambiente local daquele projeto/clone.

Gerar uma nova chave:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Variáveis adicionais, como:

```text
DB_PASSWORD
API_KEY
SERVICE_TOKEN
```

devem ser obtidas a partir da documentação específica do projeto ou de seu `.env.example`.


---

## 4. Segurança do Ambiente de Desenvolvimento, Variáveis de Ambiente e `.env`

### 4.1. Natureza da segurança definida neste documento

As regras desta seção tratam de:

- proteção básica do ambiente de desenvolvimento;
- proteção de credenciais;
- prevenção de exposição acidental de segredos;
- segurança do processo de desenvolvimento;
- segurança operacional durante utilização de agentes de IA.

Esta seção (Domínio A) trata da segurança do **ambiente e do processo**. O baseline de segurança da **aplicação** Django está na Parte C (§12–§21); valores específicos e exceções do projeto são registrados no Doc ② §10.

---

### 4.2. Isolamento de credenciais

É terminantemente proibido inserir diretamente no código-fonte:

- `SECRET_KEY`;
- senhas;
- credenciais de banco;
- chaves de API;
- tokens;
- credenciais de serviços;
- outros segredos.

Não devem ser armazenados diretamente em arquivos como:

```text
settings.py
models.py
views.py
scripts/
testes/
```

quando representarem valores secretos reais.

---

### 4.3. Arquivo `.env`

As configurações sensíveis e variáveis dinâmicas de desenvolvimento devem permanecer no arquivo físico:

```text
.env
```

localizado na raiz do projeto, no mesmo nível do:

```text
manage.py
```

O `.env` não deve ser versionado.

---

### 4.4. Integração com `django-environ`

O padrão global adotado para estes projetos Django utiliza `django-environ` para gerenciamento das variáveis de ambiente.

O `settings.py` deve utilizar conversão tipada das variáveis quando aplicável.

Para valores booleanos, é obrigatório utilizar conversão explícita.

Nunca utilizar:

```python
DEBUG = env('DEBUG')
```

como única forma de interpretar um booleano.

Utilizar:

```python
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
```

---

### 4.5. `DEBUG`

`DEBUG=True` pode ser utilizado no ambiente de desenvolvimento local.

O valor padrão utilizado pelo código deve ser seguro:

```python
DEBUG = env.bool('DEBUG', default=False)
```

`DEBUG=False` é obrigatório em qualquer ambiente exposto (Seção 20.1). O baseline de configuração de segurança da aplicação (HTTPS, HSTS, cookies, CSP etc.) está na Seção 12; a infraestrutura de produção (hospedagem, proxy reverso, certificados) permanece em documentação específica do projeto.

Um agente de IA não deve presumir que uma configuração de desenvolvimento possa ser utilizada em produção.

---

### 4.6. `.env.example`

Todo projeto deve manter:

```text
.env.example
```

versionado no Git.

Esse arquivo deve conter os nomes das variáveis necessárias, mas não valores reais ou segredos.

Exemplo:

```env
SECRET_KEY=
DEBUG=False
DB_PASSWORD=
API_KEY=
```

Sempre que uma nova variável de ambiente for adicionada ao projeto, o `.env.example` deve ser atualizado no mesmo commit.

O `.env.example` é a variante documentacional destinada ao versionamento.

O `.env` físico permanece local e não deve ser commitado.

---

### 4.7. `.gitignore`

Antes de qualquer operação de `git add` ou `git commit`, o arquivo `.gitignore` deve existir na raiz do projeto.

O conjunto mínimo global deve conter:

```gitignore
.venv/
.env
*.pyc
__pycache__/
*.log
.DS_Store
media/
staticfiles/
```

Arquivos específicos do projeto podem ser adicionados posteriormente conforme suas necessidades.

Por exemplo, se o projeto utilizar SQLite local:

```gitignore
db.sqlite3
```

deve ser incluído.


---

## 5. Identidade e Privacidade do Git

### 5.1. Política geral de e-mail

Para evitar exposição desnecessária de endereço de e-mail pessoal em históricos e repositórios públicos do GitHub, o padrão global recomendado é utilizar o endereço mascarado `noreply` fornecido pelo próprio GitHub.

Formato:

```text
ID+usuario@users.noreply.github.com
```

Cada colaborador deve utilizar seu próprio alias.

---

### 5.2. Configuração genérica

A configuração deve utilizar os dados correspondentes à própria conta:

```bash
git config --global user.name "SEU_USUARIO_GITHUB"
git config --global user.email "SEU_ID+SEU_USUARIO@users.noreply.github.com"
```

**Não deve existir neste documento global um endereço específico de uma conta individual.**

Os valores concretos devem ser obtidos pelo próprio colaborador nas configurações da sua conta GitHub.

---

### 5.3. Verificação obrigatória

Antes de realizar commits:

```bash
git config user.email
```

O endereço retornado deve utilizar:

```text
users.noreply.github.com
```

Se retornar um endereço pessoal ou estiver vazio, o agente de IA deve interromper a operação e informar o problema ao usuário.

Um agente de IA não deve configurar arbitrariamente um endereço pessoal para resolver a ausência de configuração.

---

## 6. Fluxo de Trabalho Git

### 6.1. Isolamento de branches

É expressamente proibido desenvolver ou realizar commits diretamente na branch principal:

```text
main
```

ou:

```text
master
```

Todo trabalho deve ocorrer em uma branch específica.

Padrão:

```text
tipo/descricao-kebab-case
```

Tipos globais:

```text
feat/
fix/
refactor/
style/
docs/
test/
chore/
```

Exemplos:

```text
feat/modulo-produtos
fix/erro-autenticacao
refactor/estrutura-servicos
style/ajustes-layout
docs/atualizacao-documentacao
test/cobertura-produtos
chore/atualizacao-dependencias
```

---

### 6.2. Início de uma tarefa nova

```bash
git checkout main
git pull origin main
git switch -c tipo/nome-da-branch
```

---

### 6.3. Retomada de tarefa em andamento

```bash
git checkout tipo/nome-da-branch
git pull origin main
```

A atualização da branch de trabalho deve preservar as alterações locais.

Em caso de conflito, seguir as regras da Seção 7.

---

### 6.4. Auditoria antes do commit

Antes de preparar alterações:

```bash
git status
git diff
```

Verificar especialmente:

- `.env`;
- `.venv`;
- tokens;
- credenciais;
- logs;
- arquivos temporários;
- dados de teste sensíveis;
- informações pessoais;
- artefatos de depuração.

Somente depois da inspeção:

```bash
git add .
```

Após o staging, executar novamente:

```bash
git status
```

e verificar o conteúdo que será enviado ao commit.

---

### 6.5. Conventional Commits

As mensagens de commit devem seguir:

```text
tipo(escopo-opcional): descrição concisa no imperativo
```

Exemplos:

```bash
git commit -m "feat(auth): implementa autenticacao baseada em tokens JWT"
```

```bash
git commit -m "fix(settings): adiciona conversao booleana para flag DEBUG"
```

```bash
git commit -m "chore(deps): atualiza requirements com django-environ"
```

---

### 6.6. Publicação da branch

Primeiro envio:

```bash
git push -u origin tipo/nome-da-branch
```

Envios subsequentes:

```bash
git push
```

O push da branch de trabalho pode ser utilizado como mecanismo de preservação remota do trabalho em andamento.

---

### 6.7. Conclusão da tarefa

A funcionalidade deve ser concluída através de Pull Request.

Fluxo:

```text
branch de trabalho
       │
       ▼
     push
       │
       ▼
 Pull Request
       │
       ▼
 revisão humana
       │
       ▼
    merge
       │
       ▼
     main
```

O merge deve ocorrer através da plataforma remota e após revisão adequada.

Depois do merge:

```bash
git checkout main
git pull origin main
git branch -d tipo/nome-da-branch
git fetch --prune
```

---

## 7. Salvaguardas para Agentes de IA em Operações Git

### 7.1. Princípio de autorização

A capacidade técnica de executar um comando **não equivale à autorização para executá-lo**.

Um agente de IA deve respeitar as regras deste documento mesmo quando possua permissões técnicas suficientes para ignorá-las.

---

### 7.2. Comandos que exigem confirmação explícita

Um agente de IA **NUNCA deve executar por iniciativa própria**:

```text
git push --force
git push -f
git push --force-with-lease
git reset --hard
git clean -fd
git branch -D
git push origin --delete <branch>
git rebase
git commit --amend
```

quando a operação puder resultar em perda de trabalho, reescrita de histórico ou alteração destrutiva.

Antes de executar uma dessas operações, o agente deve:

1. interromper a operação;
2. explicar ao usuário o que o comando fará;
3. informar a consequência potencial;
4. solicitar confirmação explícita;
5. somente prosseguir após a confirmação.

---

### 7.3. Pull Requests e merge

Um agente de IA não deve aprovar ou realizar merge de Pull Request sem revisão humana quando isso estiver sob sua capacidade de execução.

A revisão humana constitui uma barreira adicional contra:

- código incorreto;
- alterações inesperadas;
- exposição de segredos;
- alterações destrutivas;
- mudanças não solicitadas.

---

### 7.4. Erros e conflitos

Se um comando Git falhar ou resultar em conflito, o agente deve:

1. preservar o estado atual;
2. informar o erro ao usuário;
3. apresentar opções possíveis;
4. aguardar orientação quando uma ação puder causar perda de dados.

O agente não deve tentar resolver automaticamente o problema utilizando comandos destrutivos.

---

### 7.5. Arquivos locais protegidos

Um agente não deve excluir sem confirmação explícita:

```text
.env
db.sqlite3
.venv/
```

mesmo que a exclusão pareça ser uma solução para um problema de ambiente.

A existência de um problema técnico não autoriza automaticamente a remoção de dados locais.

---

### 7.6. Protocolo de plano e confirmação (toda iteração)

A cada nova tarefa/prompt, o agente DEVE:

1. **Ler** este documento, o `PROJECT_SPEC.md` (Doc ②), o `regras_de_negocio.md` e os `README.md` dos apps afetados antes de propor qualquer mudança.
2. **Apresentar um plano de ação detalhado** antes de executar: arquivos afetados, migrações, dependências novas (com justificativa), riscos e testes previstos.
3. **Aguardar confirmação humana explícita.** Sem confirmação, o agente apenas lê e analisa. Não cria nem altera arquivos, não instala pacotes, não gera/aplica migrações e não executa comandos destrutivos.
4. **Comunicar em português.**
5. **Reportar ao final:** o que foi feito, resultado dos testes e pendências.

O usuário pode dispensar o plano prévio para uma tarefa, de forma explícita. Essa dispensa **nunca** afrouxa a Seção 7.2.

---

### 7.7. Dependências novas

Nenhuma dependência é adicionada sem constar no plano aprovado, com: finalidade, alternativa em biblioteca padrão/Django, e impacto de segurança. Toda adição atualiza o `requirements.txt` no mesmo commit (Conventional Commit `chore(deps)`).

---

## 8. Segurança do Processo de Desenvolvimento

Esta seção estabelece controles globais relacionados ao processo de desenvolvimento.

Ela trata do **processo**; a segurança da aplicação está na Parte C (§12–§21).

Os controles globais incluem:

```text
Credenciais
   │
   ├── não hardcode
   ├── .env local
   └── .env.example sem segredos

Código
   │
   ├── Git
   ├── branches
   ├── revisão
   └── histórico

Agente de IA
   │
   ├── autorização explícita
   ├── proteção contra operações destrutivas
   └── revisão humana

Ambiente
   │
   ├── WSL 2
   ├── filesystem Linux
   └── .venv isolado
```

O baseline de segurança da aplicação Django está na Parte C (§12–§21); valores específicos e exceções do projeto ficam no Doc ② §10.

---

# PARTE B — DOMÍNIO: ARQUITETURA GLOBAL DE APLICAÇÃO

*(§9–§11: como estruturar. Os valores e a composição concreta do projeto ficam no Doc ②.)*

---

## 9. Arquitetura Modular e Desacoplamento

### 9.1. Princípio

O sistema DEVE ser modular, com o **máximo de desacoplamento possível**. Em Django/Python, quanto melhor separadas estiverem as aplicações e funcionalidades, mais fácil é reaproveitar uma app em novos projetos. Por isso, **documentar cada app individualmente é obrigatório** (Seção 9.3).

---

### 9.2. Regras de desacoplamento

1. **Localização:** apps ficam em `apps/<nome_app>/`, cada uma com `AppConfig` próprio (`name = 'apps.<nome_app>'`), `models`, `services`, `forms`, `views`, `urls`, `templates`, `static` e `tests` internos.
2. **Direção de dependência:** apps de domínio dependem de `core`; `core` nunca depende de app de domínio. É proibida importação circular.
3. **Entre apps de domínio:** comunicação por `services` públicos, sinais ou interfaces declaradas no README. Evitar importar `models`/`views` de outra app de domínio.
4. **Usuário:** usar `settings.AUTH_USER_MODEL` e `get_user_model()`; nunca importar a classe de usuário diretamente. Relações por string (`'app.Model'`).
5. **Configuração:** chaves de settings da app prefixadas (`<APP>_...`) e lidas com `getattr(settings, 'CHAVE', padrao)`. A app funciona com valores-padrão seguros.
6. **Namespacing:** templates em `templates/<app>/`, estáticos em `static/<app>/`, URLs com `app_name`, nomes de rota estáveis.
7. **RBAC:** as funcionalidades (permissões) expostas pela app são declaradas na própria app e registradas na matriz (Seção 17.4).
8. **Testes:** dentro da app, executáveis isoladamente (`python manage.py test apps.<nome_app>`).
9. **Sem regra de produto em app reutilizável.** Regras específicas ficam em app de domínio do projeto.
10. **Tenancy:** a app declara quais modelos têm escopo de tenant e funciona em modo `single` sem alteração (Seção 10.6).

---

### 9.3. Documentação individual de cada app

Cada app possui `apps/<nome_app>/README.md` com, no mínimo:

| Item | Conteúdo |
| :--- | :--- |
| Finalidade | O que a app faz e o que **não** faz. |
| Dependências | Outras apps, pacotes e chaves de settings/`.env`. |
| Modelos | Entidades, relações, identificadores (UUID) e **quais têm escopo de tenant** (Seção 10.6). |
| Serviços públicos | Funções/classes que outras apps podem chamar. |
| URLs e permissões | Rotas (`name`) e funcionalidades RBAC exigidas. |
| Instalação em novo projeto | `INSTALLED_APPS`, `urls`, settings, migrações. |
| Testes e changelog | Como rodar e histórico de mudanças. |

Uma app nova ou alterada sem README atualizado **não está concluída** (Doc ② §12, Definition of Done).

---

### 9.4. Catálogo de apps reutilizáveis (proposta)

| App | Responsabilidade |
| :--- | :--- |
| `core` | Utilitários transversais: criptografia (Fernet), model-base com UUID e timestamps, resolvedor de tenant, handlers de erro, helpers de rate limit, validadores. |
| `accounts` | Usuário customizado (UUID), perfis, matriz RBAC, login local, OAuth, recuperação de senha. |
| `audit` | Histórico auditável (quem, quando, o quê, origem). |
| `site` | Landing/apresentação (com visibilidade controlada pelo RBAC), páginas institucionais, páginas de erro, **tema (`ConfigTema`)** e configurações do site. |
| `<dominio>` | Apps específicas do produto (Doc ② §1.5). |

---

## 10. Camadas, Dados e Identificadores

### 10.1. Camadas

| Arquivo | Responsabilidade |
| :--- | :--- |
| `models.py` | Persistência e invariantes de dados. |
| `forms.py` | Entrada e validação de interface. |
| `services.py` | Regras de negócio, cálculos e orquestração. |
| `views.py` | Controladores enxutos: recebem, delegam, respondem. |

---

### 10.2. Transações e concorrência

Operações críticas que envolvem múltiplos registros ou invariantes (conflito de recursos, capacidade, saldo, estado) DEVEM usar `django.db.transaction.atomic()` e barrar a operação com **erro claro**, nunca com aviso ignorável. Quando possível, reforçar a invariante também no banco (Seção 10.5). Observação: `select_for_update()` não tem efeito em SQLite.

---

### 10.3. Máquinas de estado e histórico

Transições de status são validadas em `services.py` contra uma tabela explícita de transições permitidas. Toda transição grava histórico auditável (quem, quando, de → para) e, quando a regra exigir (ex.: recusa), **justificativa obrigatória**.

---

### 10.4. Identificadores: UUIDv4

Para mitigar enumeração de recursos (IDOR/BOLA) e fingerprinting temporal:

1. Todo identificador exposto (URLs, APIs, templates) de **usuários e recursos do sistema** é **UUIDv4**, com o módulo nativo (`import uuid`), sem dependência extra. A regra vale principalmente para rotas públicas e se estende a todos os recursos.
2. Modelo-base em `core`:

```python
import uuid
from django.db import models

class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
```

3. Rotas usam `<uuid:id>`. `<int:pk>` é proibido em rotas de recursos.
4. O **usuário customizado com chave UUID deve existir antes da primeira migração** (`AUTH_USER_MODEL`); alterá-lo depois é custoso.
5. **UUID não é autorização.** Continuam obrigatórias as checagens de propriedade/permissão (Seção 17.3).
6. UUID não é segredo nem token de acesso. Tokens seguem a Seção 18.
7. Alternativa aceita: PK inteira interna + campo `public_id` UUID, quando uma app exigir PK sequencial. Registrar em ADR no Doc ② §13.

---

### 10.5. Integridade no banco

"Valide no banco": usar `NOT NULL`, `UNIQUE`, `CheckConstraint`, chaves estrangeiras com `on_delete` deliberado. Alterações de esquema apenas por migrações formais (`makemigrations` / `migrate`); nunca editar o arquivo de banco manualmente.

---

### 10.6. Tenancy: contrato neutro (preparação)

**Princípio.** Tenancy (atender várias organizações em uma mesma instalação) é uma **decisão arquitetural de cada produto**, declarada no Doc ② §8.8. Este documento **não escolhe o modelo**: fixa um contrato neutro e o padrão `single`. Sem declaração no Doc ②, o projeto é `single`.

**Modos reconhecidos:**

| Modo | Isolamento | Posição neste padrão |
| :--- | :--- | :--- |
| `single` | Uma instalação por cliente; nenhum código de tenancy | **Padrão** |
| `row` | Mesmo banco e esquema, com coluna de escopo | **Único modo com referência neste documento** |
| `schema` | Um *schema* por tenant (exige PostgreSQL, inclusive em desenvolvimento) | Somente por ADR (Doc ② §13) e biblioteca justificada no plano (ex.: `django-tenants`). Contradiz o SQLite local do padrão, e o ADR deve tratar disso. |
| `database` | Um banco por tenant (roteador de bancos) | Somente por ADR |

**Contrato do resolvedor** (em `apps/core`):

1. Setting `TENANCY_MODE` lida do `.env` (`single` | `row` | `schema` | `database`; padrão `single`).
2. Função única `get_tenant(request)`, que devolve o tenant da requisição. Em `single`, devolve sempre o mesmo tenant fixo. Nos demais modos, resolve por subdomínio, prefixo de caminho ou vínculo do usuário, conforme o Doc ② §8.8.
3. Tarefas em segundo plano, comandos de gerenciamento e testes recebem o tenant **explicitamente**. Não há estado global compartilhado.
4. Mudar o `TENANCY_MODE` de um projeto em uso exige ADR e migração planejada; não é uma troca de `.env`.

**Escopo é mais uma dimensão do queryset escopado** (Seção 17.3). Em `row`, os modelos com escopo herdam de um modelo-base do `core` (campo de tenant + gerenciador que filtra pelo tenant corrente). Em `single`, o campo **não é criado** (evita custo), mas valem as regras de preparação abaixo.

**Regras de preparação (valem em qualquer modo, inclusive `single`):**

1. Unicidade pensada **por escopo** (`UniqueConstraint` composto), e não global, quando o dado puder se repetir entre organizações (código, slug, número).
2. Configurações do sistema guardadas como **dado com escopo** (tenant, com *fallback* global), e não como constantes no código: tema (Seção 11.12), visibilidade das páginas públicas (Seção 11.1), parâmetros do produto e credenciais de integração.
3. **Prefixo de escopo** em caminhos de arquivos (Seção 15.5), chaves de cache e chaves de rate limit (Seção 19.3).
4. **Campo de escopo** no registro de auditoria (Seção 21.1) e no contexto das tarefas em segundo plano.
5. A app declara no README quais modelos têm escopo (Seção 9.3).

**Segurança:**

1. O tenant **nunca** vem de dado informado pelo cliente (cabeçalho, parâmetro, corpo) sem checagem do vínculo do usuário com aquele tenant.
2. Vazamento entre tenants é a forma mais grave de BOLA: responde `404` (Seção 17.2) e tem teste obrigatório (Seção 22.1).
3. Operação **entre tenants** só por perfil de escopo global (Seção 17.6), sempre auditada.
4. Credenciais de integração por tenant (ex.: OAuth) ficam **cifradas com Fernet no banco** (Seção 18.1), e não no `.env`.

**Evolução híbrida por camada** (maioria dos tenants em banco compartilhado e alguns isolados): fora deste padrão; o contrato acima não a impede.

---

## 11. Interface Base, Navegação e Temas

### 11.1. Páginas públicas (landing e apresentação)

A página inicial pública apresenta o produto, seus benefícios e características. O conteúdo é definido no Doc ② §3. Sua exibição é **controlada pelo RBAC**:

| Visibilidade pública | Rota `/` | Páginas públicas controláveis |
| :--- | :--- | :--- |
| **Ativa** | Landing/apresentação, com botão **Login** destacado | Acessíveis sem autenticação |
| **Desativada** | **Tela de login** | Respondem `404` (e não `403`), pela política anti-enumeração da Seção 17.2 |

Regras:

1. A visibilidade é uma **configuração com escopo** (Seção 10.6), alterada somente por quem tem a funcionalidade `site.visibilidade_publica` (Seção 17.5). Padrão do ecossistema: **ativa**; cada produto declara o valor inicial no Doc ② §3.
2. Pode haver um interruptor geral e, opcionalmente, uma *flag* por página pública (ex.: landing ativa e página institucional oculta).
3. **Nunca** ficam sob esse controle: login, recuperação de senha, páginas de erro e política de privacidade/termos (LGPD).
4. Com a visibilidade desativada, a NAVBAR pública não exibe links para as páginas ocultas, e o usuário já autenticado que acessa `/` vai direto para a home do seu perfil. Com a visibilidade ativa, o autenticado vê a landing com um atalho "Ir para o sistema" (ajustável no Doc ② §3).
5. Alterar a visibilidade é registrado na auditoria (Seção 21.1) e invalida o cache dessas páginas.
6. Requisitos técnicos: acessível sem autenticação, sem dados privados, compatível com a CSP (Seção 14), título e `meta description`.

---

### 11.2. Menus e NAVBAR

- Todas as funcionalidades de usuário DEVEM estar acessíveis por menus da **aplicação**, e não somente via Django Admin.
- Os menus da NAVBAR são **agrupados por assunto e funções correlatas**.
- Links e visibilidade derivam da **mesma fonte do RBAC** (Seção 17.4). Ocultar um item **não** protege a rota; a verificação é sempre no backend.
- As configurações do site (**Aparência/tema** e **Visibilidade pública**) são itens do grupo **Administração**, visíveis conforme a matriz.
- NAVBAR pública: botão Login. NAVBAR autenticada: nome, avatar, notificações com badge e dropdown de perfil, com **Sair via POST**.

---

### 11.3. Django Admin

O Admin é ferramenta de backoffice técnico e **não substitui** a interface do produto. Regras:

- URL não padrão, lida de `ADMIN_URL` no `.env`;
- acesso restrito a perfis técnicos/administrativos (`is_staff` + RBAC);
- coberto pelo mesmo **rate limit/lockout** de login (Seção 19);
- somente sobre HTTPS; MFA recomendada.

---

### 11.4. Base visual

- `templates/base.html` é uma **casca fina**: a estrutura vem do tema ativo (Seção 11.5). As cores vêm do `/tema.css` gerado pela aplicação, e a estrutura estática vem de `static/css/base.css`.
- Bootstrap 5 e Bootstrap Icons por **CDN, com versão fixada e SRI** (`integrity` com o hash oficial da versão, `crossorigin="anonymous"`). Sem Node.js no WSL.
- **Sem `style="..."` e sem `onclick="..."` inline** (a CSP os bloqueia). JS e CSS em arquivos estáticos.
- Tipografia: pilhas de fontes do sistema, por padrão. Fonte web externa é exceção: o host entra na CSP e é registrado no Doc ② §10.
- O tema padrão do produto, os modelos habilitados e o briefing de design são definidos no Doc ② §4.

---

### 11.5. Sistema de temas: princípio e arquitetura

**Objetivo:** trocar cores, estilo e layout do sistema **inteiro** sem editar nenhuma página de domínio.

| Camada | Papel | Muda com o tema? |
| :--- | :--- | :-: |
| Tokens (variáveis CSS) | Três cores (Fundos, Destaques, Escritas) e derivados | Sim (`/tema.css`) |
| Eixos de estilo (atributos `data-*` em `<html>`) | Raio, sombra, densidade, movimento, tipografia, ícones | Sim |
| HTMLs-base (cascas e tipos de página) | Estrutura de layout, em variantes (Seção 11.11) | Sim (escolhe a variante) |
| Componentes de UI | Lista, formulário, detalhe, cartão, painel | Sim (uma implementação por variante) |
| **Páginas de domínio** | Conteúdo e dados | **Não** |

Regras de contrato:

1. Páginas de domínio **não contêm estilo, cor fixa nem estrutura de casca**. Elas estendem `base.html` e preenchem os **blocos nomeados**: `title`, `meta`, `extra_head`, `page_title`, `page_subtitle`, `toolbar_actions`, `navbar_notifications`, `content`, `extra_js`. **Toda variante de casca implementa o mesmo conjunto de blocos.**
2. `base.html` estende a casca escolhida pelo tema (`{% extends shell_template %}`, com `shell_template` fornecido por um context processor).
3. Lista, formulário, detalhe e painel são **componentes** (inclusão ou tag) com uma implementação por variante. A página de domínio entrega dados e rótulos, não markup de layout.
4. Trocar tema, cor ou layout **não exige alterar, regenerar nem retestar manualmente** as páginas de domínio. Um teste automatizado garante isso (Seção 22.1).
5. O context processor do tema **nunca falha**: com configuração ausente, inválida ou indisponível, aplica o tema padrão (Profissional, T05).
6. A luminância dos **Fundos** define se o tema é claro ou escuro, e `data-bs-theme` (`light`/`dark`) em `<html>` faz os componentes do Bootstrap (formulários, dropdowns, tabelas) acompanharem.

---

### 11.6. Catálogo de modelos de design (10)

Cada modelo é um **preset** (três cores, eixos de estilo e layouts padrão). **T10 Outro** é o modelo livre.

| ID | Modelo | Personalidade e uso | Aparência (forma, tipografia, superfícies, ícones) | Movimento | Paleta padrão (Fundos · Destaques · Escritas) |
| :-: | :--- | :--- | :--- | :--- | :--- |
| T01 | **Alegre** | Vivo e acolhedor; serviços ao cidadão, educação, públicos amplos | Cantos bem arredondados; botões em pílula; sombras suaves; sans arredondada; ícones preenchidos | Micro-interações discretas | `#FFFBF0` · `#E4572E` · `#2B2118` |
| T02 | **Sofisticado** | Elegante e contido; institucional e consultoria | Cantos suaves; sem sombras (filetes finos); títulos serifados e corpo sans; muito espaço em branco; ícones de contorno fino | Transições lentas e suaves | `#F5F1EA` · `#7B2D3B` · `#1F1B16` |
| T03 | **Sóbrio** | Neutro e formal; governo, jurídico, financeiro | Cantos retos ou mínimos; sem sombras; bordas finas; sans do sistema; densidade compacta; ícones de contorno | Nenhum | `#F1F5F9` · `#334155` · `#0F172A` |
| T04 | **Animado** | Dinâmico e energético; produtos de consumo e comunidades | Cantos arredondados; sombras marcadas, cartões que "flutuam"; sans arredondada; ícones preenchidos | **Expressivo**: entrada de elementos, elevação no hover, transições entre telas | `#FAF5FF` · `#7E22CE` · `#1E1B4B` |
| T05 | **Profissional** (padrão do ecossistema) | Corporativo equilibrado; uso geral e sistemas internos | Cantos suaves; sombras muito leves; sans do sistema; densidade confortável; ícones de contorno | Discreto | `#F8FAFC` · `#1E3A8A` · `#0F172A` |
| T06 | **Luxuoso** | Exclusivo; produtos de alto valor | Tema escuro quente; cantos retos; filetes e detalhes no tom de Destaque; títulos serifados; muito espaço; ícones de contorno fino | Fades lentos | `#16120F` · `#D4AF37` · `#F6EEDC` |
| T07 | **SoftClean** | Leve e limpo; bem-estar, saúde e cuidado | Cantos arredondados; sombras difusas muito suaves; sans em peso leve; muito espaço; ícones de contorno | Discreto | `#FBFBFD` · `#4A76A8` · `#334155` |
| T08 | **Noturno** | Modo escuro neutro; uso prolongado e pouca luz | Fundo escuro frio (sem preto puro); bordas luminosas sutis no lugar de sombras; cantos suaves; ícones de contorno | Discreto | `#12141A` · `#4FA3FF` · `#E6E8EE` |
| T09 | **Acessível** | Alto contraste e leitura facilitada | Bordas de 2 px; foco reforçado; texto-base maior; espaçamento amplo; ícones sempre com rótulo; contraste de texto ≥ 7:1 (AAA) | **Nenhum** | `#FFFFFF` · `#0B3D91` · `#000000` |
| T10 | **Outro** | Modelo livre | Parte do Profissional e libera as três cores (Seções 11.8 e 11.9), os eixos de estilo (Seção 11.10) e os layouts (Seção 11.11) | Livre | Livre |

Regras:

1. **Personalizar:** nos modelos T01 a T09 as cores, os eixos e os layouts são os do preset. Qualquer alteração passa pelo botão **Personalizar**, que copia o preset para **T10 Outro** e libera a edição. Os presets permanecem canônicos.
2. Em qualquer modelo, o movimento respeita `prefers-reduced-motion` (Seção 11.12).
3. Todas as paletas padrão acima atendem os mínimos de contraste da Seção 11.7.

---

### 11.7. As três cores: Fundos, Destaques e Escritas

| Campo | O que controla |
| :--- | :--- |
| **Fundos** | Fundo da página e base das superfícies (cartões, painéis) |
| **Destaques** | Barra de marca/NAVBAR, botões primários, links, foco, itens selecionados, ênfases |
| **Escritas** | Texto principal; base do texto atenuado e das bordas |

**Derivados**, gerados no servidor de forma determinística (e portanto testável): superfície, borda, texto atenuado, destaque em hover/ativo, anel de foco e **texto sobre Destaque** (branco ou preto, o de maior contraste, sempre ≥ 4,5:1).

**Cores semânticas** (sucesso, perigo, alerta, informação) **não fazem parte das três cores**: são fixas e ajustadas automaticamente para manter contraste com os Fundos. Assim, um Destaque verde não se confunde com "sucesso", e a informação nunca é transmitida só por cor.

**Contraste (WCAG 2.1):**

| Par | Mínimo | Se reprovar |
| :--- | :--- | :--- |
| Escritas × Fundos | 4,5:1 (7:1 no modelo Acessível) | **Bloqueia** o Aplicar |
| Destaques × Fundos | 3:1 (4,5:1 no modelo Acessível) | **Bloqueia** o Aplicar |
| Texto sobre Destaques | 4,5:1 | Automático (escolhe branco ou preto) |

A tela mostra a razão de cada par e sugere a correção automática mais próxima (ajusta a luminosidade preservando o matiz). Exemplo: `#5B3961` sobre `#59ADFF` resulta em 4,0:1 e é reprovado.

---

### 11.8. Seletor de cores (componente)

Cada uma das três cores tem um campo com **amostra e valor hexadecimal visíveis**. Clicar abre o seletor, num diálogo "Editar cores" com botões **OK** e **Cancelar**. O seletor é um componente próprio, descrito a seguir.

1. **Área principal 2D:** o eixo horizontal é o **matiz** (espectro do vermelho ao vermelho) e o vertical é a **saturação** (do tom vivo, no topo, ao branco, na base). O cursor circular é arrastável por mouse ou toque e escolhe matiz e saturação.
2. **Barra vertical de brilho**, ao lado da área, do claro ao preto, com marcador circular arrastável.
3. **Amostra** grande da cor atual.
4. **Campo Hexadecimal** (`#RRGGBB`), **sempre exibido** com a cor selecionada e atualizado ao vivo. Aceita com ou sem `#`, em 3 ou 6 dígitos, e normaliza para maiúsculas.
5. **Seletor de modo de entrada**, com **RGB** como padrão e os campos **Vermelho, Verde e Azul** (0–255). Os modos HSB e HSL são opcionais.
6. **Nome da cor** em *tooltip* (pt-BR) ao mover o cursor sobre a área ("Vermelho", "Azul claro", "Roxo escuro"), obtido da cor nomeada mais próxima em uma tabela de nomes.
7. **Cores básicas:** linha fixa de 12 amostras (rosa-salmão, vermelho, tons de marrom, ciano claro, ciano e tons de azul).
8. **Cores personalizadas:** 6 espaços tracejados e botão **+** que salva a cor atual no próximo espaço livre (ao encher, substitui a mais antiga). Persistidas **por usuário**, como conveniência pessoal.
9. **Indicador de contraste** do par em edição (razão e aprovado/reprovado), conforme a Seção 11.7.
10. **Teclado e acessibilidade:** setas movem o cursor (1 unidade; `Shift` = 10), `Tab` percorre os campos, `Esc` cancela; `role="dialog"` com foco preso e rótulos ARIA em português. Tudo é possível sem mouse pelos campos Hexadecimal e RGB.
11. **Implementação:** JS estático próprio, sem biblioteca externa e **sem estilo inline** (cursor e amostra são posicionados por CSSOM/variáveis CSS). Sem JavaScript, o campo cai para `<input type="color">` mais o campo Hexadecimal.
12. Ao abrir o seletor a partir de uma paleta sugerida (Seção 11.9), ele parte da cor atual da paleta. Alterar qualquer das três cores marca a paleta como **Personalizada**.

---

### 11.9. Paletas sugeridas (20)

Ao selecionar uma paleta, as três cores são aplicadas à **pré-visualização** (e ao sistema somente após **Aplicar**). A lista é de **sugestões**: o usuário pode editar qualquer uma das três cores pelo seletor (Seção 11.8) ou ignorar as paletas e escolher as três do zero. Todas atendem os mínimos de contraste da Seção 11.7 (razões na tabela). As paletas e o seletor estão disponíveis no modelo **T10 Outro**.

| ID | Paleta | Fundos | Destaques | Escritas | Escritas × Fundos | Destaques × Fundos |
| :-: | :--- | :--- | :--- | :--- | :-: | :-: |
| P01 | Oceano | `#F0F7FF` | `#0B5FA5` | `#0B1F33` | 15,5:1 | 6,1:1 |
| P02 | Floresta | `#F2F8F2` | `#1F6B3A` | `#10261A` | 14,8:1 | 6,0:1 |
| P03 | Terracota | `#FBF4EE` | `#B4502B` | `#2B1A12` | 15,3:1 | 4,7:1 |
| P04 | Lavanda | `#F7F3FF` | `#6D3FC4` | `#231942` | 14,9:1 | 6,1:1 |
| P05 | Grafite | `#F4F4F5` | `#3F3F46` | `#18181B` | 16,1:1 | 9,5:1 |
| P06 | Areia | `#FAF6EE` | `#9A6B1F` | `#2E2412` | 14,1:1 | 4,3:1 |
| P07 | Cereja | `#FFF5F6` | `#B3123A` | `#2A0E15` | 16,8:1 | 6,4:1 |
| P08 | Menta | `#F0FBF8` | `#0F766E` | `#0B2B28` | 14,3:1 | 5,2:1 |
| P09 | Céu | `#F2F9FF` | `#0369A1` | `#0C2A3D` | 14,0:1 | 5,6:1 |
| P10 | Pôr do sol | `#FFF7ED` | `#C2410C` | `#3B1B0A` | 14,7:1 | 4,9:1 |
| P11 | Ameixa | `#F8F2F8` | `#7A2E7E` | `#2B112C` | 15,6:1 | 7,6:1 |
| P12 | Esmeralda noturna | `#0B1F1A` | `#34D399` | `#E6FFF5` | 16,3:1 | 8,9:1 |
| P13 | Índigo noturno | `#0F1B3D` | `#8AB4FF` | `#E8EEFF` | 14,5:1 | 8,1:1 |
| P14 | Bordô e creme | `#FFF8F0` | `#7B1E3A` | `#2A1015` | 16,8:1 | 9,5:1 |
| P15 | Rosa chá | `#FFF5F7` | `#BE185D` | `#3A0A1F` | 15,8:1 | 5,7:1 |
| P16 | Turquesa | `#F0FDFC` | `#0E7490` | `#082F3A` | 13,6:1 | 5,1:1 |
| P17 | Oliva | `#F6F7EE` | `#5B6B1F` | `#1F2410` | 14,8:1 | 5,5:1 |
| P18 | Cobalto | `#F3F6FF` | `#1D4ED8` | `#0B1B4D` | 15,2:1 | 6,2:1 |
| P19 | Névoa | `#F5F7FA` | `#4B6584` | `#1B2733` | 14,1:1 | 5,6:1 |
| P20 | Alto contraste | `#FFFFFF` | `#0033A0` | `#000000` | 21,0:1 | 10,6:1 |

---

### 11.10. Eixos de estilo

Além das cores, o estilo tem seis eixos. Cada modelo define seus valores (Seção 11.6); em T10 Outro todos são livres. São aplicados por atributos `data-*` em `<html>` lidos por `base.css`, sem regenerar páginas.

| Eixo | Atributo | Opções | Efeito |
| :--- | :--- | :--- | :--- |
| Raio dos cantos | `data-raio` | `reto`, `suave`, `arredondado`, `pilula` | Cartões, botões, campos |
| Sombra | `data-sombra` | `nenhuma` (só bordas), `suave`, `marcada`, `difusa` | Profundidade das superfícies |
| Densidade | `data-densidade` | `compacta`, `confortavel`, `ampla` | Espaçamentos e altura de campos e linhas |
| Movimento | `data-movimento` | `nenhum`, `discreto`, `expressivo` | Duração e tipo de transições |
| Tipografia | `data-tipografia` | `sans`, `arredondada`, `serifa-titulos` | Pilha de fontes **do sistema** |
| Ícones | `data-icones` | `contorno`, `preenchido` | Variante do ícone escolhida pelos componentes |

---

### 11.11. Variantes de layout por HTML-base

Cada HTML-base tem **variantes** de layout: não apenas cor, mas a **estrutura** da página muda. A variante é escolhida por tipo de página (padrão do modelo, ajustável em T10 Outro). As páginas de domínio não mudam (Seção 11.5).

| HTML-base | Variante | Descrição |
| :--- | :--- | :--- |
| **Casca autenticada** (`shell`) | `topo` | NAVBAR superior fixa, toolbar da página abaixo, conteúdo em largura total |
| | `lateral` | Menu em barra lateral fixa à esquerda; barra superior mínima (busca, notificações, perfil); toolbar dentro do conteúdo |
| | `lateral-recolhivel` | Barra lateral que recolhe para ícones (rótulos em *tooltip*), com o estado memorizado por usuário |
| **Landing/apresentação** | `hero-centralizado` | Proposta de valor centrada com botão Login, seções empilhadas |
| | `hero-dividido` | Texto e chamada de um lado, área visual estática (imagem/ilustração) do outro |
| | `faixas` | Página única em faixas alternadas por seção, com âncoras no topo |
| **Login** | `cartao` | Cartão centralizado sobre o fundo |
| | `dividido` | Tela dividida: painel de marca (logo, frase, cor de Destaque) e formulário |
| | `coluna` | Formulário em coluna lateral estreita sobre fundo de marca |
| **Lista/relatório** | `tabela` | Tabela com cabeçalho fixo, ordenação e paginação |
| | `cartoes` | Grade de cartões com os campos-chave e ações |
| | `compacta` | Lista densa com expansão in-line por seta, sem perder a rolagem |
| **Formulário** | `coluna-unica` | Campos em uma coluna |
| | `duas-colunas` | Campos agrupados em duas colunas |
| | `passos` | Etapas com indicador de progresso e validação por etapa |
| **Detalhe/dossiê** | `abas` | Página dedicada com abas (Resumo, Histórico, Documentos etc.) |
| | `drawer` | Painel lateral (*offcanvas*, 35% a 45% da largura) com abas e "Mais Ações", e link "Ver completo" |
| | `secoes` | Rolagem contínua com índice lateral de âncoras |
| **Painel (dashboard)** | `grade-de-cartoes` | Indicadores e gráficos em grade |
| | `faixa-e-tabela` | Faixa de indicadores no topo e tabela/lista abaixo |
| | `colunas-2-1` | Coluna principal larga e coluna lateral de avisos e atalhos |
| **Erro / estado vazio** | `minimo` | Texto e ação |
| | `ilustrado` | Ilustração SVG estática, texto e ação |
| | `com-atalhos` | Sugestões de áreas permitidas ao perfil (na 404, sem expor rotas não autorizadas) |
| **Conta** (perfil, configurações, recuperação de senha) | — | Reutiliza as variantes de **Login** (recuperação) e de **Formulário** (perfil e configurações) |

Observações: em telas pequenas, todas as cascas viram menu deslizante (*offcanvas*). Uma visão adicional de lista definida pelo produto (ex.: kanban, alternável com a tabela) é declarada no Doc ② §4.5. A ordem do formulário de login vale em **todas** as variantes de Login (Seção 16.2).

**Layout padrão por modelo:**

| Modelo | Casca | Landing | Login | Lista | Formulário | Detalhe | Painel | Erro |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T01 Alegre | `topo` | `hero-dividido` | `dividido` | `cartoes` | `passos` | `drawer` | `grade-de-cartoes` | `ilustrado` |
| T02 Sofisticado | `lateral` | `faixas` | `dividido` | `tabela` | `duas-colunas` | `abas` | `colunas-2-1` | `minimo` |
| T03 Sóbrio | `topo` | `hero-centralizado` | `cartao` | `tabela` | `coluna-unica` | `abas` | `faixa-e-tabela` | `minimo` |
| T04 Animado | `topo` | `hero-dividido` | `dividido` | `cartoes` | `passos` | `drawer` | `grade-de-cartoes` | `ilustrado` |
| T05 Profissional | `topo` | `hero-centralizado` | `cartao` | `tabela` | `duas-colunas` | `abas` | `colunas-2-1` | `com-atalhos` |
| T06 Luxuoso | `lateral` | `faixas` | `dividido` | `tabela` | `duas-colunas` | `secoes` | `colunas-2-1` | `minimo` |
| T07 SoftClean | `lateral-recolhivel` | `hero-centralizado` | `cartao` | `cartoes` | `coluna-unica` | `drawer` | `grade-de-cartoes` | `ilustrado` |
| T08 Noturno | `lateral-recolhivel` | `hero-centralizado` | `cartao` | `compacta` | `duas-colunas` | `abas` | `colunas-2-1` | `minimo` |
| T09 Acessível | `topo` | `hero-centralizado` | `cartao` | `tabela` | `coluna-unica` | `secoes` | `faixa-e-tabela` | `minimo` |
| T10 Outro | Parte do T05 Profissional; todas as variantes livres | | | | | | | |

---

### 11.12. Configuração, permissão e operação do tema

1. **Armazenamento:** `ConfigTema`, um **dado com escopo** (Seção 10.6), na app `site`: modelo, três cores (`#RRGGBB`), eixos de estilo, variante por tipo de página e versão.
2. **Permissão (RBAC):** funcionalidade `site.tema_editar` (Seção 17.5). Padrão: grupos 3 e 4; **delegável** a outros perfis pela matriz. A tela fica no item **Aparência** do grupo Administração.
3. **Fluxo:** escolher o modelo → (opcional) **Personalizar** → escolher uma paleta sugerida e/ou editar cada uma das três cores no seletor (com o hexadecimal visível) → ajustar eixos e layouts → **pré-visualização** → validação de contraste → **Aplicar**.
4. **Pré-visualização:** painel de amostra na própria tela (cabeçalho, botões, formulário, tabela, alerta), com as variáveis aplicadas por CSSOM em JS estático. Sem iframe, sem estilo inline, compatível com a CSP. Nada muda para os demais usuários até o **Aplicar**.
5. **Restaurar padrão:** volta ao modelo e à paleta padrão do produto (Doc ② §4.2), com confirmação por POST.
6. **Entrega do CSS:** `/tema.css` é uma rota **pública** (a tela de login precisa dela), gerada **somente** de valores validados: hexadecimal `^#[0-9A-Fa-f]{6}$` e opções de listas fechadas. **Nunca** interpolar texto livre. Servida com `Content-Type: text/css`, URL versionada (`?v=<hash>`) e cache longo; a versão muda a cada **Aplicar**. A CSP já cobre (`style-src 'self'`), sem exceção.
7. **Resiliência:** configuração ausente, inválida ou indisponível aplica o tema padrão. A página `500` usa apenas `base.css` (fallback do tema Profissional) e não consulta o banco.
8. **E-mails** transacionais (ex.: recuperação de senha) usam os três valores do tema ativo em estilo inline (a CSP não se aplica a e-mail). O layout do e-mail é fixo; só as cores variam.
9. **Auditoria:** quem, quando e valores antes/depois, com o escopo (Seção 21.1).
10. **Escopo:** global; por tenant quando o modo não for `single` (Seção 10.6).
11. **Preferência individual** por usuário (ex.: modo escuro pessoal) não faz parte deste padrão: o tema é do sistema.
12. **Acessibilidade:** `prefers-reduced-motion` é honrado em qualquer modelo; o foco é sempre visível; nenhuma informação é transmitida só por cor.

---

# PARTE C — DOMÍNIO: SEGURANÇA GLOBAL DA APLICAÇÃO

*(§12–§21: piso de segurança de toda aplicação Django do ecossistema. Valores específicos e exceções: Doc ② §10.)*

---

## 12. Princípios e Hardening de Settings

### 12.1. Princípios

- **Seguro por padrão:** todo valor-padrão do código é o seguro; relaxar exige exceção registrada (Doc ② §10).
- **Negar por padrão** (default deny) e **menor privilégio**.
- **Defesa em profundidade:** nenhuma camada confia na anterior.
- **Falhar fechado:** na dúvida, negar.

O limite deste baseline é a aplicação. Infraestrutura de produção (proxy, certificados, WAF) segue em documentação do projeto.

---

### 12.2. Middlewares de segurança do Django

O Django já trata boa parte da segurança por middlewares. Eles DEVEM permanecer habilitados e na ordem gerada pelo `startproject`: `SecurityMiddleware`, `SessionMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, `XFrameOptionsMiddleware`. Pode-se reforçar; **remover é proibido**. A tarefa do projeto é **verificar e endurecer os valores** (HSTS, CSRF, cookies, cabeçalhos), conforme a Seção 12.3.

---

### 12.3. Baseline de settings

```python
# settings.py — baseline de segurança (valores seguros por padrão; DEBUG apenas local)
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])           # nunca ['*'] fora do local
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])  # com esquema: https://dominio

# Transporte (HTTPS)
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0 if DEBUG else 3600)  # elevar até 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)

# Cookies, sessão e CSRF
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Cabeçalhos (declarados explicitamente, mesmo coincidindo com defaults do Django)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'

# Limites de entrada (Seção 15.4)
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int('DATA_UPLOAD_MAX_MEMORY_SIZE', default=1_048_576)  # 1 MiB
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int('DATA_UPLOAD_MAX_NUMBER_FIELDS', default=500)
```

Regras associadas:

1. **HSTS:** em produção, iniciar com valor baixo, validar o HTTPS em todo o domínio e só então elevar até 1 ano. `SECURE_HSTS_PRELOAD` somente com decisão consciente (é de difícil reversão).
2. **Proxy reverso:** `SECURE_PROXY_SSL_HEADER` só pode ser definido quando houver proxy confiável que **sobrescreve** o cabeçalho; nunca por padrão. Valor concreto → Doc ② §10.
3. Os valores `same-origin` de Referrer-Policy e COOP, e `DENY` de frames, são o padrão. Relaxamentos (ex.: `SAMEORIGIN`) pertencem ao projeto e exigem exceção registrada.
4. `python manage.py check --deploy`, com variáveis de produção simuladas, não pode apontar avisos de segurança sem justificativa. É item do Doc ② §12 (DoD).

---

## 13. Cookies, Sessão e CSRF

### 13.1. Cookies

- Cookie de sessão, tokens (acesso, refresh, JWT) e **quaisquer chaves sensíveis em cookies** DEVEM ter `HttpOnly`, `Secure` (HTTPS) e `SameSite`. Objetivo: impedir roubo/sequestro de sessão por script injetado.
- Tokens **nunca** em `localStorage` ou `sessionStorage`.
- Exceção: cookie que o JavaScript precise ler (ex.: token CSRF em chamadas `fetch`). Registrar no Doc ② §10. Preferir enviar o token CSRF pelo DOM (meta tag/campo oculto) ou usar `CSRF_USE_SESSIONS`.

---

### 13.2. Sessão

- Rotacionar a sessão no login e invalidá-la no logout (comportamento nativo do Django, não contornar).
- Invalidar sessões ao trocar a senha (`update_session_auth_hash`).
- Tempo de vida (`SESSION_COOKIE_AGE`) e expiração por inatividade definidos no Doc ② §9.

---

### 13.3. CSRF

- `CsrfViewMiddleware` sempre ativo. Todo formulário POST contém `{% csrf_token %}`; chamadas AJAX enviam `X-CSRFToken`.
- `@csrf_exempt` é proibido, exceto em endpoint de webhook autenticado por assinatura HMAC (Seção 18.3).

---

### 13.4. Métodos HTTP

- **Nunca** alterar estado via GET/HEAD. Alteração, exclusão e logout são sempre **POST** (ou PUT/PATCH/DELETE em APIs), sobre **HTTPS**.
- Usar `@require_POST` / `require_http_methods` e tratar o `405`.
- "Excluir" é um formulário POST com confirmação, nunca um link.

---

## 14. CSP e Clickjacking

### 14.1. Princípio

A CSP DEVE ser **restrita e baseada em allowlist (whitelist), nunca em blacklist**: `default-src` restritivo, fontes explícitas por diretiva, sem `*`, sem `'unsafe-inline'` e sem `'unsafe-eval'`.

---

### 14.2. Baseline de diretivas

| Diretiva | Baseline |
| :--- | :--- |
| `default-src` | `'self'` |
| `script-src` | `'self'` + nonce + hosts de CDN em allowlist |
| `style-src` | `'self'` + nonce + hosts de CDN em allowlist |
| `img-src` | `'self'` `data:` |
| `font-src` | `'self'` + host da CDN de fontes/ícones |
| `connect-src` | `'self'` |
| `object-src` | `'none'` |
| `base-uri` | `'self'` |
| `form-action` | `'self'` |
| `frame-ancestors` | `'none'` |
| `upgrade-insecure-requests` | ativa em produção |

---

### 14.3. Implementação por versão do Django

- **Django ≥ 6.0:** suporte nativo (`ContentSecurityPolicyMiddleware`, `SECURE_CSP`, `SECURE_CSP_REPORT_ONLY`, nonce pelo context processor `django.template.context_processors.csp`).
- **Django < 6.0:** `django-csp` (dependência a justificar no plano).

```python
# Django >= 6.0
from django.utils.csp import CSP

CDN = 'https://cdn.jsdelivr.net'
SECURE_CSP_REPORT_ONLY = {   # fase inicial; migrar a mesma política para SECURE_CSP ao impor
    'default-src': [CSP.SELF],
    'script-src': [CSP.SELF, CSP.NONCE, CDN],
    'style-src': [CSP.SELF, CSP.NONCE, CDN],
    'img-src': [CSP.SELF, 'data:'],
    'font-src': [CSP.SELF, CDN],
    'connect-src': [CSP.SELF],
    'object-src': [CSP.NONE],
    'base-uri': [CSP.SELF],
    'form-action': [CSP.SELF],
    'frame-ancestors': [CSP.NONE],
}
# MIDDLEWARE += ['django.middleware.csp.ContentSecurityPolicyMiddleware']
# TEMPLATES[...]['OPTIONS']['context_processors'] += ['django.template.context_processors.csp']
```

Em templates, o nonce é usado como `<script nonce="{{ csp_nonce }}">`. Páginas que usam nonce **não podem ser servidas de cache compartilhado**.

---

### 14.4. Implantação gradual

1. Publicar em **Report-Only** e coletar violações.
2. Corrigir templates (remover `style=`/`onclick=` inline, mover scripts para arquivos estáticos).
3. Impor (`SECURE_CSP`).

---

### 14.5. Anti-clickjacking e embed

- A aplicação NÃO pode ser embutida (iframe) em outro site: `frame-ancestors 'none'` + `X_FRAME_OPTIONS = 'DENY'` (compatibilidade com navegadores antigos).
- Relaxar para a própria origem (`'self'` / `SAMEORIGIN`) só quando o produto exigir (ex.: pré-visualização de documento em iframe). É particularidade do projeto: exceção registrada no Doc ② §10.

---

### 14.6. Recursos de terceiros

CDN somente em allowlist exata, **versão fixa**, com **SRI** e `crossorigin="anonymous"`. Adicionar um host novo à CSP é mudança de segurança e exige registro no Doc ② §10.

---

## 15. Entrada de Dados: Validação, Sanitização e Limites

### 15.1. Injeção de SQL

O ORM do Django trata SQL por parâmetros; **usar sempre o ORM**. `raw()`, `extra()` e `cursor.execute()` só com parâmetros ligados (`%s`), nunca com concatenação ou f-string, e com revisão explícita.

---

### 15.2. Três camadas de validação

| Camada | Onde | O que valida |
| :--- | :--- | :--- |
| **Entrada** | Forms, serializers, parâmetros de GET/POST/rota/cabeçalhos/cookies/uploads | Tipo, tamanho, formato, domínio de valores. |
| **Transporte (DTO)** | Objetos tipados entregues a `services.py` (dataclass, Pydantic ou serializer) | Services recebem dados já validados e tipados, **nunca** `request.POST`/`request.GET` cru. |
| **Banco** | Constraints (Seção 10.5) | Invariantes que sobrevivem a qualquer caminho de escrita. |

Nenhuma camada confia na anterior.

---

### 15.3. Sanitização e saída

- Normalizar: `strip`, Unicode NFC, remoção de caracteres de controle; validar por **allowlist** de formato.
- Escapar na saída: autoescape dos templates ativo; `|safe` e `mark_safe` proibidos com conteúdo vindo de usuário.
- HTML rico, se inevitável, só por sanitizador em allowlist (ex.: `nh3`), justificado no plano.
- Dados para JavaScript via `json_script`; sem `eval` e sem `innerHTML` com dado externo.

---

### 15.4. Limites de tamanho e profundidade

Limitar a entrada em **bytes** para impedir negação de serviço, estouro de pilha e recursividade injetada:

- `DATA_UPLOAD_MAX_MEMORY_SIZE` e `DATA_UPLOAD_MAX_NUMBER_FIELDS` (Seção 12.3);
- `max_length` em todo campo de form/serializer; `page_size` máximo em listagens;
- JSON: corpo limitado; **profundidade de aninhamento limitada**; tratar `RecursionError`/`ValueError` como `400`;
- limites de corpo também na borda (ex.: `client_max_body_size`), como complemento, nunca como substituto.

---

### 15.5. Uploads e arquivos compactados

- Limitar tamanho **por arquivo** com validador próprio. Atenção: `FILE_UPLOAD_MAX_MEMORY_SIZE` só define quando o arquivo vai para disco; **não é um limite**.
- Validar extensão **e** tipo real (assinatura/magic bytes) contra allowlist de tipos.
- Renomear com UUID; nunca usar o nome enviado pelo cliente; nunca montar caminho de disco a partir dele (path traversal).
- Imagens: manter `Image.MAX_IMAGE_PIXELS` do Pillow e verificar a imagem (`verify()`).
- **ZipBomb:** preferir não aceitar arquivos compactados. Se necessário, limitar tamanho total descompactado, razão de compressão, número de entradas e profundidade de aninhamento, e nunca extrair sem esses limites.
- Arquivos enviados ficam fora de qualquer diretório público.
- Com tenancy diferente de `single`, o caminho de armazenamento é prefixado pelo escopo do tenant (Seção 10.6).

---

### 15.6. Documentos sensíveis

Documentos sensíveis (saúde, financeiros, pessoais) são servidos **somente** por endpoint autenticado e autorizado (streaming, `FileResponse`) ou por URL pré-assinada de expiração curta (sugestão: 5 minutos, via `django.core.signing`). Nunca link direto ou público. Enviar `X-Content-Type-Options: nosniff`. Acessos são auditados (Seção 21).

---

## 16. Autenticação

> **Autenticação ≠ Autorização.** Autenticar prova *quem* é; a Seção 17 decide *o que pode*.

### 16.1. Senhas: Argon2id

- `PASSWORD_HASHERS` com `django.contrib.auth.hashers.Argon2PasswordHasher` **em primeiro lugar**, seguido dos demais (para migrar hashes antigos no próximo login); `argon2-cffi` no `requirements.txt`.
- `AUTH_PASSWORD_VALIDATORS` ativos. Senhas nunca em log, e-mail ou resposta.

---

### 16.2. Login

- **Login com usuário e senha é obrigatório.** OAuth 2.0/2.1 é complementar (opcional por produto): o sistema não fica dependente só de provedor externo.
- Mensagens de erro genéricas (não revelar se o usuário existe). Logout por POST. Rate limit e lockout (Seção 19), inclusive no Admin.
- **Ordem do formulário de login (padrão obrigatório em qualquer variante de layout, Seção 11.11):**

| # | Elemento | Observação |
| :-: | :--- | :--- |
| 1 | Usuário / e-mail | `autocomplete="username"` |
| 2 | Senha | `autocomplete="current-password"`; botão mostrar/ocultar |
| 3 | Lembrar-me | Somente se o produto usar (Seção 13.2) |
| 4 | Botão **Entrar** | Ação principal |
| 5 | Link **Esqueci minha senha** | **Abaixo do botão**: é um recurso menos usado |
| 6 | Divisor "ou" e botões de login social (OAuth) | Somente se habilitados |
| 7 | Link de cadastro ou solicitação de acesso | Somente se existir |

**"Esqueci minha senha" nunca fica entre o campo de usuário e o de senha.** Nessa posição ele quebra o fluxo de teclado (usuário → `Tab` → senha → `Enter`), atrapalha os gerenciadores de senha, que esperam os dois campos consecutivos, e dá peso visual a um recurso raro. A ordem no código (DOM) é igual à ordem visual, sem `tabindex` positivo. O link permanece agrupado com as credenciais locais, acima do divisor do OAuth.

---

### 16.3. Recuperação de senha

- Fluxo nativo do Django: `PasswordResetView`, `PasswordResetDoneView`, `PasswordResetConfirmView`, `PasswordResetCompleteView`.
- Token temporário, invalidado ao trocar a senha (uso efetivamente único), com `PASSWORD_RESET_TIMEOUT` curto (sugestão: 3600 s).
- Resposta idêntica exista ou não o e-mail. Rate limit. Templates na identidade visual do projeto (Doc ② §4). E-mail por variáveis `EMAIL_*`; em desenvolvimento, backend de console.

---

### 16.4. OAuth 2.0 / 2.1 (django-allauth)

- Fluxo **Authorization Code** com **PKCE** quando o provedor suportar; sem *implicit flow*; redirect URIs exatos.
- `client_id`/`client_secret` no `.env`, nunca no código. Com tenancy diferente de `single`, as credenciais por tenant ficam **cifradas com Fernet no banco** (Seção 10.6).
- **Não armazenar tokens** do provedor, a menos que o produto precise chamar APIs dele em nome do usuário (`SOCIALACCOUNT_STORE_TOKENS` fica falso por padrão). Se armazenar, **token e refresh token cifrados com Fernet em repouso** (Seção 18.1).
- Escopos mínimos. Não vincular conta social a conta existente por e-mail não verificado.
- Provedores habilitados: Doc ② §9. Uma página técnica tipo "Wizard" para guiar a configuração das chaves PODE existir, restrita a perfil técnico e sem exibir segredos já gravados.

---

### 16.5. MFA

Recomendada para perfis administrativos e técnicos.

---

## 17. Autorização

### 17.1. Princípio

Toda view, API, relatório e download verifica **ativamente** se quem requisita tem autorização. Ocultar um item de menu não protege a rota.

---

### 17.2. Política de respostas: 401, 403, 404, 429

| Situação | Resposta |
| :--- | :--- |
| Não autenticado, API ou cliente de máquina | `401` + `WWW-Authenticate`. |
| Não autenticado, view web | Redirecionamento (302) ao login, com `next` validado. |
| Autenticado sem permissão em funcionalidade cuja existência é pública/conhecida (ex.: área administrativa genérica) | `403`. |
| Recurso privado por identificador (de outro usuário/escopo) ou cuja existência o requisitante não deve conhecer | `404`, **idêntico** ao de recurso inexistente (mesmo corpo e status). Evita enumeração de recursos e usuários. |
| Limite de requisições excedido | `429` + `Retry-After`. |

A escolha é **analisada caso a caso** e a classificação por recurso fica no Doc ② §6.5.

---

### 17.3. IDOR e BOLA: padrão de queryset escopado

- Todo objeto é buscado por queryset **já filtrado** pelo requisitante/escopo (ex.: `Model.objects.visible_to(user)` + `get_object_or_404`). `Model.objects.get(id=...)` sem escopo em view é proibido.
- A checagem de propriedade vale para **consulta, edição e exclusão**, e também para listagens, exportações, ações em lote e opções de formulário (`ModelChoiceField` com queryset escopado).
- UUID dificulta adivinhar, mas **não substitui** a checagem.
- **Tenancy:** quando o modo não for `single`, o tenant é parte do escopo do queryset (Seção 10.6). Acessar dado de outro tenant é BOLA e responde `404`.
- Testes obrigatórios: usuário A **não** acessa recurso de B, nem um tenant acessa o de outro (Seção 22.1).

---

### 17.4. Padrão RBAC (mecanismo)

1. **Escala numerada de grupos** (padrão do ecossistema: 0 a 4). O número **identifica o grupo e não é ordem de privilégio**; a ordem é declarada no Doc ② §6.1. Os grupos **3 (Administrador)** e **4 (Desenvolvedor)** são reservados, com sentido fixo no ecossistema; **0 a 2** são perfis operacionais com nomes definidos pelo produto.
2. **Matriz Funcionalidade × Perfil como dado**, editável por toggle/checkbox. É a **fonte única** para checagem no backend, visibilidade de menus e templates. Padrão: negar.
3. **Verificação central:** mixin/decorator (ex.: `RBACRequiredMixin`, `@require_funcionalidade('codigo')`) e template tag. Proibido espalhar `if user.groups...` pelo código.
4. **Regras de elevação e edição:**
   - ninguém atribui perfil acima do próprio nível de privilégio;
   - o Desenvolvedor (4) atribui qualquer perfil; o Administrador (3) atribui até o 3;
   - ninguém edita as **próprias** permissões; o Administrador não altera as permissões do grupo 4;
   - perfis operacionais não editam a matriz; a interface da matriz é visível somente para 3 e 4.
5. **Proteção do último** Administrador/Desenvolvedor (não pode ser removido ou rebaixado).
6. **Segregação de funções** por produto (ex.: perfil operacional sem acesso a configurações globais ou a dados sensíveis): Doc ② §6.4.
7. Toda alteração de perfil ou de matriz é **auditada** (Seção 21) e invalida caches.
8. **Usuário externo** (cidadão, cliente, paciente etc.) fica **fora** da escala interna: modelado como perfil externo/portal com escopo restrito aos próprios dados (Doc ② §6.2).
9. **Funcionalidades reservadas** do ecossistema (Seção 17.5) e **escopo da atribuição** em tenancy (Seção 17.6).

---

### 17.5. Funcionalidades reservadas do ecossistema

Nomes fixos, registrados na matriz (Seção 17.4) por apps do ecossistema. Padrão: negar, exceto onde indicado.

| Funcionalidade | Permite | Padrão | Delegável? |
| :--- | :--- | :-: | :-: |
| `accounts.matriz` | Ver e editar a matriz RBAC | Grupos 3 e 4 | **Não** |
| `accounts.atribuir_perfis` | Atribuir perfis (com as regras de elevação da Seção 17.4) | Grupos 3 e 4 | Não |
| `site.tema_editar` | Alterar o tema do sistema (Seção 11.12) | Grupos 3 e 4 | Sim |
| `site.visibilidade_publica` | Ativar/desativar as páginas públicas (Seção 11.1) | Grupos 3 e 4 | Sim |

Nas funcionalidades delegáveis, a matriz pode conceder o acesso a outros perfis. Esses itens aparecem no menu **Administração** somente para quem os possui.

---

### 17.6. Escopo da atribuição e superadministrador (tenancy)

- A atribuição de perfil a um usuário carrega **escopo** (global ou tenant), quando o modo de tenancy não for `single` (Seção 10.6).
- **Superadministrador** é um perfil com escopo **global**. Por padrão é o grupo 4; o produto pode estender ao grupo 3 no Doc ② §6.1.
- O Administrador de um tenant atua **somente** no seu tenant. Qualquer operação entre tenants é auditada (Seção 21.1).
- A matriz é **global** por padrão. Sobreposição por tenant só existe se declarada no Doc ② §8.8.

---

## 18. Criptografia e Integridade

### 18.1. Dados sensíveis em repouso: Fernet

Camada de serviço em `apps/core` com `cryptography.fernet`:

```python
# apps/core/crypto.py
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

def _fernet() -> MultiFernet:
    # settings.FIELD_ENCRYPTION_KEYS = env.list('FIELD_ENCRYPTION_KEY')
    # A primeira chave cifra; todas decifram (rotação sem perda de dados).
    return MultiFernet([Fernet(k) for k in settings.FIELD_ENCRYPTION_KEYS])

def encrypt(texto: str) -> str:
    return _fernet().encrypt(texto.encode()).decode()

def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
```

Regras:

1. A chave vem **exclusivamente do `.env`** (`FIELD_ENCRYPTION_KEY`); gerar com `Fernet.generate_key()`; uma por ambiente; nunca no código, no banco ou em log.
2. Backup da chave **separado** do backup do banco. Perder a chave é perder os dados.
3. Cifrar: tokens OAuth e refresh tokens, segredos de integração, dados sensíveis (LGPD) conforme a classificação do Doc ② §8.6.
4. Campo cifrado não é pesquisável nem ordenável. Se precisar de busca por igualdade, usar índice cego (HMAC do valor) por decisão registrada no Doc ② §13.
5. Fernet **não** é para senhas: senhas usam Argon2id (Seção 16.1).

---

### 18.2. HMAC e tokens assinados

- Assinaturas com **HMAC-SHA256**; comparar com `hmac.compare_digest`.
- Tokens pontuais internos (link de download, confirmação): **preferir `django.core.signing`** (`signing.dumps(..., salt=...)`, `max_age`), sem dependência extra.
- **JWT** apenas quando houver API/interoperabilidade: assinado **HS256**, expiração curta (sugestão: acesso ≤ 15 min), chave dedicada `JWT_SIGNING_KEY` (≥ 32 bytes aleatórios, distinta da `SECRET_KEY`). Validar `alg` explicitamente (rejeitar `none` e troca de algoritmo), `exp`, `iss`, `aud`. Refresh token rotativo, revogável e armazenado cifrado ou com hash. Em cookie `HttpOnly`, nunca em `localStorage`. A biblioteca (PyJWT ou, com DRF, simplejwt) é justificada no plano.

---

### 18.3. Webhooks

1. Assinatura **obrigatória** em `X-Signature` (HMAC-SHA256 sobre o corpo **bruto**), com segredo por integração no `.env`.
2. Verificar **antes** de qualquer parse ou acesso a banco; falhou, abortar (`401`/`403`).
3. Validar carimbo de tempo (janela curta) e idempotência quando o provedor permitir (anti-replay).
4. `@csrf_exempt` somente aqui. Aplicar limite de corpo e rate limit. Logs sem payload sensível.

---

### 18.4. Gestão de chaves

`SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `JWT_SIGNING_KEY` e segredos de webhook são **distintos entre si** e nunca reutilizados para outra finalidade. Todos listados (sem valor) no `.env.example`. Conjunto-base de variáveis do ecossistema:

```env
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=
ADMIN_URL=
FIELD_ENCRYPTION_KEY=
JWT_SIGNING_KEY=
EMAIL_HOST=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## 19. Rate Limiting na Aplicação

### 19.1. O que é e por que na aplicação

Rate limiting restringe quantas requisições uma **chave** (IP, usuário, token, e-mail, endpoint) pode fazer numa **janela de tempo**. Ao exceder, a resposta é `429 Too Many Requests` com `Retry-After`.

Ele **não pode ser delegado só à borda** (proxy/WAF/CDN). A borda enxerga IP e volume; a aplicação conhece **identidade, rota e resultado de negócio** (tentativas de login por usuário, reset por e-mail, downloads por usuário). A borda complementa; não substitui.

---

### 19.2. Como aplicar na aplicação

1. **Decorator por view** para rotas sensíveis (ex.: `django-ratelimit`).
2. **Lockout de login** por usuário + IP (ex.: `django-axes`), que também cobre o **Django Admin**.
3. **Throttling** de API (ex.: throttles do DRF, se usado) ou middleware leve para limite global.
4. **Implementação própria** com contadores no `cache` do Django (incremento atômico), se não adotar bibliotecas.

Bibliotecas são dependências novas: justificar no plano (Seção 7.7).

```python
from django.http import HttpResponse
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST', block=False)
def login_view(request):
    if getattr(request, 'limited', False):
        resp = HttpResponse('Muitas tentativas. Tente novamente em instantes.', status=429)
        resp['Retry-After'] = '60'
        return resp
    ...
```

---

### 19.3. Requisitos técnicos

- Em produção, **cache compartilhado** com incremento atômico (ex.: Redis ou Memcached). `LocMemCache` é por processo: aceitável só em desenvolvimento e testes.
- **IP real:** só confiar em `X-Forwarded-For` quando vier de proxy conhecido (Doc ② §10). Caso contrário, todos os usuários atrás do proxy compartilham a mesma chave, ou o IP pode ser forjado.
- Login usa chave **composta** (usuário + IP) para que um atacante não bloqueie o usuário legítimo apenas pelo nome.
- Com tenancy diferente de `single`, a chave do rate limit inclui o escopo do tenant: um tenant não consome a cota de outro.
- Mensagens de bloqueio genéricas; bloqueios registrados em log, sem dados sensíveis.

---

### 19.4. Escopos mínimos e valores iniciais

Valores de partida, parametrizados por `.env`/settings. Os finais ficam no Doc ② §10.

| Escopo | Chave | Limite inicial sugerido |
| :--- | :--- | :--- |
| Login (inclui Admin) | IP; usuário + IP | 5/min por IP; bloqueio temporário após 5 falhas seguidas (ex.: 15 min) |
| Recuperação de senha | IP; e-mail | 3/hora |
| Cadastro / convite | IP | 5/hora |
| Callback OAuth | IP | 20/min |
| Webhook | origem | 60/min |
| Download de documento sensível | usuário | 30/min |
| API autenticada | usuário/token | 60/min |
| Páginas públicas e API anônima | IP | 20/min |

---

## 20. Erros, `DEBUG=False` e Páginas de Erro

### 20.1. `DEBUG`

`DEBUG=False` em qualquer ambiente exposto. Com `DEBUG=True`, o Django mostra a página técnica de 404 **listando todas as rotas** e tracebacks com configurações: isso é **proibido fora do ambiente local**.

---

### 20.2. Handlers e templates

- `handler400`, `handler403`, `handler404` e `handler500` no `urls.py` raiz, apontando para views do app `core`/`site`; `CSRF_FAILURE_VIEW` própria.
- Templates `templates/400.html`, `403.html`, `404.html` e `500.html`. Os três primeiros herdam do `base.html`; o `500.html` é **autossuficiente** (sem context processors nem consultas ao banco).

---

### 20.3. 404 personalizada

Construir **uma ou mais** páginas 404 (ex.: variante pública e autenticada):

- mesma página para recurso inexistente e recurso não autorizado (Seção 17.2);
- sem listagem de rotas, sem stack trace;
- pode ser "inteligente" (busca, atalhos para áreas permitidas ao perfil), **sem expor rotas não autorizadas**;
- tom e identidade conforme o Doc ② §4.8.

---

### 20.4. Logs de erro

Detalhes de erro vão para o `logging` do servidor, **nunca para a resposta**.

---

## 21. Auditoria, Logs e Dados Pessoais

### 21.1. Eventos auditáveis mínimos

Login (sucesso e falha), bloqueios por rate limit, alteração de perfil ou de matriz, alteração do **tema** e da **visibilidade das páginas públicas**, ações destrutivas, aprovações/recusas com justificativa, **acesso a documentos sensíveis**, uso de endpoints administrativos e operações **entre tenants**.

Registro **somente de acréscimo** (imutável): quem, quando, o quê, origem (IP), objeto (UUID), **escopo (tenant)** e, quando pertinente, antes/depois.

---

### 21.2. Logs sem segredos

Nunca registrar senhas, tokens, chaves, corpo sensível de webhook ou dados clínicos/pessoais. Mascarar quando necessário.

---

### 21.3. Dados pessoais (LGPD)

- Minimização: coletar o necessário.
- Classificar campos (comum/sensível) no Doc ② §8.6; cifrar os sensíveis em repouso (Seção 18.1).
- Acesso por necessidade, via RBAC. Base legal e retenção são definidas pelo produto; validar com o responsável jurídico.

---

# PARTE D — DOMÍNIO: QUALIDADE, ENTREGA E GOVERNANÇA

---

## 22. Testes e Dependências Globais

### 22.1. Testes mínimos de segurança (todo projeto)

| # | Teste |
| :-: | :--- |
| 1 | **Ownership/BOLA:** usuário A não consulta, edita nem exclui recurso de B (`404`/`403` conforme a política). |
| 2 | View protegida sem autenticação: redirecionamento (web) ou `401` (API). |
| 3 | **RBAC:** cada perfil × funcionalidades críticas; negar por padrão. |
| 4 | **Matriz:** elevação acima do próprio nível e autoedição de permissões são barradas. |
| 5 | **404 personalizada** com `DEBUG=False`, sem listar rotas. |
| 6 | **Cabeçalhos:** CSP, `X-Frame-Options`/`frame-ancestors`, `nosniff`; HSTS com configuração de produção. |
| 7 | **Cookies:** flags `HttpOnly`/`Secure`/`SameSite`. |
| 8 | GET não altera estado (`405` em rotas de alteração). |
| 9 | **Rate limit** devolve `429` (limpar o cache entre testes). |
| 10 | **Limites de entrada:** corpo/arquivo acima do limite é rejeitado. |
| 11 | **Webhook** com assinatura inválida aborta antes de tocar o banco. |
| 12 | `check --deploy` sem avisos injustificados. |
| 13 | **Tema:** contraste reprovado (Escritas × Fundos, Destaques × Fundos) é bloqueado; valor fora de `#RRGGBB` ou opção fora da lista fechada é rejeitado (sem injeção de CSS). |
| 14 | **Tema:** `/tema.css` é público, versionado e `text/css`; trocar tema, cor ou layout muda o CSS e a variante renderizada **sem editar páginas de domínio**; com configuração ausente aplica o padrão. |
| 15 | **Sem estilo inline:** nenhuma página renderizada emite `style=` ou `onclick=`. |
| 16 | **Login:** a ordem do formulário segue a Seção 16.2 (o link "Esqueci minha senha" vem depois do botão Entrar, no DOM). |
| 17 | **Visibilidade pública:** ativa → `/` mostra a landing; desativada → `/` mostra o login e as páginas controláveis respondem `404`; as páginas sempre acessíveis continuam acessíveis. |
| 18 | **Tenancy:** com modo diferente de `single`, usuário de um tenant não acessa recurso, arquivo, exportação nem configuração de outro (`404`); em `single`, o resolvedor devolve o tenant fixo. |
| 19 | **Funcionalidades reservadas:** sem `site.tema_editar` ou `site.visibilidade_publica`, as telas e as ações são negadas (Seção 17.2). |

---

### 22.2. Dependências padrão do ecossistema

| Pacote | Quando | Observação |
| :--- | :--- | :--- |
| `Django` (versão suportada, fixada) | Sempre | CSP nativo a partir da 6.0. |
| `django-environ` | Sempre | Padrão de leitura do `.env`. |
| `argon2-cffi` | Sempre | Hasher Argon2id. |
| `cryptography` | Dados sensíveis, tokens | Fernet. |
| `django-allauth` | OAuth/login social | Seção 16.4. |
| `PyJWT` (ou simplejwt) | JWT | Justificar; preferir `django.core.signing` em tokens internos. |
| `django-ratelimit` / `django-axes` | Rate limit / lockout | Ou implementação própria (Seção 19.2). |
| `django-csp` | Apenas Django < 6.0 | Justificar. |
| `Pillow` | Imagens | Seção 15.5. |
| `nh3` | HTML rico | Seção 15.3. |
| `django-tenants` (ou equivalente) | Tenancy `schema` | Somente por ADR (Seção 10.6); exige PostgreSQL. |

Toda dependência nova segue a Seção 7.7. Recomenda-se verificar vulnerabilidades conhecidas das dependências (ex.: `pip-audit`) antes de merge.

---

## 23. Checklists de Validação Obrigatória

### 23.1. Projeto novo

Antes do primeiro commit:

- [ ] Projeto localizado em `~/projetos/django/<nome_do_projeto>/`.
- [ ] Projeto armazenado no filesystem nativo do WSL.
- [ ] Repositório Git inicializado no diretório do projeto.
- [ ] `.gitignore` criado.
- [ ] `.env` protegido pelo `.gitignore`.
- [ ] `.venv` protegido pelo `.gitignore`.
- [ ] `.venv` criado na raiz do projeto.
- [ ] `.venv` ativado.
- [ ] Django instalado no ambiente virtual.
- [ ] `django-environ` instalado quando utilizado pelo padrão do projeto.
- [ ] Dependências registradas em `requirements.txt`.
- [ ] `settings.py` preparado para variáveis de ambiente.
- [ ] `DEBUG` utilizando conversão booleana explícita.
- [ ] `.env` criado localmente.
- [ ] `SECRET_KEY` gerada exclusivamente para o projeto.
- [ ] `.env.example` criado.
- [ ] `.env.example` não contém valores reais.
- [ ] Git configurado com identidade `noreply`.
- [ ] `git status` revisado.
- [ ] `git diff` revisado.
- [ ] Nenhum segredo está no staging.

---

### 23.2. Projeto clonado

Antes de executar o projeto:

- [ ] Repositório clonado em `~/projetos/django/<nome_do_projeto>/`.
- [ ] `.venv` recriado localmente.
- [ ] `.venv` ativado.
- [ ] `requirements.txt` instalado.
- [ ] `.env.example` consultado.
- [ ] `.env` recriado localmente.
- [ ] `SECRET_KEY` nova gerada para o ambiente local.
- [ ] Nenhuma credencial de produção utilizada.
- [ ] Variáveis adicionais identificadas.
- [ ] Migrações executadas conforme necessidade do projeto.
- [ ] Git configurado corretamente.
- [ ] Branch de trabalho verificada.

---

### 23.3. Rotina diária

Antes de trabalhar:

- [ ] Ambiente virtual ativo.
- [ ] Diretório correto (`~/projetos/django/<nome_do_projeto>/`).
- [ ] Branch correta.
- [ ] `git status` verificado.

Antes de commit:

- [ ] `git status` executado.
- [ ] `git diff` executado.
- [ ] `.env` não está no staging.
- [ ] `.venv` não está no staging.
- [ ] Tokens não estão no código.
- [ ] Senhas não estão no código.
- [ ] Logs de depuração não serão persistidos indevidamente.
- [ ] Dados sensíveis não foram adicionados.
- [ ] Commit segue Conventional Commits.

Antes de merge:

- [ ] Branch publicada.
- [ ] Pull Request criado.
- [ ] Alterações revisadas.
- [ ] Testes apropriados ao projeto executados.
- [ ] Revisão humana realizada.
- [ ] Merge autorizado.


---

### 23.4. Baseline de segurança (antes da primeira migração e do primeiro deploy)

- [ ] Usuário customizado (`AUTH_USER_MODEL`) com chave UUID criado **antes** da primeira migração.
- [ ] `PASSWORD_HASHERS` com Argon2id em primeiro lugar; `argon2-cffi` no `requirements.txt`.
- [ ] Baseline de settings da Seção 12.3 aplicado; `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` via `.env`.
- [ ] Middlewares de segurança do Django preservados.
- [ ] CSP em Report-Only configurada (Seção 14) e templates sem `style=`/`onclick=` inline.
- [ ] Bootstrap/Icons com versão fixa e SRI.
- [ ] `FIELD_ENCRYPTION_KEY` (e `JWT_SIGNING_KEY`, se aplicável) distintas, geradas localmente e só no `.env`.
- [ ] `ADMIN_URL` não padrão e Admin coberto por rate limit/lockout.
- [ ] Handlers 400/403/404/500 e templates próprios; `DEBUG=False` validado.
- [ ] Landing/apresentação conforme a visibilidade pública (Seção 11.1); login local funcionando com a ordem do formulário da Seção 16.2.
- [ ] Tema padrão aplicado, `/tema.css` servido e `base.html` como casca fina (Seção 11.5).
- [ ] Funcionalidades `site.tema_editar` e `site.visibilidade_publica` registradas na matriz (Seção 17.5).
- [ ] `TENANCY_MODE` declarado (padrão `single`) e resolvedor de tenant no `core` (Seção 10.6).
- [ ] `python manage.py check --deploy` executado com variáveis de produção simuladas.

---

### 23.5. Cada funcionalidade nova (segurança e arquitetura)

- [ ] Identificadores expostos são UUIDv4; rotas em `<uuid:id>`.
- [ ] Objeto buscado por queryset escopado (IDOR/BOLA); resposta `401`/`403`/`404` conforme a Seção 17.2.
- [ ] Funcionalidade registrada na matriz RBAC e no menu da NAVBAR, quando aplicável.
- [ ] Entrada validada em formulário/serializer, DTO e banco; limites de tamanho definidos.
- [ ] Ação que altera estado usa POST + CSRF.
- [ ] Dados sensíveis cifrados e fora de logs; acessos relevantes auditados.
- [ ] Endpoints sensíveis com rate limit.
- [ ] Página de domínio sem estilo, cor fixa nem estrutura de casca: só blocos e componentes do tema (Seção 11.5).
- [ ] Se houver escopo de tenant: modelos declarados no README e unicidade por escopo.
- [ ] README da app atualizado.

---

## 24. Relação com a Documentação Específica dos Projetos

Este documento permanece **global e estável** em `~/projetos/django/AGENT_INSTRUCTIONS_DJANGO.md`. Cada projeto documenta suas características dentro da própria pasta:

```text
~/projetos/django/AGENT_INSTRUCTIONS_DJANGO.md        ① padrão global
            │
            ▼
~/projetos/django/<nome_do_projeto>/
            ├── PROJECT_SPEC.md           ② obrigatório (PRD + TRD mínimo)
            ├── regras_de_negocio.md      obrigatório (RF/RN)
            ├── apps/<app>/README.md      obrigatório por app (§9.3)
            └── ARCHITECTURE.md · DATABASE.md · API.md · TESTING.md · SECURITY.md   opcionais
```

- `SECURITY.md` é **opcional** e serve apenas para detalhamento que não caiba no Doc ② §10 (parâmetros e exceções).
- Os documentos do projeto podem definir: apps e módulos, modelos e banco, APIs, perfis e matriz, regras de negócio, requisitos, integrações, design e conteúdo.
- Eles **não** podem reabrir o que é baseline global sem exceção registrada.
- Essas definições não devem ser incorporadas a este documento apenas por pertencerem a um projeto. A promoção de uma regra do projeto para o padrão global exige revisão deste documento.

---

## 25. Princípio de Separação entre Global e Projeto

> **O padrão global define como o ambiente, o processo, a arquitetura-base e o piso de segurança funcionam; a documentação do projeto define o que o produto deve construir e com quais valores.**

```text
GLOBAL (Ecossistema Django) — Doc ①
│
├── Onde desenvolver?            WSL 2 / Linux sob ~/projetos/django/
├── Como isolar Python?          .venv individual por projeto
├── Como proteger segredos?      .env / .env.example / chaves distintas
├── Como versionar?              Git / branches / PR
├── Como limitar a IA?           salvaguardas + plano com confirmação
├── Como estruturar?             apps modulares, camadas, UUIDv4
├── Como trocar a identidade visual?  sistema de temas (10 modelos, 3 cores, layouts)
├── Como preparar multi-organização?  contrato de tenancy (single por padrão)
└── Qual o piso de segurança?    HTTP, cookies, CSP, entrada, auth, RBAC, cripto, rate limit, erros
```

```text
PROJETO / PRODUTO (~/projetos/django/<nome_do_projeto>/) — Doc ②
│
├── O que o sistema faz e para quem?          PRD
├── Como o usuário navega? Como é a landing?  AppFlow, landing, design
├── Quais perfis e matriz?                    RBAC concreto
├── Qual tema, layouts e visibilidade pública?  Doc ② §3 e §4
├── Qual modelo de tenancy?                   Doc ② §8.8
├── Quais dados, integrações e valores?       TRD do projeto
└── Quais exceções ao baseline, e por quê?    Doc ② §10
```

Essa separação deve ser preservada.

---

## 26. Princípio Geral para Agentes de IA

Ao operar em um projeto Django submetido a este padrão, o agente deve:

1. Respeitar o ambiente WSL e a localização `~/projetos/django/<nome_do_projeto>/`.
2. Utilizar o `.venv` do projeto e evitar instalações globais.
3. Nunca expor ou hardcodar segredos; respeitar `.env` e `.env.example`.
4. Trabalhar em branches apropriadas e revisar alterações antes dos commits.
5. Evitar operações Git destrutivas sem confirmação.
6. Seguir o **protocolo de plano e confirmação** (Seção 7.6) e comunicar em português.
7. Não interpretar o `.txt` como autoridade operacional.
8. Aplicar o **baseline de segurança** (Parte C) por padrão, sem que o usuário precise pedir.
9. Não enfraquecer uma regra global; qualquer desvio é exceção registrada no Doc ② §10.
10. Respeitar o `PROJECT_SPEC.md` e o `regras_de_negocio.md` quando existirem.
11. Não inventar requisitos funcionais ou arquiteturais que não estejam definidos.
12. Não transformar regra específica de projeto em regra global sem revisão deste documento.

---

## 27. Limite de Escopo de Segurança

As definições de segurança deste documento são classificadas como:

| Classe | Alcance |
| :--- | :--- |
| **Segurança do ambiente** | Proteção da máquina e do ambiente de desenvolvimento. |
| **Segurança das credenciais** | Segredos, variáveis de ambiente, chaves. |
| **Segurança do processo** | Fluxo Git, revisão, histórico. |
| **Segurança operacional de agentes** | Limitação de ações destrutivas e protocolo de plano/confirmação. |
| **Segurança da aplicação (baseline)** | Parte C: HTTP, sessão, CSP, entrada, autenticação, autorização, criptografia, rate limit, erros, auditoria. |

Continuam **fora** do escopo global: infraestrutura de produção, WAF/CDN, monitoramento, backup e recuperação de desastres, testes de intrusão e a conformidade jurídica completa de cada produto.

---

## 28. Documento de Referência Técnica

O documento `DEV_ENVIRONMENT_GUIDELINES.txt` permanece como registro de análise, contexto, histórico, racional das decisões e comandos de referência do **domínio de ambiente**. Ele pode conter explicações mais extensas que não são necessárias no documento operacional. Sua existência não implica duplicação de autoridade.

```text
① AGENT_INSTRUCTIONS_DJANGO.md  ──►  regras operacionais obrigatórias
              ▲
              │ fundamentado por
              │
③ DEV_ENVIRONMENT_GUIDELINES.txt  ──►  análise / contexto / referência (não normativo)
```

---

## 29. Registro de Alterações

### v3.1

- **Renumeração dos documentos:** ② passa a ser `PROJECT_SPEC.md` (especificação do projeto) e ③ passa a ser `DEV_ENVIRONMENT_GUIDELINES.txt` (a tratar posteriormente). Todas as referências a "Doc ③" foram trocadas por "Doc ②", inclusive nas entradas anteriores deste registro.
- **Integração 1: sistema de temas** (Seções 11.5 a 11.12). Dez modelos de design (Alegre, Sofisticado, Sóbrio, Animado, Profissional, Luxuoso, SoftClean, Noturno, Acessível e o modelo livre **Outro**); três cores (Fundos, Destaques, Escritas) com validação de contraste WCAG; **seletor de cores** com matiz/saturação, brilho, hexadecimal e RGB; **20 paletas sugeridas**; seis eixos de estilo; **variantes de layout** por HTML-base; troca de tema sem editar as páginas de domínio; permissão `site.tema_editar`.
- **Integração 2: ordem do formulário de login** (Seção 16.2). "Esqueci minha senha" passa a ficar **abaixo do botão Entrar**.
- **Integração 3: visibilidade das páginas públicas via RBAC** (Seções 11.1 e 17.5). Com a visibilidade ativa, `/` é a landing; desativada, `/` é o login. A Seção 11.1 anterior, que fixava a landing na raiz, passa a ser condicional. Funcionalidade `site.visibilidade_publica`.
- **Integração 4: tenancy híbrido** (Seções 10.6 e 17.6). Contrato neutro com `single` como padrão e `row` como referência; `schema` e `database` só por ADR. Regras de preparação válidas em qualquer modo. Propagado para as Seções 9.2, 9.3, 9.4, 15.5, 16.4, 17.3, 19.3, 21.1, 22 e 23.
- Nova Seção 17.5 (funcionalidades reservadas do RBAC) e Seção 17.6 (escopo e superadministrador).
- Testes 13 a 19 na Seção 22.1; novos itens nos checklists 23.4 e 23.5.

### v3.0

- **Reestruturação por domínios:** Parte A (Ambiente e Processo), Parte B (Arquitetura Global), Parte C (Segurança Global da Aplicação) e Parte D (Qualidade, Entrega e Governança). Mapa de domínios na Seção 0.2.
- Criada a **tabela de classificação Doc ① × Doc ②** (Seção 0.5) e o **mapa PRD/TRD** (Seção 0.4).
- **Escopo ampliado:** HSTS, CSP, CSRF, cabeçalhos, autenticação, autorização, JWT/HMAC e rate limiting passam de "não cobertos" a **baseline global**; o projeto registra apenas valores e exceções.
- Nova Seção 7.6 (protocolo de plano e confirmação humana) e 7.7 (dependências novas).
- Nova Seção 9 (modularidade, desacoplamento e README por app) e catálogo de apps reutilizáveis.
- Nova Seção 10 (camadas, transações, máquinas de estado, **UUIDv4**, integridade no banco).
- Nova Seção 11 (landing pública, NAVBAR com RBAC, hardening do Admin, base visual compatível com CSP).
- Nova Parte C (§12–§21): baseline de settings; cookies `HttpOnly`; CSP em allowlist e anti-clickjacking; validação em três camadas, limites de tamanho e ZipBomb; Argon2id, login local + OAuth 2.0/2.1, recuperação de senha; autorização ≠ autenticação, política 401/403/404, IDOR/BOLA e RBAC; Fernet, HMAC/JWT e webhooks; rate limiting na aplicação (inclusive Admin); `DEBUG=False` e páginas de erro; auditoria e LGPD.
- Nova Seção 22 (testes mínimos de segurança e dependências padrão); checklists 23.4 e 23.5.
- `.gitignore` global passa a incluir `media/` e `staticfiles/`.
- Documento ③ renomeado para `DEV_ENVIRONMENT_GUIDELINES.txt`; referências atualizadas.
- Seções 4.1, 4.5 e 8 ajustadas para remeter ao novo baseline; Seções 10–14 anteriores reescritas como 24–28.

### v2.2

- Atualizada a topologia de diretórios para acomodar múltiplos ecossistemas de stacks (`~/projetos/django/`, `~/projetos/nodejs/`, etc.).
- Ajustada a localização normativa dos projetos para `~/projetos/django/<nome_do_projeto>/`.
- Atualizado o fluxo de clonagem para execução a partir do diretório `~/projetos/django/`.
- Atualizados os checklists de validação de projetos novos, clonados e rotina diária com a hierarquia de caminhos revisada.
- Adicionado diagrama visual da arquitetura de pastas multi-stack na Seção 0.4.

### v2.1

- Reforçada a definição do documento como padrão global de ambiente e processo de desenvolvimento.
- Mantida a separação entre ambiente global e especificações individuais de cada projeto.
- Criada hierarquia documental explícita para acomodar futuras especificações de projeto.
- Reforçada a precedência do `.md` sobre o documento `.txt`.
- Definido que a consulta ao `.txt` não é obrigatória para agentes quando as regras necessárias já estiverem disponíveis no `.md`.
- Alterada a definição de segurança para deixar explícito que este documento trata de segurança do ambiente, credenciais, processo e operação de agentes, e não da segurança completa da aplicação.
- Reforçada a separação entre segurança global e segurança específica do projeto.
- Tornada a política de `DEBUG` explícita para desenvolvimento local, sem definir configurações de produção.
- Removido o endereço de e-mail específico de uma conta individual, mantendo apenas o padrão genérico `users.noreply.github.com`.
- Mantido o `requirements.txt` como padrão global, permitindo que a estratégia específica de gerenciamento de dependências seja refinada posteriormente por projeto.
- Preservadas as salvaguardas para operações Git destrutivas.
- Preservado o escopo original de Django + WSL 2 + fluxo de desenvolvimento.

### v2.0

- Renomeado de `AGENT_INSTRUCTIONS.md` para `AGENT_INSTRUCTIONS_DJANGO.md`.
- Adicionada Seção 0 de escopo.
- Adicionado bootstrap único da máquina.
- Expandido o fluxo de clonagem.
- Adicionada documentação por `.env.example`.
- Separada a política de mascaramento de e-mail do valor específico do ambiente.
- Adicionadas salvaguardas para agentes de IA em operações Git destrutivas.
- Adicionado checklist de onboarding para projetos clonados.

### v1.0

- Versão inicial, destilada do documento histórico de configuração do ambiente Django.
