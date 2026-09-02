# Os códigos foram gerados com auxilio de I.A.
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .base import BaseMarketplaceConnector


class AmazonConnector(BaseMarketplaceConnector):
    """
    O QUE FAZ: Conector stub didático para integração com a Amazon Selling Partner API (SP-API).
    POR QUE FAZ: Extensibilidade para suporte à Amazon com autenticação LWA / IAM.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Parametrizado com a ContaMarketplace da Amazon da loja.
    """
    @property
    def canal_nome(self) -> str:
        return CanalMarketplaceEnum.AMAZON

    def autenticar(self) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.conta or not self.conta.access_token:
            return False, "Conta Amazon sem LWA Access Token configurado.", {}

        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.AMAZON,
            evento=EventoAuditoriaEnum.TESTE_CONEXAO,
            payload_enviado={},
            resposta_recebida={"status": "authenticated", "seller_id": self.conta.seller_id_externo or "AMAZON_SELLER_1"},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=75,
        )
        return True, "Conexão ativa com Amazon SP-API!", {"status": "ok"}

    def atualizar_preco(
        self, item_id_externo: str, novo_preco: Decimal, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        if not self.conta or not self.conta.access_token:
            return False, "Conta Amazon sem credenciais.", None

        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.AMAZON,
            evento=EventoAuditoriaEnum.SYNC_PRECO,
            item_id_externo=item_id_externo,
            payload_enviado={"price": float(novo_preco), "asin_ou_sku": item_id_externo},
            resposta_recebida={"status": "ACCEPTED", "feed_submission_id": "AMZ_FEED_123"},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=65,
        )
        return True, f"Feed de preço R$ {novo_preco:.2f} submetido à Amazon SP-API!", log

    def atualizar_estoque(
        self, item_id_externo: str, novo_estoque: int, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        if not self.conta or not self.conta.access_token:
            return False, "Conta Amazon sem credenciais.", None

        quantidade = max(0, int(novo_estoque))
        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.AMAZON,
            evento=EventoAuditoriaEnum.SYNC_ESTOQUE,
            item_id_externo=item_id_externo,
            payload_enviado={"quantity": quantidade, "asin_ou_sku": item_id_externo},
            resposta_recebida={"status": "ACCEPTED", "feed_submission_id": "AMZ_FEED_456"},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=60,
        )
        return True, f"Feed de estoque {quantidade} un. submetido à Amazon SP-API!", log

    def publicar_anuncio(
        self, produto, conta: Optional[ContaMarketplace] = None, dados_extras: Optional[Dict[str, Any]] = None, usuario=None
    ) -> Tuple[bool, str, Dict[str, Any], Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Publicação simulada de anúncio na Amazon SP-API (Stub didático).
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
            nome = produto.get('title') or produto.get('nome') or 'Produto Amazon'
            sku = produto.get('sku') or 'AMZ-TEMP'
            preco = Decimal(str(produto.get('price') or produto.get('preco') or 100.00))
            estoque = max(0, int(produto.get('available_quantity') or produto.get('estoque') or 0))
            loja = conta_alvo.loja if conta_alvo else None
        else:
            return False, "Produto inválido para publicação.", {}, None

        item_id_externo = f"B00{sku}"
        link_anuncio = f"https://www.amazon.com.br/dp/{item_id_externo}"
        payload = {"title": nome, "price": float(preco), "quantity": estoque, "sku": sku}
        res_json = {"asin": item_id_externo, "status": "active", "url": link_anuncio}

        log = LogSincronizacao.objects.create(
            loja=loja,
            conta_marketplace=conta_alvo,
            canal=CanalMarketplaceEnum.AMAZON,
            evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
            item_id_externo=item_id_externo,
            payload_enviado=payload,
            resposta_recebida=res_json,
            status_http=201,
            sucesso=True,
            tempo_resposta_ms=65,
        )

        dados_retorno = {
            "item_id_externo": item_id_externo,
            "link_anuncio": link_anuncio,
            "preco_sincronizado": preco,
            "status_anuncio": "ativo",
            "raw_response": res_json,
        }
        return True, f"Listing publicado na Amazon! (ASIN: {item_id_externo})", dados_retorno, log

    def buscar_pedidos(
        self, data_inicio=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        return True, "0 pedidos retornados (Stub Amazon).", []
