# Os códigos foram gerados com auxilio de I.A.

# Início do bloco de docstring que documenta o propósito da configuração WSGI e links oficiais do Django
"""
WSGI config for hub project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""
# Fim do bloco de documentação do arquivo

# Importa o módulo nativo 'os' para interagir com o sistema operacional e configurar variáveis de ambiente
import os

# Importa a função do Django responsável por instanciar a aplicação compatível com a especificação síncrona WSGI
from django.core.wsgi import get_wsgi_application

# Define 'hub.settings' como o módulo de configurações padrão caso a variável DJANGO_SETTINGS_MODULE ainda não exista
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Inicializa o framework Django e expõe o callable 'application' para ser executado por servidores WSGI (como Gunicorn ou uWSGI)
application = get_wsgi_application()