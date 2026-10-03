# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Módulo central de RBAC com mapeamento de todas as funcionalidades granulares do ecossistema,
          verificação de permissões persistidas em banco de dados e salvaguardas mandatórias (Doc ① §17.4 e §17.5).
POR QUE FAZ: Padroniza os papéis hierárquicos e o controle de acesso com a Matriz Funcionalidade × Perfil
             gerenciada como dado persistido e auditável.
PERMISSÕES RBAC:
  - accounts.matriz: ver e editar matriz RBAC (exclusivo Grupos 3 e 4, não delegável a 0 e 1).
  - accounts.atribuir_perfis: atribuir perfis com regras de elevação (exclusivo Grupos 3 e 4, não delegável).
  - site.tema_editar: configurar tema visual (Grupos 3 e 4 por padrão, delegável).
  - site.visibilidade_publica: alternar visibilidade pública de páginas (Grupos 3 e 4 por padrão, delegável).
MULTI-TENANCY: Matriz com escopo global por padrão (§17.6).
"""

from functools import wraps
from typing import Dict, Any, List, Optional
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin

# Chaves das Funcionalidades Reservadas do Ecossistema (Doc ① §17.5)
FUNC_ACCOUNTS_MATRIZ = 'accounts.matriz'
FUNC_ACCOUNTS_ATRIBUIR_PERFIS = 'accounts.atribuir_perfis'
FUNC_ACCOUNTS_ALTERAR_SENHA = 'accounts.alterar_senha'
FUNC_SITE_TEMA_EDITAR = 'site.tema_editar'
FUNC_SITE_VISIBILIDADE_PUBLICA = 'site.visibilidade_publica'

# Mapeamento canônico dos papéis para os números de grupos canônicos (Doc ① §17.4)
PAPEL_PARA_GRUPO = {
    'DEV': 4,
    'ADMIN': 3,
    'SUPERVISOR': 1,
    'USUARIO': 0,
}

GRUPO_PARA_PAPEL = {
    4: 'DEV',
    3: 'ADMIN',
    1: 'SUPERVISOR',
    0: 'USUARIO',
}

PAPEIS_SISTEMA = [
    {
        'codigo': 'USUARIO',
        'grupo': 0,
        'nome': 'Usuário Padrão',
        'rotulo_completo': 'Usuário Padrão (Grupo 0 / USUÁRIO)',
        'badge': 'secondary',
    },
    {
        'codigo': 'SUPERVISOR',
        'grupo': 1,
        'nome': 'Supervisor da Loja',
        'rotulo_completo': 'Supervisor da Loja (Grupo 1 / SUPERVISOR)',
        'badge': 'info',
    },
    {
        'codigo': 'ADMIN',
        'grupo': 3,
        'nome': 'Administrador da Loja',
        'rotulo_completo': 'Administrador da Loja (Grupo 3 / ADMIN)',
        'badge': 'primary',
    },
    {
        'codigo': 'DEV',
        'grupo': 4,
        'nome': 'Desenvolvedor',
        'rotulo_completo': 'Desenvolvedor (Grupo 4 / DEV / SUPERUSER)',
        'badge': 'danger',
    },
]

# Catálogo completo e granular das 26 funcionalidades agrupadas por blocos temáticos correlatos
CATALOGO_FUNCIONALIDADES_RBAC: List[Dict[str, Any]] = [
    {
        'modulo': 'Aparência & Identidade Visual',
        'slug_modulo': 'aparencia',
        'icone': 'bi-palette',
        'funcionalidades': [
            {
                'codigo': 'site.tema_editar',
                'nome': 'Personalizar Tema & Cores',
                'descricao': 'Alternar presets e personalizar as 3 cores no modelo T10.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'site.visibilidade_publica',
                'nome': 'Visibilidade Pública',
                'descricao': 'Alternar entre Landing Page e Login na rota raiz /.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Governança & Identidade',
        'slug_modulo': 'governanca',
        'icone': 'bi-shield-lock',
        'funcionalidades': [
            {
                'codigo': 'accounts.matriz',
                'nome': 'Matriz RBAC',
                'descricao': 'Visualizar e alterar a Matriz RBAC (exclusivo Grupos 3 e 4).',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': False,  # Salvaguarda: NUNCA delegável a perfis operacionais (Grupos 0 e 1)
            },
            {
                'codigo': 'accounts.atribuir_perfis',
                'nome': 'Atribuir Perfis Hierárquicos',
                'descricao': 'Criar/editar usuários e definir papéis hierárquicos.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': False,  # Salvaguarda: NUNCA delegável a perfis operacionais (Grupos 0 e 1)
            },
            {
                'codigo': 'accounts.alterar_senha',
                'nome': 'Redefinir Credenciais de Acesso',
                'descricao': 'Redefinir senhas e gerenciar credenciais de acesso.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Tenancy (Lojas)',
        'slug_modulo': 'tenancy',
        'icone': 'bi-shop',
        'funcionalidades': [
            {
                'codigo': 'tenancy.loja_ver',
                'nome': 'Consultar Lojas',
                'descricao': 'Consultar lista e detalhes de lojas/tenants.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'tenancy.loja_criar',
                'nome': 'Cadastrar Novas Lojas',
                'descricao': 'Cadastrar novas lojas/tenants.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': False, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'tenancy.loja_editar',
                'nome': 'Configurar Parâmetros de Lojas',
                'descricao': 'Configurar parâmetros de lojas existentes.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Catálogo & Estoque',
        'slug_modulo': 'catalogo',
        'icone': 'bi-boxes',
        'funcionalidades': [
            {
                'codigo': 'catalogo.categoria_gerenciar',
                'nome': 'Gerenciar Categorias',
                'descricao': 'Criar, editar e excluir categorias da árvore taxonômica.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'catalogo.produto_ver',
                'nome': 'Visualizar Produtos & Custos',
                'descricao': 'Listar produtos e visualizar detalhes de custos.',
                'padrao': {'USUARIO': True, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'catalogo.produto_criar',
                'nome': 'Cadastrar Produtos',
                'descricao': 'Cadastrar novos produtos no estoque.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'catalogo.produto_editar',
                'nome': 'Editar Produtos & Preços',
                'descricao': 'Atualizar preços, descrições e estoque.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'catalogo.produto_excluir',
                'nome': 'Excluir Produtos',
                'descricao': 'Remover produtos do catálogo.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Marketplaces & Conectores',
        'slug_modulo': 'marketplaces',
        'icone': 'bi-diagram-3',
        'funcionalidades': [
            {
                'codigo': 'marketplaces.conector_ver',
                'nome': 'Visualizar Canais Integrados',
                'descricao': 'Visualizar canais integrados (Mercado Livre, etc.).',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'marketplaces.conector_configurar',
                'nome': 'Configurar Credenciais & Conectores',
                'descricao': 'Gerenciar credenciais OAuth2, segredos e webhooks.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'marketplaces.sincronizar_manual',
                'nome': 'Disparar Sincronização Manual',
                'descricao': 'Disparar rotinas manuais de sincronização de catálogo/estoque.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Anúncios',
        'slug_modulo': 'anuncios',
        'icone': 'bi-megaphone',
        'funcionalidades': [
            {
                'codigo': 'anuncios.anuncio_ver',
                'nome': 'Consultar Anúncios & SKUs',
                'descricao': 'Consultar anúncios e mapeamentos de SKUs.',
                'padrao': {'USUARIO': True, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'anuncios.anuncio_publicar',
                'nome': 'Publicar e Gerenciar Anúncios',
                'descricao': 'Publicar, pausar ou reativar anúncios.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'anuncios.preco_ajustar',
                'nome': 'Ajustar Precificação nos Canais',
                'descricao': 'Alterar precificação exclusiva de anúncios nos canais.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Pedidos & Expedição',
        'slug_modulo': 'pedidos',
        'icone': 'bi-receipt',
        'funcionalidades': [
            {
                'codigo': 'pedidos.pedido_ver',
                'nome': 'Visualizar Pedidos & Vendas',
                'descricao': 'Visualizar lista de pedidos e histórico de vendas.',
                'padrao': {'USUARIO': True, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'pedidos.pedido_baixar_estoque',
                'nome': 'Confirmar Baixa & Reserva',
                'descricao': 'Confirmar baixa e reserva de estoque.',
                'padrao': {'USUARIO': True, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Simulador Financeiro',
        'slug_modulo': 'financeiro',
        'icone': 'bi-calculator',
        'funcionalidades': [
            {
                'codigo': 'financeiro.simulador_acessar',
                'nome': 'Acessar Simulador Financeiro',
                'descricao': 'Acessar calculadora de margens, markups e ponto de equilíbrio.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'financeiro.taxas_editar',
                'nome': 'Configurar Tabelas de Comissões',
                'descricao': 'Configurar tabelas de comissões e tarifas de marketplaces.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
    {
        'modulo': 'Telemetria, Logs e Ferramentas',
        'slug_modulo': 'core',
        'icone': 'bi-cpu',
        'funcionalidades': [
            {
                'codigo': 'core.logs_ver',
                'nome': 'Consultar Logs & Auditoria',
                'descricao': 'Consultar logs de auditoria e sincronização multicanal.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': True, 'ADMIN': True, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'core.mockar_dados',
                'nome': 'Gerador de Dados Mock',
                'descricao': 'Executar gerador de dados mock (restrito a ambientes de desenvolvimento/teste).',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': False, 'DEV': True},
                'delegavel': True,
            },
            {
                'codigo': 'core.testes_executar',
                'nome': 'Painel e Execução de Testes',
                'descricao': 'Visualizar status e disparar testes de integração.',
                'padrao': {'USUARIO': False, 'SUPERVISOR': False, 'ADMIN': False, 'DEV': True},
                'delegavel': True,
            },
        ]
    },
]

# Dicionário indexado de funcionalidades para busca O(1)
MAPA_FUNCIONALIDADES: Dict[str, Dict[str, Any]] = {}
for _bloco in CATALOGO_FUNCIONALIDADES_RBAC:
    for _func in _bloco['funcionalidades']:
        MAPA_FUNCIONALIDADES[_func['codigo']] = {
            'nome': _func['nome'],
            'descricao': _func['descricao'],
            'modulo': _bloco['modulo'],
            'slug_modulo': _bloco['slug_modulo'],
            'padrao': _func['padrao'],
            'delegavel': _func['delegavel'],
        }

# Retrocompatibilidade com FUNCIONALIDADES_RESERVADAS legadas
FUNCIONALIDADES_RESERVADAS = {
    FUNC_ACCOUNTS_MATRIZ: {
        'nome': 'Ver e editar a matriz RBAC',
        'padrao_grupos': [3, 4],
        'delegavel': False,
    },
    FUNC_ACCOUNTS_ATRIBUIR_PERFIS: {
        'nome': 'Atribuir perfis hierárquicos',
        'padrao_grupos': [3, 4],
        'delegavel': False,
    },
    FUNC_SITE_TEMA_EDITAR: {
        'nome': 'Alterar o tema do sistema',
        'padrao_grupos': [3, 4],
        'delegavel': True,
    },
    FUNC_SITE_VISIBILIDADE_PUBLICA: {
        'nome': 'Ativar/desativar as páginas públicas',
        'padrao_grupos': [3, 4],
        'delegavel': True,
    },
}

# Cache local em memória para minimizar consultas repetitivas de banco na mesma requisição
_CACHE_REGRAS_RBAC: Optional[Dict[str, bool]] = None


def invalidar_cache_rbac():
    """Invalida o cache em memória das regras RBAC após alterações na matriz."""
    global _CACHE_REGRAS_RBAC
    _CACHE_REGRAS_RBAC = None


def get_grupo_usuario(user) -> int:
    """Retorna o nível de grupo numérico do usuário (0 a 4) conforme Doc ① §17.4."""
    if not user or not user.is_authenticated:
        return -1
    if user.is_superuser:
        return 4
    perfil = getattr(user, 'perfil', None)
    if perfil:
        papel = getattr(perfil, 'papel', None)
        return PAPEL_PARA_GRUPO.get(papel, 0)
    return 0


def get_padrao_funcionalidade(codigo_funcionalidade: str, papel: str) -> bool:
    """Retorna a concessão padrão canônica definida no catálogo para o papel."""
    if papel == 'DEV':
        return True
    func_meta = MAPA_FUNCIONALIDADES.get(codigo_funcionalidade)
    if func_meta:
        return bool(func_meta['padrao'].get(papel, False))
    return False


def tem_funcionalidade(user, codigo_funcionalidade: str) -> bool:
    """
    O QUE FAZ: Avalia se o usuário possui acesso à funcionalidade solicitada.
    POR QUE FAZ: Fonte única para checagem no backend, visibilidade de menus e templates (Doc ① §17.4 e §17.5).
    FONTE DE DADOS: Consulta RegraRBAC persistida no banco; se não cadastrada, utiliza o padrão canônico do catálogo.
    """
    if not user or not user.is_authenticated:
        return False

    # Superusuários nativos e perfil DEV (Grupo 4) possuem acesso total
    if user.is_superuser:
        return True

    grupo = get_grupo_usuario(user)
    if grupo == 4:
        return True

    perfil = getattr(user, 'perfil', None)
    papel = getattr(perfil, 'papel', 'USUARIO') if perfil else 'USUARIO'

    # Consulta tabela persistida no banco
    try:
        from apps.accounts.models import RegraRBAC
        regra = RegraRBAC.objects.filter(funcionalidade=codigo_funcionalidade, papel=papel).first()
        if regra is not None:
            return regra.concedido
    except Exception:
        # Fallback resiliente caso o banco ainda não tenha aplicado a migração
        pass

    # Fallback para os valores canônicos padrão do catálogo
    return get_padrao_funcionalidade(codigo_funcionalidade, papel)


def validar_alteracao_matriz(autor, funcionalidade: str, papel: str, concedido: bool) -> tuple[bool, str]:
    """
    O QUE FAZ: Aplica as salvaguardas mandatórias do Doc ① §17.4 antes de salvar qualquer alternância de switch.
    REGRAS DE SALVAGUARDA:
      1. accounts.matriz e accounts.atribuir_perfis não podem ser concedidos a perfis operacionais (Grupos 0 e 1).
      2. O Administrador (Grupo 3) não pode alterar nem revogar permissões da coluna do Desenvolvedor (Grupo 4).
      3. A coluna do Desenvolvedor (Grupo 4) tem permissões ativas e fixas para evitar auto-bloqueio acidental.
    """
    if not autor or not autor.is_authenticated:
        return False, "Usuário não autenticado."

    if not (autor.is_superuser or tem_funcionalidade(autor, FUNC_ACCOUNTS_MATRIZ)):
        return False, "Acesso negado: apenas Administradores e Desenvolvedores podem alterar a Matriz RBAC."

    # Salvaguarda 3: Desenvolvedor (Grupo 4) não pode ter permissões revogadas no sistema
    if papel == 'DEV':
        return False, "As permissões da coluna do Desenvolvedor (Grupo 4) são fixas e protegidas contra bloqueio acidental."

    # Salvaguarda 2: Administrador (Grupo 3) não altera a coluna do Desenvolvedor
    grupo_autor = get_grupo_usuario(autor)
    if grupo_autor == 3 and papel == 'DEV':
        return False, "Administradores não têm autorização para modificar permissões do Desenvolvedor."

    # Salvaguarda 1: accounts.matriz e accounts.atribuir_perfis NUNCA delegáveis a 0 e 1
    if funcionalidade in [FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS]:
        if papel in ['USUARIO', 'SUPERVISOR'] and concedido:
            return False, "Salvaguarda de Segurança (Doc ① §17.4): As permissões de governança (accounts.matriz e accounts.atribuir_perfis) não podem ser delegadas a perfis operacionais."

    # Verifica se a funcionalidade é válida no catálogo
    if funcionalidade not in MAPA_FUNCIONALIDADES:
        return False, f"Funcionalidade desconhecida: '{funcionalidade}'."

    return True, ""


class RBACFuncionalidadeRequiredMixin(AccessMixin):
    """Mixin para CBVs que exige determinada funcionalidade do RBAC."""
    funcionalidade_requerida = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.funcionalidade_requerida and not tem_funcionalidade(request.user, self.funcionalidade_requerida):
            raise PermissionDenied(f"Acesso negado: funcionalidade '{self.funcionalidade_requerida}' necessária.")

        return super().dispatch(request, *args, **kwargs)


def require_funcionalidade(codigo_funcionalidade: str):
    """Decorador de função para validação RBAC de views."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                from django.conf import settings
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
            if not tem_funcionalidade(request.user, codigo_funcionalidade):
                raise PermissionDenied(f"Acesso negado: funcionalidade '{codigo_funcionalidade}' necessária.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
