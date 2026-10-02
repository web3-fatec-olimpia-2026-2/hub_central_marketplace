// static/js/app.js — Scripts Estáticos do Hub Central de Marketplaces (Doc ① §11.4)
// Totalmente compatível com CSP estrita (sem inline scripts e sem eval)

(() => {
    'use strict';

    // Utilitário para leitura de cookies (CSRF e preferências)
    const getCookie = name => {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };

    // Preferência de iluminação persistida
    const getStoredTheme = () => {
        const stored = localStorage.getItem('theme');
        if (stored) return stored;
        return getCookie('hub_iluminacao') || null;
    };

    const setStoredTheme = theme => {
        localStorage.setItem('theme', theme);
        document.cookie = `hub_iluminacao=${encodeURIComponent(theme)}; path=/; max-age=31536000; samesite=lax`;
    };

    // Aplica o tema na tag <html>
    const applyTheme = theme => {
        if (theme === 'auto') {
            const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-bs-theme', systemDark ? 'dark' : 'light');
        } else if (theme === 'light' || theme === 'dark') {
            document.documentElement.setAttribute('data-bs-theme', theme);
        }
    };

    // Atualiza o estado ativo dos botões no dropdown
    const updateActiveButton = theme => {
        const active = theme || 'light';
        document.querySelectorAll('[data-bs-theme-value]').forEach(button => {
            const isMatch = button.getAttribute('data-bs-theme-value') === active;
            button.classList.toggle('active', isMatch);
            button.setAttribute('aria-pressed', isMatch ? 'true' : 'false');
        });
    };

    // Envia a preferência de iluminação ao backend em segundo plano para persistência na sessão
    const saveIluminacaoToServer = theme => {
        const csrfToken = getCookie('csrftoken');
        if (!csrfToken) return;

        fetch('/tema/alternar/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            },
            body: new URLSearchParams({ iluminacao: theme })
        }).catch(() => {
            // Falha silenciosa; cookie e localStorage garantem continuidade no cliente
        });
    };

    // Aplicação inicial imediata
    const initialTheme = getStoredTheme();
    if (initialTheme) {
        applyTheme(initialTheme);
    }

    // Sincronização bidirecional entre picker (color) e text input (hex)
    const syncPair = (pickerId, textId) => {
        const picker = document.getElementById(pickerId);
        const text = document.getElementById(textId);
        if (!picker || !text) return;

        const fromPicker = () => {
            text.value = picker.value.toUpperCase();
        };

        const fromText = () => {
            let val = text.value.trim();
            if (val && !val.startsWith('#') && /^[0-9A-Fa-f]{6}$/.test(val)) {
                val = '#' + val;
                text.value = val.toUpperCase();
            }
            if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
                picker.value = val;
            }
        };

        picker.addEventListener('input', fromPicker);
        picker.addEventListener('change', fromPicker);
        text.addEventListener('input', fromText);
        text.addEventListener('change', fromText);
        text.addEventListener('blur', fromText);
    };

    const setupAllPickers = () => {
        syncPair('picker_fundos', 'cor_fundos');
        syncPair('picker_destaques', 'cor_destaques');
        syncPair('picker_escritas', 'cor_escritas');
    };

    document.addEventListener('DOMContentLoaded', () => {
        // Inicialização de tooltips do Bootstrap
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
        }

        // Configuração do seletor rápido de tema claro/escuro
        updateActiveButton(initialTheme || 'light');

        // Configuração dos seletores de cor do Modal T10
        setupAllPickers();

        // Ouvinte de abertura do modal para re-sincronizar
        const modalEl = document.getElementById('modalTemaPersonalizado');
        if (modalEl) {
            modalEl.addEventListener('show.bs.modal', setupAllPickers);
        }

        // Validação defensiva no submit do formulário T10
        const formT10 = document.querySelector('#modalTemaPersonalizado form');
        if (formT10) {
            formT10.addEventListener('submit', () => {
                ['fundos', 'destaques', 'escritas'].forEach(tipo => {
                    const picker = document.getElementById(`picker_${tipo}`);
                    const text = document.getElementById(`cor_${tipo}`);
                    if (picker && text) {
                        let val = text.value.trim();
                        if (!val || !/^#[0-9A-Fa-f]{6}$/.test(val)) {
                            text.value = picker.value.toUpperCase();
                        }
                    }
                });
            });
        }
    });

    // Delegação de evento de clique para alternância de modo de iluminação (Claro / Escuro / Auto)
    document.addEventListener('click', e => {
        const themeBtn = e.target.closest('[data-bs-theme-value]');
        if (themeBtn) {
            e.preventDefault();
            const selected = themeBtn.getAttribute('data-bs-theme-value');
            setStoredTheme(selected);
            applyTheme(selected);
            updateActiveButton(selected);
            saveIluminacaoToServer(selected);
            return;
        }

        // Delegação de evento de clique para Paletas Sugeridas de 1 Clique no Modal T10
        const paletteBtn = e.target.closest('.btn-paleta-rapida');
        if (paletteBtn) {
            e.preventDefault();
            const f = (paletteBtn.getAttribute('data-fundo') || '').toUpperCase();
            const d = (paletteBtn.getAttribute('data-destaque') || '').toUpperCase();
            const esc = (paletteBtn.getAttribute('data-escrita') || '').toUpperCase();

            const pF = document.getElementById('picker_fundos');
            const tF = document.getElementById('cor_fundos');
            const pD = document.getElementById('picker_destaques');
            const tD = document.getElementById('cor_destaques');
            const pE = document.getElementById('picker_escritas');
            const tE = document.getElementById('cor_escritas');

            if (pF && tF) { pF.value = f; tF.value = f; }
            if (pD && tD) { pD.value = d; tD.value = d; }
            if (pE && tE) { pE.value = esc; tE.value = esc; }

            document.querySelectorAll('.btn-paleta-rapida').forEach(b => {
                b.classList.remove('active', 'border-primary', 'bg-light', 'shadow-sm');
            });
            paletteBtn.classList.add('active', 'border-primary', 'bg-light', 'shadow-sm');
        }
    });

    // Reação automática caso o usuário mude o tema do sistema operacional no modo 'auto'
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        const storedTheme = getStoredTheme();
        if (storedTheme === 'auto') {
            applyTheme('auto');
        }
    });
})();
