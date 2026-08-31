import time
import requests
from decimal import Decimal
from typing import Tuple, Dict, Any, List, Optional
from django.db import transaction
from django.db.models import QuerySet

from .models import Loja, Produto, LogSincronizacao, LogAuditoria
from .enums import (
    MarketplaceEnum, EventoAuditoriaEnum, StatusSincronizacaoEnum
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
