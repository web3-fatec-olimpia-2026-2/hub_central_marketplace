# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from .models import ContaMarketplace, LogSincronizacao, LogAuditoria


@admin.register(ContaMarketplace)
class ContaMarketplaceAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Administração de contas de marketplaces no Django Admin.
    POR QUE FAZ: Gestão e inspeção de credenciais e status de conexões por loja.
    PERMISSÕES RBAC: DEV e Superuser.
    MULTI-TENANCY: Vínculo por Loja.
    """
    list_display = ('apelido_conta', 'canal', 'loja', 'seller_id_externo', 'ativo', 'created_at')
    list_filter = ('canal', 'ativo', 'loja')
    search_fields = ('apelido_conta', 'client_id', 'seller_id_externo', 'loja__nome')


@admin.register(LogSincronizacao)
class LogSincronizacaoAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Visualização de logs de sincronização e chamadas de API externas.
    POR QUE FAZ: Diagnóstico técnico e auditoria de integrações (RF-05 / RN-04).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Por loja.
    """
    list_display = ('canal', 'evento', 'loja', 'item_id_externo', 'status_http', 'sucesso', 'tempo_resposta_ms', 'criado_em')
    list_filter = ('canal', 'evento', 'sucesso', 'status_http', 'loja', 'criado_em')
    search_fields = ('item_id_externo', 'mensagem_erro', 'loja__nome')
    readonly_fields = (
        'loja', 'conta_marketplace', 'canal', 'evento', 'item_id_externo',
        'payload_enviado', 'resposta_recebida', 'status_http', 'sucesso',
        'mensagem_erro', 'tempo_resposta_ms', 'criado_em'
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Visualização de logs de auditoria de eventos cadastrais e RBAC.
    POR QUE FAZ: Conformidade com RN-04 (Fonte única da verdade e rastreabilidade).
    PERMISSÕES RBAC: DEV e Superuser (somente leitura).
    MULTI-TENANCY: Por loja.
    """
    list_display = ('evento', 'autor', 'usuario_afetado', 'loja', 'criado_em')
    list_filter = ('evento', 'loja', 'criado_em')
    search_fields = ('detalhes', 'autor__username', 'usuario_afetado__username', 'loja__nome')
    readonly_fields = ('loja', 'autor', 'usuario_afetado', 'evento', 'detalhes', 'ip_origem', 'criado_em')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
