# Os códigos foram gerados com auxilio de I.A.
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

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


class SincronizacaoAnuncioService:
    """
    O QUE FAZ: Camada de orquestração para recálculo e sincronização de cotas e preços.
    POR QUE FAZ: Prepara os métodos core que serão integrados nas Fases 2, 3 e 4 (Baixas e Webhook).
    """

    @staticmethod
    def recalcular_cota(anuncio_id: int) -> int:
        """Calcula a cota máxima disponível a partir dos produtos vinculados na composição."""
        anuncio = Anuncio.objects.get(pk=anuncio_id)
        return anuncio.calcular_cota_disponivel()
