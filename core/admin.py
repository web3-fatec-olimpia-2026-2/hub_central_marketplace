from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Loja, PerfilUsuario, LogAuditoria


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil de Acesso (RBAC & Tenant)'
    fk_name = 'usuario'
    extra = 0


class UserAdmin(BaseUserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_papel', 'get_loja', 'is_staff')
    list_select_related = ('perfil', 'perfil__loja')

    def get_papel(self, instance):
        if hasattr(instance, 'perfil'):
            return instance.perfil.get_papel_display()
        return "Sem Perfil"
    get_papel.short_description = 'Papel RBAC'

    def get_loja(self, instance):
        if hasattr(instance, 'perfil') and instance.perfil.loja:
            return instance.perfil.loja.nome
        return "Global / Nenhuma"
    get_loja.short_description = 'Loja (Tenant)'


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cnpj', 'cidade', 'estado', 'telefone', 'ativo', 'criado_em')
    list_filter = ('ativo', 'estado', 'criado_em')
    search_fields = ('nome', 'cnpj', 'slug', 'cidade', 'email')
    prepopulated_fields = {'slug': ('nome',)}
    fieldsets = (
        ('Identificação e Status', {
            'fields': ('nome', 'slug', 'cnpj', 'inscricao_estadual', 'ativo')
        }),
        ('Contato', {
            'fields': ('telefone', 'email')
        }),
        ('Endereço', {
            'fields': ('cep', 'endereco', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'pais')
        }),
        ('Integração Mercado Livre (Provisionamento DEV)', {
            'classes': ('collapse',),
            'fields': ('meli_client_id', 'meli_client_secret', 'meli_access_token', 'meli_refresh_token')
        }),
    )


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'papel', 'loja', 'criado_em')
    list_filter = ('papel', 'loja')
    search_fields = ('usuario__username', 'usuario__email', 'loja__nome')


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('evento', 'autor', 'usuario_afetado', 'loja', 'criado_em')
    list_filter = ('evento', 'loja', 'criado_em')
    search_fields = ('detalhes', 'autor__username', 'usuario_afetado__username', 'loja__nome')
    readonly_fields = ('loja', 'autor', 'usuario_afetado', 'evento', 'detalhes', 'ip_origem', 'criado_em')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Re-registra o modelo User com o inline de Perfil
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


