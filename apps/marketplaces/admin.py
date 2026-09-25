# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo administrativo padrão do Django para gerenciar a interface de administração
from django.contrib import admin

# Importa as entidades de modelo do app: ContaMarketplace, LogSincronizacao e LogAuditoria
from .models import ContaMarketplace, LogSincronizacao, LogAuditoria


# Decorador para registrar a classe ContaMarketplace no painel administrativo do Django
@admin.register(ContaMarketplace)
class ContaMarketplaceAdmin(admin.ModelAdmin):
    # Início do bloco de docstring que documenta o propósito, escopo de RBAC e multi-tenancy da view administrativa
    """
    O QUE FAZ: Administração de contas de marketplaces no Django Admin.
    POR QUE FAZ: Gestão e inspeção de credenciais e status de conexões por loja.
    PERMISSÕES RBAC: DEV e Superuser.
    MULTI-TENANCY: Vínculo por Loja.
    """
    # Fim do bloco de docstring informativa

    # Define as colunas visíveis na tabela de listagem do Django Admin para as contas integradas
    list_display = ('apelido_conta', 'canal', 'loja', 'seller_id_externo', 'ativo', 'created_at')

    # Configura filtros laterais rápidos por canal do marketplace, status de ativação e loja (tenant)
    list_filter = ('canal', 'ativo', 'loja')

    # Define os campos pesquisáveis via barra de busca (apelido da conta, client_id, seller_id externo e nome da loja)
    search_fields = ('apelido_conta', 'client_id', 'seller_id_externo', 'loja__nome')


# Decorador para registrar o modelo de telemetria técnica LogSincronizacao no Django Admin
@admin.register(LogSincronizacao)
class LogSincronizacaoAdmin(admin.ModelAdmin):
    # Início do bloco de docstring documentando a finalidade técnica de diagnóstico e imutabilidade dos logs
    """
    O QUE FAZ: Visualização de logs de sincronização e chamadas de API externas.
    POR QUE FAZ: Diagnóstico técnico e auditoria de integrações (RF-05 / RN-04).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Por loja.
    """
    # Fim do bloco de documentação estrutural

    # Define as colunas visíveis na tabela de listagem para análise rápida de erros e latência de rede
    list_display = ('canal', 'evento', 'loja', 'item_id_externo', 'status_http', 'sucesso', 'tempo_resposta_ms', 'criado_em')

    # Adiciona filtros laterais por canal, tipo de evento, resultado (sucesso/falha), código HTTP, loja e data de criação
    list_filter = ('canal', 'evento', 'sucesso', 'status_http', 'loja', 'criado_em')

    # Habilita pesquisa textual por ID externo do anúncio, mensagem de erro retornada e nome da loja
    search_fields = ('item_id_externo', 'mensagem_erro', 'loja__nome')

    # Trava todos os campos em modo estrito de somente leitura para impedir alteração de histórico técnico
    readonly_fields = (
        'loja', 'conta_marketplace', 'canal', 'evento', 'item_id_externo',
        'payload_enviado', 'resposta_recebida', 'status_http', 'sucesso',
        'mensagem_erro', 'tempo_resposta_ms', 'criado_em'
    )

    # Bloqueia a criação manual de registros de log via interface administrativa (deve vir apenas de chamadas de API)
    def has_add_permission(self, request):
        return False

    # Bloqueia a exclusão de registros para garantir a integridade e retenção da trilha de telemetria
    def has_delete_permission(self, request, obj=None):
        return False


# Decorador para registrar a entidade de governança LogAuditoria no Django Admin
@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    # Início do bloco de docstring documentando a conformidade com regras de rastreabilidade (RN-04)
    """
    O QUE FAZ: Visualização de logs de auditoria de eventos cadastrais e RBAC.
    POR QUE FAZ: Conformidade com RN-04 (Fonte única da verdade e rastreabilidade).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Por loja.
    """
    # Fim da docstring informativa da classe

    # Define as colunas visíveis na listagem de auditoria de segurança (evento, autor, afetado, loja e data)
    list_display = ('evento', 'autor', 'usuario_afetado', 'loja', 'criado_em')

    # Configura filtros laterais por categoria de evento de auditoria, loja proprietária e data do evento
    list_filter = ('evento', 'loja', 'criado_em')

    # Permite busca textual por detalhes da ação, username do autor, username do usuário afetado e nome da loja
    search_fields = ('detalhes', 'autor__username', 'usuario_afetado__username', 'loja__nome')

    # Define todos os campos como somente leitura para evitar adulteração de logs de auditoria
    readonly_fields = ('loja', 'autor', 'usuario_afetado', 'evento', 'detalhes', 'ip_origem', 'criado_em')

    # Desativa a permissão de adição manual de entradas de auditoria via painel
    def has_add_permission(self, request):
        return False

    # Desativa a permissão de exclusão para assegurar a inviolabilidade do histórico de conformidade
    def has_delete_permission(self, request, obj=None):
        return False
