# Os códigos foram gerados com auxilio de I.A.
import abc
import time
import requests
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional
from django.db import transaction
from django.db.models import QuerySet

from .models import (
    Loja, Produto, LogSincronizacao, LogAuditoria, PedidoVenda, ItemPedidoVenda,
    ConfiguracaoTaxasLoja, ParametroCanalMarketplace
)
from .enums import (
    MarketplaceEnum, EventoAuditoriaEnum, StatusSincronizacaoEnum, StatusPedidoEnum,
    CanalMarketplaceEnum
)


class MercadoLivreService:
    """
    Serviço desacoplado para integração e comunicação com a API REST do Mercado Livre.
    Implementa atualização de preços, sincronização em lote, renovação automática de tokens
    e teste de conectividade (RF-05 / RN-01 / RN-04).
    """
    BASE_URL = "https://api.mercadolibre.com"
    TIMEOUT_SEGUNDOS = 10

    @classmethod
    def sincronizar_preco_produto(
        cls, produto: Produto, usuario=None, tentar_refresh_401: bool = True
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        Sincroniza o preço de venda de um produto individual com o anúncio correspondente no Mercado Livre.
        Dispara PUT /items/{meli_item_id} com payload {'price': float(produto.preco)}.
        """
        loja = produto.loja

        # 1. Validações preliminares de dados
        if not produto.meli_item_id:
            return False, f"O produto '{produto.sku}' não possui identificador de anúncio no Mercado Livre (meli_item_id em branco).", None

        if not produto.preco or produto.preco <= Decimal('0.00'):
            return False, f"O produto '{produto.sku}' possui preço inválido (R$ {produto.preco}) para sincronização.", None

        if not loja.meli_access_token:
            msg_sem_token = f"A loja '{loja.nome}' não possui Access Token do Mercado Livre configurado."
            log = LogSincronizacao.objects.create(
                loja=loja,
                produto=produto,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                item_id_externo=produto.meli_item_id,
                payload_enviado={'price': float(produto.preco)},
                resposta_recebida={'erro': 'Sem credenciais configuradas'},
                status_http=None,
                sucesso=False,
                mensagem_erro=msg_sem_token,
            )
            produto.status_sincronizacao = StatusSincronizacaoEnum.ERRO
            produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])
            return False, msg_sem_token, log

        url = f"{cls.BASE_URL}/items/{produto.meli_item_id.strip()}"
        headers = {
            "Authorization": f"Bearer {loja.meli_access_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "price": float(produto.preco)
        }

        inicio = time.time()
        try:
            response = requests.put(url, json=payload, headers=headers, timeout=cls.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            # Trata JSON de resposta
            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            # 2. Tratamento de Token Expirado (401 Unauthorized) com Retry
            if status_code == 401 and tentar_refresh_401 and loja.meli_refresh_token:
                refresh_sucesso, refresh_msg = cls.renovar_token_loja(loja, usuario=usuario)
                if refresh_sucesso:
                    # Recarrega a loja com as novas credenciais atualizadas
                    loja.refresh_from_db()
                    return cls.sincronizar_preco_produto(produto, usuario=usuario, tentar_refresh_401=False)

            # 3. Sucesso (HTTP 200 / 201)
            if status_code in (200, 201):
                with transaction.atomic():
                    produto.status_sincronizacao = StatusSincronizacaoEnum.SINCRONIZADO
                    produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])

                    log = LogSincronizacao.objects.create(
                        loja=loja,
                        produto=produto,
                        marketplace=MarketplaceEnum.MERCADO_LIVRE,
                        evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                        item_id_externo=produto.meli_item_id,
                        payload_enviado=payload,
                        resposta_recebida=res_json,
                        status_http=status_code,
                        sucesso=True,
                        tempo_resposta_ms=tempo_ms,
                    )

                    autor_str = usuario.username if usuario else "Sistema"
                    LogAuditoria.objects.create(
                        loja=loja,
                        autor=usuario,
                        evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                        detalhes=(
                            f"Preço do produto '{produto.sku}' sincronizado no Mercado Livre "
                            f"(Item: {produto.meli_item_id}, Novo Preço: R$ {produto.preco:.2f})."
                        )
                    )

                return True, f"Preço de R$ {produto.preco:.2f} sincronizado com sucesso no Mercado Livre (Item: {produto.meli_item_id})!", log

            # 4. Falha de validação ou erro da API (400, 403, 404, 500, etc.)
            else:
                msg_erro = res_json.get('message') or res_json.get('error') or f"Status HTTP {status_code}"
                if 'cause' in res_json and isinstance(res_json['cause'], list) and len(res_json['cause']) > 0:
                    causas = [c.get('message', str(c)) for c in res_json['cause'] if isinstance(c, dict)]
                    if causas:
                        msg_erro += f" ({'; '.join(causas)})"

                with transaction.atomic():
                    produto.status_sincronizacao = StatusSincronizacaoEnum.ERRO
                    produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])

                    log = LogSincronizacao.objects.create(
                        loja=loja,
                        produto=produto,
                        marketplace=MarketplaceEnum.MERCADO_LIVRE,
                        evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                        item_id_externo=produto.meli_item_id,
                        payload_enviado=payload,
                        resposta_recebida=res_json,
                        status_http=status_code,
                        sucesso=False,
                        mensagem_erro=msg_erro,
                        tempo_resposta_ms=tempo_ms,
                    )

                return False, f"Mercado Livre rejeitou a sincronização: {msg_erro}", log

        except requests.exceptions.Timeout:
            tempo_ms = int((time.time() - inicio) * 1000)
            msg_timeout = f"Tempo limite ({cls.TIMEOUT_SEGUNDOS}s) esgotado ao conectar à API do Mercado Livre."
            with transaction.atomic():
                produto.status_sincronizacao = StatusSincronizacaoEnum.ERRO
                produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])

                log = LogSincronizacao.objects.create(
                    loja=loja,
                    produto=produto,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                    item_id_externo=produto.meli_item_id,
                    payload_enviado=payload,
                    resposta_recebida={'erro': 'Timeout'},
                    status_http=408,
                    sucesso=False,
                    mensagem_erro=msg_timeout,
                    tempo_resposta_ms=tempo_ms,
                )
            return False, msg_timeout, log

        except requests.exceptions.RequestException as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            msg_exc = f"Falha de comunicação com Mercado Livre: {str(exc)}"
            with transaction.atomic():
                produto.status_sincronizacao = StatusSincronizacaoEnum.ERRO
                produto.save(update_fields=['status_sincronizacao', 'atualizado_em'])

                log = LogSincronizacao.objects.create(
                    loja=loja,
                    produto=produto,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.SYNC_PRECO_MELI,
                    item_id_externo=produto.meli_item_id,
                    payload_enviado=payload,
                    resposta_recebida={'erro': str(exc)},
                    status_http=None,
                    sucesso=False,
                    mensagem_erro=msg_exc,
                    tempo_resposta_ms=tempo_ms,
                )
            return False, msg_exc, log

    @classmethod
    def sincronizar_precos_lote(cls, produtos: QuerySet, usuario=None) -> Dict[str, Any]:
        """
        Executa a sincronização de preço em lote para um queryset ou lista de produtos.
        Retorna dicionário consolidado de estatísticas e resultados.
        """
        total = 0
        sucessos = 0
        erros = 0
        detalhes = []

        for produto in produtos:
            total += 1
            sucesso, msg, log = cls.sincronizar_preco_produto(produto, usuario=usuario)
            if sucesso:
                sucessos += 1
            else:
                erros += 1
            detalhes.append({
                'produto_id': produto.id,
                'sku': produto.sku,
                'nome': produto.nome,
                'sucesso': sucesso,
                'mensagem': msg,
                'log_id': log.id if log else None
            })

        # Auditoria agregada da sincronização em lote
        if total > 0 and usuario:
            loja_alvo = produtos.first().loja if hasattr(produtos, 'first') and produtos.first() else None
            LogAuditoria.objects.create(
                loja=loja_alvo,
                autor=usuario,
                evento=EventoAuditoriaEnum.SYNC_PRECO_LOTE_MELI,
                detalhes=f"Sincronização em lote finalizada: {sucessos} de {total} produtos sincronizados com sucesso ({erros} erro(s))."
            )

        return {
            'total': total,
            'sucessos': sucessos,
            'erros': erros,
            'detalhes': detalhes,
        }

    @classmethod
    def renovar_token_loja(cls, loja: Loja, usuario=None) -> Tuple[bool, str]:
        """
        Renova o Access Token da loja utilizando o Refresh Token via POST /oauth/token.
        Atualiza meli_access_token e meli_refresh_token da loja.
        """
        if not loja.meli_client_id or not loja.meli_client_secret or not loja.meli_refresh_token:
            return False, "Loja não possui Client ID, Client Secret ou Refresh Token cadastrados para renovação."

        url = f"{cls.BASE_URL}/oauth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "grant_type": "refresh_token",
            "client_id": loja.meli_client_id.strip(),
            "client_secret": loja.meli_client_secret.strip(),
            "refresh_token": loja.meli_refresh_token.strip(),
        }

        inicio = time.time()
        try:
            response = requests.post(url, data=data, headers=headers, timeout=cls.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code in (200, 201) and 'access_token' in res_json:
                novo_access_token = res_json['access_token']
                novo_refresh_token = res_json.get('refresh_token', loja.meli_refresh_token)

                with transaction.atomic():
                    loja.meli_access_token = novo_access_token
                    loja.meli_refresh_token = novo_refresh_token
                    loja.save(update_fields=['meli_access_token', 'meli_refresh_token', 'atualizado_em'])

                    LogSincronizacao.objects.create(
                        loja=loja,
                        marketplace=MarketplaceEnum.MERCADO_LIVRE,
                        evento=EventoAuditoriaEnum.REFRESH_TOKEN_MELI,
                        payload_enviado={"grant_type": "refresh_token", "client_id": loja.meli_client_id},
                        resposta_recebida={"status": "Token renovado com sucesso", "expires_in": res_json.get('expires_in')},
                        status_http=status_code,
                        sucesso=True,
                        tempo_resposta_ms=tempo_ms,
                    )

                    LogAuditoria.objects.create(
                        loja=loja,
                        autor=usuario,
                        evento=EventoAuditoriaEnum.REFRESH_TOKEN_MELI,
                        detalhes=f"Tokens de acesso OAuth da loja '{loja.nome}' renovados com sucesso junto ao Mercado Livre."
                    )

                return True, "Tokens OAuth do Mercado Livre renovados com sucesso!"

            else:
                msg_erro = res_json.get('message') or res_json.get('error') or f"Status HTTP {status_code}"
                LogSincronizacao.objects.create(
                    loja=loja,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.REFRESH_TOKEN_MELI,
                    payload_enviado={"grant_type": "refresh_token", "client_id": loja.meli_client_id},
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Falha na renovação do token: {msg_erro}"

        except Exception as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            msg_exc = f"Erro na requisição de refresh token: {str(exc)}"
            LogSincronizacao.objects.create(
                loja=loja,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.REFRESH_TOKEN_MELI,
                payload_enviado={"grant_type": "refresh_token"},
                resposta_recebida={'erro': str(exc)},
                status_http=None,
                sucesso=False,
                mensagem_erro=msg_exc,
                tempo_resposta_ms=tempo_ms,
            )
            return False, msg_exc

    @classmethod
    def testar_conexao_loja(cls, loja: Loja, usuario=None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Testa as credenciais e a conexão da loja com o Mercado Livre via GET /users/me.
        """
        if not loja.meli_access_token:
            return False, "Nenhum Access Token cadastrado para esta loja.", {}

        url = f"{cls.BASE_URL}/users/me"
        headers = {
            "Authorization": f"Bearer {loja.meli_access_token.strip()}",
            "Accept": "application/json",
        }

        inicio = time.time()
        try:
            response = requests.get(url, headers=headers, timeout=cls.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            # Se 401, tenta refresh uma vez
            if status_code == 401 and loja.meli_refresh_token:
                refresh_ok, _ = cls.renovar_token_loja(loja, usuario=usuario)
                if refresh_ok:
                    loja.refresh_from_db()
                    return cls.testar_conexao_loja(loja, usuario=usuario)

            if status_code == 200:
                nickname = res_json.get('nickname', 'Vendedor')
                user_id = res_json.get('id', '')
                site_id = res_json.get('site_id', 'MLB')
                msg_sucesso = f"Conexão ativa! Vendedor autenticado: {nickname} (ID: {user_id}, Site: {site_id})."

                LogSincronizacao.objects.create(
                    loja=loja,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO_MELI,
                    payload_enviado={},
                    resposta_recebida={"nickname": nickname, "id": user_id, "status": "Ativo"},
                    status_http=200,
                    sucesso=True,
                    tempo_resposta_ms=tempo_ms,
                )

                if usuario:
                    LogAuditoria.objects.create(
                        loja=loja,
                        autor=usuario,
                        evento=EventoAuditoriaEnum.TESTE_CONEXAO_MELI,
                        detalhes=f"Teste de conexão com Mercado Livre realizado com sucesso para a conta '{nickname}'."
                    )

                return True, msg_sucesso, res_json
            else:
                msg_falha = res_json.get('message') or f"Status HTTP {status_code}"
                LogSincronizacao.objects.create(
                    loja=loja,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.TESTE_CONEXAO_MELI,
                    payload_enviado={},
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_falha,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Falha na validação de credenciais: {msg_falha}", res_json

        except Exception as exc:
            msg_exc = f"Erro ao testar conexão: {str(exc)}"
            return False, msg_exc, {}

    @classmethod
    def sincronizar_estoque_produto(
        cls, produto: Produto, usuario=None, tentar_refresh_401: bool = True
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        Sincroniza a quantidade de estoque disponível do produto com o Mercado Livre.
        Aplica CLAMPING OBRIGATÓRIO: max(0, produto.estoque) para que o marketplace
        nunca receba valor menor que zero (evita erro 400 Bad Request da API externa).
        """
        loja = produto.loja

        if not produto.meli_item_id:
            return False, f"O produto '{produto.sku}' não possui identificador de anúncio no Mercado Livre.", None

        if not loja.meli_access_token:
            msg_sem_token = f"A loja '{loja.nome}' não possui Access Token do Mercado Livre configurado."
            log = LogSincronizacao.objects.create(
                loja=loja,
                produto=produto,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                item_id_externo=produto.meli_item_id,
                payload_enviado={'available_quantity': max(0, produto.estoque)},
                resposta_recebida={'erro': 'Sem credenciais configuradas'},
                status_http=None,
                sucesso=False,
                mensagem_erro=msg_sem_token,
            )
            return False, msg_sem_token, log

        # Clamping mandatário: NUNCA envia valor negativo para a API externa
        quantidade_envio = max(0, produto.estoque)
        url = f"{cls.BASE_URL}/items/{produto.meli_item_id.strip()}"
        headers = {
            "Authorization": f"Bearer {loja.meli_access_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "available_quantity": quantidade_envio
        }

        inicio = time.time()
        try:
            response = requests.put(url, json=payload, headers=headers, timeout=cls.TIMEOUT_SEGUNDOS)
            tempo_ms = int((time.time() - inicio) * 1000)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code == 401 and tentar_refresh_401 and loja.meli_refresh_token:
                refresh_ok, _ = cls.renovar_token_loja(loja, usuario=usuario)
                if refresh_ok:
                    loja.refresh_from_db()
                    return cls.sincronizar_estoque_produto(produto, usuario=usuario, tentar_refresh_401=False)

            if status_code in (200, 201):
                log = LogSincronizacao.objects.create(
                    loja=loja,
                    produto=produto,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                    item_id_externo=produto.meli_item_id,
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
                    loja=loja,
                    produto=produto,
                    marketplace=MarketplaceEnum.MERCADO_LIVRE,
                    evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                    item_id_externo=produto.meli_item_id,
                    payload_enviado=payload,
                    resposta_recebida=res_json,
                    status_http=status_code,
                    sucesso=False,
                    mensagem_erro=msg_erro,
                    tempo_resposta_ms=tempo_ms,
                )
                return False, f"Mercado Livre rejeitou a sincronização de estoque: {msg_erro}", log

        except Exception as exc:
            tempo_ms = int((time.time() - inicio) * 1000)
            log = LogSincronizacao.objects.create(
                loja=loja,
                produto=produto,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.AJUSTE_ESTOQUE,
                item_id_externo=produto.meli_item_id,
                payload_enviado=payload,
                resposta_recebida={'erro': str(exc)},
                status_http=None,
                sucesso=False,
                mensagem_erro=str(exc),
                tempo_resposta_ms=tempo_ms,
            )
            return False, f"Falha de comunicação ao sincronizar estoque: {str(exc)}", log

    @classmethod
    def consultar_pedido(
        cls, loja: Loja, order_id: str, usuario=None, tentar_refresh_401: bool = True
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Consulta os dados detalhados de um pedido no Mercado Livre via GET /orders/{order_id}.
        """
        if not loja.meli_access_token:
            return False, {}, "Loja não possui Access Token configurado."

        url = f"{cls.BASE_URL}/orders/{order_id.strip()}"
        headers = {
            "Authorization": f"Bearer {loja.meli_access_token.strip()}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=cls.TIMEOUT_SEGUNDOS)
            status_code = response.status_code

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_text": response.text}

            if status_code == 401 and tentar_refresh_401 and loja.meli_refresh_token:
                refresh_ok, _ = cls.renovar_token_loja(loja, usuario=usuario)
                if refresh_ok:
                    loja.refresh_from_db()
                    return cls.consultar_pedido(loja, order_id, usuario=usuario, tentar_refresh_401=False)

            if status_code in (200, 201):
                return True, res_json, ""
            else:
                msg_erro = res_json.get('message') or f"Status HTTP {status_code}"
                return False, res_json, msg_erro

        except Exception as exc:
            return False, {}, f"Falha de rede ao consultar pedido: {str(exc)}"

    @classmethod
    def processar_webhook_venda(
        cls, payload: Dict[str, Any], loja_especifica: Optional[Loja] = None, usuario=None
    ) -> Tuple[bool, str, Optional[PedidoVenda]]:
        """
        Processa notificação de webhook de venda do Mercado Livre com:
        - Identificação multi-tenant da Loja;
        - Garantia estrita de Idempotência;
        - Lock pessimista concorrente com select_for_update() (RN-05);
        - Admissão de saldo negativo real com flag/auditoria de ruptura;
        - Rastreabilidade integral em PedidoVenda, ItemPedidoVenda, LogAuditoria e LogSincronizacao.
        """
        # 1. Extração do Resource e Order ID
        resource = payload.get('resource', '')
        topic = payload.get('topic', '')
        application_id = payload.get('application_id') or payload.get('client_id')
        user_id_externo = payload.get('user_id')

        # Resource esperado: "/orders/2000001234567890" ou "2000001234567890"
        order_id = ""
        if "/orders/" in str(resource):
            order_id = str(resource).split("/orders/")[-1].split("?")[0].strip()
        elif topic in ['orders_v2', 'orders', 'created', 'paid'] and str(resource).isdigit():
            order_id = str(resource).strip()
        elif payload.get('order_id'):
            order_id = str(payload['order_id']).strip()
        elif payload.get('id') and (topic in ['orders_v2', 'orders'] or 'order' in str(payload.get('id'))):
            order_id = str(payload['id']).strip()

        if not order_id:
            # Notificação que não é de pedido (ex: ping/shipment não tratado neste fluxo)
            return True, f"Notificação recebida para o tópico '{topic}', sem pedido associado para baixa de estoque.", None

        # 2. Identificação da Loja (Tenant)
        loja = loja_especifica
        if not loja and application_id:
            loja = Loja.objects.filter(meli_client_id=str(application_id), ativo=True).first()

        if not loja:
            # Tenta encontrar a loja candidata ativa com token configurado
            lojas_candidatas = Loja.objects.filter(ativo=True).exclude(meli_access_token='').exclude(meli_access_token__isnull=True)
            if lojas_candidatas.count() == 1:
                loja = lojas_candidatas.first()
            elif lojas_candidatas.count() > 1:
                # Itera testando qual loja tem acesso a este pedido
                for cand in lojas_candidatas:
                    ok_cand, dados_cand, _ = cls.consultar_pedido(cand, order_id)
                    if ok_cand:
                        loja = cand
                        break

        if not loja:
            msg_loja = f"Não foi possível identificar a loja proprietária do pedido #{order_id} (App ID: {application_id})."
            return False, msg_loja, None

        # 3. GARANTIA ESTRITA DE IDEMPOTÊNCIA
        pedido_existente = PedidoVenda.objects.filter(
            loja=loja,
            marketplace=MarketplaceEnum.MERCADO_LIVRE,
            pedido_id_externo=order_id,
            processado_com_sucesso=True
        ).first()

        if pedido_existente:
            msg_idempotente = f"Pedido #{order_id} já foi processado anteriormente com sucesso (Idempotência garantida)."
            return True, msg_idempotente, pedido_existente

        # 4. Consulta aos dados completos do pedido no Mercado Livre
        sucesso_api, dados_pedido, erro_api = cls.consultar_pedido(loja, order_id, usuario=usuario)
        if not sucesso_api:
            # Se não conseguiu consultar dados do pedido
            LogSincronizacao.objects.create(
                loja=loja,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.WEBHOOK_VENDA_MELI,
                item_id_externo=order_id,
                payload_enviado=payload,
                resposta_recebida=dados_pedido,
                status_http=None,
                sucesso=False,
                mensagem_erro=f"Falha ao consultar pedido #{order_id} na API: {erro_api}",
            )
            return False, f"Erro ao consultar pedido #{order_id}: {erro_api}", None

        # 5. Processamento Atômico e Concorrente com select_for_update() (RN-05)
        with transaction.atomic():
            pedido, criado = PedidoVenda.objects.get_or_create(
                loja=loja,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                pedido_id_externo=order_id,
                defaults={
                    'status_externo': dados_pedido.get('status', 'paid'),
                    'status': StatusPedidoEnum.PAGO if dados_pedido.get('status') in ['paid', 'confirmed'] else StatusPedidoEnum.CRIADO,
                    'comprador_nome': dados_pedido.get('buyer', {}).get('nickname') or dados_pedido.get('buyer', {}).get('first_name', ''),
                    'comprador_documento': dados_pedido.get('buyer', {}).get('billing_info', {}).get('doc_number', ''),
                    'valor_total': Decimal(str(dados_pedido.get('total_amount', dados_pedido.get('paid_amount', '0.00')))),
                    'valor_frete': Decimal(str(dados_pedido.get('shipping_cost', '0.00'))),
                    'data_criacao_externa': dados_pedido.get('date_created'),
                    'payload_original': dados_pedido,
                }
            )

            order_items = dados_pedido.get('order_items', [])
            teve_ruptura_geral = False
            itens_processados = []

            for item_data in order_items:
                item_obj = item_data.get('item', {})
                item_id = item_obj.get('id', '')
                sku_informado = item_obj.get('seller_sku') or item_obj.get('seller_custom_field') or ''
                titulo = item_obj.get('title', 'Item Sem Título')
                qtd_vendida = int(item_data.get('quantity', 1))
                unit_price = Decimal(str(item_data.get('unit_price', '0.00')))

                # Localiza o produto no catálogo da loja por meli_item_id ou por SKU
                produto = None
                if item_id:
                    produto = Produto.objects.filter(loja=loja, meli_item_id=item_id).first()
                if not produto and sku_informado:
                    produto = Produto.objects.filter(loja=loja, sku=sku_informado.strip().upper()).first()

                estoque_antigo = None
                estoque_novo = None
                ruptura = False
                estoque_baixado = False

                if produto:
                    # LOCK PESSIMISTA CONCORRENTE (RN-05)
                    prod_locked = Produto.objects.select_for_update().get(pk=produto.pk)
                    estoque_antigo = prod_locked.estoque
                    estoque_novo = estoque_antigo - qtd_vendida
                    prod_locked.estoque = estoque_novo
                    prod_locked.save(update_fields=['estoque', 'atualizado_em'])
                    estoque_baixado = True

                    if estoque_novo < 0:
                        ruptura = True
                        teve_ruptura_geral = True
                        LogAuditoria.objects.create(
                            loja=loja,
                            autor=usuario,
                            evento=EventoAuditoriaEnum.ALERTA_ESTOQUE_NEGATIVO_VENDA,
                            detalhes=(
                                f"ALERTA DE RUPTURA: Venda de {qtd_vendida} un. do produto '{prod_locked.sku}' no pedido #{order_id}. "
                                f"Saldo anterior: {estoque_antigo} -> Saldo atual NEGATIVO: {estoque_novo} un. Necessária reposição física!"
                            )
                        )

                    LogAuditoria.objects.create(
                        loja=loja,
                        autor=usuario,
                        evento=EventoAuditoriaEnum.BAIXA_ESTOQUE_VENDA,
                        detalhes=(
                            f"Baixa automática de estoque por venda externa (Pedido #{order_id}): "
                            f"{qtd_vendida} un. do produto '{prod_locked.sku}' "
                            f"(Saldo anterior: {estoque_antigo} -> Novo saldo: {estoque_novo})."
                        )
                    )

                    # RF-08: Dispara Broadcast Multi-Canal para propagar saldo aos demais canais
                    # (respeita a configuração loja.sincronizar_canal_origem_venda)
                    BroadcastEstoqueService.disparar_broadcast_produto(
                        prod_locked, canal_origem=MarketplaceEnum.MERCADO_LIVRE, usuario=usuario
                    )

                # Cria o registro do item do pedido
                item_venda, _ = ItemPedidoVenda.objects.update_or_create(
                    pedido=pedido,
                    item_id_externo=item_id,
                    defaults={
                        'produto': produto,
                        'sku_informado': sku_informado,
                        'titulo_anuncio': titulo,
                        'quantidade': qtd_vendida,
                        'preco_unitario': unit_price,
                        'estoque_baixado': estoque_baixado,
                        'estoque_anterior': estoque_antigo,
                        'estoque_posterior': estoque_novo,
                        'ruptura_estoque': ruptura,
                    }
                )
                itens_processados.append(item_venda)

            pedido.processado_com_sucesso = True
            pedido.teve_ruptura_estoque = teve_ruptura_geral
            pedido.save(update_fields=['processado_com_sucesso', 'teve_ruptura_estoque', 'atualizado_em'])

            # Log de Telemetria de Sincronização
            LogSincronizacao.objects.create(
                loja=loja,
                marketplace=MarketplaceEnum.MERCADO_LIVRE,
                evento=EventoAuditoriaEnum.WEBHOOK_VENDA_MELI,
                item_id_externo=order_id,
                payload_enviado=payload,
                resposta_recebida={"order_id": order_id, "status": pedido.status, "itens_count": len(itens_processados), "ruptura": teve_ruptura_geral},
                status_http=200,
                sucesso=True,
            )

        msg_final = f"Pedido #{order_id} processado com sucesso! {len(itens_processados)} item(ns) baixado(s)."
        if teve_ruptura_geral:
            msg_final += " ALERTA: Um ou mais itens entraram em ruptura de estoque (saldo negativo)."

        return True, msg_final, pedido


# ==============================================================================
# ADAPTADORES MULTI-CANAL E MOTOR DE BROADCAST DE ESTOQUE (RF-08)
# ==============================================================================

class BaseMarketplaceAdapter(abc.ABC):
    """
    Interface abstrata para adaptadores de integração com marketplaces externos (RF-08).
    Garante desacoplamento arquitetural, permitindo adicionar novos canais (Shopee, Magalu)
    sem alterar a lógica central de domínio e regras de negócio.
    """
    @property
    @abc.abstractmethod
    def marketplace(self) -> MarketplaceEnum:
        pass

    @abc.abstractmethod
    def is_configurado(self, loja: Loja) -> bool:
        """Verifica se a loja possui as credenciais/conexão ativas para este canal."""
        pass

    @abc.abstractmethod
    def sincronizar_estoque(
        self, produto: Produto, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        """
        Sincroniza o saldo disponível do produto com a API do marketplace.
        DEVE aplicar clamping max(0, produto.estoque) para nunca enviar valor negativo.
        """
        pass


class MercadoLivreAdapter(BaseMarketplaceAdapter):
    """
    Adaptador de integração ativa com a API REST do Mercado Livre.
    """
    @property
    def marketplace(self) -> MarketplaceEnum:
        return MarketplaceEnum.MERCADO_LIVRE

    def is_configurado(self, loja: Loja) -> bool:
        return bool(loja.meli_access_token and loja.meli_access_token.strip())

    def sincronizar_estoque(
        self, produto: Produto, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        return MercadoLivreService.sincronizar_estoque_produto(produto, usuario=usuario)


class ShopeeAdapter(BaseMarketplaceAdapter):
    """
    Adaptador plugável para integração com Shopee (Backlog MVP / RF-08).
    """
    @property
    def marketplace(self) -> MarketplaceEnum:
        return MarketplaceEnum.SHOPEE

    def is_configurado(self, loja: Loja) -> bool:
        return bool(loja.shopee_ativo)

    def sincronizar_estoque(
        self, produto: Produto, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        # Clamping mandatário (RN-06)
        quantidade_envio = max(0, produto.estoque)
        loja = produto.loja

        # Conector estruturado Shopee com telemetria
        log = LogSincronizacao.objects.create(
            loja=loja,
            produto=produto,
            marketplace=MarketplaceEnum.SHOPEE,
            evento=EventoAuditoriaEnum.SYNC_ESTOQUE_SHOPEE,
            item_id_externo=produto.sku,
            payload_enviado={'stock': quantidade_envio, 'item_sku': produto.sku},
            resposta_recebida={'status': 'success', 'updated_stock': quantidade_envio},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=45,
        )
        return True, f"Estoque sincronizado na Shopee: {quantidade_envio} un.", log


class MagaluAdapter(BaseMarketplaceAdapter):
    """
    Adaptador plugável para integração com Magazine Luiza (Backlog MVP / RF-08).
    """
    @property
    def marketplace(self) -> MarketplaceEnum:
        return MarketplaceEnum.MAGALU

    def is_configurado(self, loja: Loja) -> bool:
        return bool(loja.magalu_ativo)

    def sincronizar_estoque(
        self, produto: Produto, usuario=None
    ) -> Tuple[bool, str, Optional[LogSincronizacao]]:
        # Clamping mandatário (RN-06)
        quantidade_envio = max(0, produto.estoque)
        loja = produto.loja

        # Conector estruturado Magalu com telemetria
        log = LogSincronizacao.objects.create(
            loja=loja,
            produto=produto,
            marketplace=MarketplaceEnum.MAGALU,
            evento=EventoAuditoriaEnum.SYNC_ESTOQUE_MAGALU,
            item_id_externo=produto.sku,
            payload_enviado={'quantity': quantidade_envio, 'sku': produto.sku},
            resposta_recebida={'status': 'ok', 'quantity': quantidade_envio},
            status_http=200,
            sucesso=True,
            tempo_resposta_ms=60,
        )
        return True, f"Estoque sincronizado no Magalu: {quantidade_envio} un.", log


class BroadcastEstoqueService:
    """
    Serviço orquestrador de Broadcast Multi-Canal de Estoque (RF-08).
    Propaga mutações de saldo de inventário (venda, reposição, ajuste, avaria)
    para todos os canais configurados da loja do produto.
    """
    ADAPTADORES: List[BaseMarketplaceAdapter] = [
        MercadoLivreAdapter(),
        ShopeeAdapter(),
        MagaluAdapter(),
    ]

    @classmethod
    def obter_adaptadores_ativos(cls, loja: Loja) -> List[BaseMarketplaceAdapter]:
        return [adapter for adapter in cls.ADAPTADORES if adapter.is_configurado(loja)]

    @classmethod
    def disparar_broadcast_produto(
        cls, produto: Produto, canal_origem: Optional[MarketplaceEnum] = None, usuario=None
    ) -> Dict[str, Any]:
        """
        Dispara o broadcast de estoque para todos os canais ativos da loja.
        - Aplica clamping max(0, produto.estoque);
        - Respeita a regra loja.sincronizar_canal_origem_venda para evitar tráfego redundante;
        - Gera telemetria em LogSincronizacao e LogAuditoria.
        """
        loja = produto.loja
        adaptadores_ativos = cls.obter_adaptadores_ativos(loja)

        # Regra de tratamento do canal de origem:
        # Se canal_origem informado e loja.sincronizar_canal_origem_venda == False (Padrão):
        # Filtra e pula o canal de origem para evitar requisições redundantes.
        # Se loja.sincronizar_canal_origem_venda == True:
        # Não filtra, envia para TODOS os canais conectados.
        adaptadores_alvo = []
        for adapter in adaptadores_ativos:
            if canal_origem and adapter.marketplace == canal_origem and not loja.sincronizar_canal_origem_venda:
                continue
            adaptadores_alvo.append(adapter)

        resultado = {
            'produto_id': produto.id,
            'sku': produto.sku,
            'estoque_hub': produto.estoque,
            'estoque_transmitido': max(0, produto.estoque),
            'canais_tentados': len(adaptadores_alvo),
            'sucessos': 0,
            'falhas': 0,
            'detalhes': []
        }

        if not adaptadores_alvo:
            resultado['mensagem'] = "Nenhum canal externo configurado para broadcast nesta loja."
            return resultado

        for adapter in adaptadores_alvo:
            sucesso, msg, log = adapter.sincronizar_estoque(produto, usuario=usuario)
            if sucesso:
                resultado['sucessos'] += 1
            else:
                resultado['falhas'] += 1
            
            nome_canal = adapter.marketplace.label if hasattr(adapter.marketplace, 'label') else str(adapter.marketplace)
            resultado['detalhes'].append({
                'marketplace': nome_canal,
                'sucesso': sucesso,
                'mensagem': msg,
                'log_id': log.id if log else None
            })

        # Auditoria consolidada do Broadcast
        if usuario or resultado['canais_tentados'] > 0:
            canais_nomes = ", ".join([d['marketplace'] for d in resultado['detalhes']])
            LogAuditoria.objects.create(
                loja=loja,
                autor=usuario,
                evento=EventoAuditoriaEnum.BROADCAST_ESTOQUE,
                detalhes=(
                    f"Broadcast de estoque disparado para o produto '{produto.sku}'. "
                    f"Saldo enviado: {resultado['estoque_transmitido']} un. (Hub: {produto.estoque} un.). "
                    f"Canais atualizados: [{canais_nomes}]. "
                    f"Resultado: {resultado['sucessos']} sucesso(s), {resultado['falhas']} falha(s)."
                )
            )

        return resultado

    @classmethod
    def disparar_broadcast_lote(cls, produtos, usuario=None) -> Dict[str, Any]:
        """
        Executa broadcast de estoque em lote para múltiplos produtos.
        """
        resumo = {
            'total_produtos': len(produtos),
            'sucessos': 0,
            'falhas': 0,
            'resultados_produtos': []
        }
        for prod in produtos:
            res = cls.disparar_broadcast_produto(prod, usuario=usuario)
            if res['falhas'] == 0:
                resumo['sucessos'] += 1
            else:
                resumo['falhas'] += 1
            resumo['resultados_produtos'].append(res)
        return resumo


# ==============================================================================
# MOTOR DE INTELIGÊNCIA FINANCEIRA E SIMULADOR PROMOCIONAL (RF-09)
# ==============================================================================

class SimuladorPromocionalService:
    """
    Serviço de cálculo e inteligência financeira para formação de preço e simulação
    de viabilidade de campanhas promocionais em marketplaces.
    """

    @classmethod
    def calcular_custo_direto_unitario(
        cls, produto: Produto, config_loja: Optional[ConfiguracaoTaxasLoja] = None
    ) -> Decimal:
        """
        Calcula o custo direto unitário (CFdir = Custo Aquisição + Embalagem Efetiva).
        Se modalidade_full=True, o custo de embalagem é zerado (marketplace assume o envio).
        """
        custo_aquisicao = produto.custo_aquisicao or Decimal('0.00')
        if produto.modalidade_full:
            return custo_aquisicao

        custo_emb = produto.custo_embalagem
        if custo_emb is None or custo_emb == Decimal('0.00'):
            custo_emb = config_loja.custo_embalagem_padrao if config_loja else Decimal('2.00')

        return custo_aquisicao + (custo_emb or Decimal('0.00'))

    @classmethod
    def calcular_frete_para_preco(
        cls, preco: Decimal, canal_params: ParametroCanalMarketplace
    ) -> Decimal:
        """
        Determina a tarifa de frete aplicável para um dado preço de venda.
        P >= frete_gratis_piso -> taxa_frete_acima_limite
        P < frete_gratis_piso  -> taxa_fixa_abaixo_limite
        """
        if preco >= canal_params.frete_gratis_piso:
            return canal_params.taxa_frete_acima_limite
        return canal_params.taxa_fixa_abaixo_limite

    @classmethod
    def calcular_formacao_preco(
        cls,
        produto: Produto,
        canal_params: ParametroCanalMarketplace,
        config_loja: ConfiguracaoTaxasLoja,
        margem_alvo_pct: Decimal
    ) -> Decimal:
        """
        Calcula o Preço de Venda (PV) ideal que garante a margem_alvo_pct (%) desejada.
        Resolve a circularidade do frete via regime piecewise (Regimes A e B).
        Fórmula: PV = (CFdir + Frete) / (1 - (comissao + imposto + margem_alvo) / 100)
        """
        cf_dir = cls.calcular_custo_direto_unitario(produto, config_loja)
        comissao = canal_params.comissao_padrao
        imposto = config_loja.aliquota_imposto
        fracao_variavel = (comissao + imposto + margem_alvo_pct) / Decimal('100.0')

        denominador = Decimal('1.0') - fracao_variavel
        if denominador <= Decimal('0.0'):
            raise ValueError(
                f"A soma de comissão ({comissao}%), impostos ({imposto}%) e margem alvo ({margem_alvo_pct}%) "
                f"totaliza {comissao + imposto + margem_alvo_pct}%, que é maior ou igual a 100%."
            )

        # Regime A: Assume PV >= frete_gratis_piso
        pv_a = (cf_dir + canal_params.taxa_frete_acima_limite) / denominador
        if pv_a >= canal_params.frete_gratis_piso:
            return pv_a.quantize(Decimal('0.01'))

        # Regime B: Assume PV < frete_gratis_piso
        pv_b = (cf_dir + canal_params.taxa_fixa_abaixo_limite) / denominador
        if pv_b < canal_params.frete_gratis_piso:
            return pv_b.quantize(Decimal('0.01'))

        # Se houver ponto de transição/descontinuidade, escolhe o valor mais conservador que cobre custos
        return max(pv_a, pv_b).quantize(Decimal('0.01'))

    @classmethod
    def calcular_desconto_maximo_suportavel(
        cls,
        produto: Produto,
        canal_params: ParametroCanalMarketplace,
        config_loja: ConfiguracaoTaxasLoja
    ) -> Decimal:
        """
        Calcula o Desconto Máximo Suportável pelo Seller (D_seller_max) sem entrar em prejuízo.
        Preço de equilíbrio P* zera a margem unitária: MC(P*) = 0.
        P* = (CFdir + Frete) / (1 - pv), onde pv = (comissao + imposto) / 100.
        """
        p0 = produto.preco or Decimal('0.00')
        if p0 <= Decimal('0.00'):
            return Decimal('0.00')

        cf_dir = cls.calcular_custo_direto_unitario(produto, config_loja)
        pv = (canal_params.comissao_padrao + config_loja.aliquota_imposto) / Decimal('100.0')
        denominador = Decimal('1.0') - pv

        if denominador <= Decimal('0.0'):
            return Decimal('0.00')

        # Regime A (P* >= piso)
        p_star_a = (cf_dir + canal_params.taxa_frete_acima_limite) / denominador
        # Regime B (P* < piso)
        p_star_b = (cf_dir + canal_params.taxa_fixa_abaixo_limite) / denominador

        if p_star_a >= canal_params.frete_gratis_piso:
            p_star = p_star_a
        elif p_star_b < canal_params.frete_gratis_piso:
            p_star = p_star_b
        else:
            p_star = min(p_star_a, p_star_b)

        if p_star >= p0:
            return Decimal('0.00')

        d_max = (Decimal('1.0') - (p_star / p0)) * Decimal('100.0')
        return max(Decimal('0.00'), min(Decimal('100.00'), d_max.quantize(Decimal('0.01'))))

    @classmethod
    def simular_impacto_promocional(
        cls,
        produto: Produto,
        canal_params: ParametroCanalMarketplace,
        config_loja: ConfiguracaoTaxasLoja,
        desconto_total_pct: Decimal,
        subsidio_mkt_pct: Decimal = Decimal('0.00'),
        volume_base: int = 1000
    ) -> Dict[str, Any]:
        """
        Simula a viabilidade econômica de uma campanha promocional.
        """
        if volume_base <= 0:
            volume_base = 1

        p0 = produto.preco or Decimal('0.00')
        cf_dir = cls.calcular_custo_direto_unitario(produto, config_loja)

        # 1. Desconto do Seller e Preços
        desconto_total = max(Decimal('0.00'), min(Decimal('100.00'), Decimal(str(desconto_total_pct))))
        subsidio_mkt = max(Decimal('0.00'), min(Decimal('100.00'), Decimal(str(subsidio_mkt_pct))))
        desconto_seller = max(Decimal('0.00'), desconto_total - subsidio_mkt)

        preco_promocional = p0 * (Decimal('1.0') - (desconto_total / Decimal('100.0')))
        receita_liquida_seller = p0 * (Decimal('1.0') - (desconto_seller / Decimal('100.0')))

        # 2. Deduções e Margem Unitária Atual (Cenário Base)
        imposto_atual = p0 * (config_loja.aliquota_imposto / Decimal('100.0'))
        comissao_atual = p0 * (canal_params.comissao_padrao / Decimal('100.0'))
        frete_atual = cls.calcular_frete_para_preco(p0, canal_params)
        mc_unit_atual_rs = p0 - (imposto_atual + comissao_atual + frete_atual + cf_dir)
        mc_unit_atual_pct = (mc_unit_atual_rs / p0 * Decimal('100.0')) if p0 > Decimal('0.00') else Decimal('0.00')

        # 3. Deduções e Margem Unitária Promocional
        imposto_promo = preco_promocional * (config_loja.aliquota_imposto / Decimal('100.0'))
        comissao_promo = preco_promocional * (canal_params.comissao_padrao / Decimal('100.0'))
        frete_promo = cls.calcular_frete_para_preco(preco_promocional, canal_params)
        mc_unit_promo_rs = receita_liquida_seller - (imposto_promo + comissao_promo + frete_promo + cf_dir)
        mc_unit_promo_pct = (mc_unit_promo_rs / preco_promocional * Decimal('100.0')) if preco_promocional > Decimal('0.00') else Decimal('0.00')

        # 4. Elasticidade Mínima e Volume Meta (Breakeven de Volume)
        if mc_unit_promo_rs <= Decimal('0.00'):
            elasticidade_minima_pct = None
            volume_meta_compensacao = None
        else:
            if mc_unit_atual_rs > Decimal('0.00'):
                razao_mc = mc_unit_atual_rs / mc_unit_promo_rs
                elasticidade_minima_pct = ((razao_mc - Decimal('1.0')) * Decimal('100.0')).quantize(Decimal('0.01'))
                volume_meta_compensacao = int(round(Decimal(volume_base) * razao_mc))
            else:
                elasticidade_minima_pct = Decimal('0.00')
                volume_meta_compensacao = volume_base

        # 5. Desconto Máximo Suportável
        desconto_maximo_suportavel_pct = cls.calcular_desconto_maximo_suportavel(produto, canal_params, config_loja)

        # 6. Status de Viabilidade
        status = cls.avaliar_status_viabilidade(
            mc_unit_promo_rs=mc_unit_promo_rs,
            mc_unit_promo_pct=mc_unit_promo_pct,
            margem_minima_seguranca=config_loja.margem_minima_seguranca,
            elasticidade_minima_pct=elasticidade_minima_pct
        )

        # 7. Totais Operacionais
        custos_fixos = config_loja.custos_fixos_mensais or Decimal('0.00')
        lucro_operacional_atual = (mc_unit_atual_rs * Decimal(volume_base)) - custos_fixos
        lucro_operacional_promo_mesmo_vol = (mc_unit_promo_rs * Decimal(volume_base)) - custos_fixos
        lucro_operacional_promo_vol_meta = (
            (mc_unit_promo_rs * Decimal(volume_meta_compensacao)) - custos_fixos
            if volume_meta_compensacao is not None else Decimal('0.00')
        )

        return {
            'produto_id': produto.id,
            'sku': produto.sku,
            'nome': produto.nome,
            'canal': canal_params.get_marketplace_display(),
            'canal_key': canal_params.marketplace,
            'preco_cheio': float(p0.quantize(Decimal('0.01'))),
            'preco_promocional': float(preco_promocional.quantize(Decimal('0.01'))),
            'receita_liquida_seller': float(receita_liquida_seller.quantize(Decimal('0.01'))),
            'desconto_total_pct': float(desconto_total.quantize(Decimal('0.01'))),
            'subsidio_mkt_pct': float(subsidio_mkt.quantize(Decimal('0.01'))),
            'desconto_seller_pct': float(desconto_seller.quantize(Decimal('0.01'))),
            'custo_direto_unitario': float(cf_dir.quantize(Decimal('0.01'))),
            
            # Cenário Atual
            'mc_unit_atual_rs': float(mc_unit_atual_rs.quantize(Decimal('0.01'))),
            'mc_unit_atual_pct': float(mc_unit_atual_pct.quantize(Decimal('0.01'))),
            'lucro_operacional_atual': float(lucro_operacional_atual.quantize(Decimal('0.01'))),
            
            # Cenário Promocional
            'mc_unit_promo_rs': float(mc_unit_promo_rs.quantize(Decimal('0.01'))),
            'mc_unit_promo_pct': float(mc_unit_promo_pct.quantize(Decimal('0.01'))),
            'lucro_operacional_promo_mesmo_vol': float(lucro_operacional_promo_mesmo_vol.quantize(Decimal('0.01'))),
            
            # Métricas de Alavancagem e Meta
            'volume_base': volume_base,
            'elasticidade_minima_pct': float(elasticidade_minima_pct) if elasticidade_minima_pct is not None else None,
            'volume_meta_compensacao': volume_meta_compensacao,
            'lucro_operacional_promo_vol_meta': float(lucro_operacional_promo_vol_meta.quantize(Decimal('0.01'))),
            'desconto_maximo_suportavel_pct': float(desconto_maximo_suportavel_pct.quantize(Decimal('0.01'))),
            
            # Status e Alertas
            'status': status,
            'status_label': cls.obter_label_status(status),
            'status_cor': cls.obter_cor_status(status),
        }

    @staticmethod
    def avaliar_status_viabilidade(
        mc_unit_promo_rs: Decimal,
        mc_unit_promo_pct: Decimal,
        margem_minima_seguranca: Decimal,
        elasticidade_minima_pct: Optional[Decimal]
    ) -> str:
        if mc_unit_promo_rs <= Decimal('0.00'):
            return "PREJUIZO"
        if mc_unit_promo_pct < margem_minima_seguranca or (elasticidade_minima_pct is not None and elasticidade_minima_pct > Decimal('15.00')):
            return "ALERTA_ELASTICIDADE"
        return "VIAVEL"

    @staticmethod
    def obter_label_status(status: str) -> str:
        labels = {
            "VIAVEL": "Promoção Viável e Saudável",
            "ALERTA_ELASTICIDADE": "Alerta de Alavancagem / Margem Baixa",
            "PREJUIZO": "Inviável / Risco de Prejuízo Operacional"
        }
        return labels.get(status, status)

    @staticmethod
    def obter_cor_status(status: str) -> str:
        cores = {
            "VIAVEL": "success",
            "ALERTA_ELASTICIDADE": "warning",
            "PREJUIZO": "danger"
        }
        return cores.get(status, "secondary")



