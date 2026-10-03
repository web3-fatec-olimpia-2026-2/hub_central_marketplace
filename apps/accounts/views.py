# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Views de controle, visualização e alternância dinâmica da Matriz RBAC (Doc ① §17.4 e §17.5).
POR QUE FAZ: Permite que Administradores e Desenvolvedores gerenciem permissões granulares por switches,
             com persistência em banco de dados e auditoria contínua de mutações.
PERMISSÕES RBAC: Exclusivo Grupos 3 (ADMIN) e 4 (DEV/Superuser) via guard 'accounts.matriz'.
MULTI-TENANCY: Matriz com escopo global por padrão (§17.6).
"""

import json
from django.shortcuts import redirect
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from .models import RegraRBAC
from .rbac import (
    FUNC_ACCOUNTS_MATRIZ,
    FUNC_ACCOUNTS_ATRIBUIR_PERFIS,
    CATALOGO_FUNCIONALIDADES_RBAC,
    PAPEIS_SISTEMA,
    tem_funcionalidade,
    validar_alteracao_matriz,
    invalidar_cache_rbac,
    get_grupo_usuario,
    RBACFuncionalidadeRequiredMixin,
)


class MatrizRBACView(LoginRequiredMixin, RBACFuncionalidadeRequiredMixin, TemplateView):
    """
    O QUE FAZ: Renderiza a interface da Matriz RBAC estruturada por blocos temáticos e colunas de perfis.
    POR QUE FAZ: Ponto central de governança de acessos para Administradores e Desenvolvedores.
    PERMISSÕES RBAC: accounts.matriz (Grupos 3 e 4).
    """
    template_name = 'accounts/matriz_rbac.html'
    funcionalidade_requerida = FUNC_ACCOUNTS_MATRIZ

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        grupo_usuario = get_grupo_usuario(user)

        # Consulta todas as regras salvas em banco para montar o estado atual em uma única query
        regras_db = {
            (r.funcionalidade, r.papel): r.concedido
            for r in RegraRBAC.objects.all()
        }

        modulos_montados = []
        total_funcionalidades = 0

        for bloco in CATALOGO_FUNCIONALIDADES_RBAC:
            funcs_bloco = []
            for func in bloco['funcionalidades']:
                total_funcionalidades += 1
                cod = func['codigo']
                colunas_papeis = []

                for papel_info in PAPEIS_SISTEMA:
                    papel_cod = papel_info['codigo']
                    papel_grp = papel_info['grupo']

                    # Concessão atual: valor em banco ou padrão do catálogo
                    if (cod, papel_cod) in regras_db:
                        concedido = regras_db[(cod, papel_cod)]
                    else:
                        concedido = func['padrao'].get(papel_cod, False)

                    # Salvaguardas de bloqueio de UI:
                    # 1. Coluna DEV (Grupo 4) sempre bloqueada e ativa (Doc ① §17.4)
                    # 2. accounts.matriz e accounts.atribuir_perfis bloqueadas e falsas para Grupos 0 e 1
                    # 3. Administrador (Grupo 3) não altera Desenvolvedor (Grupo 4)
                    bloqueado = False
                    motivo_bloqueio = ""

                    if papel_cod == 'DEV':
                        bloqueado = True
                        concedido = True  # DEV sempre possui acesso irrestrito
                        motivo_bloqueio = "Acesso irrestrito do Desenvolvedor (Grupo 4) protegido contra auto-bloqueio."
                    elif cod in [FUNC_ACCOUNTS_MATRIZ, FUNC_ACCOUNTS_ATRIBUIR_PERFIS] and papel_grp in [0, 1]:
                        bloqueado = True
                        concedido = False
                        motivo_bloqueio = "Permissão de governança restrita aos Grupos 3 e 4 (Doc ① §17.4)."
                    elif grupo_usuario == 3 and papel_cod == 'DEV':
                        bloqueado = True
                        motivo_bloqueio = "Administradores não podem modificar a coluna do Desenvolvedor."

                    colunas_papeis.append({
                        'papel': papel_cod,
                        'grupo': papel_grp,
                        'nome_papel': papel_info['nome'],
                        'concedido': concedido,
                        'bloqueado': bloqueado,
                        'motivo_bloqueio': motivo_bloqueio,
                    })

                funcs_bloco.append({
                    'codigo': cod,
                    'nome': func['nome'],
                    'descricao': func['descricao'],
                    'delegavel': func['delegavel'],
                    'colunas': colunas_papeis,
                })

            modulos_montados.append({
                'modulo': bloco['modulo'],
                'slug_modulo': bloco['slug_modulo'],
                'icone': bloco['icone'],
                'funcionalidades': funcs_bloco,
                'total_bloco': len(funcs_bloco),
            })

        context['modulos'] = modulos_montados
        context['papeis'] = PAPEIS_SISTEMA
        context['total_modulos'] = len(modulos_montados)
        context['total_funcionalidades'] = total_funcionalidades
        context['is_dev'] = (grupo_usuario == 4)
        context['is_admin'] = (grupo_usuario == 3)
        return context


class MatrizRBACToggleView(LoginRequiredMixin, View):
    """
    O QUE FAZ: Processa a alternância assíncrona (AJAX/Fetch) ou convencional dos switches da Matriz RBAC.
    POR QUE FAZ: Persiste o dado em banco, valida salvaguardas mandatórias e grava histórico em LogAuditoria.
    PERMISSÕES RBAC: accounts.matriz (Grupos 3 e 4).
    """

    def post(self, request, *args, **kwargs):
        is_ajax = (
            request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('accept', '')
            or request.content_type == 'application/json'
        )

        # Validação do guard central accounts.matriz
        if not tem_funcionalidade(request.user, FUNC_ACCOUNTS_MATRIZ):
            if is_ajax:
                return JsonResponse(
                    {'sucesso': False, 'erro': 'Acesso negado: permissão accounts.matriz necessária.'},
                    status=403
                )
            raise PermissionDenied("Acesso negado: permissão accounts.matriz necessária.")

        # Extração de parâmetros (suporte a payload JSON ou form-data)
        if request.content_type == 'application/json' and request.body:
            try:
                dados = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({'sucesso': False, 'erro': 'Payload JSON inválido.'}, status=400)
        else:
            dados = request.POST

        funcionalidade = dados.get('funcionalidade', '').strip()
        papel = dados.get('papel', '').strip()
        raw_concedido = dados.get('concedido')

        # Normalização do valor booleano
        concedido = raw_concedido in (True, 'true', 'True', '1', 1, 'on')

        if not funcionalidade or not papel:
            erro_msg = "Parâmetros 'funcionalidade' e 'papel' são obrigatórios."
            if is_ajax:
                return JsonResponse({'sucesso': False, 'erro': erro_msg}, status=400)
            messages.error(request, erro_msg)
            return redirect('accounts:matriz')

        # Validação estrita das salvaguardas do Doc ① §17.4
        valido, mensagem_validacao = validar_alteracao_matriz(
            request.user, funcionalidade, papel, concedido
        )
        if not valido:
            if is_ajax:
                return JsonResponse({'sucesso': False, 'erro': mensagem_validacao}, status=400)
            messages.error(request, mensagem_validacao)
            return redirect('accounts:matriz')

        # Persistência dinâmica da regra no banco
        regra, _ = RegraRBAC.objects.update_or_create(
            funcionalidade=funcionalidade,
            papel=papel,
            defaults={'concedido': concedido}
        )

        # Invalidação de cache em memória
        invalidar_cache_rbac()

        # Registro auditável em LogAuditoria (Doc ① §21 / RN-04)
        try:
            from apps.marketplaces.models import LogAuditoria
            from apps.marketplaces.enums import EventoAuditoriaEnum

            perfil = getattr(request.user, 'perfil', None)
            loja = getattr(perfil, 'loja', None) if perfil else None

            status_str = "CONCEDIDA" if concedido else "REVOGADA"
            evento = getattr(EventoAuditoriaEnum, 'ALTERACAO_MATRIZ_RBAC', 'ALTERACAO_MATRIZ_RBAC')

            LogAuditoria.objects.create(
                loja=loja,
                autor=request.user,
                evento=evento,
                detalhes=(
                    f"Matriz RBAC: Permissão '{funcionalidade}' para o papel '{papel}' "
                    f"foi alterada para {status_str}."
                ),
                ip_origem=request.META.get('REMOTE_ADDR')
            )
        except Exception:
            # Não interrompe o fluxo de gravação da matriz caso ocorra falha no registro de log
            pass

        msg_sucesso = f"Permissão '{funcionalidade}' para '{papel}' atualizada com sucesso!"
        if is_ajax:
            return JsonResponse({
                'sucesso': True,
                'funcionalidade': funcionalidade,
                'papel': papel,
                'concedido': concedido,
                'mensagem': msg_sucesso
            })

        messages.success(request, msg_sucesso)
        return redirect('accounts:matriz')
