# Os códigos foram gerados com auxilio de I.A.
import logging
import threading
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from apps.catalogo.models import Produto
from apps.anuncios.services import AnuncioSincronizacaoService

logger = logging.getLogger(__name__)

_local = threading.local()


def is_signals_muted() -> bool:
    """Verifica se os sinais de sincronização estão temporariamente desativados na thread atual."""
    return getattr(_local, 'mute_signals', False)


class mute_sincronizacao_signals:
    """
    Context manager para desativar temporariamente o disparo de sinais de sincronização.
    Útil em imports massivos, rotinas de carga de dados e execuções concorrentes.
    """
    def __enter__(self):
        _local.mute_signals = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _local.mute_signals = False


@receiver(pre_save, sender=Produto)
def identificar_alteracao_produto(sender, instance: Produto, **kwargs):
    """
    O QUE FAZ: Identifica antes do salvamento se houve alteração nos campos estoque e/ou preço do Produto.
    POR QUE FAZ: Evita disparar chamadas de rede externas e recálculos desnecessários se os valores forem idênticos.
    """
    if is_signals_muted() or getattr(instance, '_ignorar_sinais_sincronizacao', False):
        instance._estoque_alterado = False
        instance._preco_alterado = False
        return

    if not instance.pk:
        # Novo produto sendo inserido
        instance._estoque_alterado = True
        instance._preco_alterado = True
        return

    try:
        antigo = Produto.objects.filter(pk=instance.pk).values('estoque', 'preco').first()
        if antigo:
            instance._estoque_alterado = (antigo['estoque'] != instance.estoque)
            instance._preco_alterado = (antigo['preco'] != instance.preco)
        else:
            instance._estoque_alterado = True
            instance._preco_alterado = True
    except Exception as exc:
        logger.warning(f"Falha ao checar estado anterior do produto {instance.pk}: {exc}")
        instance._estoque_alterado = True
        instance._preco_alterado = True


@receiver(post_save, sender=Produto)
def disparar_sincronizacao_anuncios_produto(sender, instance: Produto, created: bool, **kwargs):
    """
    O QUE FAZ: Dispara a sincronização de estoque e preço para todos os anúncios vinculados ao Produto (unitários e kits).
    POR QUE FAZ: Mantém o marketplace rigorosamente alinhado com a Fonte da Verdade do Catálogo (RF-05 / RF-08).
    """
    if is_signals_muted() or getattr(instance, '_ignorar_sinais_sincronizacao', False):
        return

    estoque_alterado = getattr(instance, '_estoque_alterado', False)
    preco_alterado = getattr(instance, '_preco_alterado', False)

    if not estoque_alterado and not preco_alterado and not created:
        return

    # Protege contra reentrância na mesma thread
    with mute_sincronizacao_signals():
        try:
            apenas_estoque = not preco_alterado
            AnuncioSincronizacaoService.sincronizar_anuncios_do_produto(
                produto=instance,
                apenas_estoque=apenas_estoque
            )
        except Exception as exc:
            logger.error(f"Erro ao sincronizar anúncios vinculados ao produto {instance.pk}: {exc}", exc_info=True)
