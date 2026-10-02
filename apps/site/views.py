# Os códigos foram gerados com auxilio de I.A.
"""
O QUE FAZ: Views do módulo de Site, Apresentação, Endpoint /tema.css e Alternância de Temas (T01 a T10).
POR QUE FAZ:
  - Serve o CSS dinâmico /tema.css sanitizado contra CSS injection.
  - Na rota raiz '/', entrega a experiência operacional direta: Dashboard para logados e chaveamento Landing/Login para anônimos.
  - Oferece a página de apresentação em /apresentacao/ respeitando a política anti-enumeração (§17.2).
  - Permite aos usuários alternar entre os 10 modelos de catálogo (T01 a T09) e personalizar as 3 cores (T10).
"""

from django.http import HttpResponse, Http404, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.conf import settings

from .models import ConfigTema, ConfigSite
from .utils_tema import gerar_css_tema, PRESETS_MODELOS, validar_cor_hex
from apps.core.tenancy import get_tenant


@require_GET
def tema_css_view(request):
    """
    Endpoint público que serve o CSS gerado do tema ativo.
    Garante sanitização estrita de hexadecimais contra CSS injection.
    """
    tenant = get_tenant(request)
    config_tema = ConfigTema.get_tema_ativo(loja=tenant)

    css_content = gerar_css_tema(
        cor_fundos=config_tema.cor_fundos,
        cor_destaques=config_tema.cor_destaques,
        cor_escritas=config_tema.cor_escritas
    )

    response = HttpResponse(css_content, content_type='text/css; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


class RaizView(View):
    """
    Controla o fluxo direto de acesso:
      - Usuário logado: acessa imediatamente o Dashboard principal (tenancy/home.html).
      - Usuário anônimo:
          * Se visibilidade pública ativa: Landing Page com status 200.
          * Se visibilidade pública desativada: Tela de login direto.
    """
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                from apps.tenancy.views import DashboardHomeView
                return DashboardHomeView.as_view()(request, *args, **kwargs)
            except Exception:
                return redirect('produto_list')

        if ConfigSite.is_visibilidade_publica_ativa():
            return render(request, 'site/landing.html', {'visibilidade_ativa': True})

        from django.contrib.auth.views import LoginView
        return LoginView.as_view(template_name='registration/login.html')(request, *args, **kwargs)


class LandingPageView(View):
    """
    Página institucional e informativa dos recursos do Hub Central de Marketplaces.
    Acessível em /apresentacao/. Responde 404 estrito se desativada (Doc ① §17.2).
    """
    def get(self, request, *args, **kwargs):
        if not ConfigSite.is_visibilidade_publica_ativa():
            raise Http404("Página desativada.")
        return render(request, 'site/landing.html', {
            'visibilidade_ativa': True
        })


class AlternarTemaView(View):
    """
    Controla a alternância dos 10 Modelos Canônicos de Design (T01 a T10):
      - T01 a T09: aplica os tokens do catálogo canônico (Doc ① §11.6).
      - T10 (Personalizado): recebe e aplica as 3 cores (Fundos, Destaques, Escritas) e eixos de estilo.
    Persiste a escolha no modelo ConfigTema escopado pelo tenant do usuário ou global.
    """
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Não autenticado'}, status=403)

        # 1. Trata alternância direta de modo de iluminação (Claro / Escuro / Auto)
        iluminacao = request.POST.get('iluminacao', '').strip().lower()
        if iluminacao in ('light', 'dark', 'auto'):
            request.session['hub_iluminacao'] = iluminacao
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or not request.POST.get('modelo'):
                response = JsonResponse({'success': True, 'iluminacao': iluminacao})
                response.set_cookie('hub_iluminacao', iluminacao, max_age=31536000, samesite='Lax')
                return response

        modelo = request.POST.get('modelo', '').strip().upper()
        tenant = get_tenant(request)

        # Localiza ou inicializa o ConfigTema para o escopo
        config = None
        if tenant:
            config = ConfigTema.objects.filter(loja=tenant).first()
        if not config:
            config = ConfigTema.objects.filter(loja__isnull=True).first()
        if not config:
            config = ConfigTema(loja=tenant)

        sucesso = False
        mensagem = ""

        if modelo in PRESETS_MODELOS and modelo != 'T10':
            preset = PRESETS_MODELOS[modelo]
            config.modelo = modelo
            config.cor_fundos = preset['fundos']
            config.cor_destaques = preset['destaques']
            config.cor_escritas = preset['escritas']
            config.raio = preset['raio']
            config.sombra = preset['sombra']
            config.densidade = preset['densidade']
            config.movimento = preset['movimento']
            config.tipografia = preset['tipografia']
            config.icones = preset['icones']
            config.save()
            sucesso = True
            mensagem = f"Tema alternado com sucesso para {preset['nome']} ({modelo})!"
            messages.success(request, mensagem)

        elif modelo == 'T10':
            # Personalizado: 3 cores (com suporte a inputs de texto e fallback para color pickers)
            cor_fundos = request.POST.get('cor_fundos', '').strip() or request.POST.get('picker_fundos', '').strip()
            cor_destaques = request.POST.get('cor_destaques', '').strip() or request.POST.get('picker_destaques', '').strip()
            cor_escritas = request.POST.get('cor_escritas', '').strip() or request.POST.get('picker_escritas', '').strip()

            try:
                config.modelo = 'T10'
                config.cor_fundos = validar_cor_hex(cor_fundos, "cor_fundos")
                config.cor_destaques = validar_cor_hex(cor_destaques, "cor_destaques")
                config.cor_escritas = validar_cor_hex(cor_escritas, "cor_escritas")

                if 'raio' in request.POST and request.POST['raio']:
                    config.raio = request.POST['raio']
                if 'sombra' in request.POST and request.POST['sombra']:
                    config.sombra = request.POST['sombra']
                if 'densidade' in request.POST and request.POST['densidade']:
                    config.densidade = request.POST['densidade']

                config.save()
                sucesso = True
                mensagem = "Tema personalizado T10 (3 cores) salvo com sucesso!"
                messages.success(request, mensagem)
            except Exception as e:
                sucesso = False
                mensagem = f"Erro na validação das cores: {e}"
                messages.error(request, mensagem)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': str(e)}, status=400)
        else:
            messages.error(request, f"Modelo de tema '{modelo}' não reconhecido.")

        referer = request.META.get('HTTP_REFERER') or '/'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            resp = JsonResponse({
                'success': sucesso,
                'message': mensagem,
                'modelo': config.modelo,
                'versao': config.versao,
                'cor_fundos': config.cor_fundos,
                'cor_destaques': config.cor_destaques,
                'cor_escritas': config.cor_escritas,
                'redirect_url': referer
            })
        else:
            resp = HttpResponseRedirect(referer)

        if 'hub_iluminacao' in request.session:
            resp.set_cookie('hub_iluminacao', request.session['hub_iluminacao'], max_age=31536000, samesite='Lax')
        return resp
