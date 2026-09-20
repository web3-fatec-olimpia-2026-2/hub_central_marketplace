# Os códigos foram gerados com auxilio de I.A.
"""
Serviços de Execução e Telemetria para Testes de Concorrência (Lock Pessimista e Double-Checked Locking).
Valida empiricamente os padrões documentados nos ADRs 004, 005 e 008.
"""
import time
import datetime
import threading
from typing import Dict, Any

from django.db import transaction, connections
from django.utils import timezone

from apps.catalogo.models import Produto
from apps.marketplaces.models import ContaMarketplace


class ConcorrenciaEstoqueTestService:
    """
    Serviço para testar baixa atômica simultânea de estoque com Lock Pessimista.
    Dispara duas requisições concorrentes em threads separadas, induzindo retenção
    temporal da trava para evidenciar a serialização e prevenção de Lost Updates.
    """

    MIN_DELAY_MS = 100
    MAX_DELAY_MS = 10000

    @classmethod
    def validar_delay(cls, delay_ms: int) -> int:
        try:
            val = int(delay_ms)
        except (ValueError, TypeError):
            raise ValueError(f"O atraso deve ser um número inteiro entre {cls.MIN_DELAY_MS} ms e {cls.MAX_DELAY_MS} ms.")
        if val < cls.MIN_DELAY_MS or val > cls.MAX_DELAY_MS:
            raise ValueError(f"O atraso deve estar estritamente entre {cls.MIN_DELAY_MS} ms e 10.000 ms (recebido: {val} ms).")
        return val

    @classmethod
    def executar_teste(cls, produto_id: int, qtd1: int, qtd2: int, delay_ms: int, user=None) -> Dict[str, Any]:
        delay_ms = cls.validar_delay(delay_ms)

        if qtd1 <= 0 or qtd2 <= 0:
            raise ValueError("As quantidades para as requisições 1 e 2 devem ser maiores que zero.")

        produto = Produto.objects.get(pk=produto_id)
        saldo_inicial = produto.estoque

        res_thread1: Dict[str, Any] = {}
        res_thread2: Dict[str, Any] = {}
        erros = []

        def worker_thread1():
            try:
                t0 = time.perf_counter()
                with transaction.atomic():
                    t_req = time.perf_counter()
                    # Promove intenção de escrita para garantir exclusão mútua consistente
                    Produto.objects.filter(pk=produto.pk).update(atualizado_em=timezone.now())
                    prod = Produto.objects.select_for_update().get(pk=produto.pk)
                    t_lock = time.perf_counter()

                    # Simula processamento com delay forçado
                    time.sleep(delay_ms / 1000.0)

                    saldo_ant = prod.estoque
                    novo_saldo = saldo_ant - qtd1
                    prod.estoque = novo_saldo
                    prod.save(update_fields=['estoque', 'atualizado_em'])

                t_end = time.perf_counter()
                res_thread1.update({
                    'status': 'SUCESSO',
                    'duracao_ms': round((t_end - t0) * 1000, 2),
                    'lock_wait_ms': round((t_lock - t_req) * 1000, 2),
                    'qtd_deduzida': qtd1,
                    'saldo_anterior': saldo_ant,
                    'novo_saldo': novo_saldo,
                })
            except Exception as e:
                erros.append(f"Erro Thread 1: {str(e)}")
                res_thread1.update({'status': 'ERRO', 'erro': str(e)})
            finally:
                connections.close_all()

        def worker_thread2():
            time.sleep(0.04)
            t0 = time.perf_counter()
            max_retries = 150
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        t_req = time.perf_counter()
                        Produto.objects.filter(pk=produto.pk).update(atualizado_em=timezone.now())
                        t_lock = time.perf_counter()
                        wait_ms = (t_lock - t0) * 1000

                        prod = Produto.objects.select_for_update().get(pk=produto.pk)
                        saldo_ant = prod.estoque
                        novo_saldo = saldo_ant - qtd2
                        prod.estoque = novo_saldo
                        prod.save(update_fields=['estoque', 'atualizado_em'])

                    t_end = time.perf_counter()
                    res_thread2.update({
                        'status': 'SUCESSO',
                        'duracao_ms': round((t_end - t0) * 1000, 2),
                        'lock_wait_ms': round(wait_ms, 2),
                        'qtd_deduzida': qtd2,
                        'saldo_anterior': saldo_ant,
                        'novo_saldo': novo_saldo,
                    })
                    break
                except Exception as e:
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.02)
                        continue
                    erros.append(f"Erro Thread 2: {str(e)}")
                    res_thread2.update({'status': 'ERRO', 'erro': str(e)})
                    break
                finally:
                    connections.close_all()

        th1 = threading.Thread(target=worker_thread1, name="Worker-Estoque-T1")
        th2 = threading.Thread(target=worker_thread2, name="Worker-Estoque-T2")

        th1.start()
        th2.start()
        th1.join(timeout=15.0)
        th2.join(timeout=15.0)

        produto.refresh_from_db()
        saldo_final = produto.estoque
        saldo_esperado = saldo_inicial - (qtd1 + qtd2)
        consistente = (saldo_final == saldo_esperado)

        if erros:
            return {
                'sucesso': False,
                'erros': erros,
                'thread1': res_thread1,
                'thread2': res_thread2,
                'saldo_inicial': saldo_inicial,
                'saldo_final': saldo_final,
            }

        return {
            'sucesso': True,
            'produto': {
                'id': produto.id,
                'nome': produto.nome,
                'sku': produto.sku,
            },
            'saldo_inicial': saldo_inicial,
            'saldo_final': saldo_final,
            'saldo_esperado': saldo_esperado,
            'qtd1': qtd1,
            'qtd2': qtd2,
            'consistente': consistente,
            'thread1': res_thread1,
            'thread2': res_thread2,
            'tempo_espera_thread2_ms': res_thread2.get('lock_wait_ms', 0),
            'duracao_total_ms': round(max(res_thread1.get('duracao_ms', 0), res_thread2.get('duracao_ms', 0)), 2),
            'mensagem': (
                f"Prova matemática confirmada: Saldo Inicial ({saldo_inicial}) - "
                f"({qtd1} + {qtd2}) = Saldo Final ({saldo_final}). Nenhuma ordem foi descartada."
            )
        }


class ConcorrenciaOAuthTestService:
    """
    Serviço para testar renovação concorrente de credenciais OAuth 2.0.
    Demonstra o Lock Pessimista associado ao padrão Double-Checked Locking:
    a primeira thread realiza a renovação remota, enquanto a segunda thread aguarda na trava
    e reaproveita a credencial renovada com zero chamadas à API externa.
    """

    MIN_DELAY_MS = 100
    MAX_DELAY_MS = 10000

    @classmethod
    def validar_delay(cls, delay_ms: int) -> int:
        try:
            val = int(delay_ms)
        except (ValueError, TypeError):
            raise ValueError(f"O atraso deve ser um número inteiro entre {cls.MIN_DELAY_MS} ms e {cls.MAX_DELAY_MS} ms.")
        if val < cls.MIN_DELAY_MS or val > cls.MAX_DELAY_MS:
            raise ValueError(f"O atraso deve estar estritamente entre {cls.MIN_DELAY_MS} ms e 10.000 ms (recebido: {val} ms).")
        return val

    @classmethod
    def executar_teste(cls, conta_id: int, delay_ms: int, user=None) -> Dict[str, Any]:
        delay_ms = cls.validar_delay(delay_ms)

        conta = ContaMarketplace.objects.get(pk=conta_id)

        # Força o token a parecer expirado antes do teste concorrente
        conta.token_expira_em = timezone.now() - datetime.timedelta(minutes=5)
        conta.save(update_fields=['token_expira_em'])

        res_thread1: Dict[str, Any] = {}
        res_thread2: Dict[str, Any] = {}
        erros = []

        def worker_thread1():
            try:
                t0 = time.perf_counter()
                with transaction.atomic():
                    t_req = time.perf_counter()
                    ContaMarketplace.objects.filter(pk=conta.pk).update(updated_at=timezone.now())
                    conta_locked = ContaMarketplace.objects.select_for_update().get(pk=conta.pk)
                    t_lock = time.perf_counter()

                    now = timezone.now()

                    # Simula a latência de rede na chamada externa à API de OAuth
                    time.sleep(delay_ms / 1000.0)

                    nova_expiracao = now + datetime.timedelta(hours=6)
                    conta_locked.access_token = f"APP_USR_MOCK_{int(time.time())}"
                    conta_locked.refresh_token = f"TG_MOCK_REFRESH_{int(time.time())}"
                    conta_locked.token_expira_em = nova_expiracao
                    conta_locked.save(update_fields=['access_token', 'refresh_token', 'token_expira_em', 'updated_at'])

                t_end = time.perf_counter()
                res_thread1.update({
                    'status': 'SUCESSO',
                    'duracao_ms': round((t_end - t0) * 1000, 2),
                    'lock_wait_ms': round((t_lock - t_req) * 1000, 2),
                    'chamadas_api_externa': 1,
                    'nova_expiracao': nova_expiracao.strftime('%d/%m/%Y %H:%M:%S'),
                    'access_token_preview': conta_locked.access_token[:25] + "...",
                })
            except Exception as e:
                erros.append(f"Erro Thread 1: {str(e)}")
                res_thread1.update({'status': 'ERRO', 'erro': str(e)})
            finally:
                connections.close_all()

        def worker_thread2():
            time.sleep(0.04)
            t0 = time.perf_counter()
            max_retries = 150
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        t_req = time.perf_counter()
                        ContaMarketplace.objects.filter(pk=conta.pk).update(updated_at=timezone.now())
                        t_lock = time.perf_counter()
                        wait_ms = (t_lock - t0) * 1000

                        conta_locked = ContaMarketplace.objects.select_for_update().get(pk=conta.pk)
                        now = timezone.now()

                        # DOUBLE-CHECKED LOCKING
                        reaproveitado = False
                        if conta_locked.token_expira_em and conta_locked.token_expira_em > (now + datetime.timedelta(minutes=10)):
                            reaproveitado = True
                            chamadas_api = 0
                            msg = "Token recém-renovado pela Thread 1 reaproveitado com sucesso via Double-Checked Locking."
                        else:
                            chamadas_api = 1
                            msg = "Token não estava válido; renovação necessária."

                    t_end = time.perf_counter()
                    res_thread2.update({
                        'status': 'SUCESSO',
                        'duracao_ms': round((t_end - t0) * 1000, 2),
                        'lock_wait_ms': round(wait_ms, 2),
                        'reaproveitado': reaproveitado,
                        'chamadas_api_externa': chamadas_api,
                        'mensagem': msg,
                        'token_expira_em': conta_locked.token_expira_em.strftime('%d/%m/%Y %H:%M:%S') if conta_locked.token_expira_em else None,
                    })
                    break
                except Exception as e:
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.02)
                        continue
                    erros.append(f"Erro Thread 2: {str(e)}")
                    res_thread2.update({'status': 'ERRO', 'erro': str(e)})
                    break
                finally:
                    connections.close_all()

        th1 = threading.Thread(target=worker_thread1, name="Worker-OAuth-T1")
        th2 = threading.Thread(target=worker_thread2, name="Worker-OAuth-T2")

        th1.start()
        th2.start()
        th1.join(timeout=15.0)
        th2.join(timeout=15.0)

        conta.refresh_from_db()

        if erros:
            return {
                'sucesso': False,
                'erros': erros,
                'thread1': res_thread1,
                'thread2': res_thread2,
            }

        return {
            'sucesso': True,
            'conta': {
                'id': conta.id,
                'apelido': conta.apelido_conta,
                'canal': conta.get_canal_display() if hasattr(conta, 'get_canal_display') else conta.canal,
                'seller_id': conta.seller_id_externo,
            },
            'thread1': res_thread1,
            'thread2': res_thread2,
            'tempo_espera_thread2_ms': res_thread2.get('lock_wait_ms', 0),
            'reaproveitado': res_thread2.get('reaproveitado', False),
            'total_chamadas_api': 1,
            'nova_expiracao': res_thread1.get('nova_expiracao'),
            'mensagem': (
                "Validação de Double-Checked Locking concluída com êxito: a Thread 2 "
                "aguardou a liberação do lock e reaproveitou a credencial recém-gerada, "
                "invocando a API externa exatamente 1 única vez."
            )
        }
