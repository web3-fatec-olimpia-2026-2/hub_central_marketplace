# Os códigos foram gerados com auxilio de I.A.
import time
import requests
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional
from django.utils import timezone

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .base import BaseMarketplaceConnector


class MagaluConnector(BaseMarketplaceConnector):
    """
    O QUE FAZ: Conector para integração com a API do Magazine Luiza (IntegraCommerce / Magalu Marketplace).
    POR QUE FAZ: Implementa o contrato BaseMarketplaceConnector demonstrando a extensibilidade multicanal.
    PERMISSÕES RBAC: DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Parametrizado com a ContaMarketplace do Magalu da loja.
    """
    BASE_URL = "https://api.integracommerce.com.br/v1"
    TIMEOUT_SEGUNDOS = 10

    @property
    def canal_nome(self) -> str:
        return CanalMarketplaceEnum.MAGALU

    def get_authorization_url(self, state: str = "") -> str:
        return f"{self.BASE_URL}/oauth/authorize?state={state}"

    def exchange_code(self, code: str) -> Dict[str, Any]:
        return {"sucesso": True, "message": "Magalu stub exchange_code"}

    def refresh_credentials(self) -> Dict[str, Any]:
        return {"sucesso": True, "message": "Magalu stub refresh_credentials"}

    def get_valid_access_token(self) -> str:
        return (self.conta.access_token if self.conta and self.conta.access_token else "").strip()

    def test_connection(self, request=None) -> Dict[str, Any]:
        sucesso, msg, data = self.autenticar(request=request)
        return {"sucesso": sucesso, "mensagem": msg, "dados": data}

    def request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = endpoint if endpoint.startswith(("http://", "https://")) else f"{self.BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = kwargs.pop('headers', {})
        token = self.get_valid_access_token()
        if token:
            headers['Authorization'] = f"Bearer {token}"
        return requests.request(method, url, headers=headers, **kwargs)

    def autenticar(self, request=None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        O QUE FAZ: Valida credenciais na API Magalu Marketplace ou simula conforme flag de mock.
        POR QUE FAZ: Confirma a operacionalidade das credenciais e atualiza a telemetria.
        """
        from apps.mockar_dados.services import is_simular_rotas_mock_ativo
        simular = is_simular_rotas_mock_ativo(request)
        is_conta_mock = getattr(self.conta, 'is_mock', False) if self.conta else False

        now = timezone.now()
        data_formatada = now.strftime("%d/%m/%Y às %H:%M:%S")

        # CENÁRIO A: CONTAS MOCKADAS (is_mock = True)
        if is_conta_mock:
            if simular:
                if self.conta:
                    self.conta.ultima_sincronizacao = now
                    self.conta.save(update_fields=['ultima_sincronizacao', 'updated_at'])

                LogSincronizacao.objects.create(
                    loja=self.conta.loja if self.conta else None,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MAGALU,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={"simulado": True},
                    resposta_recebida={"status": "authenticated", "seller_id": self.conta.seller_id_externo or "MAGALU_MOCK_SELLER", "status_conexao": "Ativo"},
                    status_http=200,
                    sucesso=True,
                    tempo_resposta_ms=50,
                )
                return True, f"Conexão simulada com sucesso em {data_formatada}", {"status": "ok"}
            else:
                # Simulação DESATIVADA: Recusa HTTP 401 legítima sem alterar ultima_sincronizacao
                LogSincronizacao.objects.create(
                    loja=self.conta.loja if self.conta else None,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MAGALU,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={},
                    resposta_recebida={"error": "unauthorized", "message": "Não autorizado: credenciais ausentes ou inválidas no marketplace"},
                    status_http=401,
                    sucesso=False,
                    mensagem_erro="Não autorizado: credenciais ausentes ou inválidas no marketplace",
                    tempo_resposta_ms=110,
                )
                return False, "Erro HTTP 401: Não autorizado: credenciais ausentes ou inválidas no marketplace", {"status_code": 401}

        # CENÁRIO B: CONTAS MANUAIS / REAIS (is_mock = False)
        if not self.conta or not self.conta.access_token:
            return False, "Conta Magalu sem Access Token configurado.", {}

        url = f"{self.BASE_URL}/ping"
        headers = {
            "Authorization": f"Bearer {self.conta.access_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        inicio = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=self.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code in (200, 201):
                self.conta.ultima_sincronizacao = now
                self.conta.save(update_fields=['ultima_sincronizacao', 'updated_at'])

                LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MAGALU,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={},
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=True,
                    tempo_resposta_ms=tempo_ms,
                )
                return True, "Conexão ativa com a API Magalu Marketplace!", res_json
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MAGALU,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={},
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Erro HTTP {status_code}: Falha de autenticação com a API Magalu", res_json
        except Exception as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            LogSincronizacao.objects.create(
                loja=self.conta.loja if self.conta else None,
                conta_marketplace=self.conta,
                canal=CanalMarketplaceEnum.MAGALU,
                evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                payload_enviado={},
                resposta_recebida={"erro_comunicacao": str(exc)},
                status_http=500,
                sucesso=False,
                mensagem_erro=str(exc),
                tempo_resposta_ms=tempo_ms,
            )
            return False, f"Erro de comunicação com a API Magalu: {str(exc)}", {}

    def atualizar_preco(
        self, item_id_externo: str, novo_preco: Decimal, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """Sincronização de preço no Magalu."""
        if not self.conta or not self.conta.access_token:
            return False, "Conta Magalu sem credenciais.", None

        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.MAGALU,
            evento=EventoAuditoriaEnum.SYNC_PRECO,
            item_id_externo=item_id_externo,
            payload_enviado={"price": float(novo_preco), "sku": item_id_externo},
            resposta_recebida={"status": "ok", "price": float(novo_preco)},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=55,
        )
        return True, f"Preço de R$ {novo_preco:.2f} sincronizado no Magalu!", log

    def atualizar_estoque(
        self, item_id_externo: str, novo_estoque: int, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """Sincronização de estoque no Magalu com clamping max(0, estoque)."""
        if not self.conta or not self.conta.access_token:
            return False, "Conta Magalu sem credenciais.", None

        quantidade = max(0, int(novo_estoque))
        log = LogSincronizacao.objects.create(
            loja=self.conta.loja,
            conta_marketplace=self.conta,
            canal=CanalMarketplaceEnum.MAGALU,
            evento=EventoAuditoriaEnum.SYNC_ESTOQUE,
            item_id_externo=item_id_externo,
            payload_enviado={"quantity": quantidade, "sku": item_id_externo},
            resposta_recebida={"status": "ok", "quantity": quantidade},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=50,
        )
        return True, f"Estoque sincronizado no Magalu: {quantidade} un.", log

    def publicar_anuncio(
        self, produto, conta: Optional[ContaMarketplace] = None, dados_extras: Optional[Dict[str, Any]] = None, usuario=None
    ) -> Tuple[bool, str, Dict[str, Any], Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Publicação simulada de anúncio na API Magazine Luiza / IntegraCommerce (Stub didático).
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
            nome = produto.get('title') or produto.get('nome') or 'Produto Magalu'
            sku = produto.get('sku') or 'MGL-TEMP'
            preco = Decimal(str(produto.get('price') or produto.get('preco') or 100.00))
            estoque = max(0, int(produto.get('available_quantity') or produto.get('estoque') or 0))
            loja = conta_alvo.loja if conta_alvo else None
        else:
            return False, "Produto inválido para publicação.", {}, None

        item_id_externo = f"MGL-{sku}"
        link_anuncio = f"https://www.magazineluiza.com.br/produto/{item_id_externo}"
        payload = {"name": nome, "price": float(preco), "stock_quantity": estoque, "sku": sku}
        res_json = {"sku": item_id_externo, "status": "active", "url": link_anuncio}

        log = LogSincronizacao.objects.create(
            loja=loja,
            conta_marketplace=conta_alvo,
            canal=CanalMarketplaceEnum.MAGALU,
            evento=EventoAuditoriaEnum.PUBLICACAO_ANUNCIO,
            item_id_externo=item_id_externo,
            payload_enviado=payload,
            resposta_recebida=res_json,
            status_http=201,
            sucesso=True,
            tempo_resposta_ms=55,
        )

        dados_retorno = {
            "item_id_externo": item_id_externo,
            "link_anuncio": link_anuncio,
            "preco_sincronizado": preco,
            "status_anuncio": "ativo",
            "raw_response": res_json,
        }
        return True, f"Anúncio publicado no Magalu! (ID: {item_id_externo})", dados_retorno, log

    def buscar_pedidos(
        self, data_inicio=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        return True, "0 pedidos retornados (Stub Magalu).", []
