# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o arquivo de rotas com exemplos práticos da documentação oficial
"""
URL configuration for hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# Fim do bloco de documentação inicial das URLs

# Importa o módulo do painel administrativo integrado do Django
from django.contrib import admin

# Importa as funções 'path' (mapeamento de rota) e 'include' (delegação para URLs de outros módulos)
from django.urls import path, include

# Importa as visualizações baseadas em classe (CBVs) focadas em testes de carga, concorrência e integridade do app core
from apps.core.views_testes import (
    # Painel central para execução e monitoramento de testes manuais e de estresse
    TestesDashboardView,
    # Validador de concorrência em atualizações simultâneas de estoque (mitigação de race conditions)
    ConcorrenciaEstoqueView,
    # Validador de concorrência para renovação e troca de tokens OAuth de múltiplos canais
    ConcorrenciaOAuthView,
    # Ponto consolidado de testes de concorrência e locks transacionais da plataforma
    ConcorrenciaTestesView,
)

# Lista de padrões de roteamento avaliada sequencialmente a cada requisição HTTP recebida
urlpatterns = [
    # Mapeia a rota do console administrativo nativo do Django para auditoria e gestão direta do banco
    path('admin/', admin.site.urls),
    
    # Mapeia as rotas padrão de autenticação do Django (login, logout, recuperação e reset de senha)
    path('auth/', include('django.contrib.auth.urls')),
    
    # Conecta as rotas do módulo tenancy diretamente na raiz (contexto de lojistas, onboarding, seleção de empresa)
    path('', include('apps.tenancy.urls')),
    
    # Registra novamente as rotas de tenancy sob o namespace 'core' para retrocompatibilidade com reverse URLs legadas
    path('', include(('apps.tenancy.urls', 'core'), namespace='core')),
    
    # Conecta as rotas do conector de marketplaces (conexões de contas, callbacks OAuth, webhooks dos canais)
    path('', include('apps.marketplaces.urls')),
    
    # Conecta as rotas de catálogo de produtos, marcas, categorias e atributos globais
    path('', include('apps.catalogo.urls')),
    
    # Conecta as rotas do módulo de anúncios com o prefixo '/anuncios/' (publicações e precificação por canal)
    path('anuncios/', include('apps.anuncios.urls')),
    
    # Conecta as rotas do ciclo de pedidos, despacho, esteira de faturamento e pós-venda na raiz
    path('', include('apps.pedidos.urls')),
    
    # Conecta as rotas de gestão financeira, comissionamento de marketplaces e conciliação de repasses
    path('', include('apps.financeiro.urls')),
    
    # Expõe a suíte de endpoints com prefixo '/mockar-dados/' para geração de dados e simulações em homologação
    path('mockar-dados/', include('apps.mockar_dados.urls')),
    
    # Rota para acessar o painel gráfico de testes e validações de ambiente
    path('testes/', TestesDashboardView.as_view(), name='testes_dashboard'),
    
    # Rota que executa testes de simulação de concorrência e condições de corrida na baixa de estoque
    path('testes/concorrencia/estoque/', ConcorrenciaEstoqueView.as_view(), name='teste_concorrencia_estoque'),
    
    # Rota que valida requisições concorrentes disparadas para refresh de tokens OAuth (evitando invalidação acidental)
    path('testes/concorrencia/oauth/', ConcorrenciaOAuthView.as_view(), name='teste_concorrencia_oauth'),
    
    # Rota agregadora para os cenários consolidados de estresse e concorrência
    path('testes/concorrencia/', ConcorrenciaTestesView.as_view(), name='testes_concorrencia'),
]

