import logging
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple, List

from django.db import transaction
from django.utils import timezone

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from apps.catalogo.models import Produto
from apps.anuncios.models import Anuncio, AnuncioComposicao

logger = logging.getLogger(__name__)


class AnuncioImportacaoService:
    """
    O QUE FAZ: Orquestra o fluxo de importação e conciliação de anúncios externos no Hub.
    POR QUE FAZ: Conecta o conector de cada marketplace à base relacional, garantindo idempotência
                 (update_or_create) e auto-vinculação com produtos físicos por correspondência de SKU.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Vincula todos os anúncios exclusivamente à ContaMarketplace e Loja do tenant.
    """

    @classmethod
    def importar_anuncios_da_conta(
        cls,
        conta: ContaMarketplace,
        associar_produtos_por_sku: bool = True,
        usuario=None,
        search_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executa a importação completa dos anúncios da conta e persiste na tabela Anuncio.
        """
        if not conta or not conta.pk:
            return {"sucesso": False, "mensagem": "Conta de marketplace inválida.", "total": 0}

        connector = conta.get_connector()
        if not hasattr(connector, 'importar_anuncios'):
            return {
                "sucesso": False,
                "mensagem": f"O conector para {conta.get_canal_display()} não implementa importação de anúncios.",
                "total": 0,
            }

        resultado_conector = connector.importar_anuncios(search_type=search_type)
        if not resultado_conector.get('sucesso'):
            return resultado_conector

        itens_retornados = resultado_conector.get('itens', [])
        criados = 0
        atualizados = 0
        vinculados = 0

        with transaction.atomic():
            for item in itens_retornados:
                item_id = item.get('item_id_externo')
                if not item_id:
                    continue

                sku_vendedor = item.get('sku_vendedor')
                if sku_vendedor:
                    sku_vendedor = sku_vendedor.strip()

                defaults = {
                    'titulo': item.get('titulo', f"Anúncio {item_id}"),
                    'preco_venda': item.get('preco', Decimal('0.00')),
                    'estoque_publicado': max(0, int(item.get('quantidade_disponivel', 0))),
                    'status': item.get('status', 'active'),
                    'sku_vendedor': sku_vendedor,
                    'thumbnail': item.get('thumbnail'),
                    'permalink': item.get('permalink'),
                }

                anuncio, created = Anuncio.objects.update_or_create(
                    conta=conta,
                    item_id_externo=item_id,
                    defaults=defaults
                )

                if created:
                    criados += 1
                else:
                    atualizados += 1

                # Vínculo automático inicial 1:1 por SKU físico caso exista na mesma loja
                if associar_produtos_por_sku and sku_vendedor:
                    if not anuncio.itens_composicao.exists():
                        produto_fisico = Produto.objects.filter(
                            loja=conta.loja,
                            sku__iexact=sku_vendedor
                        ).first()
                        if produto_fisico:
                            AnuncioComposicao.objects.create(
                                anuncio=anuncio,
                                produto=produto_fisico,
                                quantidade=1
                            )
                            vinculados += 1

            # Log de auditoria
            LogAuditoria.objects.create(
                loja=conta.loja,
                autor=usuario,
                evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
                detalhes=(
                    f"Importação de anúncios do canal {conta.get_canal_display()} concluída. "
                    f"Total: {criados + atualizados} ({criados} novos, {atualizados} atualizados, "
                    f"{vinculados} auto-vinculados por SKU físico)."
                )
            )

        msg = (
            f"Importação de anúncios concluída com sucesso! "
            f"{criados + atualizados} anúncios processados ({criados} novos, {atualizados} atualizados"
        )
        if vinculados:
            msg += f", {vinculados} auto-vinculados a produtos físicos)."
        else:
            msg += ")."

        return {
            "sucesso": True,
            "mensagem": msg,
            "total": criados + atualizados,
            "total_importados": criados,
            "total_atualizados": atualizados,
            "total_vinculados": vinculados,
        }


class AnuncioSincronizacaoService:
    """
    O QUE FAZ: Orquestra a sincronização segura de estoque e preço entre os produtos físicos (catálogo)
                 e os anúncios dos marketplaces (Mercado Livre, etc.).
    POR QUE FAZ: Aplica cálculo de cotas para kits, idempotência para evitar chamadas de rede redundantes,
                 clamping defensivo e Circuit Breaker contra variações de preço anômalas ou zeramento em lote acidental.
    PERMISSÕES RBAC: DEV, ADMIN, SUPERVISOR; Sistema (disparado via Signals / Tarefas).
    MULTI-TENANCY: Todos os cálculos e sincronizações respeitam estritamente a Loja/Conta do anúncio.
    """

    # Limites de segurança do Circuit Breaker
    MAX_QUEDA_PRECO_PERCENTUAL = Decimal('0.50')   # 50% de queda máxima permitida sem override
    MAX_ALTA_PRECO_PERCENTUAL = Decimal('1.00')    # 100% de alta máxima permitida sem override
    LIMITE_ZERAMENTO_LOTE_ITENS = 5                # Mais de 5 itens zerando ao mesmo tempo
    LIMITE_ZERAMENTO_LOTE_PERCENTUAL = 0.50        # Mais de 50% dos itens ativos zerando ao mesmo tempo

    @classmethod
    def recalcular_cota(cls, anuncio_id: int) -> int:
        """Calcula a cota máxima disponível a partir dos produtos vinculados na composição."""
        anuncio = Anuncio.objects.get(pk=anuncio_id)
        return max(0, anuncio.calcular_cota_disponivel())

    @classmethod
    def validar_variacao_preco(cls, anuncio: Anuncio, novo_preco: Decimal, forcar: bool = False) -> Tuple[bool, str]:
        """
        O QUE FAZ: Valida se o novo preço não apresenta oscilação anômala que indique erro operacional.
        POR QUE FAZ: Circuit breaker para evitar prejuízos por precificação incorreta (queda > 50% ou alta > 100%).
        """
        novo_preco = Decimal(str(novo_preco))
        if novo_preco <= Decimal('0.00'):
            return False, "Preço de venda deve ser estritamente positivo (maior que zero)."

        if forcar:
            return True, "Variação de preço autorizada por override explícito."

        preco_atual = anuncio.preco_venda
        if not preco_atual or preco_atual <= Decimal('0.00'):
            return True, "Preço inicial aprovado."

        if novo_preco < preco_atual:
            queda = (preco_atual - novo_preco) / preco_atual
            if queda > cls.MAX_QUEDA_PRECO_PERCENTUAL:
                return False, (
                    f"Circuit Breaker acionado: Queda anômala de preço de {queda * 100:.1f}% "
                    f"(De R$ {preco_atual:.2f} para R$ {novo_preco:.2f}). "
                    f"Variação permitida sem confirmação explícita é de até 50%."
                )
        elif novo_preco > preco_atual:
            alta = (novo_preco - preco_atual) / preco_atual
            if alta > cls.MAX_ALTA_PRECO_PERCENTUAL:
                return False, (
                    f"Circuit Breaker acionado: Aumento anômalo de preço de {alta * 100:.1f}% "
                    f"(De R$ {preco_atual:.2f} para R$ {novo_preco:.2f}). "
                    f"Variação permitida sem confirmação explícita é de até 100%."
                )

        return True, "Preço aprovado pelo Circuit Breaker."

    @classmethod
    def validar_zeramento_em_lote(cls, total_itens_lote: int, total_zerando: int, forcar: bool = False) -> Tuple[bool, str]:
        """
        O QUE FAZ: Avalia se uma operação em lote resultará em zeramento simultâneo massivo de inventário.
        POR QUE FAZ: Previne paralisia acidental de vendas por inconsistências de rede ou integrações externas.
        """
        if forcar:
            return True, "Zeramento em lote autorizado por override explícito."

        if total_zerando > cls.LIMITE_ZERAMENTO_LOTE_ITENS or (
            total_itens_lote > 1 and (total_zerando / total_itens_lote) > cls.LIMITE_ZERAMENTO_LOTE_PERCENTUAL
        ):
            return False, (
                f"Circuit Breaker acionado: Tentativa de zeramento em massa de {total_zerando} anúncios "
                f"em um lote de {total_itens_lote} itens bloqueada para proteção de vendas."
            )

        return True, "Zeramento em lote aprovado."

    @classmethod
    def sincronizar_estoque_anuncio(
        cls,
        anuncio: Anuncio,
        usuario=None,
        forcar: bool = False
    ) -> Dict[str, Any]:
        """
        O QUE FAZ: Recalcula a cota física disponível e atualiza o saldo de estoque no marketplace.
        POR QUE FAZ: Garante que anúncios unitários e kits reflitam com exatidão o inventário real.
        """
        if not anuncio or not anuncio.pk:
            return {"sucesso": False, "mensagem": "Anúncio inválido para sincronização.", "estoque": 0}

        # 1. Recálculo da cota física disponível com clamping defensivo
        cota_calculada = max(0, anuncio.calcular_cota_disponivel())

        # 2. Otimização por idempotência (evita requisição externa redundante)
        if not forcar and anuncio.estoque_publicado == cota_calculada and anuncio.status == 'active':
            return {
                "sucesso": True,
                "mensagem": f"Estoque já sincronizado ({cota_calculada} un). Requisição ignorada por idempotência.",
                "estoque_sincronizado": cota_calculada,
                "ignorado_idempotencia": True,
            }

        # 3. Disparo via conector do marketplace
        connector = anuncio.conta.get_connector()
        sucesso, msg, log = connector.atualizar_estoque(anuncio.item_id_externo, cota_calculada, usuario=usuario)

        if sucesso:
            anuncio.estoque_publicado = cota_calculada
            anuncio.save(update_fields=['estoque_publicado', 'atualizado_em'])

        return {
            "sucesso": sucesso,
            "mensagem": msg,
            "estoque_sincronizado": cota_calculada,
            "log": log,
            "ignorado_idempotencia": False,
        }

    @classmethod
    def sincronizar_preco_anuncio(
        cls,
        anuncio: Anuncio,
        novo_preco: Decimal,
        usuario=None,
        forcar: bool = False
    ) -> Dict[str, Any]:
        """
        O QUE FAZ: Valida regras de segurança e sincroniza o preço de venda no marketplace externo.
        POR QUE FAZ: Previne precificação errônea via Circuit Breaker e propaga novos valores aprovados.
        """
        if not anuncio or not anuncio.pk:
            return {"sucesso": False, "mensagem": "Anúncio inválido para sincronização.", "preco": Decimal('0.00')}

        novo_preco = Decimal(str(novo_preco))

        # 1. Validação de segurança via Circuit Breaker
        ok_cb, msg_cb = cls.validar_variacao_preco(anuncio, novo_preco, forcar=forcar)
        if not ok_cb:
            LogAuditoria.objects.create(
                loja=anuncio.conta.loja,
                autor=usuario,
                evento=EventoAuditoriaEnum.SYNC_PRECO,
                detalhes=f"Bloqueio de Circuit Breaker no anúncio [{anuncio.item_id_externo}]: {msg_cb}"
            )
            return {
                "sucesso": False,
                "mensagem": msg_cb,
                "bloqueado_circuit_breaker": True,
                "preco_sincronizado": anuncio.preco_venda,
            }

        # 2. Otimização por idempotência
        if not forcar and anuncio.preco_venda == novo_preco:
            return {
                "sucesso": True,
                "mensagem": f"Preço já sincronizado (R$ {novo_preco:.2f}). Requisição ignorada por idempotência.",
                "preco_sincronizado": novo_preco,
                "ignorado_idempotencia": True,
            }

        # 3. Disparo via conector
        connector = anuncio.conta.get_connector()
        sucesso, msg, log = connector.atualizar_preco(anuncio.item_id_externo, novo_preco, usuario=usuario)

        if sucesso:
            anuncio.preco_venda = novo_preco
            anuncio.save(update_fields=['preco_venda', 'atualizado_em'])

        return {
            "sucesso": sucesso,
            "mensagem": msg,
            "preco_sincronizado": novo_preco,
            "log": log,
            "ignorado_idempotencia": False,
        }

    @classmethod
    def sincronizar_anuncios_do_produto(
        cls,
        produto: Produto,
        usuario=None,
        apenas_estoque: bool = False,
        forcar: bool = False
    ) -> Dict[str, Any]:
        """
        O QUE FAZ: Identifica todos os anúncios vinculados ao produto no catálogo (unitários e kits)
                     e dispara a sincronização segura correspondente.
        POR QUE FAZ: Acionado automaticamente por Django Signals após alteração de estoque ou preço no produto mestre.
        """
        anuncios = Anuncio.objects.filter(
            composicoes__produto=produto
        ).select_related('conta', 'conta__loja').distinct()

        resultados_estoque = []
        resultados_preco = []

        for anuncio in anuncios:
            # Sincroniza estoque recalculado para o anúncio
            res_est = cls.sincronizar_estoque_anuncio(anuncio, usuario=usuario, forcar=forcar)
            resultados_estoque.append({"anuncio_id": anuncio.pk, "item_id": anuncio.item_id_externo, "resultado": res_est})

            # Se não for apenas estoque e o anúncio for unitário (1:1 com o produto), propaga o preço atualizado
            if not apenas_estoque:
                itens = list(anuncio.itens_composicao.all())
                if len(itens) == 1 and itens[0].produto_id == produto.pk and itens[0].quantidade == 1:
                    res_prc = cls.sincronizar_preco_anuncio(anuncio, produto.preco, usuario=usuario, forcar=forcar)
                    resultados_preco.append({"anuncio_id": anuncio.pk, "item_id": anuncio.item_id_externo, "resultado": res_prc})

        return {
            "total_anuncios": anuncios.count(),
            "resultados_estoque": resultados_estoque,
            "resultados_preco": resultados_preco,
        }


# Alias de compatibilidade
SincronizacaoAnuncioService = AnuncioSincronizacaoService

