# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo administrativo padrão do Django para registro e personalização da interface Django Admin
from django.contrib import admin

# Importa a classe UserAdmin original do Django para estendê-la preservando as funcionalidades padrão de autenticação
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Importa o modelo User padrão do framework de autenticação do Django
from django.contrib.auth.models import User

# Importa as entidades de modelo Loja (tenant), ModuloLoja (feature flags) e PerfilUsuario (vínculo RBAC)
from .models import Loja, ModuloLoja, PerfilUsuario


# Declaração do inline tabular para gerenciar os módulos habilitados diretamente na página da Loja
class ModuloLojaInline(admin.TabularInline):
    # Início do bloco de docstring que documenta a função, objetivos, permissões e isolamento multi-tenant
    """
    O QUE FAZ: Inline de Feature Flags de Módulos dentro do admin da Loja.
    POR QUE FAZ: Permite ao usuário DEV alternar módulos por tenant diretamente na interface do Django Admin.
    PERMISSÕES RBAC: DEV / Staff.
    MULTI-TENANCY: Escopo da loja editada.
    """
    # Fim do bloco de docstring descritivo

    # Define o modelo dependente a ser renderizado de forma tabular
    model = ModuloLoja

    # Suprime linhas vazias automáticas para inserção extra, mantendo apenas os registros persistidos
    extra = 0

    # Desativa a exclusão de módulos no inline para evitar desativações acidentais por deleção
    can_delete = False

    # Título personalizado da seção no Django Admin
    verbose_name_plural = 'Módulos Habilitados (Feature Flags)'


# Declaração do inline empilhado (stacked) para associar o perfil RBAC e Loja diretamente na tela do usuário
class PerfilUsuarioInline(admin.StackedInline):
    # Início do bloco de docstring explicando o objetivo do inline no modelo User
    """
    O QUE FAZ: Inline de PerfilUsuario no modelo User padrão do Django.
    POR QUE FAZ: Centraliza a atribuição de Tenant e Papel RBAC na criação de usuários pelo Django Admin.
    PERMISSÕES RBAC: DEV / Superuser.
    MULTI-TENANCY: Vínculo com Loja.
    """
    # Fim do bloco de docstring explicativa

    # Define PerfilUsuario como o modelo relacionado
    model = PerfilUsuario

    # Desabilita remoção do perfil via interface para preservar integridade relacional 1:1
    can_delete = False

    # Título do bloco inline na tela de edição do usuário
    verbose_name_plural = 'Perfil de Acesso (RBAC & Tenant)'

    # Especifica explicitamente o nome do campo ForeignKey que conecta o perfil ao usuário
    fk_name = 'usuario'

    # Não renderiza formulários vazios excedentes
    extra = 0


# Registra e customiza a administração da entidade central Loja (Tenant)
@admin.register(Loja)
class LojaAdmin(admin.ModelAdmin):
    # Início da docstring da classe LojaAdmin
    """
    O QUE FAZ: Administração de Lojas e Tenants no Django Admin.
    POR QUE FAZ: Provisionamento, edição cadastral e auditoria de módulos.
    PERMISSÕES RBAC: Exclusivo DEV / Superuser.
    MULTI-TENANCY: Visão global.
    """
    # Fim da docstring informativa

    # Colunas exibidas na listagem tabular de lojas
    list_display = ('nome', 'cnpj', 'cidade', 'estado', 'telefone', 'ativo', 'criado_em')

    # Filtros laterais para segmentação rápida por status operacional, UF e data de cadastro
    list_filter = ('ativo', 'estado', 'criado_em')

    # Campos pesquisáveis por busca textual livre
    search_fields = ('nome', 'cnpj', 'slug', 'cidade', 'email')

    # Preenche automaticamente o campo slug a partir do nome da loja em tempo real
    prepopulated_fields = {'slug': ('nome',)}

    # Acopla a listagem de feature flags de módulos na mesma página da loja
    inlines = [ModuloLojaInline]


# Registra a administração direta do modelo ModuloLoja para consultas e auditorias isoladas
@admin.register(ModuloLoja)
class ModuloLojaAdmin(admin.ModelAdmin):
    # Início da docstring da classe ModuloLojaAdmin
    """
    O QUE FAZ: Administração de Feature Flags de Módulos.
    POR QUE FAZ: Controle direto das flags por tenant.
    PERMISSÕES RBAC: Exclusivo DEV.
    MULTI-TENANCY: Por loja.
    """
    # Fim da docstring explicativa

    # Colunas exibidas na lista de módulos
    list_display = ('loja', 'modulo', 'ativo', 'ativado_em')

    # Filtros laterais por chave do módulo, flag ativo e tenant
    list_filter = ('modulo', 'ativo', 'loja')

    # Pesquisa textual pelo nome da loja ou nome do módulo
    search_fields = ('loja__nome', 'modulo')


# Registra a gestão de perfis de usuário de forma individual
@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    # Início da docstring da classe PerfilUsuarioAdmin
    """
    O QUE FAZ: Administração dos perfis e vinculações de papéis.
    POR QUE FAZ: Gerenciamento do RBAC pelo Django Admin.
    PERMISSÕES RBAC: DEV.
    MULTI-TENANCY: Por loja.
    """
    # Fim da docstring explicativa

    # Colunas visíveis na listagem de perfis RBAC
    list_display = ('usuario', 'papel', 'loja', 'criado_em')

    # Filtros laterais por papel hierárquico e por loja
    list_filter = ('papel', 'loja')

    # Campos indexados para consulta textual
    search_fields = ('usuario__username', 'usuario__email', 'loja__nome')


# Desregistra e re-registra o modelo User com o inline de PerfilUsuario
# Bloco defensivo para desregistrar o User padrão do Django sem gerar exceção caso não estivesse registrado
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


# Estende a classe de administração de usuários padrão injetando o perfil RBAC e a loja
class UserAdmin(BaseUserAdmin):
    # Anexa o inline de perfil para preenchimento obrigatório na mesma tela
    inlines = (PerfilUsuarioInline,)

    # Colunas visíveis na tabela principal de usuários do Django Admin
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_papel', 'get_loja', 'is_staff')

    # Otimiza o carregamento do perfil e da loja via INNER JOIN para evitar o problema N+1 queries
    list_select_related = ('perfil', 'perfil__loja')

    # Método para recuperar e exibir o rótulo legível do papel RBAC do usuário
    def get_papel(self, instance):
        if hasattr(instance, 'perfil'):
            return instance.perfil.get_papel_display()
        return "Sem Perfil"
    # Define o título da coluna na listagem
    get_papel.short_description = 'Papel RBAC'

    # Método para recuperar e exibir o nome da loja vinculada ao perfil do usuário
    def get_loja(self, instance):
        if hasattr(instance, 'perfil') and instance.perfil.loja:
            return instance.perfil.loja.nome
        return "Global / Nenhuma"
    # Define o cabeçalho da coluna na interface administrativa
    get_loja.short_description = 'Loja (Tenant)'


# Registra novamente o modelo User utilizando a classe estendida UserAdmin
admin.site.register(User, UserAdmin)
