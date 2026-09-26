# Os códigos foram gerados com auxilio de I.A.

# Importa o tipo Decimal para tratamento financeiro e monetário preciso sem erros de arredondamento
from decimal import Decimal

# Importa tipagens estáticas da biblioteca typing para assinaturas formais de métodos
from typing import Dict, Any, Tuple, Optional

# Importa o gerenciador de transações atômicas e a exceção de integridade única do Django ORM
from django.db import transaction, IntegrityError

# Importa o modelo Loja para contextualização e isolamento estrito de tenant
from apps.tenancy.models import Loja

# Importa os modelos de Conta de integração e Log de Auditoria para rastreabilidade de eventos
from apps.marketplaces.models import ContaMarketplace, LogAuditoria

# Importa as enumerações de canais de venda parceiros e tipos de eventos auditáveis
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum

# Importa a fábrica (Factory) responsável por instanciar o conector HTTP do respectivo canal
from apps.marketplaces.connectors.factory import get_connector_for_conta

# Importa funções auxiliares de conversão segura para Decimal e Inteiro prevenindo falhas por dados nulos ou inválidos
from apps.marketplaces.utils import safe_decimal, safe_int

# Importa as entidades de catálogo: Produto (estoque físico) e AnuncioMarketplace (anúncio legado)
from apps.catalogo.models import Produto, AnuncioMarketplace

# Importa os modelos de persistência de pedidos e seus itens vendidos
from .models import PedidoVenda, ItemPedidoVenda

# Importa o enum com as constantes de status de pedidos no Hub
from .enums import StatusPedidoEnum


# Declaração da classe do serviço que orquestra a ingestão de pedidos, dedução atômica de estoque e broadcast multicanal
class ProcessamentoPedidoService:
    # Início do bloco de docstring estrutural documentando os pilares de consistência ACID, RBAC e isolamento multi-tenant
    """
    O QUE FAZ: Serviço central de processamento atômico de pedidos de venda recebidos via Webhook ou conciliação (RF-06 / RN-05).
    POR QUE FAZ:
      1. Garante isolamento concorrente com lock pessimista (select_for_update) em transação atômica (ACID).
      2. Deduz estoque físico de forma segura, detectando e alertando sobre eventuais rupturas (saldo negativo).
      3. Propaga o novo saldo atualizado para todos os outros canais integrados (Broadcast Multicanal de Estoque).
    PERMISSÕES RBAC: Executado de forma automatizada por endpoints de webhooks e rotinas de conciliação.
    MULTI-TENANCY: Processa pedidos estritamente no escopo da Loja (Tenant) identificada no webhook.
    """
    # Fim do bloco descritivo da classe de serviço

    # Método de classe que processa o payload do pedido, grava o cabeçalho, os itens e debita o estoque
    @classmethod
    def processar_pedido_venda(
        cls,
        loja: Loja,
        canal: str,
        pedido_id_externo: str,
        dados_pedido: Dict[str, Any],
        conta: Optional[ContaMarketplace] = None
    ) -> Tuple[bool, str, Optional[PedidoVenda]]:
        # Início da docstring descritiva do método
        """
        O QUE FAZ: Cria ou atualiza o PedidoVenda, processa seus itens e debita o estoque com lock atômico.
        """
        # Fim da docstring explicativa

        # Validação defensiva: exige que a organização tenant (loja) seja explicitamente informada
        if not loja:
            return False, "Loja não informada para o processamento.", None

        # Validação defensiva: exige que o identificador externo do pedido seja fornecido
        if not pedido_id_externo:
            return False, "Identificador externo de pedido não informado.", None

        # Idempotência: verifica se o pedido já foi recebido e processado
        # Consulta prévia no banco para garantir que requisições duplicadas do webhook não reprocessam o estoque
        pedido_existente = PedidoVenda.objects.filter(
            loja=loja, canal_origem=canal, pedido_id_externo=pedido_id_externo
        ).first()

        # Caso o pedido já exista, retorna com sucesso indicando a existência prévia sem executar novas baixas
        if pedido_existente:
            return True, f"Pedido #{pedido_id_externo} já processado anteriormente.", pedido_existente

        # Extrai a lista de itens vendidos navegando por chaves alternativas comuns em APIs de e-commerce
        itens_payload = dados_pedido.get('items', dados_pedido.get('order_items', []))

        # Tenta resolver o montante financeiro total do pedido em diferentes atributos suportados
        total_val = dados_pedido.get('total_amount')
        if total_val is None:
            total_val = dados_pedido.get('valor_total')
        if total_val is None:
            total_val = dados_pedido.get('paid_amount')
        # Sanitiza e converte o valor total para Decimal seguro
        valor_total = safe_decimal(total_val, Decimal('0.00'))

        # Trata a seção de entrega/frete assegurando que seja um dicionário válido
        shipping_data = dados_pedido.get('shipping')
        if not isinstance(shipping_data, dict):
            shipping_data = {}

        # Tenta extrair o valor cobrado de frete a partir de múltiplos nós possíveis
        frete_val = dados_pedido.get('shipping_cost')
        if frete_val is None:
            frete_val = shipping_data.get('cost')
        if frete_val is None:
            frete_val = dados_pedido.get('valor_frete')
        # Converte o valor de frete em Decimal seguro
        valor_frete = safe_decimal(frete_val, Decimal('0.00'))

        # Trata o objeto contendo as informações cadastrais do comprador
        comprador = dados_pedido.get('buyer', {})
        if not isinstance(comprador, dict):
            comprador = {}

        # Constrói o nome completo do comprador recorrendo a fallbacks sucessivos
        comprador_nome = (
            f"{comprador.get('first_name', '')} {comprador.get('last_name', '')}".strip()
            or comprador.get('name')
            or comprador.get('nickname')
            or "Comprador Marketplace"
        )

        # Abre o bloco de transação atômica do banco de dados para garantir integridade ACID
        with transaction.atomic():
            # Bloco protegido para capturar eventuais colisões de concorrência com chave única duplicada
            try:
                # Instancia e persiste o registro consolidado do pedido de venda
                pedido = PedidoVenda.objects.create(
                    loja=loja,
                    conta_marketplace=conta,
                    canal_origem=canal,
                    pedido_id_externo=pedido_id_externo,
                    status_externo=dados_pedido.get('status', 'paid'),
                    status=StatusPedidoEnum.PAGO,
                    comprador_nome=comprador_nome,
                    valor_total=valor_total,
                    valor_frete=valor_frete,
                    payload_original=dados_pedido
                )
            # Trata concorrência no nível de banco de dados caso outro worker tenha gravado simultaneamente
            except IntegrityError:
                # Recupera o registro que acabou de ser persistido concorrentemente
                pedido_existente = PedidoVenda.objects.filter(
                    canal_origem=canal, pedido_id_externo=pedido_id_externo
                ).first()
                # Retorna idempotência positiva informando o processamento prévio
                return True, f"Pedido #{pedido_id_externo} já processado anteriormente.", pedido_existente

            # Flag acumuladora para registrar se houve pelo menos uma ocorrência de estoque negativo no pedido
            houve_ruptura_geral = False

            # Itera sobre cada item comercial vendido constante no payload
            for item_raw in itens_payload:
                # Ignora entradas malformadas que não sejam estruturas do tipo dicionário
                if not isinstance(item_raw, dict):
                    continue

                # Extrai o sub-dicionário 'item' se encapsulado ou mantém o próprio dicionário
                item_info = item_raw.get('item', item_raw)
                if not isinstance(item_info, dict):
                    item_info = item_raw

                # Obtém o identificador externo do anúncio/item vendido
                item_id_ext = str(item_info.get('id', item_raw.get('item_id', ''))).strip()

                # Obtém o título comercial do produto vendido
                titulo = item_info.get('title', item_raw.get('titulo', 'Item Vendido'))

                # Obtém e valida a quantidade vendida aplicando piso mínimo de 1 unidade
                quantidade = max(1, safe_int(item_raw.get('quantity'), default=1))

                # Extrai o valor unitário cobrado por item a partir de múltiplos atributos comuns
                unit_price_val = item_raw.get('unit_price')
                if unit_price_val is None:
                    unit_price_val = item_raw.get('full_unit_price')
                if unit_price_val is None:
                    unit_price_val = item_raw.get('preco_unitario')
                if unit_price_val is None:
                    unit_price_val = item_raw.get('price')
                # Converte o preço unitário em Decimal seguro
                unit_price = safe_decimal(unit_price_val, Decimal('0.00'))

                # 1. Busca prioritária pelo Anuncio moderno (apps.anuncios.models.Anuncio)
                # Importação tardia do modelo moderno de Anúncio unificado
                from apps.anuncios.models import Anuncio
                anuncio_v2 = None

                # Busca o anúncio filtrando rigorosamente pela conta de integração atual
                if conta:
                    anuncio_v2 = Anuncio.objects.filter(
                        conta=conta, item_id_externo=item_id_ext
                    ).prefetch_related('itens_composicao__produto').first()

                # Se não encontrado pela conta, busca pelos anúncios pertencentes à loja tenant
                if not anuncio_v2:
                    anuncio_v2 = Anuncio.objects.filter(
                        conta__loja=loja, item_id_externo=item_id_ext
                    ).prefetch_related('itens_composicao__produto').first()

                # Fallback adicional: busca pelo ID externo sem filtro de conta
                if not anuncio_v2:
                    anuncio_v2 = Anuncio.objects.filter(
                        item_id_externo=item_id_ext
                    ).prefetch_related('itens_composicao__produto').first()

                # 2. Localiza anúncio legado AnuncioMarketplace se existir
                # Consulta de retrocompatibilidade para anúncios legados
                anuncio_legado = AnuncioMarketplace.objects.filter(
                    conta_marketplace__loja=loja, item_id_externo=item_id_ext
                ).first()

                # Lista de componentes físicos para anúncios compostos (Kits/Combos)
                composicoes = []
                # Se o anúncio moderno foi localizado
                if anuncio_v2:
                    # Sobrescreve o título se estiver ausente ou for o valor de fallback
                    if not titulo or titulo == 'Item Vendido':
                        titulo = anuncio_v2.titulo
                    # Carrega as regras de composição ordenadas por ID do produto físico
                    composicoes = list(anuncio_v2.itens_composicao.select_related('produto').order_by('produto_id'))

                # Inicializa variáveis de controle de estoque para a linha do item
                produto = None
                estoque_ant = None
                estoque_pos = None
                teve_ruptura = False
                estoque_baixado = False

                # Resolve o nome legível do marketplace para descrições de auditoria
                try:
                    canal_label = CanalMarketplaceEnum(canal).label
                except (ValueError, TypeError):
                    canal_label = str(canal or 'Marketplace').title()

                # CENÁRIO 1: Anúncio possui composição vinculada (Kit, Combo ou Simples com regras)
                if composicoes:
                    # Composição heterogênea ou homogênea (Kit/Combo/Simples)
                    # Dedução ordenada por produto_id para prevenir deadlocks (ADR-008, ADR-009)
                    # Itera por cada componente físico que compõe a unidade vendida
                    for comp in composicoes:
                        # Aplica bloqueio pessimista exclusivo na linha do produto para concorrência segura
                        prod_locked = Produto.objects.select_for_update().get(pk=comp.produto_id)

                        # Vincula o primeiro produto da composição como referência principal do item
                        if produto is None:
                            produto = prod_locked

                        # Calcula o total de unidades físicas a deduzir (quantidade vendida vezes o multiplicador do kit)
                        qtd_deduzir = quantidade * comp.quantidade

                        # Registra o saldo físico anterior
                        saldo_ant = prod_locked.estoque

                        # Calcula o novo saldo físico resultante
                        saldo_pos = saldo_ant - qtd_deduzir

                        # Atualiza o saldo no objeto
                        prod_locked.estoque = saldo_pos

                        # Sinaliza para os hooks do modelo o motivo da alteração
                        prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'

                        # Persiste o saldo no banco de dados
                        prod_locked.save(update_fields=['estoque', 'atualizado_em'])

                        # Marca que a baixa de estoque foi efetivamente concretizada
                        estoque_baixado = True

                        # Guarda os saldos para preenchimento da linha do item de venda
                        if estoque_ant is None:
                            estoque_ant = saldo_ant
                            estoque_pos = saldo_pos

                        # Registro de Histórico de Estoque do Produto
                        # Grava o histórico detalhado na linha do tempo do produto
                        prod_locked.registrar_historico(
                            estoque_anterior=saldo_ant,
                            novo_estoque=saldo_pos,
                            motivo=f"Baixa por venda via {canal_label} - Pedido #{pedido_id_externo} ({comp.quantidade}x)"
                        )

                        # Alerta de Ruptura se o saldo ficar negativo
                        # Se o saldo resultante for negativo, caracteriza ruptura de inventário (RN-06)
                        if saldo_pos < 0:
                            teve_ruptura = True
                            houve_ruptura_geral = True

                            # Registra evento de auditoria técnica alertando a equipe operacional
                            LogAuditoria.objects.create(
                                loja=loja,
                                evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE,
                                detalhes=(
                                    f"ALERTA DE RUPTURA: Venda do pedido #{pedido_id_externo} no canal '{canal}' "
                                    f"deixou o componente SKU '{prod_locked.sku}' com saldo NEGATIVO ({saldo_pos} un.). "
                                    f"Estoque anterior: {saldo_ant} un. | Quantidade deduzida: {qtd_deduzir} un."
                                )
                            )

                        # Registra log de auditoria técnica da baixa de estoque realizada com êxito
                        LogAuditoria.objects.create(
                            loja=loja,
                            evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                            detalhes=(
                                f"Baixa automática de {qtd_deduzir} un. no componente SKU '{prod_locked.sku}' "
                                f"por venda #{pedido_id_externo} ({canal}). Saldo: {saldo_ant} -> {saldo_pos}."
                            )
                        )

                        # Propaga o novo saldo do produto físico para todas as demais plataformas conectadas
                        cls.propagar_estoque_multicanal(prod_locked, canal_origem=canal)

                    # Atualiza o estoque publicado no anúncio com a nova cota
                    # Recalcula a cota máxima de venda disponível no anúncio após a dedução dos componentes
                    anuncio_v2.estoque_publicado = anuncio_v2.calcular_cota_disponivel()
                    anuncio_v2.save(update_fields=['estoque_publicado', 'atualizado_em'])

                # CENÁRIO 2: Anúncio direto/legado sem tabela de composição
                else:
                    # Anúncio sem composição direta ou busca por SKU direto / legado
                    # Tenta associar o produto através do SKU vendedor do anúncio moderno
                    if anuncio_v2 and anuncio_v2.sku_vendedor:
                        produto = Produto.objects.filter(loja=loja, sku=anuncio_v2.sku_vendedor).first()
                    # Tenta associar através do anúncio legado
                    elif anuncio_legado:
                        produto = anuncio_legado.produto
                    # Tenta resolver via SKU de vendedor enviado no payload do marketplace
                    else:
                        sku_seller = item_info.get('seller_sku', item_info.get('seller_custom_field', ''))
                        if sku_seller:
                            produto = Produto.objects.filter(loja=loja, sku=sku_seller).first()

                    # Se um produto físico do catálogo foi identificado
                    if produto:
                        # Executa bloqueio pessimista na linha do produto (select_for_update)
                        prod_locked = Produto.objects.select_for_update().get(pk=produto.pk)

                        # Coleta saldo anterior
                        estoque_ant = prod_locked.estoque
                        qtd_deduzir = quantidade
                        estoque_pos = estoque_ant - qtd_deduzir

                        # Atualiza saldo no produto
                        prod_locked.estoque = estoque_pos
                        prod_locked._motivo_alteracao = 'VENDA_MARKETPLACE'
                        prod_locked.save(update_fields=['estoque', 'atualizado_em'])
                        estoque_baixado = True

                        # Grava registro na trilha de histórico de estoque
                        prod_locked.registrar_historico(
                            estoque_anterior=estoque_ant,
                            novo_estoque=estoque_pos,
                            motivo=f"Baixa por venda via {canal_label} - Pedido #{pedido_id_externo}"
                        )

                        # Se o saldo pós-baixa for negativo, sinaliza alerta de ruptura
                        if estoque_pos < 0:
                            teve_ruptura = True
                            houve_ruptura_geral = True

                            # Registra evento de auditoria para o estoque em ruptura
                            LogAuditoria.objects.create(
                                loja=loja,
                                evento=EventoAuditoriaEnum.ALERTA_RUPTURA_ESTOQUE,
                                detalhes=(
                                    f"ALERTA DE RUPTURA: Venda do pedido #{pedido_id_externo} no canal '{canal}' "
                                    f"deixou o produto SKU '{prod_locked.sku}' com saldo NEGATIVO ({estoque_pos} un.). "
                                    f"Estoque anterior: {estoque_ant} un. | Quantidade vendida: {qtd_deduzir} un."
                                )
                            )

                        # Registra log de auditoria técnica da baixa de estoque efetuada
                        LogAuditoria.objects.create(
                            loja=loja,
                            evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                            detalhes=(
                                f"Baixa automática de {qtd_deduzir} un. no SKU '{prod_locked.sku}' por venda #{pedido_id_externo} ({canal}). "
                                f"Saldo: {estoque_ant} -> {estoque_pos}."
                            )
                        )

                        # Propaga o saldo recalculado aos demais canais
                        cls.propagar_estoque_multicanal(prod_locked, canal_origem=canal)

                # Persiste a linha detalhada do item vendido associado ao pedido
                ItemPedidoVenda.objects.create(
                    pedido=pedido,
                    produto=produto,
                    anuncio_marketplace=anuncio_legado,
                    item_id_externo=item_id_ext,
                    titulo_anuncio=titulo,
                    quantidade=quantidade,
                    preco_unitario=unit_price,
                    status_integracao='vinculado' if produto else 'pendente_vinculo',
                    estoque_baixado=estoque_baixado,
                    estoque_anterior=estoque_ant,
                    estoque_posterior=estoque_pos,
                    ruptura_estoque=teve_ruptura
                )

            # Se houve ruptura de estoque em qualquer item, marca a flag correspondente no pedido
            if houve_ruptura_geral:
                pedido.teve_ruptura_estoque = True
                pedido.save(update_fields=['teve_ruptura_estoque', 'atualizado_em'])

        # Retorna tupla de sucesso com a instância persistida do pedido
        return True, f"Pedido #{pedido_id_externo} processado com sucesso!", pedido

    # Método de classe responsável por broadcast do saldo de estoque para outros marketplaces
    @classmethod
    def propagar_estoque_multicanal(cls, produto: Produto, canal_origem: Optional[str] = None):
        # Início da docstring descritiva do método de broadcast
        """
        O QUE FAZ: Envia o saldo atualizado do produto para todas as contas e canais vinculados aos anúncios do produto.
        POR QUE FAZ: Mantém a paridade de estoque em tempo real em todas as plataformas onde o lojista opera (Mercado Livre, Shopee, Magalu).
        """
        # Fim da docstring explicativa

        # Recupera todos os anúncios do catálogo vinculados ao produto e pré-carrega a conta de marketplace
        anuncios = produto.anuncios.select_related('conta_marketplace').all()

        # Itera disparando a sincronização de estoque para cada anúncio ativo em outras contas
        for anuncio in anuncios:
            conta = anuncio.conta_marketplace
            # Não reenvia para o mesmo canal se for a origem imediata do webhook (opcional)
            # Instancia o conector específico para a conta através da Factory
            connector = get_connector_for_conta(conta)
            try:
                # Dispara a chamada de rede para atualização remota de estoque no marketplace
                connector.atualizar_estoque(anuncio.item_id_externo, produto.estoque)
            # Captura exceções de rede ou recusa da API prevenindo interrupção do loop principal
            except Exception:
                pass
