from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError

from .enums import (
    PapelUsuarioEnum, EventoAuditoriaEnum, StatusProdutoEnum,
    StatusSincronizacaoEnum, TipoAjusteEstoqueEnum, MarketplaceEnum,
    StatusPedidoEnum
)


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
    e o papel RBAC do usuário (consumindo PapelUsuarioEnum).
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
            # RN-01: Perfis não-DEV devem obrigatoriamente estar vinculados a uma loja
            raise ValidationError({'loja': 'Usuários com papel diferente de DEV devem pertencer a uma Loja.'})


class LogAuditoria(models.Model):
    """
    Registro histórico de ações críticas e alterações cadastrais/RBAC (RN-04).
    Garante rastreabilidade total de mutações de usuários e tenants.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_auditoria', verbose_name="Loja (Tenant)"
    )
    autor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_realizados', verbose_name="Autor da Ação"
    )
    usuario_afetado = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_recebidos', verbose_name="Usuário Afetado"
    )
    evento = models.CharField(
        max_length=30, choices=EventoAuditoriaEnum.choices, verbose_name="Evento"
    )
    detalhes = models.TextField(
        verbose_name="Detalhes da Ação / Histórico de Alterações"
    )
    ip_origem = models.CharField(
        max_length=45, blank=True, null=True, verbose_name="IP de Origem"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Evento"
    )

    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-criado_em']

    def __str__(self):
        autor_str = self.autor.username if self.autor else "Sistema"
        return f"[{self.get_evento_display()}] por {autor_str} em {self.criado_em.strftime('%d/%m/%Y %H:%M')}"


class Categoria(models.Model):
    """
    Representa a categorização de produtos por loja (tenant).
    Possui isolamento multi-tenant (RN-01) com slug único por loja.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='categorias', verbose_name="Loja (Tenant)"
    )
    nome = models.CharField(max_length=100, verbose_name="Nome da Categoria")
    slug = models.SlugField(max_length=120, verbose_name="Identificador (Slug)")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição da Categoria")
    ativo = models.BooleanField(default=True, verbose_name="Categoria Ativa")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        unique_together = [['loja', 'slug']]
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.loja.nome})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.nome)
            slug = base_slug
            counter = 1
            while Categoria.objects.filter(loja=self.loja, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Produto(models.Model):
    """
    Entidade central do Hub Marketplaces — Catálogo e Fonte Única da Verdade.
    Unicidade de SKU por loja (RN-02) e regras estritas de preço e estoque (RN-06).
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='produtos', verbose_name="Loja (Tenant)"
    )
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name='produtos', verbose_name="Categoria"
    )
    sku = models.CharField(
        max_length=60, verbose_name="Código SKU (Identificador Único na Loja)"
    )
    nome = models.CharField(max_length=200, verbose_name="Nome do Produto")
    descricao = models.TextField(
        blank=True, null=True, verbose_name="Descrição Detalhada do Produto"
    )
    preco = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço de Venda (R$)"
    )
    estoque = models.IntegerField(
        default=0, verbose_name="Saldo de Estoque Físico"
    )
    status = models.CharField(
        max_length=20, choices=StatusProdutoEnum.choices, default=StatusProdutoEnum.ATIVO,
        verbose_name="Status do Produto"
    )
    
    # Integração Mercado Livre
    meli_item_id = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="ID do Anúncio Mercado Livre (MLB...)"
    )
    status_sincronizacao = models.CharField(
        max_length=20, choices=StatusSincronizacaoEnum.choices,
        default=StatusSincronizacaoEnum.NAO_SINCRONIZADO, verbose_name="Status de Sincronização"
    )
    
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        unique_together = [['loja', 'sku']]
        ordering = ['nome']

    def __str__(self):
        return f"[{self.sku}] {self.nome} — R$ {self.preco} (Estoque: {self.estoque})"

    def clean(self):
        super().clean()
        if self.preco is not None and self.preco < Decimal('0.00'):
            raise ValidationError({'preco': 'O preço de venda não pode ser negativo (RN-06).'})
        if self.categoria_id and self.loja_id:
            if self.categoria.loja_id != self.loja_id:
                raise ValidationError({'categoria': 'A categoria selecionada deve pertencer à mesma loja do produto.'})

    def save(self, *args, **kwargs):
        if self.sku:
            self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)


class HistoricoPreco(models.Model):
    """
    Registro histórico de alterações de preços de venda (RN-04 / RF-05).
    Armazena preço anterior, novo preço, responsável e data da mutação.
    """
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Produto"
    )
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='historico_precos', verbose_name="Loja (Tenant)"
    )
    preco_anterior = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Preço Anterior (R$)"
    )
    preco_novo = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Novo Preço (R$)"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='precos_alterados', verbose_name="Usuário Responsável"
    )
    motivo = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Motivo da Alteração"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora da Alteração"
    )

    class Meta:
        verbose_name = "Histórico de Preço"
        verbose_name_plural = "Históricos de Preços"
        ordering = ['-criado_em']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema"
        return f"{self.produto.sku}: R$ {self.preco_anterior} -> R$ {self.preco_novo} por {user_str} em {self.criado_em.strftime('%d/%m/%Y %H:%M')}"


class LogSincronizacao(models.Model):
    """
    Registro detalhado de chamadas e respostas de integração com marketplaces externos (RF-05 / RN-04).
    Armazena o payload enviado, resposta da API, status HTTP, sucesso e eventuais mensagens de erro.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='logs_sincronizacao', verbose_name="Loja (Tenant)"
    )
    produto = models.ForeignKey(
        Produto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_sincronizacao', verbose_name="Produto Relacionado"
    )
    marketplace = models.CharField(
        max_length=30, choices=MarketplaceEnum.choices, default=MarketplaceEnum.MERCADO_LIVRE,
        verbose_name="Marketplace"
    )
    evento = models.CharField(
        max_length=40, choices=EventoAuditoriaEnum.choices, verbose_name="Tipo de Operação / Evento"
    )
    item_id_externo = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="ID Externo no Marketplace (MLB...)"
    )
    payload_enviado = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Enviado (JSON)"
    )
    resposta_recebida = models.JSONField(
        default=dict, blank=True, verbose_name="Resposta Recebida da API (JSON)"
    )
    status_http = models.IntegerField(
        null=True, blank=True, verbose_name="Status HTTP"
    )
    sucesso = models.BooleanField(
        default=False, verbose_name="Operação Bem-Sucedida"
    )
    mensagem_erro = models.TextField(
        blank=True, null=True, verbose_name="Mensagem de Erro / Diagnóstico"
    )
    tempo_resposta_ms = models.IntegerField(
        null=True, blank=True, verbose_name="Tempo de Resposta (ms)"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Disparo"
    )

    class Meta:
        verbose_name = "Log de Sincronização"
        verbose_name_plural = "Logs de Sincronização"
        ordering = ['-criado_em']

    def __str__(self):
        status_txt = "Sucesso" if self.sucesso else "Falha"
        prod_sku = self.produto.sku if self.produto else (self.item_id_externo or "Geral")
        return f"[{self.get_marketplace_display()}] {self.get_evento_display()} - {prod_sku} ({status_txt}, HTTP {self.status_http}) em {self.criado_em.strftime('%d/%m/%Y %H:%M:%S')}"


class PedidoVenda(models.Model):
    """
    Registro estruturado de pedidos de venda recebidos de marketplaces externos (RF-06 / RF-07).
    Possui restrição de unicidade ['loja', 'marketplace', 'pedido_id_externo'] para garantir Idempotência.
    """
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='pedidos_venda', verbose_name="Loja (Tenant)"
    )
    marketplace = models.CharField(
        max_length=30, choices=MarketplaceEnum.choices, default=MarketplaceEnum.MERCADO_LIVRE,
        verbose_name="Marketplace de Origem"
    )
    pedido_id_externo = models.CharField(
        max_length=64, db_index=True, verbose_name="ID do Pedido no Marketplace"
    )
    status_externo = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Status Original no Marketplace"
    )
    status = models.CharField(
        max_length=30, choices=StatusPedidoEnum.choices, default=StatusPedidoEnum.PAGO,
        verbose_name="Status no Hub"
    )
    comprador_nome = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Nome do Comprador / Apelido"
    )
    comprador_documento = models.CharField(
        max_length=30, blank=True, null=True, verbose_name="CPF/CNPJ do Comprador"
    )
    valor_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor Total (R$)"
    )
    valor_frete = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Valor do Frete (R$)"
    )
    data_criacao_externa = models.DateTimeField(
        null=True, blank=True, verbose_name="Data / Hora da Venda no Marketplace"
    )
    processado_com_sucesso = models.BooleanField(
        default=False, verbose_name="Processado com Sucesso"
    )
    teve_ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Teve Ruptura de Estoque (Saldo Negativo)"
    )
    observacoes = models.TextField(
        blank=True, null=True, verbose_name="Observações do Pedido / Diagnóstico"
    )
    payload_original = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Original do Webhook/Pedido (JSON)"
    )
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Recebido em"
    )
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Atualizado em"
    )

    class Meta:
        verbose_name = "Pedido de Venda"
        verbose_name_plural = "Pedidos de Venda"
        unique_together = [['loja', 'marketplace', 'pedido_id_externo']]
        ordering = ['-criado_em']

    def __str__(self):
        return f"Pedido #{self.pedido_id_externo} ({self.get_marketplace_display()}) - R$ {self.valor_total} [{self.get_status_display()}]"


class ItemPedidoVenda(models.Model):
    """
    Itens pertencentes a um PedidoVenda, com rastreabilidade detalhada do saldo de estoque anterior e posterior.
    """
    pedido = models.ForeignKey(
        PedidoVenda, on_delete=models.CASCADE, related_name='itens', verbose_name="Pedido de Venda"
    )
    produto = models.ForeignKey(
        Produto, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='itens_vendidos', verbose_name="Produto no Catálogo"
    )
    item_id_externo = models.CharField(
        max_length=64, blank=True, null=True, verbose_name="ID do Anúncio (MLB...)"
    )
    sku_informado = models.CharField(
        max_length=60, blank=True, null=True, verbose_name="SKU no Pedido"
    )
    titulo_anuncio = models.CharField(
        max_length=255, verbose_name="Título do Anúncio"
    )
    quantidade = models.IntegerField(
        default=1, verbose_name="Quantidade Vendida"
    )
    preco_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Preço Unitário (R$)"
    )
    estoque_baixado = models.BooleanField(
        default=False, verbose_name="Estoque Foi Abatido"
    )
    estoque_anterior = models.IntegerField(
        null=True, blank=True, verbose_name="Estoque Anterior"
    )
    estoque_posterior = models.IntegerField(
        null=True, blank=True, verbose_name="Estoque Posterior"
    )
    ruptura_estoque = models.BooleanField(
        default=False, verbose_name="Entrou em Ruptura (Saldo Negativo)"
    )

    class Meta:
        verbose_name = "Item do Pedido de Venda"
        verbose_name_plural = "Itens do Pedido de Venda"

    def __str__(self):
        return f"{self.quantidade}x {self.titulo_anuncio} (R$ {self.preco_unitario})"





