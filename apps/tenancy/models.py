# Os códigos foram gerados com auxilio de I.A.
# Importa o módulo models do Django para declaração de modelos e campos ORM
from django.db import models

# Importa o modelo User nativo do framework de autenticação do Django
from django.contrib.auth.models import User

# Importa o utilitário slugify para converter nomes em slugs amigáveis para URL
from django.utils.text import slugify

# Importa ValidationError para emissão de exceções em validações de consistência do modelo
from django.core.exceptions import ValidationError

# Importa as enumerações de papéis de usuários (RBAC) e módulos do sistema
from .enums import PapelUsuarioEnum, ModuloSistemaEnum

# Lista canônica contendo a tupla de siglas e nomes das 27 Unidades Federativas do Brasil
ESTADOS_BRASIL = [
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
    ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
]


# Declaração do modelo central de inquilino (Tenant) que ancora todas as entidades da aplicação
class Loja(models.Model):
    # Início do bloco de docstring que detalha o papel da entidade no isolamento multi-tenant e governança RBAC
    """
    O QUE FAZ: Entidade central de Tenant (Loja) no Hub Multi-Tenant.
    POR QUE FAZ: Isola dados de clientes (produtos, usuários, pedidos, credenciais) garantindo governança e segurança por inquilino.
    PERMISSÕES RBAC: Provisionamento, edição de dados estruturais e ativação/desativação exclusivos para perfil DEV.
    MULTI-TENANCY: É a raiz de particionamento lógico de todas as entidades do sistema.
    """
    # Fim da docstring explicativa da classe Loja

    # Razão social ou nome fantasia da loja
    nome = models.CharField(max_length=150, verbose_name="Nome da Loja")

    # Identificador alfanumérico único para composição de URLs amigáveis
    slug = models.SlugField(max_length=150, unique=True, blank=True, verbose_name="Identificador (Slug)")

    # Número do Cadastro Nacional da Pessoa Jurídica com unicidade obrigatória no banco
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")

    # Inscrição estadual para fins fiscais e de faturamento (opcional)
    inscricao_estadual = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Inscrição Estadual"
    )

    # Número de telefone comercial de contato
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")

    # Endereço de e-mail institucional
    email = models.EmailField(blank=True, null=True, verbose_name="E-mail de Contato")

    # Código de Endereçamento Postal (CEP)
    cep = models.CharField(max_length=10, blank=True, null=True, verbose_name="CEP")

    # Logradouro do endereço físico
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço / Logradouro")

    # Número predial do endereço
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")

    # Complemento do endereço (apartamento, sala, bloco)
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")

    # Bairro do estabelecimento
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")

    # Cidade/Município sede da loja
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")

    # Sigla da Unidade Federativa baseada na lista canônica ESTADOS_BRASIL
    estado = models.CharField(
        max_length=2, choices=ESTADOS_BRASIL, blank=True, null=True, verbose_name="Estado (UF)"
    )

    # País sede da operação (com valor padrão "Brasil")
    pais = models.CharField(max_length=50, default="Brasil", blank=True, verbose_name="País")

    # Flag booleana que indica se o tenant está operacional ou bloqueado
    ativo = models.BooleanField(default=True, verbose_name="Loja Ativa")

    # Timestamp de gravação inicial do registro
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Timestamp da última modificação dos dados cadastrais
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Configuração de metadados e ordenação padrão do modelo
    class Meta:
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"
        ordering = ['nome']

    # Representação legível em formato string contendo nome e CNPJ
    def __str__(self):
        return f"{self.nome} ({self.cnpj})"

    # Validação customizada no ciclo de vida do modelo
    def clean(self):
        super().clean()
        # Se o CNPJ foi informado, valida a unicidade apenas pelos dígitos numéricos (ignorando pontuações distintas)
        if self.cnpj:
            import re
            cnpj_digits = re.sub(r'\D', '', self.cnpj)
            if cnpj_digits:
                # Compara com as outras lojas cadastradas excluindo a própria instância
                for outra in Loja.objects.exclude(pk=self.pk).only('cnpj', 'nome'):
                    if re.sub(r'\D', '', outra.cnpj) == cnpj_digits:
                        raise ValidationError({'cnpj': f"Já existe uma loja cadastrada com este CNPJ ({outra.nome})."})

    # Sobrescreve o método save para gerar o slug caso omitido, garantindo desambiguação numérica se colidir
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            # Incrementa sufixo numérico enquanto o slug já existir em outra loja
            while Loja.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    # Propriedade que compõe e formata o endereço textual completo para visualizações em telas e relatórios
    @property
    def endereco_completo(self):
        partes = []
        if self.endereco:
            logradouro = self.endereco
            if self.numero:
                logradouro += f", {self.numero}"
            if self.complemento:
                logradouro += f" - {self.complemento}"
            partes.append(logradouro)
        if self.bairro:
            partes.append(self.bairro)
        if self.cidade and self.estado:
            partes.append(f"{self.cidade}/{self.estado}")
        elif self.cidade:
            partes.append(self.cidade)
        if self.cep:
            partes.append(f"CEP: {self.cep}")
        return " - ".join(partes) if partes else "Endereço não informado"

    # Avalia se determinado módulo contratável está ativo para este tenant
    def tem_modulo_ativo(self, modulo: str) -> bool:
        # Início do bloco de docstring
        """
        O QUE FAZ: Verifica se um módulo funcional específico está ativo para esta loja.
        POR QUE FAZ: Base para a autorização por feature flag implementada em ModuloRequeridoMixin.
        PERMISSÕES RBAC: Consulta interna do sistema.
        MULTI-TENANCY: Avalia estritamente os registros vinculados a esta instância de Loja.
        """
        # Fim da docstring explicativa

        # Se a loja como um todo estiver inativa, nenhum módulo pode operar
        if not self.ativo:
            return False
        # Checa a existência de registro ativo na relação associativa ModuloLoja
        return self.modulos.filter(modulo=modulo, ativo=True).exists()

    # Provisiona de forma idempotente todos os módulos padrão do sistema para a loja
    def garantir_modulos_padrao(self):
        # Início do bloco de docstring explicativa
        """
        O QUE FAZ: Provisiona os registros de ModuloLoja para todos os módulos conhecidos caso ainda não existam.
        POR QUE FAZ: Garante que toda nova loja provisionada possua as entradas de controle prontas para alternância por DEV.
        PERMISSÕES RBAC: DEV ou rotinas automáticas de provisionamento.
        MULTI-TENANCY: Opera exclusivamente sobre os módulos da loja corrente.
        """
        # Fim da docstring explicativa

        # Itera por todas as opções de módulos definidos no enum ModuloSistemaEnum
        for choice in ModuloSistemaEnum.values:
            ModuloLoja.objects.get_or_create(
                loja=self,
                modulo=choice,
                defaults={'ativo': True}
            )


# Declaração do modelo associativo que materializa as feature flags de módulos contratados por loja
class ModuloLoja(models.Model):
    # Início do bloco de docstring que documenta finalidade, modelo de monetização e isolamento multi-tenant
    """
    O QUE FAZ: Controla a ativação/desativação de módulos funcionais do sistema por tenant (Feature Flags por Loja).
    POR QUE FAZ: Permite monetização modular, liberação gradual de recursos e revogação de acessos por loja sem acoplamento de código.
    PERMISSÕES RBAC: Gestão exclusiva pelo papel DEV. Demais perfis apenas consomem o acesso conforme a flag.
    MULTI-TENANCY: Relação 1:N estrita com Loja e unicidade composta ('loja', 'modulo').
    """
    # Fim da docstring explicativa

    # Vínculo com a loja tenant com deleção em cascata
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='modulos', verbose_name="Loja (Tenant)"
    )

    # Identificador do módulo conforme as opções de ModuloSistemaEnum
    modulo = models.CharField(
        max_length=30, choices=ModuloSistemaEnum.choices, verbose_name="Módulo do Sistema"
    )

    # Flag que indica se o módulo está habilitado para uso pelo tenant
    ativo = models.BooleanField(
        default=True, verbose_name="Módulo Ativo para a Loja"
    )

    # Timestamp que registra o momento da última alternância de estado da feature flag
    ativado_em = models.DateTimeField(
        auto_now=True, verbose_name="Última Alteração de Status"
    )

    # Configuração de metadados e restrição de unicidade
    class Meta:
        verbose_name = "Módulo da Loja"
        verbose_name_plural = "Módulos das Lojas"
        # Impede a criação duplicada do mesmo módulo para um mesmo tenant
        unique_together = ('loja', 'modulo')
        ordering = ['loja', 'modulo']

    # Representação legível em formato string contendo loja, módulo e status
    def __str__(self):
        status_str = "Ativo" if self.ativo else "Inativo"
        return f"{self.loja.nome} - {self.get_modulo_display()}: {status_str}"


# Declaração do modelo de extensão do User vinculando identidade, papel RBAC e tenant
class PerfilUsuario(models.Model):
    # Início do bloco de docstring que detalha a extensão do User e a governança de acesso
    """
    O QUE FAZ: Extensão do modelo User do Django vinculando a identidade do usuário a um Tenant (Loja) e a um Papel RBAC.
    POR QUE FAZ: Centraliza as regras de autorização de papéis (DEV, ADMIN, SUPERVISOR, USUARIO) e isolamento horizontal de inquilinos.
    PERMISSÕES RBAC: DEV gerencia globalmente; ADMIN gerencia subordinados de sua loja; SUPERVISOR e USUARIO não gerenciam perfis.
    MULTI-TENANCY: Vínculo obrigatório a uma Loja para perfis não-DEV (RN-01 / RN-03).
    """
    # Fim da docstring explicativa

    # Relacionamento unívoco (1:1) com a conta de autenticação nativa do Django
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil', verbose_name="Usuário"
    )

    # Tenant ao qual o operador pertence (pode ser nulo apenas para usuários com papel DEV)
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios', verbose_name="Loja (Tenant)"
    )

    # Papel hierárquico atribuído no modelo RBAC conforme PapelUsuarioEnum
    papel = models.CharField(
        max_length=20, choices=PapelUsuarioEnum.choices, default=PapelUsuarioEnum.USUARIO,
        verbose_name="Papel de Acesso"
    )

    # Timestamp de criação do perfil
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    # Timestamp da última alteração de papel ou loja
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metaclasse com nomes amigáveis para a interface
    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    # Representação textual do perfil indicando username, papel e tenant
    def __str__(self):
        loja_str = self.loja.nome if self.loja else ("Global" if self.papel == PapelUsuarioEnum.DEV else "Sem Loja")
        return f"{self.usuario.username} [{self.get_papel_display()}] - {loja_str}"

    # Atalho booleano para checagem rápida se o papel é DEV
    @property
    def is_dev(self):
        return self.papel == PapelUsuarioEnum.DEV

    # Atalho booleano para checagem rápida se o papel é ADMIN
    @property
    def is_admin(self):
        return self.papel == PapelUsuarioEnum.ADMIN

    # Atalho booleano para checagem rápida se o papel é SUPERVISOR
    @property
    def is_supervisor(self):
        return self.papel == PapelUsuarioEnum.SUPERVISOR

    # Atalho booleano para checagem rápida se o papel é USUARIO
    @property
    def is_usuario(self):
        return self.papel == PapelUsuarioEnum.USUARIO

    # Validação estrutural do modelo assegurando a regra RN-01
    def clean(self):
        super().clean()
        # Obriga que qualquer usuário não-DEV possua um tenant Loja obrigatoriamente associado
        if self.papel != PapelUsuarioEnum.DEV and not self.loja:
            raise ValidationError({'loja': 'Usuários com papel diferente de DEV devem pertencer a uma Loja (RN-01).'})
