# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Contrato neutro de Tenancy para o ecossistema Django (Doc ① §10.6).
POR QUE FAZ: Centraliza a resolução do Tenant (Loja) da requisição de forma desacoplada do modo de isolamento ('single', 'row', 'schema', 'database').
PERMISSÕES RBAC: Qualquer usuário autenticado ou rotinas de sistema.
MULTI-TENANCY: Ponto único de entrada para obter o tenant corrente da requisição ou tarefa.
"""

from django.conf import settings
from django.apps import apps


def get_tenant_mode() -> str:
    """
    O QUE FAZ: Retorna o modo de tenancy configurado na aplicação.
    POR QUE FAZ: Garante que os componentes saibam se operam em modo 'single', 'row', etc.
    """
    return getattr(settings, 'TENANCY_MODE', 'single')


def get_tenant(request=None, explicit_tenant=None):
    """
    O QUE FAZ: Função única contratual para resolver o tenant da requisição ou tarefa (Doc ① §10.6).
    POR QUE FAZ:
      - Em modo 'single': devolve sempre o mesmo tenant fixo (primeira Loja ou instância singleton).
      - Em modo 'row': resolve pelo vínculo do usuário (request.user.perfil.loja), sessão ou cabeçalho.
      - Em tarefas de background, comandos de console e testes: aceita explicit_tenant sem estado global compartilhado.
    """
    if explicit_tenant is not None:
        return explicit_tenant

    mode = get_tenant_mode()

    # Tenta obter o modelo Loja de forma tardia (lazy) para evitar dependência circular
    Loja = None
    try:
        Loja = apps.get_model('tenancy', 'Loja')
    except (LookupError, RuntimeError):
        pass

    if mode == 'single':
        if Loja is not None:
            loja_default = Loja.objects.filter(ativo=True).order_by('id').first()
            if not loja_default:
                loja_default = Loja.objects.order_by('id').first()
            return loja_default
        return None

    # Modo 'row' ou outros modos dinâmicos
    if request is not None:
        # 1. Se já anexado à requisição por middleware prévio
        if hasattr(request, 'tenant') and request.tenant is not None:
            return request.tenant

        # 2. Vínculo direto do usuário autenticado através do perfil
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            perfil = getattr(user, 'perfil', None)
            if perfil and getattr(perfil, 'loja', None):
                return perfil.loja

        # 3. Escopo de sessão (ex: lojista com acesso a mais de uma loja ou usuário DEV simulando tenant)
        session = getattr(request, 'session', None)
        if session and Loja is not None:
            tenant_id = session.get('tenant_id') or session.get('loja_id')
            if tenant_id:
                loja_sessao = Loja.objects.filter(pk=tenant_id, ativo=True).first()
                if loja_sessao:
                    return loja_sessao

    # Fallback caso nada seja identificado
    if Loja is not None:
        return Loja.objects.filter(ativo=True).order_by('id').first()
    return None
