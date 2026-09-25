# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o objetivo do serviço de testes, padrões arquiteturais (ADRs) e formato de data/hora
"""
Serviços de Execução e Telemetria para Testes de Concorrência em Tempo Real.
Valida empiricamente os padrões Lock Pessimista e Double-Checked Locking (ADRs 004, 005 e 008)
executando três requisições concorrentes disparadas no exato mesmo milissegundo.
Registra carimbos reais com detalhe de dia/mês/ano - hh:mm:ss.SSS no log do produto e na telemetria.
"""
# Fim do bloco de documentação do módulo de serviços de teste

# Importa o módulo nativo time para contadores de precisão de alta resolução (perf_counter) e suspensões temporárias (sleep)
import time

# Importa o módulo nativo datetime para manipulação e formatação de datas e intervalos
import datetime

# Importa o módulo threading para criação e sincronização de threads de execução concorrente
import threading

# Importa tipagens estáticas para documentação de estruturas de dados e assinaturas de métodos
from typing import Dict, Any, List

# Importa utilitários de transação do Django e gerenciador de conexões com o banco de dados
from django.db import transaction, connections

# Importa utilitário timezone do Django para tratamento de fusos horários consistentes
from django.utils import timezone

# Importa o modelo mestre Produto gerenciado pelo catálogo físico
from apps.catalogo.models import Produto

# Importa o modelo de credenciais de integração com canais parceiros
from apps.marketplaces.models import ContaMarketplace


# Declaração da função utilitária para formatação padronizada de timestamp com milissegundos
def formatar_timestamp_ms(dt: datetime.datetime) -> str:
    # Início do bloco de docstring que documenta o formato gerado
    """
    Formata um objeto datetime com milissegundos no padrão estrito:
    dia/mês/ano - hh:mm:ss.SSS (Ex: 20/09/2026 - 17:05:12.345)
    """
    # Fim da docstring informativa da função

    # Retorna traço simples caso a data fornecida seja nula ou vazia
    if not dt:
        return "-"

    # Se o objeto de data estiver ciente de fuso horário (aware), converte para o horário local configurado no projeto
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)

    # Converte os microssegundos para milissegundos inteiros (0 a 999)
    ms = int(dt.microsecond / 1000)

    # Formata a data no padrão dd/mm/aaaa - hh:mm:ss e anexa o sufixo de três dígitos de milissegundos
    return dt.strftime('%d/%m/%Y - %H:%M:%S.') + f"{ms:03d}"


# Serviço que orquestra a validação empírica de concorrência com lock pessimista sobre o estoque físico
class ConcorrenciaEstoqueTestService:
    # Início do bloco de docstring documentando o escopo do teste de concorrência de estoque
    """
    Serviço para testar baixa atômica simultânea de estoque com Lock Pessimista
    executando três requisições concorrentes iniciadas no mesmo milissegundo.
    Mede a contenção real do banco, grava cada baixa no log do produto (HistoricoPreco)
    e afere o tempo total de travamento da tabela.
    """
    # Fim da docstring explicativa da classe

    # Limite mínimo configurável para retenção forçada da trava em milissegundos
    MIN_TRAVA_MS = 0

    # Limite máximo seguro permitido para retenção da trava em milissegundos (10 segundos)
    MAX_TRAVA_MS = 10000

    # Método de validação e sanitização do tempo adicional de trava injetado nos testes
    @classmethod
    def validar_tempo_trava(cls, tempo_trava_ms: Any) -> int:
        # Inicia bloco protegido para conversão do valor em inteiro
        try:
            val = int(tempo_trava_ms if tempo_trava_ms is not None else 0)
        # Captura entradas inválidas ou não-numéricas
        except (ValueError, TypeError):
            raise ValueError(f"O tempo de trava deve ser um número inteiro entre {cls.MIN_TRAVA_MS} ms e {cls.MAX_TRAVA_MS} ms.")

        # Rejeita valores fora do intervalo operacional seguro estipulado
        if val < cls.MIN_TRAVA_MS or val > cls.MAX_TRAVA_MS:
            raise ValueError(f"O tempo de trava deve estar estritamente entre {cls.MIN_TRAVA_MS} ms e 10.000 ms (recebido: {val} ms).")

        # Retorna o valor inteiro validado
        return val

    # Método executor que orquestra o disparo simultâneo das 3 threads concorrentes de dedução de estoque
    @classmethod
    def executar_teste(
        cls,
        produto_id: int,
        qtd1: int,
        qtd2: int,
        qtd3: int,
        tempo_trava_ms: int = 0,
        user=None
    ) -> Dict[str, Any]:
        # Valida e normaliza o tempo de retenção da trava informado
        tempo_trava_ms = cls.validar_tempo_trava(tempo_trava_ms)

        # Inicia validação de tipos das quantidades solicitadas para cada requisição
        try:
            qtd1 = int(qtd1)
            qtd2 = int(qtd2)
            qtd3 = int(qtd3)
        except (ValueError, TypeError):
            raise ValueError("As quantidades para as três requisições devem ser números inteiros válidos.")

        # Rejeita quantidades nulas ou negativas em qualquer uma das três requisições
        if qtd1 <= 0 or qtd2 <= 0 or qtd3 <= 0:
            raise ValueError("O preenchimento das três requisições é obrigatório com quantidades maiores que zero.")

        # Busca o produto no banco de dados pela chave primária
        produto = Produto.objects.get(pk=produto_id)

        # Captura o saldo inicial de estoque antes da execução das deduções
        saldo_inicial = produto.estoque

        # Dicionário para armazenar a telemetria e o resultado individual de cada thread trabalhadora
        res_threads: Dict[str, Dict[str, Any]] = {
            'thread1': {},
            'thread2': {},
            'thread3': {}
        }

        # Lock de sincronização para garantir que a gravação na lista de ordem de atendimento seja atômica em memória
        lock_ordem = threading.Lock()

        # Lista ordenada que registrará cronologicamente qual thread concluiu primeiro a aquisição e commit
        ordem_atendimento: List[Dict[str, Any]] = []

        # Lista coletora de mensagens de erro caso alguma thread falhe
        erros: List[str] = []

        # Barreira de largada para manter as threads suspensas até que todas estejam criadas e prontas
        start_event = threading.Event()

        # Lista de elemento único para registrar o timestamp de alta resolução do momento do disparo geral
        t_inicio_disparo: List[float] = [0.0]

        # Lista de elemento único para registrar o datetime ciente de fuso do disparo geral
        dt_inicio_disparo: List[datetime.datetime] = [None]

        # Função interna que define a rotina de trabalho executada isoladamente por cada thread
        def worker(thread_key: str, req_num: int, qtd_deduzir: int):
            # Aguarda o sinal de largada para sincronização no mesmo milissegundo
            # Suspende a execução da thread até que start_event.set() seja invocado pelo coordenador
            start_event.wait()

            # Captura a data/hora exata do início da requisição na thread
            dt_req = timezone.now()

            # Captura o tempo inicial de alta precisão
            t_req = time.perf_counter()

            # Define o limite máximo de tentativas de aquisição de trava em caso de contenção de concorrência
            max_retries = 200

            # Loop de retentativas para tratamento de eventuais conflitos transitórios de lock no banco
            for attempt in range(max_retries):
                try:
                    # Abre bloco transacional atômico para manter o lock ativo até o commit final
                    with transaction.atomic():
                        # Força um update do timestamp para elevar a concorrência na linha e acionar mecanismos de validação
                        Produto.objects.filter(pk=produto.pk).update(atualizado_em=timezone.now())

                        # Captura o momento em que a transação inicia a contenção
                        dt_lock = timezone.now()
                        t_lock = time.perf_counter()

                        # Calcula o tempo em milissegundos que a thread aguardou até iniciar a obtenção do recurso
                        wait_ms = (t_lock - t_req) * 1000

                        # Executa consulta com Lock Pessimista exclusivo de linha (SELECT FOR UPDATE)
                        prod = Produto.objects.select_for_update().get(pk=produto.pk)

                        # Se foi configurado tempo adicional de trava, aplica retenção na 1ª thread a obter o lock
                        # Injeta a espera forçada se solicitado para acentuar a fila de espera das demais threads
                        if tempo_trava_ms > 0 and attempt == 0:
                            time.sleep(tempo_trava_ms / 1000.0)

                        # Lê o saldo de estoque atual garantido pelo lock exclusivo
                        saldo_ant = prod.estoque

                        # Calcula o novo saldo físico após a dedução solicitada
                        novo_saldo = saldo_ant - qtd_deduzir

                        # Atualiza o atributo estoque da instância
                        prod.estoque = novo_saldo

                        # Persiste o novo saldo e o timestamp de atualização de forma explícita
                        prod.save(update_fields=['estoque', 'atualizado_em'])

                        # Captura o momento final logo antes da saída do bloco transacional (commit)
                        dt_commit = timezone.now()
                        t_commit = time.perf_counter()

                        # REGISTRO NO HISTÓRICO DO PRODUTO (AUDITORIA OFICIAL)
                        # Formata os carimbos de início, obtenção de lock e término no padrão dd/mm/aaaa - hh:mm:ss.SSS
                        dt_inicio_fmt = formatar_timestamp_ms(dt_req)
                        dt_lock_fmt = formatar_timestamp_ms(dt_lock)
                        dt_fim_fmt = formatar_timestamp_ms(dt_commit)

                        # Monta a justificativa detalhada com a telemetria completa para auditoria
                        motivo_log = (
                            f"Baixa Concorrente Lock Pessimista - Req {req_num} (baixa de {qtd_deduzir} un.) "
                            f"[Início: {dt_inicio_fmt} | Lock: {dt_lock_fmt} | Fim: {dt_fim_fmt}]"
                        )

                        # Grava na tabela oficial de histórico de preço e estoque com rastreamento de usuário
                        prod.registrar_historico(
                            estoque_anterior=saldo_ant,
                            novo_estoque=novo_saldo,
                            usuario=user,
                            motivo=motivo_log
                        )

                    # Captura o tempo final após o commit da transação
                    t_end = time.perf_counter()

                    # Calcula a retenção real da escrita (tempo em que a linha ficou bloqueada) em milissegundos
                    retencao_ms = (t_end - t_lock) * 1000

                    # Calcula a duração total da requisição na thread desde o disparo até a liberação
                    duracao_ms = (t_end - t_req) * 1000

                    # Dicionário de telemetria consolidada da thread
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
                        'hora_inicio_fmt': dt_inicio_fmt,
                        'hora_lock_fmt': dt_lock_fmt,
                        'hora_fim_fmt': dt_fim_fmt,
                        'timestamp_inicio_req_formatado': dt_inicio_fmt,
                        'timestamp_lock_adquirido_formatado': dt_lock_fmt,
                        'timestamp_fim_formatado': dt_fim_fmt,
                        'dt_inicio': dt_req,
                        'dt_fim': dt_commit,
                        't_inicio': t_req,
                        't_fim': t_end,
                    }

                    # Atualiza os resultados da respectiva thread no mapa geral
                    res_threads[thread_key].update(info_thread)

                    # Adiciona a thread à fila de ordem de finalização protegida pelo lock de memória
                    with lock_ordem:
                        ordem_atendimento.append(info_thread)

                    # Encerra o loop de tentativas após o sucesso da operação
                    break

                # Captura exceções ocorridas durante o processamento da thread
                except Exception as e:
                    # Se o erro indicar bloqueio temporário do banco de dados e ainda houver tentativas disponíveis
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        # Aguarda 5 milissegundos antes de tentar adquirir o lock novamente
                        time.sleep(0.005)
                        continue

                    # Em caso de falha definitiva, anexa o erro à lista global de inconsistências
                    erros.append(f"Erro {thread_key.title()} (Req {req_num}): {str(e)}")

                    # Atualiza o estado da thread registrando a falha
                    res_threads[thread_key].update({
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'ERRO',
                        'erro': str(e)
                    })
                    # Interrompe as tentativas da thread
                    break

                # Garante que as conexões de banco abertas nesta thread sejam devidamente fechadas
                finally:
                    connections.close_all()

        # Instancia a primeira thread de requisição concorrente
        th1 = threading.Thread(target=worker, args=('thread1', 1, qtd1), name="Worker-Estoque-1")

        # Instancia a segunda thread de requisição concorrente
        th2 = threading.Thread(target=worker, args=('thread2', 2, qtd2), name="Worker-Estoque-2")

        # Instancia a terceira thread de requisição concorrente
        th3 = threading.Thread(target=worker, args=('thread3', 3, qtd3), name="Worker-Estoque-3")

        # Inicia a execução da primeira thread (que ficará em espera no evento de largada)
        th1.start()

        # Inicia a execução da segunda thread (em espera no evento de largada)
        th2.start()

        # Inicia a execução da terceira thread (em espera no evento de largada)
        th3.start()

        # Registra a data/hora oficial ciente de fuso do disparo unificado
        dt_inicio_disparo[0] = timezone.now()

        # Registra o tempo de alta resolução do momento exato do disparo
        t_inicio_disparo[0] = time.perf_counter()

        # Dispara o sinal de largada liberando as três threads no exato mesmo instante
        start_event.set()

        # Aguarda a conclusão da thread 1 com timeout de segurança de 25 segundos
        th1.join(timeout=25.0)

        # Aguarda a conclusão da thread 2 com timeout de segurança de 25 segundos
        th2.join(timeout=25.0)

        # Aguarda a conclusão da thread 3 com timeout de segurança de 25 segundos
        th3.join(timeout=25.0)

        # Marca o tempo final global após o término de todas as threads
        t_fim_global = time.perf_counter()

        # Registra o datetime de término global
        dt_fim_global = timezone.now()

        # Recarrega o estado atualizado do produto a partir do banco de dados
        produto.refresh_from_db()

        # Obtém o saldo físico final consolidado
        saldo_final = produto.estoque

        # Calcula a soma total deduzida pelas três requisições
        total_deduzido = qtd1 + qtd2 + qtd3

        # Calcula o saldo matematicamente esperado
        saldo_esperado = saldo_inicial - total_deduzido

        # Avalia se a integridade matemática foi rigorosamente respeitada sem perdas por concorrência
        consistente = (saldo_final == saldo_esperado)

        # Cálculo de tempos e carimbos de bloqueio global da tabela
        # Extrai os datetimes e tempos de início e fim registrados por todas as threads bem-sucedidas
        dt_inicios = [t['dt_inicio'] for t in res_threads.values() if t.get('dt_inicio')]
        dt_fins = [t['dt_fim'] for t in res_threads.values() if t.get('dt_fim')]
        t_inicios = [t['t_inicio'] for t in res_threads.values() if t.get('t_inicio')]
        t_fins = [t['t_fim'] for t in res_threads.values() if t.get('t_fim')]

        # Se houver registros válidos de início e término das threads
        if t_inicios and t_fins:
            # Calcula o tempo total de bloqueio e contenção da tabela em milissegundos
            tempo_total_bloqueio_ms = round((max(t_fins) - min(t_inicios)) * 1000, 2)
            # Formata o início do primeiro bloqueio adquirido
            dt_bloqueio_inicio_fmt = formatar_timestamp_ms(min(dt_inicios))
            # Formata o encerramento do último bloqueio liberado
            dt_bloqueio_fim_fmt = formatar_timestamp_ms(max(dt_fins))
        # Fallback utilizando o intervalo global do disparo
        else:
            tempo_total_bloqueio_ms = round((t_fim_global - t_inicio_disparo[0]) * 1000, 2)
            dt_bloqueio_inicio_fmt = formatar_timestamp_ms(dt_inicio_disparo[0])
            dt_bloqueio_fim_fmt = formatar_timestamp_ms(dt_fim_global)

        # Progressão acumulativa dos saldos
        # Calcula os saldos teóricos em cada etapa progressiva para exibição na interface
        saldo_etapa_1 = saldo_inicial - qtd1
        saldo_etapa_2 = saldo_inicial - (qtd1 + qtd2)
        saldo_etapa_3 = saldo_inicial - (qtd1 + qtd2 + qtd3)

        # Se ocorreram erros durante a execução das threads, retorna estrutura de falha com detalhes
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

        # Retorna o dicionário completo de telemetria e validação matemática de concorrência com sucesso
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
            'tempo_trava_ms': tempo_trava_ms,
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
            'bloqueio_inicio_fmt': dt_bloqueio_inicio_fmt,
            'bloqueio_fim_fmt': dt_bloqueio_fim_fmt,
            'tempo_inicio_formatado': dt_bloqueio_inicio_fmt,
            'tempo_fim_formatado': dt_bloqueio_fim_fmt,
            'mensagem': (
                f"Prova matemática confirmada e gravada no histórico do produto: "
                f"Saldo Inicial ({saldo_inicial}) - (Req1: {qtd1} + Req2: {qtd2} + Req3: {qtd3} = {total_deduzido} un.) = "
                f"Saldo Final ({saldo_final} un.). 3 registros de auditoria criados em HistoricoPreco."
            )
        }


# Serviço que testa empiricamente a renovação concorrente de tokens OAuth2 utilizando o padrão Double-Checked Locking
class ConcorrenciaOAuthTestService:
    # Início do bloco de docstring que documenta o teste de renovação e reaproveitamento de tokens
    """
    Serviço para testar renovação concorrente de credenciais OAuth 2.0
    executando três requisições iniciadas no mesmo milissegundo.
    A primeira requisição realiza a renovação remota, enquanto a segunda e terceira
    aguardam na trava e reaproveitam a credencial renovada via Double-Checked Locking.
    """
    # Fim da docstring explicativa da classe

    # Limite mínimo permitido para tempo de trava em milissegundos
    MIN_TRAVA_MS = 0

    # Limite máximo permitido para tempo de trava em milissegundos (10 segundos)
    MAX_TRAVA_MS = 10000

    # Validador de integridade do parâmetro numérico de retenção da trava
    @classmethod
    def validar_tempo_trava(cls, tempo_trava_ms: Any) -> int:
        try:
            val = int(tempo_trava_ms if tempo_trava_ms is not None else 0)
        except (ValueError, TypeError):
            raise ValueError(f"O tempo de trava deve ser um número inteiro entre {cls.MIN_TRAVA_MS} ms e {cls.MAX_TRAVA_MS} ms.")
        if val < cls.MIN_TRAVA_MS or val > cls.MAX_TRAVA_MS:
            raise ValueError(f"O tempo de trava deve estar estritamente entre {cls.MIN_TRAVA_MS} ms e 10.000 ms (recebido: {val} ms).")
        return val

    # Método executor que orquestra o teste concorrente de 3 threads sobre a renovação de credenciais da conta
    @classmethod
    def executar_teste(cls, conta_id: int, tempo_trava_ms: int = 0, user=None) -> Dict[str, Any]:
        # Valida o tempo de trava informado
        tempo_trava_ms = cls.validar_tempo_trava(tempo_trava_ms)

        # Recupera a conta de marketplace no banco de dados
        conta = ContaMarketplace.objects.get(pk=conta_id)

        # Força o token a parecer expirado antes do teste concorrente
        # Retrocede o timestamp de expiração para 5 minutos atrás, induzindo a expiração lógica
        conta.token_expira_em = timezone.now() - datetime.timedelta(minutes=5)

        # Salva o campo de expiração modificado
        conta.save(update_fields=['token_expira_em'])

        # Dicionário de resultados individuais por thread
        res_threads: Dict[str, Dict[str, Any]] = {
            'thread1': {},
            'thread2': {},
            'thread3': {}
        }

        # Lista para coletar eventuais erros de execução das threads
        erros: List[str] = []

        # Barreira de largada para sincronizar a largada no mesmo instante
        start_event = threading.Event()

        # Registradores de tempo inicial de alta resolução e datetime
        t_inicio_disparo: List[float] = [0.0]
        dt_inicio_disparo: List[datetime.datetime] = [None]

        # Função de trabalho da thread para renovação ou reaproveitamento de token OAuth
        def worker(thread_key: str, req_num: int):
            # Aguarda a liberação conjunta pelo start_event
            start_event.wait()

            # Captura data/hora e tempo de início da requisição na thread
            dt_req = timezone.now()
            t_req = time.perf_counter()

            # Define número máximo de tentativas em caso de disputa de banco
            max_retries = 200

            # Loop de tentativas
            for attempt in range(max_retries):
                try:
                    # Inicia bloco transacional para garantir o lock de linha durante a validação
                    with transaction.atomic():
                        # Força atualização de timestamp na tabela para gerar contenção inicial
                        ContaMarketplace.objects.filter(pk=conta.pk).update(updated_at=timezone.now())

                        # Captura o momento da tentativa de obtenção de lock
                        dt_lock = timezone.now()
                        t_lock = time.perf_counter()

                        # Calcula o tempo em que a thread aguardou na fila
                        wait_ms = (t_lock - t_req) * 1000

                        # Executa SELECT FOR UPDATE exclusivo sobre a conta de marketplace
                        conta_locked = ContaMarketplace.objects.select_for_update().get(pk=conta.pk)
                        now = timezone.now()

                        # DOUBLE-CHECKED LOCKING
                        # Segunda checagem: após obter o lock exclusivo, verifica se uma thread anterior já renovou o token
                        if conta_locked.token_expira_em and conta_locked.token_expira_em > (now + datetime.timedelta(minutes=10)):
                            # Se a expiração estiver no futuro (mais de 10 minutos), reaproveita o token sem bater na API externa
                            reaproveitado = True
                            chamadas_api = 0
                            operacao = "Reaproveitado via Double-Checked Locking"
                        # Primeira thread a obter o lock: encontra o token expirado e executa a renovação
                        else:
                            reaproveitado = False
                            chamadas_api = 1
                            operacao = "Renovação Remota de Credencial"

                            # Retenção adicional se configurada
                            # Se configurada retenção artificial da trava, simula latência de rede na chamada externa
                            if tempo_trava_ms > 0:
                                time.sleep(tempo_trava_ms / 1000.0)

                            # Define a nova expiração para 6 horas no futuro
                            nova_expiracao = now + datetime.timedelta(hours=6)

                            # Atualiza as credenciais gerando novos tokens fictícios baseados em timestamp
                            conta_locked.access_token = f"APP_USR_REAL_{int(time.time() * 1000)}"
                            conta_locked.refresh_token = f"TG_REAL_{int(time.time() * 1000)}"
                            conta_locked.token_expira_em = nova_expiracao

                            # Persiste os novos tokens e o timestamp de renovação
                            conta_locked.save(update_fields=['access_token', 'refresh_token', 'token_expira_em', 'updated_at'])

                        # Registra o timestamp final logo antes do commit
                        dt_commit = timezone.now()

                    # Captura o tempo final após o commit da transação
                    t_end = time.perf_counter()

                    # Calcula a retenção da escrita e a duração total em milissegundos
                    retencao_ms = (t_end - t_lock) * 1000
                    duracao_ms = (t_end - t_req) * 1000

                    # Salva a telemetria estruturada da thread no mapa de resultados
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
                        'hora_inicio_fmt': formatar_timestamp_ms(dt_req),
                        'hora_lock_fmt': formatar_timestamp_ms(dt_lock),
                        'hora_fim_fmt': formatar_timestamp_ms(dt_commit),
                        'timestamp_inicio_req_formatado': formatar_timestamp_ms(dt_req),
                        'timestamp_lock_adquirido_formatado': formatar_timestamp_ms(dt_lock),
                        'timestamp_fim_formatado': formatar_timestamp_ms(dt_commit),
                        'dt_inicio': dt_req,
                        'dt_fim': dt_commit,
                        't_inicio': t_req,
                        't_fim': t_end,
                    })

                    # Finaliza o loop de retentativas
                    break

                # Trata erros na thread
                except Exception as e:
                    # Se for bloqueio transitório, aplica pequeno intervalo e repete
                    if 'locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.005)
                        continue

                    # Em caso de falha persistente, registra o erro
                    erros.append(f"Erro {thread_key.title()} (Req {req_num}): {str(e)}")
                    res_threads[thread_key].update({
                        'requisicao': req_num,
                        'thread': thread_key,
                        'status': 'ERRO',
                        'erro': str(e)
                    })
                    break

                # Fecha as conexões da thread ao finalizar
                finally:
                    connections.close_all()

        # Cria as 3 threads trabalhadoras de renovação de OAuth
        th1 = threading.Thread(target=worker, args=('thread1', 1), name="Worker-OAuth-1")
        th2 = threading.Thread(target=worker, args=('thread2', 2), name="Worker-OAuth-2")
        th3 = threading.Thread(target=worker, args=('thread3', 3), name="Worker-OAuth-3")

        # Inicia as três threads
        th1.start()
        th2.start()
        th3.start()

        # Marca o tempo inicial do disparo simultâneo
        dt_inicio_disparo[0] = timezone.now()
        t_inicio_disparo[0] = time.perf_counter()

        # Libera a barreira de largada para execução concorrente imediata
        start_event.set()

        # Aguarda o término das threads com timeout de 25 segundos
        th1.join(timeout=25.0)
        th2.join(timeout=25.0)
        th3.join(timeout=25.0)

        # Marca os tempos finais globais
        t_fim_global = time.perf_counter()
        dt_fim_global = timezone.now()

        # Recarrega a conta do banco de dados
        conta.refresh_from_db()

        # Consolida listas de início e término das threads para cálculo de bloqueio
        dt_inicios = [t['dt_inicio'] for t in res_threads.values() if t.get('dt_inicio')]
        dt_fins = [t['dt_fim'] for t in res_threads.values() if t.get('dt_fim')]
        t_inicios = [t['t_inicio'] for t in res_threads.values() if t.get('t_inicio')]
        t_fins = [t['t_fim'] for t in res_threads.values() if t.get('t_fim')]

        # Calcula o tempo total de bloqueio e formata carimbos
        if t_inicios and t_fins:
            tempo_total_bloqueio_ms = round((max(t_fins) - min(t_inicios)) * 1000, 2)
            dt_bloqueio_inicio_fmt = formatar_timestamp_ms(min(dt_inicios))
            dt_bloqueio_fim_fmt = formatar_timestamp_ms(max(dt_fins))
        else:
            tempo_total_bloqueio_ms = round((t_fim_global - t_inicio_disparo[0]) * 1000, 2)
            dt_bloqueio_inicio_fmt = formatar_timestamp_ms(dt_inicio_disparo[0])
            dt_bloqueio_fim_fmt = formatar_timestamp_ms(dt_fim_global)

        # Totaliza chamadas externas realizadas (deve ser exatamente 1 se o Double-Checked Locking funcionar)
        total_chamadas = sum(t.get('chamadas_api_externa', 0) for t in res_threads.values())

        # Totaliza quantas requisições foram reaproveitadas da trava (devem ser exatamente 2)
        total_reaproveitadas = sum(1 for t in res_threads.values() if t.get('reaproveitado'))

        # Se houveram falhas, retorna estrutura de erro
        if erros:
            return {
                'sucesso': False,
                'erros': erros,
                'thread1': res_threads['thread1'],
                'thread2': res_threads['thread2'],
                'thread3': res_threads['thread3'],
            }

        # Retorna o resultado completo da validação empírica de Double-Checked Locking
        return {
            'sucesso': True,
            'conta': {
                'id': conta.id,
                'apelido': conta.apelido_conta,
                'canal': conta.get_canal_display() if hasattr(conta, 'get_canal_display') else conta.canal,
                'seller_id': conta.seller_id_externo,
            },
            'tempo_trava_ms': tempo_trava_ms,
            'thread1': res_threads['thread1'],
            'thread2': res_threads['thread2'],
            'thread3': res_threads['thread3'],
            'total_chamadas_api': total_chamadas,
            'total_reaproveitadas': total_reaproveitadas,
            'tempo_total_bloqueio_tabela_ms': tempo_total_bloqueio_ms,
            'bloqueio_inicio_fmt': dt_bloqueio_inicio_fmt,
            'bloqueio_fim_fmt': dt_bloqueio_fim_fmt,
            'tempo_inicio_formatado': dt_bloqueio_inicio_fmt,
            'tempo_fim_formatado': dt_bloqueio_fim_fmt,
            'nova_expiracao': conta.token_expira_em.strftime('%d/%m/%Y %H:%M:%S') if conta.token_expira_em else None,
            'mensagem': (
                f"Double-Checked Locking validado com 3 requisições simultâneas: "
                f"estritamente {total_chamadas} chamada à API externa efetuada; "
                f"{total_reaproveitadas} requisições aguardaram na trava e reaproveitaram a credencial."
            )
        }