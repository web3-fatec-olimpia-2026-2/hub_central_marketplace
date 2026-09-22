# Os códigos foram gerados com auxilio de I.A.

# Importa o módulo padrão logging para registrar advertências, fluxos e exceções do sistema
import logging

# Importa o módulo threading para criar e gerenciar estados locais isolados por thread (Thread-Local Storage)
import threading

# Importa os sinais pre_save (executado antes do commit/save) e post_save (executado após a gravação no banco) do Django
from django.db.models.signals import pre_save, post_save

# Importa o decorador receiver utilizado para registrar funções ouvintes de sinais do dispatcher do Django
from django.dispatch import receiver

# Importa o modelo Produto que representa o item físico do catálogo cuja alteração dispara os sinais
from apps.catalogo.models import Produto

# Importa a classe de serviço responsável pelas sincronizações seguras de anúncios nos canais remotos
from apps.anuncios.services import AnuncioSincronizacaoService

# Inicializa o logger para o módulo corrente
logger = logging.getLogger(__name__)

# Instancia o objeto thread-local que armazenará variáveis com escopo estrito à thread em execução
_local = threading.local()


# Função utilitária para inspecionar se os sinais estão silenciados no contexto da thread corrente
def is_signals_muted() -> bool:
    """Verifica se os sinais de sincronização estão temporariamente desativados na thread atual."""
    # Retorna o valor booleano do atributo 'mute_signals' ou False como padrão caso ainda não tenha sido definido
    return getattr(_local, 'mute_signals', False)


# Context manager customizado para suprimir a propagação de eventos de sincronização em operações em massa ou internas
class mute_sincronizacao_signals:
    """
    Context manager para desativar temporariamente o disparo de sinais de sincronização.
    Útil em imports massivos, rotinas de carga de dados e execuções concorrentes.
    """
    # Método executado ao abrir o bloco 'with', ativando a flag de silenciamento na thread
    def __enter__(self):
        # Define 'mute_signals' como True na memória da thread corrente
        _local.mute_signals = True
        # Retorna a própria instância do context manager
        return self

    # Método executado automaticamente ao encerrar o bloco 'with', mesmo em caso de exceções
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restaura a flag para False, reabilitando o processamento normal dos sinais
        _local.mute_signals = False


# Conecta a função ao evento pre_save disparado exclusivamente pelo modelo Produto
@receiver(pre_save, sender=Produto)
def identificar_alteracao_produto(sender, instance: Produto, **kwargs):
    """
    O QUE FAZ: Identifica antes do salvamento se houve alteração nos campos estoque e/ou preço do Produto.
    POR QUE FAZ: Evita disparar chamadas de rede externas e recálculos desnecessários se os valores forem idênticos.
    """
    # Avalia se os sinais globais estão silenciados na thread ou se a instância contém instrução de ignorar sinais
    if is_signals_muted() or getattr(instance, '_ignorar_sinais_sincronizacao', False):
        # Desmarca as flags transitórias de alteração
        instance._estoque_alterado = False
        # Desmarca a flag de preço alterado
        instance._preco_alterado = False
        # Encerra prematuramente o listener sem efetuar consultas adicionais
        return

    # Se a instância ainda não possuir chave primária, significa que é um novo produto sendo inserido
    if not instance.pk:
        # Novo produto sendo inserido
        # Define que houve alteração de estoque (inserção inicial)
        instance._estoque_alterado = True
        # Define que houve alteração de preço (inserção inicial)
        instance._preco_alterado = True
        # Encerra o pre_save para novos produtos
        return

    # Inicia bloco protegido para consultar o estado anterior persistido no banco
    try:
        # Busca no banco apenas os valores atuais de estoque e preço do registro antes do commit da alteração
        antigo = Produto.objects.filter(pk=instance.pk).values('estoque', 'preco').first()
        # Se encontrou o registro prévio no banco
        if antigo:
            # Compara se o estoque mudou em relação ao valor em memória que está sendo salvo
            instance._estoque_alterado = (antigo['estoque'] != instance.estoque)
            # Compara se o preço de venda mudou em relação ao valor em memória que está sendo salvo
            instance._preco_alterado = (antigo['preco'] != instance.preco)
        # Fallback defensivo: se o registro não foi localizado pelo filtro
        else:
            # Assume que houve modificação de estoque por segurança
            instance._estoque_alterado = True
            # Assume que houve modificação de preço por segurança
            instance._preco_alterado = True
    # Captura possíveis exceções de infraestrutura de banco de dados
    except Exception as exc:
        # Registra advertência informando que não foi possível comparar com o estado antigo
        logger.warning(f"Falha ao checar estado anterior do produto {instance.pk}: {exc}")
        # Em caso de falha na checagem, assume de forma defensiva que ambos os atributos mudaram
        instance._estoque_alterado = True
        instance._preco_alterado = True


# Conecta a função ao evento post_save disparado logo após a conclusão da gravação do Produto
@receiver(post_save, sender=Produto)
def disparar_sincronizacao_anuncios_produto(sender, instance: Produto, created: bool, **kwargs):
    """
    O QUE FAZ: Identifica mutações de estoque/preço no Produto e marca os anúncios vinculados como PENDENTE de envio.
    POR QUE FAZ: Desacopla o envio automático para a API externa, garantindo que o envio só ocorra com confirmação explícita do usuário.
    """
    # Verifica novamente se a execução de sinais está silenciada ou se a instância solicitou supressão
    if is_signals_muted() or getattr(instance, '_ignorar_sinais_sincronizacao', False):
        # Aborta a execução do sinal sem realizar ações secundárias
        return

    # Recupera a flag calculada no pre_save que sinaliza modificação no estoque
    estoque_alterado = getattr(instance, '_estoque_alterado', False)
    # Recupera a flag calculada no pre_save que sinaliza modificação no preço
    preco_alterado = getattr(instance, '_preco_alterado', False)

    # Se nem estoque nem preço mudaram e também não se trata da criação de um novo registro
    if not estoque_alterado and not preco_alterado and not created:
        # Aborta o processamento pois não há impacto comercial nas publicações externas
        return

    # Extrai o motivo da operação (ex.: 'VENDA_MARKETPLACE') caso tenha sido anexado à instância
    motivo = getattr(instance, '_motivo_alteracao', None)

    # Protege contra reentrância na mesma thread
    # Ativa o context manager para evitar loops recursivos de sinais durante updates internos
    with mute_sincronizacao_signals():
        # Inicia bloco de tratamento para capturar erros durante a atualização dos anúncios vinculados
        try:
            # Importa timezone localmente para evitar problemas de carregamento circular
            from django.utils import timezone
            # Importa os modelos de Anúncio e de Histórico de Auditoria do ciclo
            from apps.anuncios.models import Anuncio, HistoricoSincronizacaoAnuncio
            # Consulta todos os anúncios que contêm este produto físico em suas composições (unitários ou kits)
            anuncios = Anuncio.objects.filter(composicoes__produto=instance).distinct()
            # Captura a data/hora corrente ciente de fuso horário
            agora = timezone.now()
            # Extrai a referência do operador ou usuário responsável pela operação
            usuario = getattr(instance, '_usuario_operacao', None)

            # Avalia se a alteração decorre de um pedido confirmado vindo de webhook de integração
            if motivo == 'VENDA_MARKETPLACE':
                # Venda real originada de Webhook: NÃO deve ficar PENDENTE no modal esperando operador.
                # Marca como ENVIADO e sincroniza a nova cota física calculada para prevenir ruptura (RN-05).
                # Itera por cada anúncio associado ao produto vendido
                for anc in anuncios:
                    # Registra o preço atual do anúncio antes da nova gravação
                    preco_ant = anc.preco_venda
                    # Registra o saldo de cota anterior persistido no anúncio
                    cota_ant = anc.estoque_publicado
                    # Recalcula a nova cota física vendável com base no estoque restante no catálogo
                    cota_nova = anc.calcular_cota_disponivel()

                    # Define o status da sincronização diretamente como 'ENVIADO' (baixa automática sem fila de confirmação manual)
                    anc.status_sincronizacao = 'ENVIADO'
                    # Atualiza o snapshot do estoque publicado local para o novo valor calculado
                    anc.estoque_publicado = cota_nova
                    # Persiste os campos alterados de forma explícita otimizando a query
                    anc.save(update_fields=['status_sincronizacao', 'estoque_publicado', 'atualizado_em'])

                    # Cria um registro detalhado na trilha de histórico do ciclo de sincronização
                    HistoricoSincronizacaoAnuncio.objects.create(
                        # Anúncio que sofreu a baixa
                        anuncio=anc,
                        # Status confirmado resultante
                        status_resultante='ENVIADO',
                        # Preço anterior preservado
                        preco_anterior=preco_ant,
                        # Preço mantido idêntico
                        preco_proposto=preco_ant,
                        # Cota anterior antes da dedução
                        estoque_anterior=cota_ant,
                        # Nova cota resultante da baixa
                        estoque_proposto=cota_nova,
                        # Usuário ou nulo caso tenha sido acionado via webhook
                        usuario=usuario,
                        # Motivo padronizado do disparo
                        motivo="Baixa automática por venda de marketplace (VENDA_MARKETPLACE)",
                        # Data de pendência nula pois a baixa é imediata
                        data_pendencia=None
                    )

                    # Propagação multicanal atômica imediata de cota para todos os canais/anúncios vinculados
                    # Inicia bloco protegido para chamada de rede externa ao conector do marketplace
                    try:
                        # Recupera a instância do conector associado à conta do anúncio
                        connector = anc.conta.get_connector()
                        # Envia imediatamente a nova cota para a API externa a fim de evitar overselling
                        connector.atualizar_estoque(anc.item_id_externo, cota_nova, usuario=usuario)
                    # Captura eventuais falhas de comunicação com a API remota
                    except Exception as exc:
                        # Registra advertência de falha no envio sem abortar as demais baixas do loop
                        logger.warning(f"Falha ao propagar cota do anúncio {anc.item_id_externo} pós-venda: {exc}")

                # Também sincroniza anúncios do catálogo (AnuncioMarketplace) se houver
                # Trata modelos de anúncios legados mantidos na app catalogo caso ainda existam
                try:
                    # Importa o modelo alternativo de vínculo de anúncio do catálogo
                    from apps.catalogo.models import AnuncioMarketplace
                    # Varre anúncios legados do catálogo vinculados diretamente a este produto
                    for am in AnuncioMarketplace.objects.filter(produto=instance).select_related('conta_marketplace'):
                        # Tenta atualizar o canal externo desse anúncio complementar
                        try:
                            # Obtém conector da conta de marketplace legada
                            am_conn = am.conta_marketplace.get_connector()
                            # Atualiza estoque diretamente com o saldo bruto do produto
                            am_conn.atualizar_estoque(am.item_id_externo, instance.estoque, usuario=usuario)
                        # Ignora silenciosamente erros no fluxo alternativo legado
                        except Exception:
                            pass
                # Captura falha geral ao tentar referenciar modelos secundários
                except Exception:
                    pass

                # Encerra a função pois o fluxo prioritário de venda de marketplace foi totalmente concluído
                return

            # Para alterações manuais de operadores (Ajuste Geral de Balanço ou Edição de Preço):
            # Percorre os anúncios quando a alteração for manual (cadastro de produto, contagem de inventário, etc.)
            for anc in anuncios:
                # Armazena o preço antes do ajuste
                preco_ant = anc.preco_venda
                # Armazena a cota atualmente publicada no canal
                cota_ant = anc.estoque_publicado
                # Recalcula a cota física disponível a partir do novo inventário
                cota_nova = anc.calcular_cota_disponivel()

                # Se houver divergência entre a nova cota física e a antiga ou se o preço foi alterado
                if cota_nova != cota_ant or anc.preco_venda != instance.preco:
                    # Coloca o anúncio em estado de aprovação/revisão pendente
                    anc.status_sincronizacao = 'PENDENTE'
                    # Salva os campos de status e data de modificação
                    anc.save(update_fields=['status_sincronizacao', 'atualizado_em'])

                    # Cria um registro no histórico documentando que a modificação aguarda revisão do operador
                    HistoricoSincronizacaoAnuncio.objects.create(
                        # Anúncio pendente
                        anuncio=anc,
                        # Novo status indicando pendência
                        status_resultante='PENDENTE',
                        # Preço anterior à mutação
                        preco_anterior=preco_ant,
                        # Preço proposto conforme o novo preço cadastrado no produto
                        preco_proposto=instance.preco,
                        # Saldo de cota anterior à contagem
                        estoque_anterior=cota_ant,
                        # Nova cota apurada elegível
                        estoque_proposto=cota_nova,
                        # Operador que editou o produto no painel
                        usuario=usuario,
                        # Motivo da pendência gerada
                        motivo="Alteração no catálogo físico (pendente de envio ao canal)",
                        # Timestamp em que a pendência foi registrada para monitoramento em fila
                        data_pendencia=agora
                    )
        # Captura qualquer exceção não tratada ocorrida no processamento dos anúncios vinculados
        except Exception as exc:
            # Registra no log o erro detalhado acompanhado de todo o traceback de execução
            logger.error(f"Erro ao marcar pendência nos anúncios vinculados ao produto {instance.pk}: {exc}", exc_info=True)
