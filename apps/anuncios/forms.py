# Os códigos foram gerados com auxilio de I.A.
from django import forms
from apps.anuncios.models import AnuncioComposicao
from apps.catalogo.models import Produto


class AnuncioComposicaoForm(forms.ModelForm):
    """
    Formulário para vincular um produto físico a um anúncio e definir o multiplicador (Kit).
    """
    class Meta:
        model = AnuncioComposicao
        fields = ['produto', 'quantidade']
        widgets = {
            'produto': forms.Select(attrs={'class': 'form-select select2'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'value': 1}),
        }

    def __init__(self, *args, anuncio=None, **kwargs):
        super().__init__(*args, **kwargs)
        if anuncio:
            loja = anuncio.conta.loja
            self.fields['produto'].queryset = Produto.objects.filter(loja=loja, status='ATIVO').order_by('nome')
