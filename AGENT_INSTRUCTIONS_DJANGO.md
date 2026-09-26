# AGENT_INSTRUCTIONS_DJANGO.md — Diretrizes Globais de Ambiente, Segurança Operacional e Fluxo de Desenvolvimento Django (WSL 2)

**Versão:** 2.2  
**Aplica-se a:** projetos Django desenvolvidos em ambiente WSL 2 (Windows + Ubuntu) estruturados dentro do ecossistema de stacks (`~/projetos/django/`).

---

## 0. Escopo, Autoridade e Hierarquia Documental

### 0.1. Finalidade

Este documento estabelece as regras globais e mandatórias para a configuração do ambiente de desenvolvimento, isolamento do sistema, gerenciamento do ambiente Python, proteção básica de credenciais, identidade e fluxo de trabalho Git e salvaguardas para operações realizadas por agentes de IA em projetos Django.

Estas regras constituem o **padrão global do ecossistema de desenvolvimento Django**.

O documento não define as características funcionais, arquiteturais ou de segurança específicas de um projeto individual.

---

### 0.2. O que este documento cobre

Este documento cobre:

- Bootstrap único da máquina host.
- Topologia de isolamento Windows / WSL 2.
- Localização dos projetos no sistema de arquivos Linux sob o diretório do ecossistema Django (`~/projetos/django/<nome_do_projeto>/`).
- Gerenciamento de ambiente virtual Python (`.venv`).
- Gerenciamento básico de dependências Python.
- Segurança básica de credenciais e variáveis de ambiente.
- Utilização de `.env` e `.env.example`.
- Proteção básica do repositório por `.gitignore`.
- Identidade de commits Git.
- Fluxo de branches, commits, sincronização e Pull Requests.
- Salvaguardas para agentes de IA em operações Git potencialmente destrutivas.
- Checklists globais de validação do ambiente e do fluxo de desenvolvimento.

---

### 0.3. O que este documento NÃO cobre

As seguintes definições devem ser estabelecidas em documentos específicos de cada projeto ou ambiente e **não fazem parte deste padrão global**:

- Configurações específicas de produção e deploy.
- `ALLOWED_HOSTS` específico de cada aplicação.
- HTTPS e certificados.
- Cabeçalhos HTTP de segurança.
- CSP, HSTS e demais políticas de segurança HTTP.
- CSRF específico da aplicação.
- Arquitetura dos apps Django.
- Modelos de dados e regras de negócio.
- Estratégia de testes específica do projeto.
- APIs e contratos de integração.
- Autenticação e autorização específicas da aplicação.
- Gestão de sessões, JWT ou outros mecanismos de autenticação.
- Rate limiting específico da aplicação.
- Configurações de banco de dados específicas do projeto.
- Infraestrutura de produção.
- Containers e orquestração, caso adotados.
- Pipelines de CI/CD.
- Requisitos funcionais.
- Requisitos não funcionais específicos.
- Regras de negócio.
- Qualquer outra característica exclusiva de um projeto individual.

---

### 0.4. Hierarquia de documentos e Estrutura de Contexto

A organização documental e a topologia de diretórios seguem o seguinte princípio hierárquico:

```text
~/projetos/
├── django/                                     <-- Diretório do Ecossistema Django
│   ├── AGENT_INSTRUCTIONS_DJANGO.md           <-- PADRÃO GLOBAL NORMATIVO DJANGO
│   │
│   ├── <nome_do_projeto_A>/                    <-- Raiz do Repositório Git do Projeto A
│   │   ├── .venv/                             <-- Ambiente virtual isolado do Projeto A
│   │   ├── .env                               <-- Credenciais locais (ignorado no Git)
│   │   ├── .env.example
│   │   ├── .gitignore
│   │   ├── requirements.txt
│   │   ├── manage.py
│   │   ├── PROJECT_SPEC.md                    <-- Especificação técnica / Regras de negócio
│   │   ├── ARCHITECTURE.md                    <-- Arquitetura dos apps e camadas
│   │   ├── DATABASE.md                        <-- Modelagem de dados
│   │   └── SECURITY.md                        <-- Políticas de segurança da aplicação
│   │
│   └── <nome_do_projeto_B>/                    <-- Raiz do Repositório Git do Projeto B
│       ├── .venv/
│       ├── .env
│       ├── requirements.txt
│       ├── manage.py
│       └── PROJECT_SPEC.md
│
├── nodejs/                                    <-- Outros Ecossistemas (Exemplo)
│   ├── AGENT_INSTRUCTIONS_NODE.md
│   └── <projeto_node>/
│
└── rust/                                      <-- Outros Ecossistemas (Exemplo)
    ├── AGENT_INSTRUCTIONS_RUST.md
    └── <projeto_rust>/
```

Precedência de instrução:

```text
Padrões e instruções superiores da plataforma/agente
                    │
                    ▼
       AGENT_INSTRUCTIONS_DJANGO.md (../)
             PADRÃO GLOBAL
                    │
                    ▼
      Documentação específica do projeto (./)
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    Arquitetura  Segurança    Banco/API
                    │
                    ▼
             Tarefa específica
```

O `AGENT_INSTRUCTIONS_DJANGO.md` estabelece as regras globais do ambiente e do processo de desenvolvimento.

Documentos específicos de um projeto podem estabelecer regras adicionais necessárias àquele projeto, desde que não contradigam as instruções de nível superior.

Uma regra específica de projeto não deve ser utilizada para eliminar ou contornar uma regra global de segurança ou operação definida neste documento.

---

### 0.5. Precedência sobre o material de referência

O arquivo:

`Ambiente_de_desenvolvimento_-_Django_-_Definição_do_fluxo_de_desenvolvimento_e_definições_de_segurança_e_escopo_básico.txt`

é o documento de análise, referência técnica e registro do processo que deu origem a este padrão.

Ele pode ser consultado para:

- compreender o contexto das decisões;
- consultar explicações mais detalhadas;
- consultar o fluxo original;
- compreender a motivação de determinadas definições;
- recuperar comandos e procedimentos de referência.

**O arquivo `.txt` não constitui fonte normativa de instruções operacionais para agentes de IA.**

Em caso de divergência entre o `.md` e o `.txt`, este documento (`AGENT_INSTRUCTIONS_DJANGO.md`) prevalece.

Um agente de IA **não deve tratar a leitura do `.txt` como requisito obrigatório antes de executar uma tarefa**, quando as regras necessárias já estiverem definidas neste `.md`.

A consulta ao `.txt` pode ser realizada quando houver necessidade de compreender o contexto ou o rationale de uma decisão, sempre respeitando a precedência deste documento.

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

Este documento **não constitui a especificação completa de segurança das aplicações Django**.

Requisitos de segurança específicos da aplicação deverão ser definidos posteriormente em documentação própria do projeto (`SECURITY.md`).

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

Configurações de produção não são definidas por este documento e deverão ser estabelecidas em documentação específica do ambiente/projeto.

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

## 8. Segurança do Processo de Desenvolvimento

Esta seção estabelece controles globais relacionados ao processo de desenvolvimento.

Ela não substitui uma especificação de segurança da aplicação.

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

Requisitos de segurança da aplicação Django deverão ser definidos posteriormente em documento específico do projeto (`SECURITY.md`).

---

## 9. Checklists de Validação Obrigatória

### 9.1. Projeto novo

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

### 9.2. Projeto clonado

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

### 9.3. Rotina diária

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

## 10. Relação com a Documentação Específica dos Projetos

Este documento deve permanecer **global e estável** dentro do diretório do ecossistema Django (`~/projetos/django/AGENT_INSTRUCTIONS_DJANGO.md`).

Quando um novo projeto Django for criado, suas características específicas devem ser documentadas dentro da pasta do próprio projeto.

Exemplo:

```text
~/projetos/django/AGENT_INSTRUCTIONS_DJANGO.md
            │
            │ padrão global
            ▼
       ~/projetos/django/<nome_do_projeto>/
            │
            ├── PROJECT_SPEC.md
            ├── ARCHITECTURE.md
            ├── SECURITY.md
            ├── DATABASE.md
            ├── API.md
            └── TESTING.md
```

Os documentos específicos podem definir:

- arquitetura;
- estrutura dos apps;
- modelos;
- banco;
- APIs;
- autenticação;
- autorização;
- regras de negócio;
- testes;
- segurança da aplicação;
- integrações;
- requisitos funcionais.

Essas definições não devem ser incorporadas ao `AGENT_INSTRUCTIONS_DJANGO.md` apenas por pertencerem a um determinado projeto.

---

## 11. Princípio de Separação entre Ambiente e Projeto

O princípio fundamental deste documento é:

> **O padrão global define como o ambiente e o processo de desenvolvimento devem funcionar; a documentação específica define o que cada projeto deve construir e como sua aplicação deve funcionar.**

Portanto:

```text
GLOBAL (Ecossistema Django)
│
├── Onde desenvolver?
│   └── WSL 2 / Linux sob ~/projetos/django/
│
├── Como isolar Python?
│   └── .venv individual por projeto
│
├── Como proteger segredos?
│   └── .env / .env.example
│
├── Como versionar?
│   └── Git / branches / PR
│
└── Como limitar ações destrutivas da IA?
    └── salvaguardas operacionais
```

Enquanto:

```text
PROJETO ESPECÍFICO (~/projetos/django/<nome_do_projeto>/)
│
├── O que o sistema faz?
├── Quais são seus módulos?
├── Qual seu modelo de dados?
├── Quais APIs existem?
├── Como funciona a autenticação?
├── Quais são seus requisitos?
└── Quais são seus controles específicos de segurança?
```

Essa separação deve ser preservada.

---

## 12. Princípio Geral para Agentes de IA

Quando um agente de IA estiver operando em um projeto Django submetido a este padrão, ele deve:

1. Respeitar o ambiente WSL e a localização sob `~/projetos/django/<nome_do_projeto>/`.
2. Utilizar o `.venv` correspondente ao projeto.
3. Evitar instalações globais de dependências do projeto.
4. Nunca expor ou hardcodar segredos.
5. Respeitar o `.env` e `.env.example`.
6. Trabalhar em branches apropriadas.
7. Revisar alterações antes de commits.
8. Evitar operações Git destrutivas sem confirmação.
9. Não interpretar o documento `.txt` como autoridade operacional.
10. Respeitar a documentação específica do projeto (`PROJECT_SPEC.md`, etc.) quando ela existir.
11. Não inventar requisitos funcionais ou arquiteturais que não estejam definidos.
12. Não transformar regras específicas de um projeto em regras globais sem revisão deste documento.

---

## 13. Limite de Escopo de Segurança

As definições de segurança deste documento são classificadas como:

### Segurança do ambiente

Proteção da máquina e do ambiente de desenvolvimento.

### Segurança das credenciais

Proteção de segredos, variáveis de ambiente e informações sensíveis.

### Segurança do processo

Proteção do fluxo Git, revisão e histórico.

### Segurança operacional de agentes

Limitação de ações potencialmente destrutivas realizadas por agentes de IA.

Este documento **não deve ser interpretado como uma política completa de segurança de uma aplicação Django**.

A segurança específica da aplicação será definida posteriormente em documentação própria (`SECURITY.md`).

---

## 14. Documento de Referência Técnica

O documento:

`Ambiente_de_desenvolvimento_-_Django_-_Definição_do_fluxo_de_desenvolvimento_e_definições_de_segurança_e_escopo_básico.txt`

permanece como documento de:

- análise;
- referência;
- contexto;
- histórico;
- racional das decisões;
- procedimentos narrativos;
- comandos de referência.

Ele pode conter explicações mais extensas que não são necessárias no documento operacional.

Sua existência não implica duplicação de autoridade.

A relação oficial é:

```text
AGENT_INSTRUCTIONS_DJANGO.md
        │
        │ documento normativo
        │
        ▼
 regras operacionais obrigatórias
        ▲
        │ fundamentado por
        │
        │
Documento .txt
        │
        └── análise / contexto / referência
```

---

## 15. Registro de Alterações

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
