# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Context Processor do Sistema de Temas e Navegação (Doc ① §11.5 e Anexo A.5).
POR QUE FAZ: Injeta variáveis globais de tema (tokens, eixos, versão), shell_template e menu_grupos.
RESILIÊNCIA: NUNCA levanta exceção. Em qualquer falha, retorna transparentemente os valores padrão do preset T05 Profissional.
"""

from typing import Dict, Any, List
from django.urls import reverse
from .utils_tema import PRESETS_MODELOS, calcular_derivados_tema
from apps.accounts.rbac import (
    tem_funcionalidade, FUNC_SITE_TEMA_EDITAR, FUNC_SITE_VISIBILIDADE_PUBLICA,
    FUNC_ACCOUNTS_ATRIBUIR_PERFIS, FUNC_ACCOUNTS_MATRIZ
)


def _get_fallback_context() -> Dict[str, Any]:
    """Retorna dicionário canônico com valores do preset T05 Profissional (sem tocar banco de dados)."""
    p = PRESETS_MODELOS['T05']
    derivados = calcular_derivados_tema(p['fundos'], p['destaques'], p['escritas'])
    return {
        'tema': {
            'slug': p['slug'],
            'modelo': 'T05',
            'bs_theme': derivados['bs_theme'],
            'navbar_bs': derivados['navbar_bs'],
            'fundos': p['fundos'],
            'destaques': p['destaques'],
            'escritas': p['escritas'],
            'raio': p['raio'],
            'sombra': p['sombra'],
            'densidade': p['densidade'],
            'movimento': p['movimento'],
            'tipografia': p['tipografia'],
            'icones': p['icones'],
        },
        'tema_versao': 't05-default',
        'shell_template': 'layouts/shell/topo.html',
        'menu_grupos': [],
    }


def _construir_menus_rbac(user) -> List[Dict[str, Any]]:
    """Constrói os grupos de menus da aplicação filtrados ativamente pelo RBAC (Doc ① §11.2)."""
    if not user or not user.is_authenticated:
        return []

    grupos = []

    # Grupo 1: Catálogo e Produtos
    itens_catalogo = []
    try:
        itens_catalogo.append({'titulo': 'Produtos', 'url': reverse('produto_list')})
        itens_catalogo.append({'titulo': 'Categorias', 'url': reverse('categoria_list')})
    except Exception:
        pass

    if itens_catalogo:
        grupos.append({
            'titulo': 'Catálogo',
            'icone': 'bi-box-seam',
            'itens': itens_catalogo,
        })

    # Grupo 2: Integrações Marketplaces
    itens_mkt = []
    try:
        itens_mkt.append({'titulo': 'Canais de Venda', 'url': reverse('canal_list')})
        itens_mkt.append({'titulo': 'Anúncios', 'url': reverse('anuncio_list')})
        itens_mkt.append({'titulo': 'Logs de Sincronização', 'url': reverse('log_sincronizacao_list')})
    except Exception:
        pass

    if itens_mkt:
        grupos.append({
            'titulo': 'Marketplaces',
            'icone': 'bi-diagram-3',
            'itens': itens_mkt,
        })

    # Grupo 3: Vendas e Pedidos
    itens_pedidos = []
    try:
        itens_pedidos.append({'titulo': 'Painel de Pedidos', 'url': reverse('pedido_list')})
    except Exception:
        pass

    if itens_pedidos:
        grupos.append({
            'titulo': 'Pedidos',
            'icone': 'bi-receipt',
            'itens': itens_pedidos,
        })

    # Grupo 4: Precificação e Finanças
    itens_fin = []
    try:
        itens_fin.append({'titulo': 'Simulador Promocional', 'url': reverse('simulador_promocional')})
        if getattr(user, 'is_superuser', False) or getattr(user, 'perfil', None) and (user.perfil.is_dev or user.perfil.is_admin):
            itens_fin.append({'titulo': 'Taxas das Lojas', 'url': reverse('taxas_loja_list')})
            itens_fin.append({'titulo': 'Parâmetros dos Marketplaces', 'url': reverse('parametro_canal_list')})
    except Exception:
        pass

    if itens_fin:
        grupos.append({
            'titulo': 'Precificação',
            'icone': 'bi-cash-coin',
            'itens': itens_fin,
        })

    # Grupo 5: Logs e Telemetria
    itens_logs = []
    try:
        itens_logs.append({'titulo': 'Logs de Integração', 'url': reverse('log_sincronizacao_list')})
        if getattr(user, 'is_superuser', False) or getattr(user, 'perfil', None) and (user.perfil.is_dev or user.perfil.is_admin):
            itens_logs.append({'titulo': 'Logs de Auditoria', 'url': reverse('log_auditoria_list')})
    except Exception:
        pass

    if itens_logs:
        grupos.append({
            'titulo': 'Logs',
            'icone': 'bi-journal-text',
            'itens': itens_logs,
        })

    # Grupo 6: Administração e Governança
    itens_admin = []
    try:
        # Usuários e Perfis
        if tem_funcionalidade(user, FUNC_ACCOUNTS_ATRIBUIR_PERFIS) or getattr(user, 'is_staff', False):
            itens_admin.append({'titulo': 'Operadores & Perfis', 'url': reverse('usuario_list')})

        # Matriz RBAC
        if tem_funcionalidade(user, FUNC_ACCOUNTS_MATRIZ):
            itens_admin.append({'titulo': 'Matriz RBAC', 'url': reverse('accounts:matriz')})

        # Gestão de Lojas (Tenants - Exclusivo DEV)
        perfil = getattr(user, 'perfil', None)
        if (perfil and perfil.is_dev) or user.is_superuser:
            itens_admin.append({'titulo': 'Gestão de Lojas (Tenants)', 'url': reverse('loja_list')})

        # Testes de Concorrência e Diagnóstico
        if (perfil and perfil.is_dev) or user.is_superuser:
            itens_admin.append({'titulo': 'Painel de Testes & Carga', 'url': reverse('testes_dashboard')})
    except Exception:
        pass

    if itens_admin:
        grupos.append({
            'titulo': 'Administração',
            'icone': 'bi-shield-shaded',
            'itens': itens_admin,
        })

    return grupos


def tema(request) -> Dict[str, Any]:
    """
    Context processor canônico: injeta tema, tema_versao, shell_template e menu_grupos.
    Garantia de resiliência absoluta (nunca quebra a página por ausência ou falha de banco).
    """
    try:
        from .models import ConfigTema
        from apps.core.tenancy import get_tenant

        tenant = None
        try:
            tenant = get_tenant(request)
        except Exception:
            pass

        config_tema = ConfigTema.get_tema_ativo(loja=tenant)
        derivados = calcular_derivados_tema(
            config_tema.cor_fundos,
            config_tema.cor_destaques,
            config_tema.cor_escritas
        )

        user = getattr(request, 'user', None)
        menus = _construir_menus_rbac(user)

        variante = getattr(config_tema, 'shell_variante', 'topo') or 'topo'
        shell_template = f"layouts/shell/{variante}.html"

        # Resolução do slug amigável do modelo
        slug_modelo = PRESETS_MODELOS.get(config_tema.modelo, {}).get('slug', 'profissional')

        # Iluminação persistida (Claro / Escuro / Auto)
        iluminacao = None
        if hasattr(request, 'session'):
            iluminacao = request.session.get('hub_iluminacao')
        if not iluminacao and hasattr(request, 'COOKIES'):
            iluminacao = request.COOKIES.get('hub_iluminacao')
        if not iluminacao or iluminacao not in ('light', 'dark', 'auto'):
            iluminacao = derivados['bs_theme']  # default nativo do modelo (dark para T06/T08, light para os demais)

        html_theme = 'dark' if iluminacao == 'dark' else 'light'

        return {
            'tema': {
                'slug': slug_modelo,
                'modelo': config_tema.modelo,
                'bs_theme': derivados['bs_theme'],
                'navbar_bs': derivados['navbar_bs'],
                'fundos': config_tema.cor_fundos,
                'destaques': config_tema.cor_destaques,
                'escritas': config_tema.cor_escritas,
                'raio': config_tema.raio,
                'sombra': config_tema.sombra,
                'densidade': config_tema.densidade,
                'movimento': config_tema.movimento,
                'tipografia': config_tema.tipografia,
                'icones': config_tema.icones,
            },
            'tema_versao': config_tema.versao or 'v1',
            'shell_template': shell_template,
            'menu_grupos': menus,
            'presets_modelos': PRESETS_MODELOS,
            'iluminacao': iluminacao,
            'html_theme': html_theme,
        }
    except Exception:
        # Fallback seguro para T05 Profissional em caso de qualquer exceção
        ctx = _get_fallback_context()
        ctx['presets_modelos'] = PRESETS_MODELOS
        return ctx
