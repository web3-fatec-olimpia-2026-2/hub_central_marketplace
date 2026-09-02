# Os códigos foram gerados com auxilio de I.A.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Loja, ModuloLoja, PerfilUsuario


class ModuloLojaInline(admin.TabularInline):
    """
    O QUE FAZ: Inline de Feature Flags de Módulos dentro do admin da Loja.
    POR QUE FAZ: Permite ao usuário DEV alternar módulos por tenant diretamente na interface do Django Admin.
    PERMISSÕES RBAC: DEV / Staff.
    MULTI-TENANCY: Escopo da loja editada.
    """
    model = ModuloLoja
    extra = 0
    can_delete = False
    verbose_name_plural = 'Módulos Habilitados (Feature Flags)'


class PerfilUsuarioInline(admin.StackedInline):
    """
    O QUE FAZ: Inline de PerfilUsuario no modelo User padrão do Django.
    POR QUE FAZ: Centraliza a atribuição de Tenant e Papel RBAC na criação de usuários pelo Django Admin.
    PERMISSÕES RBAC: DEV / Superuser.
    MULTI-TENANCY: Vínculo com Loja.
    """
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = 'Perfil de Acesso (RBAC & Tenant)'
    fk_name = 'usuario'
    extra = 0


@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Administração de Lojas e Tenants no Django Admin.
    POR QUE FAZ: Provisionamento, edição cadastral e auditoria de módulos.
    PERMISSÕES RBAC: Exclusivo DEV / Superuser.
    MULTI-TENANCY: Visão global.
    """
    list_display = ('nome', 'cnpj', 'cidade', 'estado', 'telefone', 'ativo', 'criado_em')
    list_filter = ('ativo', 'estado', 'criado_em')
    search_fields = ('nome', 'cnpj', 'slug', 'cidade', 'email')
    prepopulated_fields = {'slug': ('nome',)}
    inlines = [ModuloLojaInline]


@admin.register(ModuloLoja)
class ModuloLojaAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Administração de Feature Flags de Módulos.
    POR QUE FAZ: Controle direto das flags por tenant.
    PERMISSÕES RBAC: Exclusivo DEV.
    MULTI-TENANCY: Por loja.
    """
    list_display = ('loja', 'modulo', 'ativo', 'ativado_em')
    list_filter = ('modulo', 'ativo', 'loja')
    search_fields = ('loja__nome', 'modulo')


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    """
    O QUE FAZ: Administração dos perfis e vinculações de papéis.
    POR QUE FAZ: Gerenciamento do RBAC pelo Django Admin.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Por loja.
    """
    list_display = ('usuario', 'papel', 'loja', 'criado_em')
    list_filter = ('papel', 'loja')
    search_fields = ('usuario__username', 'usuario__email', 'loja__nome')


# Desregistra e re-registra o modelo User com o inline de PerfilUsuario
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


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


admin.site.register(User, UserAdmin)
