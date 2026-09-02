# Os códigos foram gerados com auxilio de I.A.
import time
import requests
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional
from django.db import transaction

from apps.marketplaces.models import ContaMarketplace, LogSincronizacao, LogAuditoria
from apps.marketplaces.enums import CanalMarketplaceEnum, EventoAuditoriaEnum
from .base import BaseMarketplaceConnector


class MercadoLivreConnector(BaseMarketplaceConnector):
    """
    O QUE FAZ: Conector de integração ativa com a API REST oficial do Mercado Livre (developers.mercadolivre.com.br).
    POR QUE FAZ: Executa operações de atualização de preços (RF-05 / PUT /items/{id}), sincronização de estoque com clamping (RN-05/06), renovação OAuth 2.0 e busca de pedidos.
    PERMISSÕES RBAC: Disparado por DEV, ADMIN e SUPERVISOR.
    MULTI-TENANCY: Utiliza as credenciais isoladas da ContaMarketplace associada à Loja do tenant.
    """
    BASE_URL = "https://api.mercadolibre.com"
    TIMEOUT_SEGUNDOS = 10

    @property
    def canal_nome(self) -> str:
        return CanalMarketplaceEnum.MERCADOLIVRE

    def _obter_headers(self) -> Dict[str, str]:
        """Gera o cabeçalho HTTP padrão com o Bearer Token da conta."""
        token = self.conta.access_token.strip() if (self.conta and self.conta.access_token) else ""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def renovar_token(self, usuario=None) -> Tuple[bool, str]:
        """
        O QUE FAZ: Renova o Access Token expirado utilizando o Refresh Token via POST /oauth/token.
        POR QUE FAZ: Garante tolerância a falhas e execução ininterrupta de sincronizações agendadas.
        PERMISSÕES RBAC: Operação interna / DEV / ADMIN.
        MULTI-TENANCY: Atualiza exclusivamente o registro da ContaMarketplace da loja.
        """
        if not self.conta or not self.conta.refresh_token:
            return False, "Conta não possui Refresh Token cadastrado para renovação."

        url = f"{self.BASE_URL}/oauth/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
        data = {
            "grant_type": "refresh_token",
            "client_id": (self.conta.client_id or "").strip(),
            "client_secret": (self.conta.client_secret or "").strip(),
            "refresh_token": self.conta.refresh_token.strip(),
        }

        inicio = time.time()
        try:
            response = requests.post(url, data=data, headers=headers, timeout=self.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code in (200, 201) and 'access_token' in res_json:
                with transaction.atomic():
                    self.conta.access_token = res_json['access_token']
                    self.conta.refresh_token = res_json.get('refresh_token', self.conta.refresh_token)
                    self.conta.save(update_fields=['access_token', 'refresh_token', 'updated_at'])

                    LogSincronizacao.objects.create(
                        loja=self.conta.loja,
                        conta_marketplace=self.conta,
                        canal=CanalMarketplaceEnum.MERCADOLIVRE,
                        evento=EventoAuditoriaEnum.REFRESH_TOKEN,
                        payload_enviado={"grant_type": "refresh_token", "client_id": self.conta.client_id},
                        resposta_recebida={"status": "Token renovado com sucesso", "expires_in": res_json.get('expires_in')},
                        status_http=status_code,
                        sucesso=True,
                        tempo_resposta_ms=tempo_ms,
                    )
                return True, "Token do Mercado Livre renovado com sucesso!"
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                LogSincronizacao.objects.create(
                    loja=self.conta.loja if self.conta else None,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.REFRESH_TOKEN,
                    payload_enviado={"grant_type": "refresh_token"},
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Falha na renovação: {msg_erro}"

        except Exception as exc:
            return False, f"Erro de comunicação ao renovar token: {str(exc)}"

    def autenticar(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        O QUE FAZ: Valida as credenciais da conta via GET /users/me na API do Mercado Livre.
        POR QUE FAZ: Confirma se o Access Token é válido e obtém o nickname e user_id do vendedor.
        """
        if not self.conta or not self.conta.access_token:
            return False, "Nenhum Access Token cadastrado para esta conta.", {}

        url = f"{self.BASE_URL}/users/me"
        inicio = time.time()
        try:
            response = requests.get(url, headers=self._obter_headers(), timeout=self.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            # Retry automático em caso de 401 Unauthorized
            if status_code == 401 and self.conta.refresh_token:
                ok_ref, _ = self.renovar_token()
                if ok_ref:
                    self.conta.refresh_from_db()
                    return self.autenticar()

            if status_code == 200:
                nickname = res_json.get('nickname', 'Vendedor')
                user_id = str(res_json.get('id', ''))
                # Salva o seller_id se não estiver preenchido
                if user_id and not self.conta.seller_id_externo:
                    self.conta.seller_id_externo = user_id
                    self.conta.save(update_fields=['seller_id_externo', 'updated_at'])

                LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO,
                    payload_enviado={},
                    resposta_recebida={"nickname": nickname, "id": user_id, "status": "Ativo"},
                    status_http=200,
                    sucesso=True,
                    tempo_resposta_ms=tempo_ms,
                )
                return True, f"Conexão ativa! Vendedor: {nickname} (ID: {user_id})", res_json
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                return False, f"Falha na validação de credenciais: {msg_erro}", res_json

        except Exception as exc:
            return False, f"Erro ao testar conexão: {str(exc)}", {}

    def atualizar_preco(
        self, item_id_externo: str, novo_preco: Decimal, usuario=None, tentar_refresh: bool = True
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Atualiza o preço do item no Mercado Livre (PUT /items/{id}).
        POR QUE FAZ: RF-08 / RF-05 — Propagação do novo preço para a plataforma externa.
        """
        if not self.conta or not self.conta.access_token:
            return False, "Conta sem Access Token configurado.", None

        if not item_id_externo:
            return False, "Identificador externo de anúncio (MLB...) não informado.", None

        url = f"{self.BASE_URL}/items/{item_id_externo.strip()}"
        payload = {"price": float(novo_preco)}

        inicio = time.time()
        try:
            response = requests.put(url, json=payload, headers=self._obter_headers(), timeout=self.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code == 401 and tentar_refresh and self.conta.refresh_token:
                ok_ref, _ = self.renovar_token(usuario=usuario)
                if ok_ref:
                    self.conta.refresh_from_db()
                    return self.atualizar_preco(item_id_externo, novo_preco, usuario=usuario, tentar_refresh=False)

            if status_code in (200, 201):
                log = LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.SYNC_PRECO,
                    item_id_externo=item_id_externo,
                    payload_enviado=payload,
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=True,
                    tempo_resposta_ms=tempo_ms,
                )
                return True, f"Preço de R$ {novo_preco:.2f} sincronizado no Mercado Livre!", log
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                log = LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.SYNC_PRECO,
                    item_id_externo=item_id_externo,
                    payload_enviado=payload,
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Mercado Livre rejeitou: {msg_erro}", log

        except requests.exceptions.Timeout:
            log = LogSincronizacao.objects.create(
                loja=self.conta.loja,
                conta_marketplace=self.conta,
                canal=CanalMarketplaceEnum.MERCADOLIVRE,
                evento=EventoAuditoriaEnum.SYNC_PRECO,
                item_id_externo=item_id_externo,
                payload_enviado=payload,
                resposta_recebida={'erro': 'Timeout'},
                status_http=408,
                sucesso=False,
                mensagem_erro="Tempo limite esgotado ao conectar ao Mercado Livre.",
            )
            return False, "Tempo limite esgotado.", log
        except Exception as exc:
            return False, f"Erro de comunicação: {str(exc)}", None

    def atualizar_estoque(
        self, item_id_externo: str, novo_estoque: int, usuario=None, tentar_refresh: bool = True
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        O QUE FAZ: Sincroniza o estoque no anúncio do Mercado Livre aplicando clamping (PUT /items/{id}).
        POR QUE FAZ: Garante que valores negativos nunca sejam enviados para a API externa (RN-05/06).
        """
        if not self.conta or not self.conta.access_token:
            return False, "Conta sem Access Token configurado.", None

        # Clamping mandatário (RN-06): nunca envia menor que 0
        quantidade_envio = max(0, int(novo_estoque))
        url = f"{self.BASE_URL}/items/{item_id_externo.strip()}"
        payload = {"available_quantity": quantidade_envio}

        inicio = time.time()
        try:
            response = requests.put(url, json=payload, headers=self._obter_headers(), timeout=self.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code == 401 and tentar_refresh and self.conta.refresh_token:
                ok_ref, _ = self.renovar_token(usuario=usuario)
                if ok_ref:
                    self.conta.refresh_from_db()
                    return self.atualizar_estoque(item_id_externo, novo_estoque, usuario=usuario, tentar_refresh=False)

            if status_code in (200, 201):
                log = LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.SYNC_ESTOQUE,
                    item_id_externo=item_id_externo,
                    payload_enviado=payload,
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=True,
                    tempo_resposta_ms=tempo_ms,
                )
                return True, f"Estoque sincronizado no Mercado Livre: {quantidade_envio} un.", log
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                log = LogSincronizacao.objects.create(
                    loja=self.conta.loja,
                    conta_marketplace=self.conta,
                    canal=CanalMarketplaceEnum.MERCADOLIVRE,
                    evento=EventoAuditoriaEnum.SYNC_ESTOQUE,
                    item_id_externo=item_id_externo,
                    payload_enviado=payload,
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Mercado Livre rejeitou sincronização de estoque: {msg_erro}", log

        except Exception as exc:
            return False, f"Erro de comunicação ao sincronizar estoque: {str(exc)}", None

    def publicar_anuncio(
        self, dados_anuncio: Dict[str, Any], usuario=None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        O QUE FAZ: Publica novo anúncio no Mercado Livre via POST /items (RF-04).
        """
        url = f"{self.BASE_URL}/items"
        try:
            response = requests.post(url, json=dados_anuncio, headers=self._obter_headers(), timeout=self.TIMEOUT_SEGUNDOS)
            res_json = response.json() if response.status_code in (200, 201) else {"error": response.text}
            if response.status_code in (200, 201):
                return True, "Anúncio publicado com sucesso no Mercado Livre!", res_json
            return False, f"Erro ao publicar anúncio: {response.text}", res_json
        except Exception as exc:
            return False, f"Falha de rede ao publicar: {str(exc)}", {}

    def buscar_pedidos(
        self, data_inicio=None
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        O QUE FAZ: Consulta pedidos recentes no Mercado Livre via GET /orders/search.
        """
        seller_id = self.conta.seller_id_externo if self.conta else ""
        url = f"{self.BASE_URL}/orders/search?seller={seller_id}&order.status=paid"
        try:
            response = requests.get(url, headers=self._obter_headers(), timeout=self.TIMEOUT_SEGUNDOS)
            if response.status_code == 200:
                res_json = response.json()
                results = res_json.get('results', [])
                return True, f"{len(results)} pedido(s) encontrado(s).", results
            return False, f"Erro na consulta de pedidos: HTTP {response.status_code}", []
        except Exception as exc:
            return False, f"Falha ao buscar pedidos: {str(exc)}", []
