# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .base import BaseMarketplaceConnector


class ShopeeConnector(BaseMarketplaceConnector):
    """
    O QUE FAZ: Conector stub didático para integração com o marketplace Shopee (OpenAPI v2).
    POR QUE FAZ: Implementa o contrato BaseMarketplaceConnector demonstrando a extensibilidade da arquitetura multicanal sem impactar os demais canais.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Parametrizado com a ContaMarketplace da Shopee da loja.
    """
    @property
    def canal_nome(self) -> str:
        return CanalMarketplaceEnum.SHOPEE

    def autenticar(self) -> Tuple[bool, str, Dict[str, Any]]:
        """Validação simulada de credenciais da Shopee com telemetria."""
        if not self.conta or not self.conta.access_token:
            return False, "Conta Shopee sem Access Token configurado.", {}

        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.SHOPEE,
            evento=EventoAuditoriaEnum.TESTE_CONEXAO,
            payload_enviado={},
            resposta_recebida={"status": "authenticated", "shop_id": self.conta.seller_id_externo or "SHOPEE_SHOP_1"},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=50,
        )
        return True, "Conexão ativa com a API Shopee OpenAPI v2!", {"status": "ok"}

    def atualizar_preco(
        self, item_id_externo: str, novo_preco: Decimal, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """Sincronização de preço na Shopee."""
        if not self.conta or not self.conta.access_token:
            return False, "Conta Shopee sem credenciais.", None

        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.SHOPEE,
            evento=EventoAuditoriaEnum.SYNC_PRECO,
            item_id_externo=item_id_externo,
            payload_enviado={"price": float(novo_preco), "item_id": item_id_externo},
            resposta_recebida={"status": "success", "updated_price": float(novo_preco)},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=45,
        )
        return True, f"Preço de R$ {novo_preco:.2f} sincronizado na Shopee!", log

    def atualizar_estoque(
        self, item_id_externo: str, novo_estoque: int, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """Sincronização de estoque na Shopee com clamping max(0, estoque)."""
        if not self.conta or not self.conta.access_token:
            return False, "Conta Shopee sem credenciais.", None

        quantidade = max(0, int(novo_estoque))
        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.SHOPEE,
            evento=EventoAuditoriaEnum.SYNC_ESTOQUE,
            item_id_externo=item_id_externo,
            payload_enviado={"stock": quantidade, "item_id": item_id_externo},
            resposta_recebida={"status": "success", "updated_stock": quantidade},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=40,
        )
        return True, f"Estoque sincronizado na Shopee: {quantidade} un.", log

    def publicar_anuncio(
        self, produto, conta: Optional[ContaMarketplace] = None, dados_extras: Optional[Dict[str, Any]] = None, usuario=None
    ) -> Tuple[bool, str, Dict[str, Any], Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Publicação simulada de anúncio na API Shopee OpenAPI v2 (Stub didático).
        """
        conta_alvo = conta or self.conta
        dados_extras = dados_extras or {}

        if hasattr(produto, 'nome'):
            nome = produto.nome
            sku = produto.sku
            preco = Decimal(str(dados_extras.get('preco') or produto.preco))
            estoque = max(0, int(produto.estoque))
            loja = produto.loja
        elif isinstance(produto, dict):
            nome = produto.get('title') or produto.get('nome') or 'Produto Shopee'
            sku = produto.get('sku') or 'SHP-TEMP'
            preco = Decimal(str(produto.get('price') or produto.get('preco') or 100.00))
            estoque = max(0, int(produto.get('available_quantity') or produto.get('estoque') or 0))
            loja = conta_alvo.loja if conta_alvo else None
        else:
            return False, "Produto inválido para publicação.", {}, None

        item_id_externo = f"SHP-{sku}"
        link_anuncio = f"https://shopee.com.br/product/{conta_alvo.seller_id_externo if conta_alvo else '123'}/{item_id_externo}"
        payload = {"item_name": nome, "price": float(preco), "stock": estoque, "sku": sku}
        res_json = {"item_id": item_id_externo, "status": "success", "url": link_anuncio}

        log = LogSincronizacao.objects.create(
            loja=loja,
            conta_marketplace=conta_alvo,
            canal=CanalMarketplaceEnum.SHOPEE,
            evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
            item_id_externo=item_id_externo,
            payload_enviado=payload,
            resposta_recebida=res_json,
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=50,
        )

        dados_retorno = {
            "item_id_externo": item_id_externo,
            "link_anuncio": link_anuncio,
            "preco_sincronizado": preco,
            "status_anuncio": "ativo",
            "raw_response": res_json,
        }
        return True, f"Anúncio publicado na Shopee! (ID: {item_id_externo})", dados_retorno, log

    def buscar_pedidos(
        self, data_inicio=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        return True, "0 pedidos retornados (Stub Shopee).", []
