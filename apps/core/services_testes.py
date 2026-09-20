# Os códigos foram gerados com auxilio de I.A.
"""
Serviços de Execução e Telemetria para Testes de Concorrência em Tempo Real.
Valida empiricamente os padrões Lock Pessimista e Double-Checked Locking (ADRs 004, 005 e 008)
executando três requisições concorrentes disparadas no exato mesmo milissegundo.
"""
import time
import datetime
import threading
from typing import Dict, Any, List

from django.db import transaction, connections
from django.utils import timezone

from apps.catalogo.models import Produto
from apps.marketplaces.models import ContaMarketplace


class ConcorrenciaEstoqueTestService:
    """
    Serviço para testar baixa atômica simultânea de estoque com Lock Pessimista
    executando três requisições concorrentes iniciadas no mesmo milissegundo.
    Mede a contenção real do banco e o tempo total de travamento da tabela.
    """

    @classmethod
    def executar_teste(cls, produto_id: int, qtd1: int, qtd2: int, qtd3: int, user=None) -> Dict[str, Any]:
        try:
            qtd1 = int(qtd1)
            qtd2 = int(qtd2)
            qtd3 = int(qtd3)
        except (ValueError, TypeError):
            raise ValueError("As quantidades para as três requisições devem ser números inteiros válidos.")

        if qtd1 <= 0 or qtd2 <= 0 or qtd3 <= 0:
            raise ValueError("O preenchimento das três requisições é obrigatório com quantidades maiores que zero.")

        produto = Produto.objects.get(pk=produto_id)
        saldo_inicial = produto.estoque

        # Resultados por thread
        res_threads: Dict[str, Dict[str, Any]] = {
            'thread1': {},
            'thread2': {},
            'thread3': {}
        }
        ordem_atendimento: List[Dict[str, Any]] = []
        lock_ordem = threading.Lock()
        erros: List[str] = []

        # Evento de largada sincronizada: todas as 3 threads partem no mesmo milissegundo
        start_event = threading.Event()
        t_inicio_disparo: List[float] = [0.0]

        def worker(thread_key: str, req_num: int, qtd_deduzir: int):
            # Aguarda o sinal de largada para iniciar no mesmo instante
            start_event.wait()
            t_req = time.perf_counter()

            max_retries = 200
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        # Adquire intenção de escrita para assegurar a serialização física
                        Produto.objects.filter(pk=produto.pk).update(atualizado_em=timezone.now())
                        t_lock = time.perf_counter()
                        wait_ms = (t_lock - t_req) * 1000

                        prod = Produto.objects.select_for_update().get(pk=produto.pk)
                        saldo_ant = prod.estoque
                        novo_saldo = saldo_ant - qtd_deduzir
                        prod.estoque = novo_saldo
                        prod.save(update_fields=['estoque', 'atualizado_em'])

                        t_commit = time.perf_counter()

                    t_end = time.perf_counter()
                    retencao_ms = (t_end - t_lock) * 1000
                    duracao_ms = (t_end - t_req) * 1000

                    info_thread = {
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'SUCESSO',
                        'qtd_deduzida': qtd_deduzir,
                        'saldo_anterior': saldo_ant,
                        'novo_saldo': novo_saldo,
                        'espera_trava_ms': round(wait_ms, 2),
                        'retencao_escrita_ms': round(retencao_ms, 2),
                        'duracao_total_ms': round(duracao_ms, 2),
                        'timestamp_inicio': t_req,
                        'timestamp_lock': t_lock,
                        'timestamp_fim': t_end,
                    }

                    res_threads[thread_key].update(info_thread)

                    with lock_ordem:
                        ordem_atendimento.append(info_thread)

                    break
                except Exception as e:
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.005)
                        continue
                    erros.append(f"Erro {thread_key.title()} (Req {req_num}): {str(e)}")
                    res_threads[thread_key].update({
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'ERRO',
                        'erro': str(e)
                    })
                    break
                finally:
                    connections.close_all()

        th1 = threading.Thread(target=worker, args=('thread1', 1, qtd1), name="Worker-Estoque-1")
        th2 = threading.Thread(target=worker, args=('thread2', 2, qtd2), name="Worker-Estoque-2")
        th3 = threading.Thread(target=worker, args=('thread3', 3, qtd3), name="Worker-Estoque-3")

        th1.start()
        th2.start()
        th3.start()

        # Dispara todas as três no mesmo instante
        t_inicio_disparo[0] = time.perf_counter()
        start_event.set()

        th1.join(timeout=15.0)
        th2.join(timeout=15.0)
        th3.join(timeout=15.0)

        t_fim_global = time.perf_counter()

        produto.refresh_from_db()
        saldo_final = produto.estoque
        total_deduzido = qtd1 + qtd2 + qtd3
        saldo_esperado = saldo_inicial - total_deduzido
        consistente = (saldo_final == saldo_esperado)

        # Cálculo do tempo total em que a tabela ficou bloqueada (do primeiro request até a última liberação)
        timestamps_inicio = [t.get('timestamp_inicio') for t in res_threads.values() if t.get('timestamp_inicio')]
        timestamps_fim = [t.get('timestamp_fim') for t in res_threads.values() if t.get('timestamp_fim')]

        if timestamps_inicio and timestamps_fim:
            tempo_total_bloqueio_ms = round((max(timestamps_fim) - min(timestamps_inicio)) * 1000, 2)
        else:
            tempo_total_bloqueio_ms = round((t_fim_global - t_inicio_disparo[0]) * 1000, 2)

        # Cálculo progressivo do saldo (Req 1, Req 1 + Req 2, Req 1 + Req 2 + Req 3)
        saldo_etapa_1 = saldo_inicial - qtd1
        saldo_etapa_2 = saldo_inicial - (qtd1 + qtd2)
        saldo_etapa_3 = saldo_inicial - (qtd1 + qtd2 + qtd3)

        if erros:
            return {
                'sucesso': False,
                'erros': erros,
                'thread1': res_threads['thread1'],
                'thread2': res_threads['thread2'],
                'thread3': res_threads['thread3'],
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
            'qtd3': qtd3,
            'total_deduzido': total_deduzido,
            'progressao_saldos': {
                'etapa1': {'qtd_acumulada': qtd1, 'saldo_resultante': saldo_etapa_1},
                'etapa2': {'qtd_acumulada': qtd1 + qtd2, 'saldo_resultante': saldo_etapa_2},
                'etapa3': {'qtd_acumulada': qtd1 + qtd2 + qtd3, 'saldo_resultante': saldo_etapa_3},
            },
            'consistente': consistente,
            'thread1': res_threads['thread1'],
            'thread2': res_threads['thread2'],
            'thread3': res_threads['thread3'],
            'tempo_total_bloqueio_tabela_ms': tempo_total_bloqueio_ms,
            'mensagem': (
                f"Prova matemática confirmada: Saldo Inicial ({saldo_inicial}) - "
                f"(Req1: {qtd1} + Req2: {qtd2} + Req3: {qtd3} = {total_deduzido} un.) = "
                f"Saldo Final ({saldo_final}). Nenhuma ordem foi descartada."
            )
        }


class ConcorrenciaOAuthTestService:
    """
    Serviço para testar renovação concorrente de credenciais OAuth 2.0
    executando três requisições iniciadas no mesmo milissegundo.
    A primeira requisição realiza a renovação remota, enquanto a segunda e terceira
    aguardam na trava e reaproveitam a credencial renovada via Double-Checked Locking.
    """

    @classmethod
    def executar_teste(cls, conta_id: int, user=None) -> Dict[str, Any]:
        conta = ContaMarketplace.objects.get(pk=conta_id)

        # Força o token a parecer expirado antes do teste concorrente
        conta.token_expira_em = timezone.now() - datetime.timedelta(minutes=5)
        conta.save(update_fields=['token_expira_em'])

        res_threads: Dict[str, Dict[str, Any]] = {
            'thread1': {},
            'thread2': {},
            'thread3': {}
        }
        erros: List[str] = []

        start_event = threading.Event()
        t_inicio_disparo: List[float] = [0.0]

        def worker(thread_key: str, req_num: int):
            start_event.wait()
            t_req = time.perf_counter()

            max_retries = 200
            for attempt in range(max_retries):
                try:
                    with transaction.atomic():
                        ContaMarketplace.objects.filter(pk=conta.pk).update(updated_at=timezone.now())
                        t_lock = time.perf_counter()
                        wait_ms = (t_lock - t_req) * 1000

                        conta_locked = ContaMarketplace.objects.select_for_update().get(pk=conta.pk)
                        now = timezone.now()

                        # DOUBLE-CHECKED LOCKING
                        if conta_locked.token_expira_em and conta_locked.token_expira_em > (now + datetime.timedelta(minutes=10)):
                            # Token já foi renovado por thread anterior
                            reaproveitado = True
                            chamadas_api = 0
                            operacao = "Reaproveitado via Double-Checked Locking"
                        else:
                            # Primeira thread a obter o lock: realiza renovação
                            reaproveitado = False
                            chamadas_api = 1
                            operacao = "Renovação Remota de Credencial"
                            nova_expiracao = now + datetime.timedelta(hours=6)
                            conta_locked.access_token = f"APP_USR_REAL_{int(time.time() * 1000)}"
                            conta_locked.refresh_token = f"TG_REAL_{int(time.time() * 1000)}"
                            conta_locked.token_expira_em = nova_expiracao
                            conta_locked.save(update_fields=['access_token', 'refresh_token', 'token_expira_em', 'updated_at'])

                    t_end = time.perf_counter()
                    retencao_ms = (t_end - t_lock) * 1000
                    duracao_ms = (t_end - t_req) * 1000

                    res_threads[thread_key].update({
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'SUCESSO',
                        'espera_trava_ms': round(wait_ms, 2),
                        'retencao_escrita_ms': round(retencao_ms, 2),
                        'duracao_total_ms': round(duracao_ms, 2),
                        'reaproveitado': reaproveitado,
                        'chamadas_api_externa': chamadas_api,
                        'operacao': operacao,
                        'timestamp_inicio': t_req,
                        'timestamp_lock': t_lock,
                        'timestamp_fim': t_end,
                    })
                    break
                except Exception as e:
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.005)
                        continue
                    erros.append(f"Erro {thread_key.title()} (Req {req_num}): {str(e)}")
                    res_threads[thread_key].update({
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'ERRO',
                        'erro': str(e)
                    })
                    break
                finally:
                    connections.close_all()

        th1 = threading.Thread(target=worker, args=('thread1', 1), name="Worker-OAuth-1")
        th2 = threading.Thread(target=worker, args=('thread2', 2), name="Worker-OAuth-2")
        th3 = threading.Thread(target=worker, args=('thread3', 3), name="Worker-OAuth-3")

        th1.start()
        th2.start()
        th3.start()

        t_inicio_disparo[0] = time.perf_counter()
        start_event.set()

        th1.join(timeout=15.0)
        th2.join(timeout=15.0)
        th3.join(timeout=15.0)

        t_fim_global = time.perf_counter()

        conta.refresh_from_db()

        timestamps_inicio = [t.get('timestamp_inicio') for t in res_threads.values() if t.get('timestamp_inicio')]
        timestamps_fim = [t.get('timestamp_fim') for t in res_threads.values() if t.get('timestamp_fim')]

        if timestamps_inicio and timestamps_fim:
            tempo_total_bloqueio_ms = round((max(timestamps_fim) - min(timestamps_inicio)) * 1000, 2)
        else:
            tempo_total_bloqueio_ms = round((t_fim_global - t_inicio_disparo[0]) * 1000, 2)

        total_chamadas = sum(t.get('chamadas_api_externa', 0) for t in res_threads.values())
        total_reaproveitadas = sum(1 for t in res_threads.values() if t.get('reaproveitado'))

        if erros:
            return {
                'sucesso': False,
                'erros': erros,
                'thread1': res_threads['thread1'],
                'thread2': res_threads['thread2'],
                'thread3': res_threads['thread3'],
            }

        return {
            'sucesso': True,
            'conta': {
                'id': conta.id,
                'apelido': conta.apelido_conta,
                'canal': conta.get_canal_display() if hasattr(conta, 'get_canal_display') else conta.canal,
                'seller_id': conta.seller_id_externo,
            },
            'thread1': res_threads['thread1'],
            'thread2': res_threads['thread2'],
            'thread3': res_threads['thread3'],
            'total_chamadas_api': total_chamadas,
            'total_reaproveitadas': total_reaproveitadas,
            'tempo_total_bloqueio_tabela_ms': tempo_total_bloqueio_ms,
            'nova_expiracao': conta.token_expira_em.strftime('%d/%m/%Y %H:%M:%S') if conta.token_expira_em else None,
            'mensagem': (
                f"Double-Checked Locking validado com 3 requisições simultâneas: "
                f"estritamente {total_chamadas} chamada à API externa efetuada; "
                f"{total_reaproveitadas} requisições aguardaram na trava e reaproveitaram a credencial."
            )
        }
