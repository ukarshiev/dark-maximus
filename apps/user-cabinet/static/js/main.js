/**
 * Основной JavaScript для личного кабинета
 */

const STEP_STORAGE_KEY = 'userCabinetActiveStep';
const FALLBACK_DEFAULT_MESSAGE = 'Откройте ссылку ниже в новой вкладке.';

function syncThemeToggle(theme) {
    const checkbox = document.querySelector('.theme-toggle__input');
    if (checkbox) {
        checkbox.checked = (theme === 'dark');
    }
}

function handleStepTheme(stepId) {
    if (!window.ThemeUtils) {
        return;
    }

    if (stepId === 'subscription') {
        window.ThemeUtils.setTheme('dark', false);
        syncThemeToggle('dark');
        return;
    }

    const preferredTheme = window.ThemeUtils.getTheme();
    window.ThemeUtils.setTheme(preferredTheme, false);
    syncThemeToggle(preferredTheme);
}

let activeFullscreenPane = null;

function setFullscreenState(pane, enabled) {
    if (!pane) {
        return;
    }

    pane.classList.toggle('step-pane--fullscreen', enabled);

    const fullscreenButton = pane.querySelector('.step-pane__action[data-action="fullscreen"]');
    if (fullscreenButton) {
        fullscreenButton.setAttribute('aria-pressed', String(enabled));
        fullscreenButton.dataset.state = enabled ? 'expanded' : 'collapsed';
        fullscreenButton.setAttribute(
            'aria-label',
            enabled ? 'Свернуть из полноэкранного режима' : 'Развернуть на весь экран'
        );
    }

    if (enabled) {
        document.body.classList.add('step-pane-fullscreen-active');
        activeFullscreenPane = pane;
        return;
    }

    if (activeFullscreenPane === pane) {
        const anotherPane = document.querySelector('.step-pane--fullscreen');
        activeFullscreenPane = anotherPane || null;
    }

    if (!activeFullscreenPane) {
        document.body.classList.remove('step-pane-fullscreen-active');
    }
}

function toggleFullscreen(button) {
    const pane = button.closest('.step-pane');
    if (!pane) {
        return;
    }

    const isActive = pane.classList.contains('step-pane--fullscreen');

    if (isActive) {
        setFullscreenState(pane, false);
        return;
    }

    if (activeFullscreenPane && activeFullscreenPane !== pane) {
        setFullscreenState(activeFullscreenPane, false);
    }

    setFullscreenState(pane, true);
}

function openStepContent(button) {
    const pane = button.closest('.step-pane');
    if (!pane) {
        return;
    }

    const iframeId = button.dataset.targetIframe;
    const iframe = iframeId ? document.getElementById(iframeId) : pane.querySelector('iframe');
    let targetUrl = iframe?.dataset?.fallbackUrl || iframe?.src;

    if ((!targetUrl || targetUrl === 'about:blank') && pane) {
        const fallbackLink = pane.querySelector('[data-fallback-link]');
        if (fallbackLink && fallbackLink.getAttribute('href')) {
            targetUrl = fallbackLink.getAttribute('href');
        }
    }

    if (targetUrl) {
        window.open(targetUrl, '_blank', 'noopener');
    }
}

function initializeToolbarActions() {
    const actionButtons = Array.from(document.querySelectorAll('.step-pane__action'));
    actionButtons.forEach((button) => {
        const action = button.dataset.action;
        if (action === 'open') {
            button.addEventListener('click', () => openStepContent(button));
        }
        if (action === 'fullscreen') {
            if (!button.dataset.state) {
                button.dataset.state = 'collapsed';
            }
            button.addEventListener('click', () => toggleFullscreen(button));
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && activeFullscreenPane) {
            setFullscreenState(activeFullscreenPane, false);
        }
    });
}

function persistActiveStep(stepId) {
    try {
        sessionStorage.setItem(STEP_STORAGE_KEY, stepId);
    } catch (error) {
        console.warn('Не удалось сохранить активный шаг пользователя', error);
    }
}

function readStoredStep() {
    try {
        return sessionStorage.getItem(STEP_STORAGE_KEY);
    } catch (error) {
        console.warn('Не удалось прочитать активный шаг пользователя', error);
        return null;
    }
}

function activateStep(stepId) {
    const navItems = Array.from(document.querySelectorAll('.steps-nav__item'));
    const panels = Array.from(document.querySelectorAll('.step-pane'));

    if (!navItems.length || !panels.length) {
        return;
    }

    const availableSteps = navItems.map((item) => item.dataset.step).filter(Boolean);
    const normalizedStepId = availableSteps.includes(stepId) && stepId ? stepId : availableSteps[0];

    if (!normalizedStepId) {
        return;
    }

    if (activeFullscreenPane && activeFullscreenPane.dataset.step !== normalizedStepId) {
        setFullscreenState(activeFullscreenPane, false);
    }

    navItems.forEach((item) => {
        const isActive = item.dataset.step === normalizedStepId;
    item.classList.toggle('is-active', isActive);
        item.setAttribute('aria-selected', String(isActive));
        item.setAttribute('tabindex', isActive ? '0' : '-1');
    item.dataset.state = isActive ? 'active' : 'idle';

    if (isActive) {
      item.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'center'
      });
    }
    });

    panels.forEach((panel) => {
        const isActive = panel.dataset.step === normalizedStepId;
        panel.classList.toggle('is-active', isActive);
        panel.setAttribute('aria-hidden', String(!isActive));
        panel.setAttribute('tabindex', isActive ? '0' : '-1');
    });

    persistActiveStep(normalizedStepId);
    handleStepTheme(normalizedStepId);
}

function focusAdjacentStep(currentItem, offset) {
    const navItems = Array.from(document.querySelectorAll('.steps-nav__item'));
    const currentIndex = navItems.indexOf(currentItem);

    if (currentIndex === -1 || !navItems.length) {
        return;
    }

    const nextIndex = (currentIndex + offset + navItems.length) % navItems.length;
    navItems[nextIndex].focus();
}

function initializeStepNavigation() {
    const navItems = Array.from(document.querySelectorAll('.steps-nav__item'));
    if (!navItems.length) {
        return;
    }

  const navList = document.querySelector('.steps-nav');
  if (navList) {
    navList.setAttribute('aria-live', 'polite');
  }

    navItems.forEach((item) => {
        item.addEventListener('click', (event) => {
            event.preventDefault();

            const stepId = item.dataset.step;
            if (!stepId) {
                return;
            }

            activateStep(stepId);

            const targetPanel = document.querySelector(`.step-pane[data-step="${stepId}"]`);
            if (targetPanel) {
                targetPanel.focus({ preventScroll: true });
                targetPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });

        item.addEventListener('keydown', (event) => {
            switch (event.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                    event.preventDefault();
                    focusAdjacentStep(item, 1);
                    break;
                case 'ArrowLeft':
                case 'ArrowUp':
                    event.preventDefault();
                    focusAdjacentStep(item, -1);
                    break;
                case 'Home':
                    event.preventDefault();
                    document.querySelector('.steps-nav__item')?.focus();
                    break;
                case 'End': {
                    event.preventDefault();
                    const items = document.querySelectorAll('.steps-nav__item');
                    items[items.length - 1]?.focus();
                    break;
                }
                default:
                    break;
            }
        });
    });

    const storedStep = readStoredStep();
    activateStep(storedStep);
}

function resetIframeState(iframeId) {
    const iframe = document.getElementById(iframeId);

    if (iframe) {
        iframe.dataset.errorHandled = 'false';
        iframe.classList.remove('is-hidden');
        iframe.removeAttribute('aria-hidden');
    }
}

// Обработка ошибок загрузки iframe
function handleIframeError(iframeId, fallbackUrl) {
    const iframe = document.getElementById(iframeId);
    if (iframe) {
        iframe.dataset.errorHandled = 'true';
    }
}

// Копирование subscription link
function copySubscriptionLink() {
    const linkAnchor = document.getElementById('subscription-link-anchor');
    if (linkAnchor) {
        const linkValue = linkAnchor.getAttribute('href') || linkAnchor.textContent;
        navigator.clipboard.writeText(linkValue).then(() => {
            alert('Ссылка скопирована в буфер обмена!');
        }).catch(err => {
            console.error('Failed to copy:', err);
            // Fallback для старых браузеров
            const textArea = document.createElement('textarea');
            textArea.value = linkValue;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                alert('Ссылка скопирована в буфер обмена!');
            } catch (err) {
                console.error('Fallback copy failed:', err);
            }
            document.body.removeChild(textArea);
        });
    }
}

// Генерация QR-кода для subscription link
function generateQRCode(url) {
    // Используем библиотеку qrcode.js через CDN
    const container = document.getElementById('qr-code-container');
    if (!container) return;
    
    // Очищаем контейнер
    container.innerHTML = '';
    
    // Создаем canvas для QR-кода
    const canvas = document.createElement('canvas');
    container.appendChild(canvas);
    
    // Загружаем библиотеку динамически если её нет
    if (typeof QRCode === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js';
        script.onload = () => {
            QRCode.toCanvas(canvas, url, {
                width: 200,
                margin: 2,
                color: {
                    dark: '#000000',
                    light: '#FFFFFF'
                }
            }, (err) => {
                if (err) {
                    console.error('QR code generation failed:', err);
                    container.innerHTML = '<p>Не удалось создать QR-код</p>';
                }
            });
        };
        document.head.appendChild(script);
    } else {
        QRCode.toCanvas(canvas, url, {
            width: 200,
            margin: 2,
            color: {
                dark: '#000000',
                light: '#FFFFFF'
            }
        }, (err) => {
            if (err) {
                console.error('QR code generation failed:', err);
                container.innerHTML = '<p>Не удалось создать QR-код</p>';
            }
        });
    }
}

// Проверка через ipwho.is (напрямую из браузера)
async function checkIPWho() {
    const ipInfo = document.getElementById('ip-info-ipwho');
    if (!ipInfo) return;
    
    ipInfo.innerHTML = '<p>Загрузка информации...</p>';
    
    try {
        const timestamp = new Date().getTime();
        // Прямой запрос из браузера к ipwho.is
        const response = await fetch(`https://ipwho.is/?_t=${timestamp}`, { 
            cache: 'no-store',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message || 'Unknown error from ipwho.is');
        }
        
        const connection = data.connection || {};
        ipInfo.innerHTML = `
            <p><strong>IP-адрес:</strong> ${data.ip || 'Не определен'}</p>
            <p><strong>Страна:</strong> ${data.country || 'Не определена'}</p>
            ${data.region ? `<p><strong>Регион:</strong> ${data.region}</p>` : ''}
            <p><strong>Город:</strong> ${data.city || 'Не определен'}</p>
            <p><strong>Провайдер:</strong> ${connection.isp || connection.org || 'Не определен'}</p>
        `;
    } catch (error) {
        console.error('IP check failed (ipwho.is):', error);
        
        // Fallback: пробуем через серверный эндпоинт
        try {
            console.log('Trying fallback via server endpoint...');
            const fallbackResponse = await fetch(`/api/ip-info-ipwho?_t=${new Date().getTime()}`, {
                cache: 'no-store'
            });
            const payload = await fallbackResponse.json();
            
            if (fallbackResponse.ok && payload.status === 'ok') {
                const data = payload.data || {};
                ipInfo.innerHTML = `
                    <p><strong>IP-адрес:</strong> ${data.ip || 'Не определен'}</p>
                    <p><strong>Страна:</strong> ${data.country || 'Не определена'}</p>
                    ${data.region ? `<p><strong>Регион:</strong> ${data.region}</p>` : ''}
                    <p><strong>Город:</strong> ${data.city || 'Не определен'}</p>
                    <p><strong>Провайдер:</strong> ${data.provider || 'Не определен'}</p>
                    <p style="font-size: 0.85rem; color: var(--color-text-second); margin-top: 0.5rem;">⚠️ Использован резервный метод</p>
                `;
                return;
            }
        } catch (fallbackError) {
            console.error('Fallback also failed:', fallbackError);
        }
        
        ipInfo.innerHTML = `
            <p style="color: var(--color-button-warning);">Не удалось получить информацию.</p>
            <p style="font-size: 0.9rem;">${error.message || 'Проверьте подключение к интернету.'}</p>
        `;
    }
}

// Проверка через 2ip.ru (напрямую из браузера)
async function checkIP2ip() {
    const ipInfo = document.getElementById('ip-info-2ip');
    if (!ipInfo) return;
    
    ipInfo.innerHTML = '<p>Загрузка информации...</p>';
    
    try {
        const timestamp = new Date().getTime();
        // Прямой запрос из браузера к 2ip.ru API
        const response = await fetch(`https://api.2ip.io/?token=pb9x4n3dfnv0az2h&lang=ru&_t=${timestamp}`, { 
            cache: 'no-store',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const asn_info = data.asn || {};
        
        ipInfo.innerHTML = `
            <p><strong>IP-адрес:</strong> ${data.ip || 'Не определен'}</p>
            <p><strong>Страна:</strong> ${data.country || 'Не определена'}</p>
            ${data.region ? `<p><strong>Регион:</strong> ${data.region}</p>` : ''}
            <p><strong>Город:</strong> ${data.city || 'Не определен'}</p>
            <p><strong>Провайдер:</strong> ${asn_info.name || 'Не определен'}</p>
        `;
    } catch (error) {
        console.error('IP check failed (2ip.ru):', error);
        
        // Fallback: пробуем через серверный эндпоинт
        try {
            console.log('Trying fallback via server endpoint...');
            const fallbackResponse = await fetch(`/api/ip-info-2ip?_t=${new Date().getTime()}`, {
                cache: 'no-store'
            });
            const payload = await fallbackResponse.json();
            
            if (fallbackResponse.ok && payload.status === 'ok') {
                const data = payload.data || {};
                ipInfo.innerHTML = `
                    <p><strong>IP-адрес:</strong> ${data.ip || 'Не определен'}</p>
                    <p><strong>Страна:</strong> ${data.country || 'Не определена'}</p>
                    ${data.region ? `<p><strong>Регион:</strong> ${data.region}</p>` : ''}
                    <p><strong>Город:</strong> ${data.city || 'Не определен'}</p>
                    <p><strong>Провайдер:</strong> ${data.provider || 'Не определен'}</p>
                    <p style="font-size: 0.85rem; color: var(--color-text-second); margin-top: 0.5rem;">⚠️ Использован резервный метод</p>
                `;
                return;
            }
        } catch (fallbackError) {
            console.error('Fallback also failed:', fallbackError);
        }
        
        ipInfo.innerHTML = `
            <p style="color: var(--color-button-warning);">Не удалось получить информацию.</p>
            <p style="font-size: 0.9rem;">${error.message || 'Проверьте подключение к интернету.'}</p>
        `;
    }
}

// Старая функция для обратной совместимости (если используется где-то ещё)
async function checkIP() {
    await checkIPWho();
    await checkIP2ip();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    initializeStepNavigation();
    initializeToolbarActions();

    // Проверяем IP при загрузке (обе проверки)
    checkIPWho();
    checkIP2ip();
    
    // Генерируем QR-код для subscription link если iframe не загрузился
    const subscriptionLinkAnchor = document.getElementById('subscription-link-anchor');
    if (subscriptionLinkAnchor && (subscriptionLinkAnchor.textContent || subscriptionLinkAnchor.getAttribute('href'))) {
        // Проверяем через небольшую задержку, загрузился ли iframe
        setTimeout(() => {
            const iframe = document.getElementById('subscription-iframe');
            const fallback = document.getElementById('subscription-fallback');
            
            if (fallback && !fallback.hidden) {
                const fallbackUrl = subscriptionLinkAnchor.getAttribute('href') || subscriptionLinkAnchor.textContent;
                generateQRCode(fallbackUrl);
            }
        }, 2000);
    }
    
    // Обработка ошибок iframe через событие load
    const setupIframe = document.getElementById('setup-iframe');
    if (setupIframe) {
        const fallbackUrl = setupIframe.dataset.fallbackUrl || setupIframe.src;
        const fallbackTimer = setTimeout(() => {
            if (setupIframe.dataset.errorHandled !== 'true') {
                handleIframeError('setup-iframe', fallbackUrl);
            }
        }, 3000);

        setupIframe.addEventListener('load', function() {
            clearTimeout(fallbackTimer);
            resetIframeState('setup-iframe');
        });

        setupIframe.addEventListener('error', function() {
            clearTimeout(fallbackTimer);
            handleIframeError('setup-iframe', fallbackUrl);
        });
    }
    
    const subscriptionIframe = document.getElementById('subscription-iframe');
    if (subscriptionIframe) {
        subscriptionIframe.addEventListener('load', function() {
            resetIframeState('subscription-iframe');
        });

        subscriptionIframe.addEventListener('error', function() {
            handleIframeError('subscription-iframe', subscriptionIframe.src);
            const linkAnchor = document.getElementById('subscription-link-anchor');
            if (linkAnchor && (linkAnchor.getAttribute('href') || linkAnchor.textContent)) {
                const linkValue = linkAnchor.getAttribute('href') || linkAnchor.textContent;
                generateQRCode(linkValue);
            }
        });
    }
});

