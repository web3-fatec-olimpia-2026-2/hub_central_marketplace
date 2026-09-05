# Os códigos foram gerados com auxilio de I.A.
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .enums import PapelUsuarioEnum, ModuloSistemaEnum

ESTADOS_BRASIL = [
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
    ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'), ('RN', 'Rio Grande do Norte'),
    ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'), ('RR', 'Roraima'), ('SC', 'Santa Catarina'),
    ('SP', 'São Paulo'), ('SE', 'Sergipe'), ('TO', 'Tocantins'),
]


class Loja(models.Model):
    """
    O QUE FAZ: Entidade central de Tenant (Loja) no Hub Multi-Tenant.
    POR QUE FAZ: Isola dados de clientes (produtos, usuários, pedidos, credenciais) garantindo governança e segurança por inquilino.
    PERMISSÕES RBAC: Provisionamento, edição de dados estruturais e ativação/desativação exclusivos para perfil DEV.
    MULTI-TENANCY: É a raiz de particionamento lógico de todas as entidades do sistema.
    """
    nome = models.CharField(max_length=150, verbose_name="Nome da Loja")
    slug = models.SlugField(max_length=150, unique=True, blank=True, verbose_name="Identificador (Slug)")
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    inscricao_estadual = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Inscrição Estadual"
    )

    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, null=True, verbose_name="E-mail de Contato")

    cep = models.CharField(max_length=10, blank=True, null=True, verbose_name="CEP")
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço / Logradouro")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(
        max_length=2, choices=ESTADOS_BRASIL, blank=True, null=True, verbose_name="Estado (UF)"
    )
    pais = models.CharField(max_length=50, default="Brasil", blank=True, verbose_name="País")

    ativo = models.BooleanField(default=True, verbose_name="Loja Ativa")

    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"
    def clean(self):
        super().clean()
        if self.cnpj:
            import re
            cnpj_digits = re.sub(r'\D', '', self.cnpj)
            if cnpj_digits:
                for outra in Loja.objects.exclude(pk=self.pk).only('cnpj', 'nome'):
                    if re.sub(r'\D', '', outra.cnpj) == cnpj_digits:
                        raise ValidationError({'cnpj': f"Já existe uma loja cadastrada com este CNPJ ({outra.nome})."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            while Loja.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

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

    def tem_modulo_ativo(self, modulo: str) -> bool:
        """
        O QUE FAZ: Verifica se um módulo funcional específico está ativo para esta loja.
        POR QUE FAZ: Base para a autorização por feature flag implementada em ModuloRequeridoMixin.
        PERMISSÕES RBAC: Consulta interna do sistema.
        MULTI-TENANCY: Avalia estritamente os registros vinculados a esta instância de Loja.
        """
        if not self.ativo:
            return False
        return self.modulos.filter(modulo=modulo, ativo=True).exists()

    def garantir_modulos_padrao(self):
        """
        O QUE FAZ: Provisiona os registros de ModuloLoja para todos os módulos conhecidos caso ainda não existam.
        POR QUE FAZ: Garante que toda nova loja provisionada possua as entradas de controle prontas para alternância por DEV.
        PERMISSÕES RBAC: DEV ou rotinas automáticas de provisionamento.
        MULTI-TENANCY: Opera exclusivamente sobre os módulos da loja corrente.
        """
        for choice in ModuloSistemaEnum.values:
            ModuloLoja.objects.get_or_create(
                loja=self,
                modulo=choice,
                defaults={'ativo': True}
            )


class ModuloLoja(models.Model):
    """
    O QUE FAZ: Controla a ativação/desativação de módulos funcionais do sistema por tenant (Feature Flags por Loja).
    POR QUE FAZ: Permite monetização modular, liberação gradual de recursos e revogação de acessos por loja sem acoplamento de código.
    PERMISSÕES RBAC: Gestão exclusiva pelo papel DEV. Demais perfis apenas consomem o acesso conforme a flag.
    MULTI-TENANCY: Relação 1:N estrita com Loja e unicidade composta ('loja', 'modulo').
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='modulos', verbose_name="Loja (Tenant)"
    )
    modulo = models.CharField(
        max_length=30, choices=ModuloSistemaEnum.choices, verbose_name="Módulo do Sistema"
    )
    ativo = models.BooleanField(
        default=True, verbose_name="Módulo Ativo para a Loja"
    )
    ativado_em = models.DateTimeField(
        auto_now=True, verbose_name="Última Alteração de Status"
    )

    class Meta:
        verbose_name = "Módulo da Loja"
        verbose_name_plural = "Módulos das Lojas"
        unique_together = ('loja', 'modulo')
        ordering = ['loja', 'modulo']

    def __str__(self):
        status_str = "Ativo" if self.ativo else "Inativo"
        return f"{self.loja.nome} - {self.get_modulo_display()}: {status_str}"


class PerfilUsuario(models.Model):
    """
    O QUE FAZ: Extensão do modelo User do Django vinculando a identidade do usuário a um Tenant (Loja) e a um Papel RBAC.
    POR QUE FAZ: Centraliza as regras de autorização de papéis (DEV, ADMIN, SUPERVISOR, USUARIO) e isolamento horizontal de inquilinos.
    PERMISSÕES RBAC: DEV gerencia globalmente; ADMIN gerencia subordinados de sua loja; SUPERVISOR e USUARIO não gerenciam perfis.
    MULTI-TENANCY: Vínculo obrigatório a uma Loja para perfis não-DEV (RN-01 / RN-03).
    """
    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil', verbose_name="Usuário"
    )
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios', verbose_name="Loja (Tenant)"
    )
    papel = models.CharField(
        max_length=20, choices=PapelUsuarioEnum.choices, default=PapelUsuarioEnum.USUARIO,
        verbose_name="Papel de Acesso"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        loja_str = self.loja.nome if self.loja else ("Global" if self.papel == PapelUsuarioEnum.DEV else "Sem Loja")
        return f"{self.usuario.username} [{self.get_papel_display()}] - {loja_str}"

    @property
    def is_dev(self):
        return self.papel == PapelUsuarioEnum.DEV

    @property
    def is_admin(self):
        return self.papel == PapelUsuarioEnum.ADMIN

    @property
    def is_supervisor(self):
        return self.papel == PapelUsuarioEnum.SUPERVISOR

    @property
    def is_usuario(self):
        return self.papel == PapelUsuarioEnum.USUARIO

    def clean(self):
        super().clean()
        if self.papel != PapelUsuarioEnum.DEV and not self.loja:
            raise ValidationError({'loja': 'Usuários com papel diferente de DEV devem pertencer a uma Loja (RN-01).'})
