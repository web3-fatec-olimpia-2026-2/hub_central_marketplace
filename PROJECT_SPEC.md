# PROJECT_SPEC.md — Especificação Técnica, Arquitetura e Regras de Negócio

**Projeto:** `<nome_do_projeto>`  
**Versão:** 1.0  
**Ambiente:** WSL 2 (Ubuntu) em `~/projetos/django/<nome_do_projeto>/`  
**Diretriz Superior:** `AGENT_INSTRUCTIONS_DJANGO.md`  

---

## 1. Topologia e Estrutura de Arquivos

O projeto adota uma arquitetura em app único de domínio desacoplado do módulo de configuração global, contendo a pasta global de templates na raiz:

```text
~/projetos/django/<nome_do_projeto>/
├── .venv/                   # Ambiente virtual Python isolado (ignorado no Git)
├── .env                     # Credenciais e variáveis locais (ignorado no Git)
├── .env.example             # Documentação dos nomes das variáveis
├── .gitignore               # Proteção (.env, .venv/, db.sqlite3, caches, logs)
├── requirements.txt         # Dependências do projeto registradas via pip freeze
├── manage.py                # Utilitário de linha de comando do Django
├── PROJECT_SPEC.md          # Este documento (fonte técnica e arquitetural)
├── regras_de_negocio.md     # Especificação exclusiva de regras de negócio e RFs
│
├── templates/               # Layouts globais do sistema
│   └── base.html           # Template mestre (Bootstrap 5 CDN, Navbar, Toolbar, Cores)
│
├── <pacote_de_config>/      # Módulo raiz gerado pelo startproject (ex: config ou meu_site)
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py          # Configuração com django-environ e DIRS de templates
│   ├── urls.py              # Roteamento central do projeto
│   └── wsgi.py
│
└── <app_do_projeto>/        # Aplicação única de domínio
    ├── migrations/          # Histórico de migrações do banco de dados
    ├── __init__.py
    ├── admin.py             # Configuração do Django Admin
    ├── apps.py              # Declaração do app
    ├── forms.py             # Formulários e validações de interface
    ├── models.py            # Modelagem de entidades e persistência
    ├── services.py          # Regras de negócio, cálculos e orquestração
    ├── tests.py             # Testes automatizados da aplicação
    ├── urls.py              # Rotas específicas do app
    ├── views.py             # Controladores de requisição/resposta
    └── templates/           # Templates específicos das views
        └── <app_do_projeto>/
            ├── lista.html   # Herda de base.html
            └── form.html    # Herda de base.html
```

---

## 2. Banco de Dados e Persistência

- **SGBD Local:** SQLite (`db.sqlite3`), alocado na raiz do projeto dentro do filesystem nativo do Linux (ext4 no WSL 2) e rigorosamente protegido pelo `.gitignore`.
- **Transações Atômicas:** Operações críticas de escrita envolvendo múltiplos registros ou tabelas correlacionadas devem utilizar `django.db.transaction.atomic()`.
- **Gerenciamento de Esquema:** Qualquer alteração na modelagem deve ser refletida via migrações formais do Django (`makemigrations` e `migrate`). Não realizar modificações manuais no arquivo de banco.

---

## 3. Segurança e Gestão de Credenciais

- **Variáveis de Ambiente:** Nenhuma credencial, token ou segredo deve residir no código-fonte. O `settings.py` deve utilizar carregamento via `django-environ` com conversão booleana explícita para o `DEBUG`:

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

- **Controle de Acesso e Ownership:**
  - Views restritas devem utilizar `LoginRequiredMixin` ou decorators equivalentes.
  - Em operações de consulta, edição ou exclusão, deve ser validada explicitamente a propriedade do registro (`user == request.user`), impedindo acessos horizontais indevidos.
- **Proteção de Formulários:** Todo formulário HTML deve conter a tag `{% csrf_token %}`.

---

## 4. Padrão Visual, Layout e Interface (Bootstrap 5 CDN)

A identidade visual, paleta de cores e a casca do layout são centralizadas em `templates/base.html` utilizando Bootstrap 5 (via CDN), Bootstrap Icons e customização por variáveis CSS nativas (`:root`).

### 4.1. Configuração do Template Mestre (`templates/base.html`)

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Sistema Django{% endblock %}</title>

    <!-- Bootstrap 5 CSS via CDN -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons via CDN -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

    <!-- IDENTIDADE VISUAL E PALETA DE CORES GLOBAL -->
    <style>
        :root {
            --bs-primary: #1e3a8a;          /* Azul Principal / Marca */
            --bs-primary-rgb: 30, 58, 138;
            --bs-secondary: #475569;        /* Neutro / Toolbar */
            --bs-success: #16a34a;          /* Confirmações / Gravação */
            --bs-danger: #dc2626;           /* Ações Destrutivas / Cancelar */
            --bs-warning: #d97706;          /* Alertas / Pendências */
            --bs-body-bg: #f8fafc;          /* Cor de Fundo da Aplicação */
            --bs-body-color: #0f172a;       /* Cor de Texto Padrão */
        }

        body {
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            background-color: var(--bs-body-bg);
            color: var(--bs-body-color);
        }

        /* Toolbar / Barra de Ferramentas */
        .app-toolbar {
            background-color: #ffffff;
            border-bottom: 1px solid #e2e8f0;
            padding: 0.75rem 0;
            margin-bottom: 1.5rem;
        }

        /* Padronização de Botões */
        .btn {
            font-weight: 500;
            border-radius: 0.375rem;
            display: inline-flex;
            align-items: center;
            gap: 0.375rem;
        }

        /* Padronização de Cards e Formulários */
        .card {
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        .form-label {
            font-weight: 600;
            font-size: 0.875rem;
            color: #334155;
        }
        .form-control:focus, .form-select:focus {
            border-color: var(--bs-primary);
            box-shadow: 0 0 0 0.25rem rgba(var(--bs-primary-rgb), 0.15);
        }

        /* Rodapé */
        footer {
            margin-top: auto;
            border-top: 1px solid #e2e8f0;
            background-color: #ffffff;
        }
    </style>

    {% block extra_head %}{% endblock %}
</head>
<body>

    <!-- CABEÇALHO / NAVBAR -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary sticky-top shadow-sm">
        <div class="container-fluid px-4">
            <a class="navbar-brand d-flex align-items-center gap-2 fw-bold" href="/">
                <i class="bi bi-layers-fill"></i> MeuSistema
            </a>
            
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
                <span class="navbar-toggler-icon"></span>
            </button>

            <div class="collapse navbar-collapse" id="navMenu">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    <li class="nav-item">
                        <a class="nav-link active" href="/"><i class="bi bi-house-door"></i> Início</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#"><i class="bi bi-grid"></i> Módulo Principal</a>
                    </li>
                </ul>

                <ul class="navbar-nav ms-auto align-items-center">
                    {% if user.is_authenticated %}
                        <li class="nav-item dropdown">
                            <a class="nav-link dropdown-toggle text-white d-flex align-items-center gap-2" href="#" role="button" data-bs-toggle="dropdown">
                                <i class="bi bi-person-circle fs-5"></i> {{ user.username }}
                            </a>
                            <ul class="dropdown-menu dropdown-menu-end shadow">
                                <li><a class="dropdown-item" href="#"><i class="bi bi-gear me-2"></i>Configurações</a></li>
                                <li><hr class="dropdown-divider"></li>
                                <li>
                                    <form method="post" action="{% url 'logout' %}" class="d-inline">
                                        {% csrf_token %}
                                        <button type="submit" class="dropdown-item text-danger">
                                            <i class="bi bi-box-arrow-right me-2"></i>Sair
                                        </button>
                                    </form>
                                </li>
                            </ul>
                        </li>
                    {% else %}
                        <li class="nav-item">
                            <a class="btn btn-outline-light btn-sm" href="{% url 'login' %}">
                                <i class="bi bi-box-arrow-in-right"></i> Entrar
                            </a>
                        </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <!-- TOOLBAR / AÇÕES RÁPIDAS -->
    <header class="app-toolbar">
        <div class="container-fluid px-4 d-flex justify-content-between align-items-center">
            <div>
                <h1 class="h4 mb-0 fw-bold">{% block page_title %}Visão Geral{% endblock %}</h1>
                <small class="text-muted">{% block page_subtitle %}Gestão e registros{% endblock %}</small>
            </div>
            <div class="d-flex gap-2">
                {% block toolbar_actions %}{% endblock %}
            </div>
        </div>
    </header>

    <!-- MENSAGENS E ALERTAS -->
    <div class="container-fluid px-4">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags|default:'info' }} alert-dismissible fade show" role="alert">
                    <i class="bi bi-info-circle-fill me-2"></i> {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
    </div>

    <!-- ÁREA DE CONTEÚDO PRINCIPAL -->
    <main class="container-fluid px-4 mb-5">
        {% block content %}{% endblock %}
    </main>

    <!-- RODAPÉ -->
    <footer class="py-3 text-center text-muted fs-7">
        <div class="container-fluid">
            &copy; 2026 MeuSistema — Todos os direitos reservados.
        </div>
    </footer>

    <!-- Bootstrap 5 JS Bundle via CDN -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### 4.2. Padrão Semântico de Componentes

| Componente | Classe / Padrão | Utilização Obrigatória |
| :--- | :--- | :--- |
| **Botão de Confirmação** | `btn btn-success` | Salvar, Gravar, Submeter formulário. |
| **Botão de Cancelamento** | `btn btn-danger` | Cancelar edição, Excluir registro. |
| **Botão Neutro / Retorno** | `btn btn-outline-secondary` | Voltar, Limpar filtros. |
| **Botão de Ação / Novo** | `btn btn-primary` | Novo cadastro, Exportar, Ações de toolbar. |
| **Entradas de Texto/Seleção** | `.form-control`, `.form-select` | Campos de formulário Django/HTML. |
| **Container de Telas** | `card` + `card-body` | Formulários e tabelas de dados. |

---

## 5. Estratégia de Testes

- **Localização:** Implementados em `<app_do_projeto>/tests.py` (ou pacote `<app_do_projeto>/tests/`).
- **Escopo Mínimo Obrigatório:**
  - Testes de integridade de modelos e métodos de cálculo.
  - Testes de regras de negócio críticas e serviços em `services.py`.
  - Testes de isolamento de acesso (**Ownership Check**: garantir que o usuário A não manipule recursos do usuário B).
  - Testes de rotas, códigos de status HTTP e permissões de views.

---

## 6. Definition of Done (DoD)

Para considerar qualquer funcionalidade finalizada antes de abrir Pull Request:

- [ ] Lógica de negócio implementada conforme a especificação em `regras_de_negocio.md`.
- [ ] Regras de negócio encapsuladas em `forms.py` / `services.py` mantendo views enxutas.
- [ ] Interface visual construída herdando de `templates/base.html` e respeitando o padrão de botões e cores.
- [ ] Testes automatizados escritos em `tests.py` cobrindo cenários válidos, inválidos e controle de acesso.
- [ ] Migrações geradas (`makemigrations`) e aplicadas (`migrate`) sem conflitos.
- [ ] Novas variáveis de ambiente documentadas no `.env.example`.
- [ ] Conventional Commits e salvaguardas do `AGENT_INSTRUCTIONS_DJANGO.md` rigorosamente observados.

---

## 7. Regras de Negócio e Requisitos de Domínio

As definições detalhadas sobre escopo funcional, fluxos operacionais, regras de negócio (RN) e requisitos funcionais (RF) estão documentadas exclusivamente no arquivo:

👉 **`regras_de_negocio_e_outras_definicoes.md`**

O agente de IA deve consultar diretamente o arquivo `regras_de_negocio.md` para qualquer implementação de modelos, serviços, formulários e regras específicas da aplicação.
