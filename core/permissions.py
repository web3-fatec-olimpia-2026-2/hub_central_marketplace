from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def usuario_is_dev(user):
    """
    Verifica se o usuário autenticado possui o papel DEV (ou é superusuário).
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, 'perfil') and user.perfil.is_dev


class DevRequiredMixin(AccessMixin):
    """
    Mixin para Class-Based Views exigindo que o usuário esteja autenticado
    e possua o papel DEV (RN-07).
    """
    permission_denied_message = "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV)."

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not usuario_is_dev(request.user):
            messages.error(request, self.permission_denied_message)
            raise PermissionDenied(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


def dev_required(view_func):
    """
    Decorador para function-based views que restringe o acesso a usuários com papel DEV.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not usuario_is_dev(request.user):
            messages.error(request, "Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
            raise PermissionDenied("Acesso restrito exclusivamente ao perfil Desenvolvedor (DEV).")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
