# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo nativo uuid para geração de identificadores únicos universais (UUID4)
import uuid

# Importa o módulo central de modelos ORM do framework Django
from django.db import models

# Importa o modelo User padrão do Django para referências de autoria e usuários afetados nas auditorias
from django.contrib.auth.models import User

# Importa a exceção padrão de validação de regras de negócio do Django
from django.core.exceptions import ValidationError

# Importa o modelo Loja que materializa o inquilino (tenant) para isolamento horizontal
from apps.tenancy.models import Loja

# Importa enumerações tipadas com os canais suportados, eventos de auditoria e status de sincronização e webhooks
from .enums import CanalMarketplaceEnum, EventoAuditoriaEnum, StatusSincronizacaoEnum, WebhookStatusEnum

# Importa o campo customizado com criptografia simétrica Fernet em repouso para segredos e tokens sensíveis
from apps.core.security import EncryptedTextField


# Declaração do modelo principal representativo da conexão/credencial de marketplace da loja
class ContaMarketplace(models.Model):
    # Início do bloco de docstring descrevendo o propósito da conta, RBAC e integridade multi-tenant
    """
    O QUE FAZ: Representa a conexão e credenciais de uma conta de Marketplace vinculada a uma Loja (Tenant).
    POR QUE FAZ: Desacopla a integração de canais específicos, viabilizando arquitetura multicanal com persistência criptografada de tokens OAuth.
    PERMISSÕES RBAC: DEV (qualquer loja); ADMIN (sua própria loja); SUPERVISOR e USUARIO não gerenciam conexões.
    MULTI-TENANCY: FK obrigatória para Loja e restrição de unicidade ('loja', 'canal', 'seller_id_externo').
    """
    # Fim da documentação da classe ContaMarketplace

    # Chave estrangeira ligando a conta à Loja dona, com exclusão em cascata em caso de expurgo do tenant
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='contas_marketplace', verbose_name="Loja (Tenant)"
    )

    # Identificador textual do marketplace com base nas opções canônicas de CanalMarketplaceEnum
    canal = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, verbose_name="Canal de Marketplace"
    )

    # Nome amigável de exibição para facilitar a identificação da conta pelo operador
    apelido_conta = models.CharField(
        max_length=100, verbose_name="Apelido da Conta",
        help_text="Identificador amigável (Ex: Loja Principal ML, Shopee Filial)"
    )

    # Indicador booleano que permite desativar a sincronização sem precisar deletar as credenciais
    ativo = models.BooleanField(
        default=True, verbose_name="Integração Ativa"
    )

    # Indicador booleano sinalizando se a conta é simulada para rotinas de teste e homologação
    is_mock = models.BooleanField(
        default=False, verbose_name="Conta Simulada / Mock",
        help_text="Indica se a conta pertence ao conjunto de lojas e dados fictícios de teste."
    )

    # Tuplas de escolhas para a estratégia de integração da aplicação OAuth
    TIPO_APLICACAO_CHOICES = [
        ('GLOBAL', 'Aplicação Global do Hub (Centralizada)'),
        ('INDIVIDUAL', 'Aplicação Própria do Tenant (Individual)'),
    ]

    # Estratégia de Aplicação (Híbrida: Global vs Individual)
    # Define se a conta usará a app corporativa central do SaaS ou credenciais privadas registradas pelo lojista
    tipo_aplicacao = models.CharField(
        max_length=20,
        choices=TIPO_APLICACAO_CHOICES,
        default='GLOBAL',
        verbose_name="Tipo de Aplicação",
        help_text="Define se utiliza credenciais compartilhadas do Hub ou chaves próprias do lojista."
    )

    # Identificador Público de Roteamento para Webhook Individual (Segmentação na Origem)
    # UUID exclusivo para composição de endpoints dedicados de webhook por conta, indexado para busca rápida
    webhook_uuid = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name="UUID do Webhook"
    )

    # Credenciais do Desenvolvedor (Modo Individual)
    # Identificador público da aplicação do lojista no portal de desenvolvedores do marketplace
    app_key_or_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="App ID / Partner ID / Client ID",
        help_text="Identificador público da aplicação: Client ID / Partner ID"
    )

    # Segredo privado da aplicação do lojista, gravado com criptografia Fernet em repouso
    app_secret = EncryptedTextField(
        blank=True,
        null=True,
        verbose_name="App Secret / Client Secret / Partner Key",
        help_text="Chave secreta da aplicação (criptografada em repouso via Fernet)."
    )

    # Segredo compartilhado específico para conferência do HMAC da assinatura de webhook, protegido por Fernet
    webhook_secret = EncryptedTextField(
        blank=True,
        null=True,
        verbose_name="Webhook Secret",
        help_text="Chave secreta para validação de assinatura HMAC dos webhooks."
    )

    # Credenciais de Integração OAuth / API (Criptografadas em Repouso via Fernet)
    # Token de autorização para chamadas HTTP ativas, protegido em repouso
    access_token = EncryptedTextField(
        blank=True, null=True, verbose_name="Access Token"
    )

    # Token de renovação utilizado para emitir novo access_token quando este expirar, cifrado com Fernet
    refresh_token = EncryptedTextField(
        blank=True, null=True, verbose_name="Refresh Token"
    )

    # Carimbo temporal que marca a data e hora em que o access_token perderá a validade
    token_expira_em = models.DateTimeField(
        blank=True, null=True, verbose_name="Token Expira Em"
    )

    # Timestamp que registra a última execução bem-sucedida de sincronização para esta conta
    ultima_sincronizacao = models.DateTimeField(
        blank=True, null=True, verbose_name="Última Sincronização"
    )

    # Identificador único da loja/vendedor dentro da plataforma remota do marketplace
    seller_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Seller ID Externo / User ID"
    )

    # Data e hora do registro inicial da conexão da conta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Conectado em")

    # Data e hora da última mutação cadastral na conta
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    # Metadados de configuração e restrições de integridade relacional
    class Meta:
        verbose_name = "Conta de Marketplace"
        verbose_name_plural = "Contas de Marketplaces"
        constraints = [
            # Restringe cada loja a possuir no máximo uma única conexão ativa para cada canal de marketplace
            models.UniqueConstraint(
                fields=['loja', 'canal'],
                name='unique_conta_loja_canal'
            ),
            # Impede a duplicidade de apelidos para contas dentro do escopo da mesma loja
            models.UniqueConstraint(
                fields=['loja', 'apelido_conta'],
                name='unique_conta_loja_apelido'
            ),
            # Garante que um mesmo seller ID externo não seja vinculado simultaneamente a mais de uma conta no mesmo canal
            models.UniqueConstraint(
                fields=['canal', 'seller_id_externo'],
                condition=models.Q(seller_id_externo__isnull=False) & ~models.Q(seller_id_externo=''),
                name='unique_conta_canal_seller_id'
            ),
        ]
        # Ordenação padrão de consultas por loja, canal e apelido
        ordering = ['loja', 'canal', 'apelido_conta']

    # Representação textual legível formatada com o canal, apelido e nome da loja
    def __str__(self):
        return f"[{self.get_canal_display()}] {self.apelido_conta} — {self.loja.nome}"

    # Método de validação de modelo executado antes de salvar
    def clean(self):
        super().clean()

        # 1. Imutabilidade na edição: canal e loja não podem ser alterados
        # Impede a migração de uma conta existente para outra loja ou canal
        if self.pk:
            original = ContaMarketplace.objects.filter(pk=self.pk).only('loja_id', 'canal').first()
            if original:
                if original.loja_id != self.loja_id:
                    raise ValidationError({'loja': "A loja (tenant) vinculada é imutável após a conexão."})
                if original.canal != self.canal:
                    raise ValidationError({'canal': "O canal de marketplace é imutável após a conexão."})

        # 2. Trava Loja + Canal (apenas 1 conexão ativa por canal por loja)
        # Validação defensiva em nível de formulário/modelo para o par loja e canal
        if self.loja_id and self.canal:
            qs = ContaMarketplace.objects.filter(loja_id=self.loja_id, canal=self.canal)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'canal': f"A loja selecionada já possui uma conexão para o canal {self.get_canal_display()}."
                })

        # 3. Trava Canal + Seller ID Externo (não pode ser reaproveitado por outra loja)
        # Impede reaproveitamento do mesmo seller ID em outra loja no mesmo canal
        if self.canal and self.seller_id_externo:
            qs = ContaMarketplace.objects.filter(canal=self.canal, seller_id_externo=self.seller_id_externo)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'seller_id_externo': f"O Seller ID Externo '{self.seller_id_externo}' já está em uso por outra conta no canal {self.get_canal_display()}."
                })

        # 4. Trava Loja + Apelido da Conta (único dentro da loja)
        # Garante a singularidade do apelido dentro do tenant
        if self.loja_id and self.apelido_conta:
            qs = ContaMarketplace.objects.filter(loja_id=self.loja_id, apelido_conta=self.apelido_conta)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({
                    'apelido_conta': f"Já existe uma conta com o apelido '{self.apelido_conta}' cadastrada para esta loja."
                })

    # Sobrescrita do método save para reforçar imutabilidade e identificar lojas de demonstração (mock)
    def save(self, *args, **kwargs):
        """Valida imutabilidade e identifica automaticamente contas pertencentes às lojas mockadas."""
        if self.pk:
            original = ContaMarketplace.objects.filter(pk=self.pk).only('loja_id', 'canal').first()
            if original:
                if original.loja_id != self.loja_id:
                    raise ValidationError({'loja': "A loja (tenant) vinculada é imutável após a conexão."})
                if original.canal != self.canal:
                    raise ValidationError({'canal': "O canal de marketplace é imutável após a conexão."})

        # Atribui automaticamente is_mock=True se a loja pertencer ao grupo padrão de lojas mock do ambiente
        if self.loja and getattr(self.loja, 'slug', None) in ['techzone-mock', 'comfort-mock', 'passofirme-mock']:
            self.is_mock = True
        # Executa o salvamento padrão do modelo
        super().save(*args, **kwargs)

    # Propriedade de getter retrocompatível para o seller_id
    @property
    def seller_id_remoto(self):
        return self.seller_id_externo

    # Propriedade de setter retrocompatível para o seller_id
    @seller_id_remoto.setter
    def seller_id_remoto(self, value):
        self.seller_id_externo = value

    # Propriedade utilitária que avalia se a conta já possui um access token cadastrado
    @property
    def has_credentials(self) -> bool:
        """Verifica se a conta possui Access Token configurado."""
        return bool(self.access_token)

    # Método que instancia o conector correspondente ao canal desta conta utilizando o padrão Factory
    def get_connector(self):
        """
        O QUE FAZ: Instancia e retorna o conector adequado para a conta de marketplace (Strategy / Adapter Pattern).
        POR QUE FAZ: Ponto único de despacho desacoplado do conector específico de canal (Mercado Livre, Shopee, etc.).
        """
        from .connectors.factory import get_connector_for_conta
        return get_connector_for_conta(self)


# Alias de modelo conforme especificação
# Cria aliases para retrocompatibilidade com nomenclatura legada
ConfiguracaoCanal = ContaMarketplace
MarketplaceConta = ContaMarketplace


# Modelo para persistência de telemetria técnica de comunicação com as APIs externas
class LogSincronizacao(models.Model):
    # Início do bloco de docstring detalhando o objetivo técnico e conformidade com RF-05 e RN-04
    """
    O QUE FAZ: Registro detalhado de telemetria, chamadas de API e respostas de comunicação com marketplaces externos.
    POR QUE FAZ: Diagnóstico de integrações, auditoria técnica e rastreabilidade de falhas (RF-05 / RN-04).
    PERMISSÕES RBAC: DEV e ADMIN (leitura); gravação automática pelo sistema.
    MULTI-TENANCY: FK obrigatória para Loja com isolamento horizontal por tenant.
    """
    # Fim da docstring explicativa de LogSincronizacao

    # Loja proprietária da operação de sincronização para segregação multi-tenant
    loja = models.ForeignKey(
        Loja, on_delete=models.CASCADE, related_name='logs_sincronizacao', verbose_name="Loja (Tenant)"
    )

    # Conta de marketplace utilizada na requisição externa
    conta_marketplace = models.ForeignKey(
        ContaMarketplace, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs', verbose_name="Conta de Origem"
    )

    # Canal parceiro de destino da mensagem
    canal = models.CharField(
        max_length=30, choices=CanalMarketplaceEnum.choices, default=CanalMarketplaceEnum.MERCADOLIVRE,
        verbose_name="Canal de Marketplace"
    )

    # Categoria de operação executada (preço, estoque, anúncio, token)
    evento = models.CharField(
        max_length=50, choices=EventoAuditoriaEnum.choices, verbose_name="Tipo de Operação / Evento"
    )

    # Identificador do anúncio ou recurso manipulado na API remota
    item_id_externo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="ID Externo no Marketplace"
    )

    # Conteúdo estruturado enviado na requisição em formato JSON
    payload_enviado = models.JSONField(
        default=dict, blank=True, verbose_name="Payload Enviado (JSON)"
    )

    # Corpo retornado pela API externa persistido em JSON
    resposta_recebida = models.JSONField(
        default=dict, blank=True, verbose_name="Resposta Recebida da API (JSON)"
    )

    # Código de status HTTP devolvido pela plataforma parceira (ex: 200, 400, 429)
    status_http = models.IntegerField(
        null=True, blank=True, verbose_name="Status HTTP"
    )

    # Booleano que simplifica a avaliação do sucesso da requisição
    sucesso = models.BooleanField(
        default=False, verbose_name="Operação Bem-Sucedida"
    )

    # Texto com a mensagem detalhada em caso de exceção de rede ou erro reportado pela API
    mensagem_erro = models.TextField(
        blank=True, null=True, verbose_name="Mensagem de Erro / Diagnóstico"
    )

    # Latência em milissegundos decorrida entre o disparo e a resposta
    tempo_resposta_ms = models.IntegerField(
        null=True, blank=True, verbose_name="Tempo de Resposta (ms)"
    )

    # Data e hora exatas em que o registro de log foi inserido
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Disparo"
    )

    # Metadados com ordenação cronológica decrescente
    class Meta:
        verbose_name = "Log de Sincronização"
        verbose_name_plural = "Logs de Sincronização"
        ordering = ['-criado_em']

    # Representação textual legível contendo canal, evento, resultado e data/hora
    def __str__(self):
        status_txt = "Sucesso" if self.sucesso else "Falha"
        return f"[{self.get_canal_display()}] {self.get_evento_display()} ({status_txt}, HTTP {self.status_http}) em {self.criado_em.strftime('%d/%m/%Y %H:%M:%S')}"


# Modelo responsável por auditar alterações cadastrais críticas e eventos do sistema
class LogAuditoria(models.Model):
    # Início do bloco de docstring documentando a conformidade com a rastreabilidade e governança
    """
    O QUE FAZ: Registro de auditoria de mutações críticas (RBAC, tenants, alterações manuais de catálogo e estoque).
    POR QUE FAZ: Rastreabilidade e conformidade com RN-04 (Fonte única da verdade e auditoria).
    PERMISSÕES RBAC: DEV (global); ADMIN e SUPERVISOR (leitura da loja); gravação automática pelo sistema.
    MULTI-TENANCY: FK para Loja com isolamento por inquilino.
    """
    # Fim da docstring explicativa de LogAuditoria

    # Loja à qual o evento pertence para garantir segregação multi-tenant
    loja = models.ForeignKey(
        Loja, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_auditoria', verbose_name="Loja (Tenant)"
    )

    # Usuário que executou ou disparou a ação (nulo para processos automáticos do sistema)
    autor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_realizados', verbose_name="Autor da Ação"
    )

    # Usuário que teve privilégios ou perfil alterado, se aplicável
    usuario_afetado = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_recebidos', verbose_name="Usuário Afetado"
    )

    # Tipo do evento auditado mapeado a partir de EventoAuditoriaEnum
    evento = models.CharField(
        max_length=50, choices=EventoAuditoriaEnum.choices, verbose_name="Evento"
    )

    # Descrição contextual com os detalhes das mutações ocorridas
    detalhes = models.TextField(
        verbose_name="Detalhes da Ação / Histórico de Alterações"
    )

    # Endereço IP do operador no momento da operação
    ip_origem = models.CharField(
        max_length=45, blank=True, null=True, verbose_name="IP de Origem"
    )

    # Data e hora do acontecimento
    criado_em = models.DateTimeField(
        auto_now_add=True, verbose_name="Data / Hora do Evento"
    )

    # Configuração de nomes e ordenação decrescente por data
    class Meta:
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"
        ordering = ['-criado_em']

    # Representação textual amigável identificando evento, autor e timestamp
    def __str__(self):
        autor_str = self.autor.username if self.autor else "Sistema"
        return f"[{self.get_evento_display()}] por {autor_str} em {self.criado_em.strftime('%d/%m/%Y %H:%M')}"


# Modelo encarregado de registrar o ciclo de vida dos webhooks recebidos e assegurar idempotência
class WebhookEventLog(models.Model):
    # Início do bloco de docstring que detalha o tratamento contra duplicidades de baixa de estoque
    """
    O QUE FAZ: Registro de eventos de Webhook com controle estrito de idempotência e auditoria de ciclo de vida.
    POR QUE FAZ: Impede deduplicações de baixa de estoque caso o marketplace reenvie a mesma notificação (retentativas de rede, atualizações intermediárias de pedidos).
    PERMISSÕES RBAC: DEV e ADMIN (consulta); gravação automatizada pelo webhook.
    """
    # Fim da documentação de WebhookEventLog

    # Nome do marketplace que emitiu o evento
    marketplace = models.CharField(
        max_length=50, default="mercadolivre", verbose_name="Marketplace de Origem"
    )

    # Assunto/tópico do evento recebido (ex: orders_v2, items, shipments)
    topic = models.CharField(
        max_length=50, verbose_name="Tópico da Notificação (ex: orders_v2, items)"
    )

    # URI ou caminho do recurso notificado na API do canal, indexado para deduplicação rápida
    resource = models.CharField(
        max_length=255, db_index=True, verbose_name="Recurso Notificado (ex: /orders/2000001234567890)"
    )

    # Identificador do vendedor/usuário associado no canal
    user_id = models.CharField(
        max_length=50, verbose_name="ID do Usuário / Vendedor no Canal"
    )

    # Cópia integral do JSON bruto recebido no webhook
    payload_raw = models.JSONField(
        default=dict, verbose_name="Payload Bruto da Notificação"
    )

    # Estado de processamento da notificação segundo WebhookStatusEnum, indexado para consultas
    status = models.CharField(
        max_length=20,
        choices=WebhookStatusEnum.choices,
        default=WebhookStatusEnum.RECEBIDO,
        db_index=True,
        verbose_name="Status de Processamento"
    )

    # Detalhamento de exceções caso o processamento falhe
    error_log = models.TextField(
        null=True, blank=True, verbose_name="Log de Erro / Justificativa"
    )

    # Carimbo temporal de chegada da notificação no endpoint
    received_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Recebido em"
    )

    # Carimbo temporal em que o worker assíncrono concluiu o processamento
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Processado em"
    )

    # Metadados com índices compostos para otimização de consultas de idempotência
    class Meta:
        verbose_name = "Log de Evento de Webhook"
        verbose_name_plural = "Logs de Eventos de Webhooks"
        ordering = ['-received_at']
        indexes = [
            # Índice composto para checar rapidamente se um recurso de determinado marketplace já foi processado
            models.Index(fields=['marketplace', 'resource', 'status'], name='idx_wh_mkt_res_status'),
            # Índice composto para consultas por URI do recurso e status
            models.Index(fields=['resource', 'status'], name='idx_wh_res_status'),
            # Índice para expurgo e ordenação por data de recebimento
            models.Index(fields=['received_at'], name='idx_wh_received_at'),
        ]

    # Representação textual informando marketplace, tópico, recurso e status
    def __str__(self):
        return f"[{self.marketplace}] {self.topic} {self.resource} ({self.get_status_display()}) em {self.received_at.strftime('%d/%m/%Y %H:%M:%S')}"