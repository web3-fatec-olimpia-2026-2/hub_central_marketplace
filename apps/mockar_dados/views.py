# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta os objetivos do módulo de views e suas restrições estritas de segurança
"""
O QUE FAZ: View do painel de controle e gerenciamento de dados mockados de desenvolvimento.
POR QUE FAZ: Fornece interface visual para o usuário DEV provisionar, restaurar e excluir dados fictícios de demonstração.
REGRAS DE SEGURANÇA E AMBIENTE:
- Acesso estritamente restrito a usuários com papel DEV (raise PermissionDenied caso contrário).
- Não afeta a conta mestre devmaster.
"""
# Fim do bloco de docstring descritivo

# Importa atalhos do Django para renderização de templates HTML e redirecionamento de rotas HTTP
from django.shortcuts import render, redirect

# Importa a classe genérica base View para implementação de Class-Based Views (CBVs)
from django.views.generic import View

# Importa o mixin de autenticação para exigir que o usuário esteja logado antes de processar qualquer requisição
from django.contrib.auth.mixins import LoginRequiredMixin

# Importa a exceção PermissionDenied para emitir resposta HTTP 403 Forbidden em caso de violação de autorização
from django.core.exceptions import PermissionDenied

# Importa o framework de mensagens do Django para fornecer notificações de feedback visual na interface
from django.contrib import messages

# Importa a função utilitária de RBAC que valida se o usuário autenticado possui o papel global DEV
from apps.tenancy.permissions import usuario_is_dev

# Importa o serviço especialista responsável pela manipulação dos dados sintéticos de teste
from .services import MockDataService


# Declaração da view responsável pela exibição do dashboard e orquestração das ações de mock
class MockarDadosDashboardView(LoginRequiredMixin, View):
    # Início da docstring da classe da view
    """
    Painel de Gestão e Ações de Mock de Dados para Desenvolvimento.
    """
    # Fim da docstring explicativa

    # Caminho do template HTML a ser renderizado para o painel de dados mockados
    template_name = 'mockar_dados/dashboard.html'

    # Interceptador central de despacho de requisições para validação estrita de segurança e RBAC
    def dispatch(self, request, *args, **kwargs):
        # Bloqueia a execução com HTTP 403 Forbidden caso o usuário autenticado não seja DEV
        if not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: o módulo Mockar Dados é de uso restrito e exclusivo do perfil DEV.")
        # Se autorizado, delega o fluxo normal para os métodos HTTP correspondentes (get ou post)
        return super().dispatch(request, *args, **kwargs)

    # Trata requisições HTTP GET levantando o status atual dos registros para exibição no painel
    def get(self, request, *args, **kwargs):
        # Avalia se existem lojas e dados sintéticos presentes no banco de dados
        tem_dados = MockDataService.tem_dados_mockados()
        # Obtém o consolidado numérico das entidades mockadas cadastradas
        contadores = MockDataService.contar_registros_mockados()

        # Monta o contexto para renderização do template
        context = {
            'tem_dados_mockados': tem_dados,
            'contadores': contadores,
            'is_dev': True,
        }
        # Renderiza e retorna o HTML do dashboard com as informações populadas
        return render(request, self.template_name, context)

    # Trata requisições HTTP POST executando as operações de criação ou expurgo da massa de dados
    def post(self, request, *args, **kwargs):
        # Captura o parâmetro de ação enviado pelo formulário da interface
        acao = request.POST.get('acao')

        # Fluxo de geração e provisionamento dos dados de teste
        if acao == 'gerar':
            # Aciona a rotina atômica de criação de lojas, produtos, contas e anúncios
            resultado = MockDataService.gerar_dados_mockados()
            # Emite mensagem de sucesso detalhando os quantitativos gerados
            messages.success(
                request,
                f"Conjunto de dados mockados gerado com sucesso! Foram provisionadas {resultado['lojas_criadas']} lojas, "
                f"{resultado['produtos_criados']} produtos e {resultado['anuncios_criados']} anúncios de marketplace."
            )
        # Fluxo de exclusão e limpeza dos dados de teste
        elif acao == 'excluir':
            # Aciona a rotina atômica de remoção dos dados preservando o superusuário devmaster
            resultado = MockDataService.excluir_dados_mockados()
            # Emite mensagem de aviso informando o total de registros limpos
            messages.warning(
                request,
                f"Todos os dados mockados foram excluídos com sucesso ({resultado['lojas_excluidas']} lojas e "
                f"{resultado['usuarios_excluidos']} usuários de teste removidos). O usuário DEV mestre permanece intacto."
            )
        # Tratamento defensivo caso o valor do campo de ação seja irreconhecível ou inválido
        else:
            messages.error(request, "Ação não reconhecida.")

        # Redireciona de volta para o dashboard de mockar dados adotando o padrão Post-Redirect-Get (PRG)
        return redirect('mockar_dados_dashboard')


# Declaração da view que permite alternar a feature flag de simulação de rotas mock em tempo de execução
class AlternarSimulacaoMockView(LoginRequiredMixin, View):
    # Início do bloco de docstring que documenta o objetivo da view e os papéis autorizados
    """
    O QUE FAZ: Alterna a feature flag SIMULAR_ROTAS_MOCK na sessão do usuário.
    POR QUE FAZ: Permite ao desenvolvedor alternar em 1 clique entre respostas de sucesso simuladas (HTTP 200) e recusa legítima (HTTP 401).
    PERMISSÕES RBAC: DEV e Superusuário.
    """
    # Fim do bloco descritivo da classe

    # Trata requisições HTTP POST para alternar a flag
    def post(self, request, *args, **kwargs):
        # Valida se o usuário tem privilégio DEV antes de permitir a alteração do comportamento do sistema
        if not usuario_is_dev(request.user):
            raise PermissionDenied("Acesso negado: controle de simulação mock exclusivo para perfil DEV.")

        # Importação tardia do helper de alternância para evitar acoplamento no escopo de módulo
        from .services import alternar_simulacao_mock
        # Executa a inversão booleana da flag na sessão e armazena o novo estado
        novo_estado = alternar_simulacao_mock(request)

        # Emite notificação de sucesso explicando o novo comportamento ativo (HTTP 200)
        if novo_estado:
            messages.success(
                request,
                "Simulação de Rotas Mock ATIVADA: Conexões de contas mockadas responderão com HTTP 200 (Sucesso Simulado)."
            )
        # Emite notificação de aviso explicando o novo comportamento ativo (HTTP 401)
        else:
            messages.warning(
                request,
                "Simulação de Rotas Mock DESATIVADA: Contas mockadas sem credenciais legítimas retornarão recusa HTTP 401 (Não Autorizado)."
            )

        # Determina a URL de redirecionamento priorizando o campo 'next', o cabeçalho 'Referer' ou a tela do dashboard
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'mockar_dados_dashboard'
        # Redireciona o usuário para a rota de destino resolvida
        return redirect(next_url)
