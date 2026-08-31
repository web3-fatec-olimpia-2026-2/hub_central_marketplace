from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError


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
    Representa uma Loja (Tenant) isolada dentro da arquitetura multi-tenant do Hub.
    O provisionamento, ativação e edição da Loja é uma operação restrita exclusivamente ao perfil DEV.
    """
    # Identificação Básica
    nome = models.CharField(max_length=150, verbose_name="Nome da Loja")
    slug = models.SlugField(max_length=150, unique=True, verbose_name="Identificador (Slug)")
    cnpj = models.CharField(max_length=20, unique=True, verbose_name="CNPJ")
    inscricao_estadual = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="Inscrição Estadual"
    )
    
    # Contato
    telefone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, null=True, verbose_name="E-mail de Contato")
    
    # Endereço
    cep = models.CharField(max_length=10, blank=True, null=True, verbose_name="CEP")
    endereco = models.CharField(max_length=255, blank=True, null=True, verbose_name="Endereço / Logradouro")
    numero = models.CharField(max_length=20, blank=True, null=True, verbose_name="Número")
    complemento = models.CharField(max_length=100, blank=True, null=True, verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    estado = models.CharField(
        max_length=2, choices=ESTADOS_BRASIL, blank=True, null=True, verbose_name="Estado (UF)"
    )
    pais = models.CharField(max_length=50, default="Brasil", verbose_name="País")
    
    # Status Operacional
    ativo = models.BooleanField(default=True, verbose_name="Loja Ativa")
    
    # Credenciais de Integração - Mercado Livre (Provisionadas por DEV)
    meli_client_id = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Mercado Livre Client ID"
    )
    meli_client_secret = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Mercado Livre Client Secret"
    )
    meli_access_token = models.TextField(
        blank=True, null=True, verbose_name="Mercado Livre Access Token"
    )
    meli_refresh_token = models.TextField(
        blank=True, null=True, verbose_name="Mercado Livre Refresh Token"
    )

    # Auditoria e Rastreabilidade
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Loja"
        verbose_name_plural = "Lojas"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.cnpj})"

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


class PerfilUsuario(models.Model):
    """
    Extensão do modelo User do Django para gerenciar a vinculação de Tenant (Loja)
    e o papel RBAC do usuário (DEV, ADMIN, SUPERVISOR, USUARIO).
    """
    PAPEL_DEV = 'DEV'
    PAPEL_ADMIN = 'ADMIN'
    PAPEL_SUPERVISOR = 'SUPERVISOR'
    PAPEL_USUARIO = 'USUARIO'

    PAPEIS_CHOICES = [
        (PAPEL_DEV, 'Desenvolvedor (DEV) — Escopo Global'),
        (PAPEL_ADMIN, 'Administrador da Loja (ADMIN)'),
        (PAPEL_SUPERVISOR, 'Supervisor da Loja (SUPERVISOR)'),
        (PAPEL_USUARIO, 'Usuário Padrão da Loja (USUÁRIO)'),
    ]

    usuario = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='perfil', verbose_name="Usuário"
    )
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios', verbose_name="Loja (Tenant)"
    )
    papel = models.CharField(
        max_length=20, choices=PAPEIS_CHOICES, default=PAPEL_USUARIO, verbose_name="Papel de Acesso"
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        loja_str = self.loja.nome if self.loja else ("Global" if self.papel == self.PAPEL_DEV else "Sem Loja")
        return f"{self.usuario.username} [{self.get_papel_display()}] - {loja_str}"

    @property
    def is_dev(self):
        return self.papel == self.PAPEL_DEV

    @property
    def is_admin(self):
        return self.papel == self.PAPEL_ADMIN

    @property
    def is_supervisor(self):
        return self.papel == self.PAPEL_SUPERVISOR

    @property
    def is_usuario(self):
        return self.papel == self.PAPEL_USUARIO

    def clean(self):
        super().clean()
        if self.papel != self.PAPEL_DEV and not self.loja:
            # RN-01: Perfis não-DEV devem obrigatoriamente estar vinculados a uma loja
            raise ValidationError({'loja': 'Usuários com papel diferente de DEV devem pertencer a uma Loja.'})

