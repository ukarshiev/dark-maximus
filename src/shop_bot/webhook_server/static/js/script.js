document.addEventListener('DOMContentLoaded', function () {
    // Закрытие flash-уведомлений по клику на крестик
    document.body.addEventListener('click', function (event) {
        const target = event.target;
        if (target && target.classList && target.classList.contains('flash-close')) {
            const flash = target.closest('.flash');
            if (flash) {
                flash.parentNode && flash.parentNode.removeChild(flash);
            }
        }
    });
	function initializePasswordToggles() {
		const togglePasswordButtons = document.querySelectorAll('.toggle-password')
		togglePasswordButtons.forEach(button => {
			button.addEventListener('click', function () {
				const parent =
					this.closest('.form-group') || this.closest('.password-wrapper')
				if (!parent) return

				const passwordInput = parent.querySelector('input')
				if (!passwordInput) return

				if (passwordInput.type === 'password') {
					passwordInput.type = 'text'
					this.textContent = '🙈'
				} else {
					passwordInput.type = 'password'
					this.textContent = '👁️'
				}
			})
		})
	}

	function setupBotControlForms() {
		const controlForms = document.querySelectorAll(
			'form[action*="start-bot"], form[action*="stop-bot"]'
		)

		controlForms.forEach(form => {
			form.addEventListener('submit', function () {
				const button = form.querySelector('button[type="submit"]')
				if (button) {
					button.disabled = true
					if (form.action.includes('start')) {
						button.textContent = 'Запускаем...'
					} else if (form.action.includes('stop')) {
						button.textContent = 'Останавливаем...'
					}
				}
				setTimeout(function () {
					window.location.reload()
				}, 1000) // 1 second
			})
		})
	}

	function setupConfirmationForms() {
		const confirmationForms = document.querySelectorAll('form[data-confirm]')
		confirmationForms.forEach(form => {
			form.addEventListener('submit', function (event) {
				const message = form.getAttribute('data-confirm')
				if (!confirm(message)) {
					event.preventDefault()
				}
			})
		})
	}

	function initializeDashboardCharts() {
		const usersChartCanvas = document.getElementById('newUsersChart')
		if (!usersChartCanvas || typeof CHART_DATA === 'undefined') {
			return
		}

		function prepareChartData(data, label, color) {
			const labels = []
			const values = []
			const today = new Date()

			for (let i = 29; i >= 0; i--) {
				const date = new Date(today)
				date.setDate(today.getDate() - i)
				const dateString = date.toISOString().split('T')[0]
				const formattedDate = `${date.getDate().toString().padStart(2, '0')}.${(
					date.getMonth() + 1
				)
					.toString()
					.padStart(2, '0')}`
				labels.push(formattedDate)
				values.push(data[dateString] || 0)
			}

			return {
				labels: labels,
				datasets: [
					{
						label: label,
						data: values,
						borderColor: color,
						backgroundColor: color + '33',
						borderWidth: 2,
						fill: true,
						tension: 0.3,
					},
				],
			}
		}

		function updateChartFontsAndLabels(chart) {
			const isMobile = window.innerWidth <= 768
			const isVerySmall = window.innerWidth <= 470
			chart.options.scales.x.ticks.font.size = isMobile ? 10 : 12
			chart.options.scales.y.ticks.font.size = isMobile ? 10 : 12
			chart.options.plugins.legend.labels.font.size = isMobile ? 12 : 14
			chart.options.scales.x.ticks.maxTicksLimit = isMobile ? 8 : 15
			chart.options.scales.x.ticks.display = !isVerySmall
			chart.options.scales.y.ticks.display = !isVerySmall
			chart.options.plugins.legend.display = !isVerySmall
			chart.update()
		}

		const usersCtx = usersChartCanvas.getContext('2d')
        const usersChartData = prepareChartData(
			CHART_DATA.users,
			'Новых пользователей в день',
            '#008771'
		)
		const usersChart = new Chart(usersCtx, {
			type: 'line',
			data: usersChartData,
			options: {
				scales: {
					y: {
						beginAtZero: true,
						ticks: {
							precision: 0,
							font: {
								size: window.innerWidth <= 768 ? 10 : 12,
							},
							display: window.innerWidth > 470,
						},
					},
					x: {
						ticks: {
							font: {
								size: window.innerWidth <= 768 ? 10 : 12,
							},
							maxTicksLimit: window.innerWidth <= 768 ? 8 : 15,
							maxRotation: 45,
							minRotation: 45,
							display: window.innerWidth > 470,
						},
					},
				},
				responsive: true,
				maintainAspectRatio: false,
				layout: {
					autoPadding: true,
					padding: 0,
				},
				plugins: {
					legend: {
						labels: {
							font: {
								size: window.innerWidth <= 768 ? 12 : 14,
							},
							display: window.innerWidth > 470,
						},
					},
				},
			},
		})

		const keysChartCanvas = document.getElementById('newKeysChart')
		if (!keysChartCanvas) return

		const keysCtx = keysChartCanvas.getContext('2d')
		const keysChartData = prepareChartData(
			CHART_DATA.keys,
			'Новых ключей в день',
			'#28a745'
		)
		const keysChart = new Chart(keysCtx, {
			type: 'line',
			data: keysChartData,
			options: {
				scales: {
					y: {
						beginAtZero: true,
						ticks: {
							precision: 0,
							font: {
								size: window.innerWidth <= 768 ? 10 : 12,
							},
							display: window.innerWidth > 470,
						},
					},
					x: {
						ticks: {
							font: {
								size: window.innerWidth <= 768 ? 10 : 12,
							},
							maxTicksLimit: window.innerWidth <= 768 ? 8 : 15,
							maxRotation: 45,
							minRotation: 45,
							display: window.innerWidth > 470,
						},
					},
				},
				responsive: true,
				maintainAspectRatio: false,
				layout: {
					autoPadding: true,
					padding: 0,
				},
				plugins: {
					legend: {
						labels: {
							font: {
								size: window.innerWidth <= 768 ? 12 : 14,
							},
							display: window.innerWidth > 470,
						},
					},
				},
			},
		})

		window.addEventListener('resize', () => {
			updateChartFontsAndLabels(usersChart)
			updateChartFontsAndLabels(keysChart)
		})
	}

	// Управление боковым меню
	function initializeSidebar() {
		const sidebarBurger = document.getElementById('sidebarBurger');
		const headerBurger = document.getElementById('headerBurger');
		const sidebar = document.getElementById('sidebar');
		
		if (!sidebar) return;
		
		// Загружаем сохраненное состояние меню
		const savedState = localStorage.getItem('sidebarState');
		const isMobile = window.innerWidth <= 768;
		
		// Применяем сохраненное состояние при загрузке страницы (только для десктопа)
		if (savedState && !isMobile) {
			const state = JSON.parse(savedState);
			if (state.collapsed) {
				collapseSidebar();
			} else if (state.hidden) {
				hideSidebar();
			}
		}
		
		// На мобильных устройствах sidebar скрыт по умолчанию
		if (isMobile) {
			sidebar.classList.remove('sidebar-mobile-open');
		}
		
		// Функция переключения меню для мобильных устройств
		// На мобильных устройствах sidebar полностью скрыт через CSS
		function toggleSidebarMobile() {
			// На мобильных устройствах sidebar скрыт, ничего не делаем
			if (window.innerWidth <= 768) {
				return;
			}
		}
		
		// Функция скрытия бокового меню (для десктопа)
		function hideSidebar() {
			sidebar.classList.add('sidebar-hidden');
			if (sidebarBurger) {
				sidebarBurger.classList.add('burger-active');
			}
			// Обновляем header-panel чтобы он занял всю ширину
			const headerPanel = document.querySelector('.header-panel');
			if (headerPanel) {
				headerPanel.style.left = '0';
			}
			// Сохраняем состояние
			localStorage.setItem('sidebarState', JSON.stringify({ hidden: true, collapsed: false }));
		}
		
		// Функция показа бокового меню (для десктопа)
		function showSidebar() {
			sidebar.classList.remove('sidebar-hidden');
			if (sidebarBurger) {
				sidebarBurger.classList.remove('burger-active');
			}
			// Возвращаем header-panel на место после sidebar
			const headerPanel = document.querySelector('.header-panel');
			if (headerPanel) {
				headerPanel.style.left = '280px';
			}
			// Сохраняем состояние
			localStorage.setItem('sidebarState', JSON.stringify({ hidden: false, collapsed: false }));
		}
		
		// Функция сворачивания бокового меню (только иконки)
		function collapseSidebar() {
			sidebar.classList.add('sidebar-collapsed');
			const mainContent = document.querySelector('.main-content');
			const headerPanel = document.querySelector('.header-panel');
			
			if (mainContent) {
				mainContent.classList.add('sidebar-collapsed');
			}
			if (headerPanel) {
				headerPanel.style.left = '60px';
			}
			// Сохраняем состояние
			localStorage.setItem('sidebarState', JSON.stringify({ hidden: false, collapsed: true }));
		}
		
		// Функция разворачивания бокового меню
		function expandSidebar() {
			sidebar.classList.remove('sidebar-collapsed');
			const mainContent = document.querySelector('.main-content');
			const headerPanel = document.querySelector('.header-panel');
			
			if (mainContent) {
				mainContent.classList.remove('sidebar-collapsed');
			}
			if (headerPanel) {
				headerPanel.style.left = '280px';
			}
			// Сохраняем состояние
			localStorage.setItem('sidebarState', JSON.stringify({ hidden: false, collapsed: false }));
		}
		
		// Обработчик события для мобильного бургерного меню (теперь только через sidebarBurger)
		// burgerMenu удален, используем только sidebarBurger
		
		// Обработчик события для бургера в боковом меню (только для десктопа)
		if (sidebarBurger) {
			sidebarBurger.addEventListener('click', function() {
				if (window.innerWidth > 768) {
					// На десктопе переключаем между развернутым, свернутым и скрытым состояниями
					if (sidebar.classList.contains('sidebar-hidden')) {
						// Если скрыт, показываем развернутым
						showSidebar();
					} else if (sidebar.classList.contains('sidebar-collapsed')) {
						// Если свернут, разворачиваем
						expandSidebar();
					} else {
						// Если развернут, сворачиваем
						collapseSidebar();
					}
				}
			});
		}
		
		// Обработчик события для бургера в header (для мобильных устройств)
		if (headerBurger) {
			headerBurger.addEventListener('click', function() {
				if (window.innerWidth <= 768) {
					// На мобильных переключаем sidebar
					sidebar.classList.toggle('sidebar-mobile-open');
					headerBurger.classList.toggle('burger-active');
					
					// Блокируем скролл при открытом меню
					if (sidebar.classList.contains('sidebar-mobile-open')) {
						document.body.style.overflow = 'hidden';
					} else {
						document.body.style.overflow = '';
					}
				}
			});
		}
		
		// Обработчик события для бургера в sidebar (для мобильных устройств)
		if (sidebarBurger) {
			sidebarBurger.addEventListener('click', function() {
				if (window.innerWidth <= 768) {
					// На мобильных переключаем sidebar
					sidebar.classList.toggle('sidebar-mobile-open');
					if (headerBurger) {
						headerBurger.classList.toggle('burger-active');
					}
					
					// Блокируем скролл при открытом меню
					if (sidebar.classList.contains('sidebar-mobile-open')) {
						document.body.style.overflow = 'hidden';
					} else {
						document.body.style.overflow = '';
					}
				}
			});
		}
		
		// Закрытие меню при клике на overlay
		document.addEventListener('click', function(e) {
			if (window.innerWidth <= 768) {
				// На мобильных закрываем sidebar при клике вне его
				if (sidebar.classList.contains('sidebar-mobile-open') && 
					!sidebar.contains(e.target) && 
					!(headerBurger && headerBurger.contains(e.target)) &&
					!(sidebarBurger && sidebarBurger.contains(e.target))) {
					sidebar.classList.remove('sidebar-mobile-open');
					if (headerBurger) {
						headerBurger.classList.remove('burger-active');
					}
					document.body.style.overflow = '';
				}
			} else {
				// Обработка для десктопа (если нужно)
				if (sidebar.classList.contains('sidebar-open') && 
					!sidebar.contains(e.target) && 
					!(sidebarBurger && sidebarBurger.contains(e.target))) {
					sidebar.classList.remove('sidebar-open');
					if (sidebarBurger) {
						sidebarBurger.classList.remove('burger-active');
					}
					document.body.style.overflow = '';
				}
			}
		});
		
		// Адаптация при изменении размера окна
		window.addEventListener('resize', function() {
			if (window.innerWidth > 768) {
				// На десктопе убираем мобильные классы и блокировку скролла
				sidebar.classList.remove('sidebar-mobile-open');
				if (headerBurger) {
					headerBurger.classList.remove('burger-active');
				}
				document.body.style.overflow = '';
				
				// Восстанавливаем сохраненное состояние для десктопа
				const savedState = localStorage.getItem('sidebarState');
				if (savedState) {
					const state = JSON.parse(savedState);
					if (state.collapsed) {
						collapseSidebar();
					} else if (state.hidden) {
						hideSidebar();
					} else {
						showSidebar();
					}
				}
			} else {
				// На мобильных устройствах скрываем sidebar по умолчанию
				sidebar.classList.remove('sidebar-mobile-open');
				if (headerBurger) {
					headerBurger.classList.remove('burger-active');
				}
				document.body.style.overflow = '';
			}
		});
	}

	// Управление чекбоксами ботов
	function initializeBotToggles() {
		// Обрабатываем только реальные бот-переключатели (Shop/Support), исключая "Режим"
		const botCheckboxes = document.querySelectorAll('.bot-checkbox[data-bot]');
		
		botCheckboxes.forEach(checkbox => {
			checkbox.addEventListener('change', function() {
				const botType = this.getAttribute('data-bot');
				const statusText = this.closest('.bot-label-row')?.querySelector('.bot-status-text');
				const isChecked = this.checked;
				
				// Обновляем текст статуса только для ботов (Shop/Support) в развернутом режиме
				if (statusText) {
					if (isChecked) {
						statusText.textContent = 'ON';
						statusText.className = 'bot-status-text status-running';
					} else {
						statusText.textContent = 'OFF';
						statusText.className = 'bot-status-text status-stopped';
					}
				}
				
				// Синхронизируем с другим переключателем того же типа
				const otherCheckbox = document.querySelector(`.bot-checkbox[data-bot="${botType}"]:not(#${this.id})`);
				if (otherCheckbox) {
					otherCheckbox.checked = isChecked;
				}
				
				// Отправляем запрос на сервер
				const action = isChecked ? 'start' : 'stop';
				const url = `/${action}-${botType}-bot`;  // ИСПРАВЛЕНО: убрал /admin/
				
				fetch(url, {
					method: 'POST',
					headers: {
						'Content-Type': 'application/x-www-form-urlencoded',
					}
				})
				.then(response => {
					if (!response.ok) {
						// Если запрос не удался, возвращаем чекбоксы в исходное состояние
						this.checked = !isChecked;
						if (otherCheckbox) otherCheckbox.checked = !isChecked;
						if (statusText) {
							if (isChecked) {
								statusText.textContent = 'OFF';
								statusText.className = 'bot-status-text status-stopped';
							} else {
								statusText.textContent = 'ON';
								statusText.className = 'bot-status-text status-running';
							}
						}
					}
				})
				.catch(error => {
					console.error('Error:', error);
					// В случае ошибки возвращаем чекбоксы в исходное состояние
					this.checked = !isChecked;
					if (otherCheckbox) otherCheckbox.checked = !isChecked;
					if (statusText) {
						if (isChecked) {
							statusText.textContent = 'OFF';
							statusText.className = 'bot-status-text status-stopped';
						} else {
							statusText.textContent = 'ON';
							statusText.className = 'bot-status-text status-running';
						}
					}
				});
			});
		});
	}

	initializePasswordToggles()
	setupBotControlForms()
	setupConfirmationForms()
	initializeDashboardCharts()
	initializeSidebar()
	initializeBotToggles()
	initializeUserModal()
	initializeHiddenModeToggle()
	initializeCreateNotificationModal()
	initializeUsersTableInteractions()
	
	
	// Загружаем заработанную сумму для всех пользователей на странице пользователей
	loadAllUsersEarned()
	loadAllUsersBalances()
})

// Функции для модального окна пользователя
let currentUserId = null

function initializeUserModal() {
	// Закрытие модального окна при клике вне его
	window.onclick = function(event) {
		const modal = document.getElementById('userModal')
		if (event.target === modal) {
			closeUserModal()
		}
	}
}

// Создание уведомления: модалка и логика
let notifSearchTimeout = null
function initializeCreateNotificationModal() {
    // Закрытие по клику вне окна
    window.addEventListener('click', function (event) {
        const modal = document.getElementById('createNotificationModal')
        if (!modal) return
        if (event.target === modal) {
            closeCreateNotificationModal()
        }
    })
}

// Инициализация действий таблицы пользователей: даблклик и кебаб-меню
function initializeUsersTableInteractions() {
    // Открытие карточки по дабл-клику по строке
    document.querySelectorAll('.users-table .user-row').forEach(row => {
        row.addEventListener('dblclick', () => {
            const userId = parseInt(row.getAttribute('data-user-id'))
            const username = row.getAttribute('data-username') || 'N/A'
            const isBanned = (row.getAttribute('data-is-banned') === 'true')
            const keysCount = parseInt(row.getAttribute('data-keys-count') || '0')
            if (!isNaN(userId)) {
                openUserModal(userId, username, isBanned, isNaN(keysCount) ? 0 : keysCount)
            }
        })
    })

    // Кебаб-меню: открытие/закрытие
    document.querySelectorAll('.kebab-menu .kebab-toggle').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation()
            const menu = btn.closest('.kebab-menu')
            const isOpen = menu.classList.contains('open')
            document.querySelectorAll('.kebab-menu.open').forEach(m => m.classList.remove('open'))
            if (!isOpen) menu.classList.add('open')
        })
    })

    // Предотвращаем даблклик на кебаб-меню от открытия карточки
    document.querySelectorAll('.kebab-menu').forEach(m => {
        m.addEventListener('dblclick', (e) => {
            e.stopPropagation()
        })
        m.addEventListener('click', (e) => {
            e.stopPropagation()
        })
    })

    // Клик вне — закрыть любые открытые меню (только в рамках страницы пользователей)
    const usersTable = document.querySelector('.users-table')
    if (usersTable) {
        document.addEventListener('click', () => {
            usersTable.querySelectorAll('.kebab-menu.open').forEach(m => m.classList.remove('open'))
        })
    }
}

function openCreateNotificationModal() {
    const modal = document.getElementById('createNotificationModal')
    if (modal) {
        // Сброс полей
        const input = document.getElementById('notifUserSearch')
        const selectedId = document.getElementById('notifSelectedUserId')
        const label = document.getElementById('notifSelectedUserLabel')
        const sugg = document.getElementById('notifUserSuggestions')
        if (input) input.value = ''
        if (selectedId) selectedId.value = ''
        if (label) label.textContent = ''
        if (sugg) sugg.innerHTML = ''
        modal.style.display = 'block'
    }
}

function closeCreateNotificationModal() {
    const modal = document.getElementById('createNotificationModal')
    if (modal) modal.style.display = 'none'
}

function debouncedSearchUsers(query) {
    clearTimeout(notifSearchTimeout)
    notifSearchTimeout = setTimeout(() => searchUsers(query), 300)
}

async function searchUsers(query) {
    const sugg = document.getElementById('notifUserSuggestions')
    const label = document.getElementById('notifSelectedUserLabel')
    const selectedId = document.getElementById('notifSelectedUserId')
    if (!sugg) return
    sugg.innerHTML = ''
    if (!query || query.trim().length < 1) return
    try {
        const resp = await fetch(`/api/search-users?q=${encodeURIComponent(query)}`)
        const data = await resp.json()
        const users = data.users || []
        if (users.length === 0) {
            sugg.innerHTML = '<div style="color:#999; padding:6px;">Не найдено</div>'
            return
        }
        users.slice(0, 10).forEach(u => {
            const div = document.createElement('div')
            div.style.padding = '6px 8px'
            div.style.cursor = 'pointer'
            div.style.border = '1px solid #444'
            div.style.borderRadius = '4px'
            div.style.marginBottom = '6px'
            div.textContent = `${u.telegram_id} · @${u.username || 'N/A'}`
            div.onclick = () => {
                if (selectedId) selectedId.value = String(u.telegram_id)
                if (label) label.textContent = `Выбрано: ${u.telegram_id} · @${u.username || 'N/A'}`
                sugg.innerHTML = ''
            }
            sugg.appendChild(div)
        })
    } catch (e) {
        sugg.innerHTML = '<div style="color:#dc3545; padding:6px;">Ошибка поиска</div>'
    }
}

async function submitCreateNotification() {
    const userIdEl = document.getElementById('notifSelectedUserId')
    const typeEl = document.getElementById('notifTypeSelect')
    const userId = userIdEl && userIdEl.value ? parseInt(userIdEl.value) : null
    const marker = typeEl ? parseInt(typeEl.value) : null
    if (!userId || !marker) {
        alert('Выберите пользователя и тип уведомления')
        return
    }
    try {
        const resp = await fetch('/create-notification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, marker_hours: marker })
        })
        const data = await resp.json()
        if (resp.ok) {
            alert(data.message || 'Уведомление отправлено')
            closeCreateNotificationModal()
            // Перезагрузим страницу, чтобы увидеть новую запись
            window.location.reload()
        } else {
            alert(data.message || 'Ошибка отправки')
        }
    } catch (e) {
        alert('Ошибка создания уведомления')
    }
}

// Скрытый режим
function initializeHiddenModeToggle() {
    const toggle = document.getElementById('hiddenModeToggle');
    const toggleCollapsed = document.getElementById('hiddenModeToggleCollapsed');
    const statusText = document.getElementById('hiddenModeStatus');
    
    // Используем основной переключатель, если есть
    const activeToggle = toggle || toggleCollapsed;
    if (!activeToggle) return;

    window.__HIDDEN_MODE__ = !!activeToggle.checked;
    // Явно синхронизируем визуальное состояние
    activeToggle.checked = window.__HIDDEN_MODE__;
    if (toggleCollapsed) toggleCollapsed.checked = window.__HIDDEN_MODE__;
    applyHiddenMode();

    function handleToggleChange() {
        const isOn = !!this.checked;
        window.__HIDDEN_MODE__ = isOn;
        // Синхронизируем оба переключателя
        if (toggle) toggle.checked = isOn;
        if (toggleCollapsed) toggleCollapsed.checked = isOn;
        if (statusText) {
            statusText.textContent = isOn ? 'ON' : 'OFF';
            statusText.className = 'bot-status-text ' + (isOn ? 'status-running' : 'status-stopped');
        }
        applyHiddenMode();
        // сохраняем на сервере и синхронизируем по ответу (0/1)
        fetch('/toggle-hidden-mode', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            const serverOn = (String(data.hidden_mode) === '1');
            window.__HIDDEN_MODE__ = serverOn;
            if (toggle) toggle.checked = serverOn;
            if (toggleCollapsed) toggleCollapsed.checked = serverOn;
            if (statusText) {
                statusText.textContent = serverOn ? 'ON' : 'OFF';
                statusText.className = 'bot-status-text ' + (serverOn ? 'status-running' : 'status-stopped');
            }
            applyHiddenMode();
        })
        .catch(() => {});
        // Доп. гарантия после любого возможного перерендера
        setTimeout(() => { 
            if (toggle) toggle.checked = window.__HIDDEN_MODE__; 
            if (toggleCollapsed) toggleCollapsed.checked = window.__HIDDEN_MODE__; 
        }, 50);
    }

    if (toggle) {
        toggle.addEventListener('change', handleToggleChange);
    }
    if (toggleCollapsed) {
        toggleCollapsed.addEventListener('change', handleToggleChange);
    }
}

function maskValue(value, type='text') {
    if (value === null || value === undefined) return '***';
    if (type === 'money') return '***';
    const str = String(value);
    if (str.length <= 2) return '**';
    return str[0] + '***' + str.slice(-1);
}

function applyHiddenMode() {
    const hidden = !!window.__HIDDEN_MODE__;
    // Users table masking
    document.querySelectorAll('.user-row').forEach(row => {
        const idCell = row.querySelector('[data-field="telegram_id"]');
        const usernameCell = row.querySelector('[data-field="username"]');
        const earnedCell = row.querySelector('[data-field="earned"]');
        if (idCell) {
            const original = idCell.getAttribute('data-original');
            if (!idCell.hasAttribute('data-original')) idCell.setAttribute('data-original', original || idCell.textContent.trim());
            const span = idCell.querySelector('span');
            if (span) span.textContent = hidden ? maskValue(original) : (original || '');
        }
        if (usernameCell) {
            const original = usernameCell.getAttribute('data-original') || usernameCell.textContent.trim();
            usernameCell.setAttribute('data-original', original);
            const nameSpan = usernameCell.querySelector('.username-text');
            if (nameSpan) nameSpan.textContent = hidden ? '@' + maskValue(original.replace(/^@/, '')) : original;
        }
        if (earnedCell) {
            const original = earnedCell.getAttribute('data-original') || earnedCell.textContent.trim();
            earnedCell.setAttribute('data-original', original);
            earnedCell.textContent = hidden ? '*** RUB' : original;
        }
    });

    // Transactions table masking
    document.querySelectorAll('.tx-row').forEach(row => {
        const idCell = row.querySelector('[data-field="user_id"]');
        const usernameCell = row.querySelector('[data-field="tx_username"]');
        const emailCell = row.querySelector('[data-field="tx_email"]');
        const priceCell = row.querySelector('[data-field="price"]');
        if (idCell) {
            const original = idCell.getAttribute('data-original') || idCell.textContent.trim();
            idCell.setAttribute('data-original', original);
            const span = idCell.querySelector('span');
            if (span) span.textContent = hidden ? maskValue(original) : original;
        }
        if (usernameCell) {
            const original = usernameCell.getAttribute('data-original') || usernameCell.textContent.trim();
            usernameCell.setAttribute('data-original', original);
            usernameCell.textContent = hidden ? maskValue(original) : original;
        }
        if (emailCell) {
            const original = emailCell.getAttribute('data-original') || emailCell.textContent.trim();
            emailCell.setAttribute('data-original', original);
            emailCell.textContent = hidden ? '***@***' : original;
        }
        if (priceCell) {
            const original = priceCell.getAttribute('data-original') || priceCell.textContent.trim();
            priceCell.setAttribute('data-original', original);
            
            // Сохраняем полный HTML контент для восстановления
            if (!priceCell.hasAttribute('data-original-html')) {
                priceCell.setAttribute('data-original-html', priceCell.innerHTML);
            }
            
            if (hidden) {
                // В скрытом режиме показываем только замаскированную цену
                const div = priceCell.querySelector('div');
                if (div) {
                    div.innerHTML = '*** RUB';
                } else {
                    priceCell.textContent = '*** RUB';
                }
            } else {
                // Восстанавливаем оригинальный HTML контент
                const originalHtml = priceCell.getAttribute('data-original-html');
                if (originalHtml) {
                    priceCell.innerHTML = originalHtml;
                }
            }
        }
    });

    // Keys table masking (user id, username)
    document.querySelectorAll('.key-row').forEach(row => {
        const idCell = row.querySelector('[data-field="key_user_id"]');
        const usernameCell = row.querySelector('[data-field="key_username"]');
        if (idCell) {
            const original = idCell.getAttribute('data-original') || idCell.textContent.trim();
            idCell.setAttribute('data-original', original);
            const span = idCell.querySelector('span');
            if (span) span.textContent = hidden ? maskValue(original) : original;
        }
        if (usernameCell) {
            const original = usernameCell.getAttribute('data-original') || usernameCell.textContent.trim();
            usernameCell.setAttribute('data-original', original);
            const nameSpan = usernameCell.querySelector('.username-text');
            if (nameSpan) nameSpan.textContent = hidden ? (original.startsWith('@') ? '@***' : '***') : original;
        }
    });

    // Settings: mask host URLs in Servers tab
    document.querySelectorAll('[data-field="host_url"]').forEach(el => {
        const original = el.getAttribute('data-original') || el.textContent.trim();
        el.setAttribute('data-original', original);
        el.textContent = hidden ? '***' : original;
    });

    // Modal fields masking
    const modalUserIdEl = document.getElementById('modalUserId');
    if (modalUserIdEl) {
        const orig = modalUserIdEl.getAttribute('data-original') || modalUserIdEl.textContent.trim();
        modalUserIdEl.setAttribute('data-original', orig);
        modalUserIdEl.textContent = hidden ? maskValue(orig) : orig;
    }
    const modalUsernameEl = document.getElementById('modalUsername');
    if (modalUsernameEl) {
        const orig = modalUsernameEl.getAttribute('data-original') || modalUsernameEl.textContent.trim();
        modalUsernameEl.setAttribute('data-original', orig);
        modalUsernameEl.textContent = hidden ? (orig.startsWith('@') ? '@***' : '***') : orig;
    }
    const modalEarnedEl = document.getElementById('modalEarned');
    if (modalEarnedEl) {
        const orig = modalEarnedEl.getAttribute('data-original') || modalEarnedEl.textContent.trim();
        modalEarnedEl.setAttribute('data-original', orig);
        modalEarnedEl.textContent = hidden ? '*** RUB' : orig;
    }
    const modalBalanceEl = document.getElementById('modalBalance');
    if (modalBalanceEl) {
        const orig = modalBalanceEl.getAttribute('data-original') || modalBalanceEl.textContent.trim();
        modalBalanceEl.setAttribute('data-original', orig);
        modalBalanceEl.textContent = hidden ? '*** RUB' : orig;
    }
}

function openUserModal(userId, username, isBanned, keysCount) {
	currentUserId = userId
	
	// Заполняем данные основной информации
	const modalUserIdEl = document.getElementById('modalUserId')
	if (modalUserIdEl) {
		modalUserIdEl.setAttribute('data-original', String(userId))
		modalUserIdEl.textContent = String(userId)
	}
	const modalUsernameEl = document.getElementById('modalUsername')
	const usernameText = username === 'N/A' ? 'N/A' : '@' + username
	if (modalUsernameEl) {
		modalUsernameEl.setAttribute('data-original', usernameText)
		modalUsernameEl.textContent = usernameText
	}
	document.getElementById('modalStatus').innerHTML = isBanned ? 
		'<span class="status-badge status-banned">Забанен</span>' : 
		'<span class="status-badge status-active">Активен</span>'
	document.getElementById('modalKeys').textContent = keysCount + ' шт.'
	
	// Показываем/скрываем кнопки в зависимости от статуса
	const banButton = document.getElementById('banButton')
	const unbanButton = document.getElementById('unbanButton')
	
	if (isBanned) {
		banButton.style.display = 'none'
		unbanButton.style.display = 'inline-block'
	} else {
		banButton.style.display = 'inline-block'
		unbanButton.style.display = 'none'
	}
	
	// Переключаемся на первую вкладку
	switchTab('payments')
	
	// Загружаем данные для вкладок
	loadUserPayments(userId)
	loadUserKeys(userId)
	loadUserNotifications(userId)
	loadUserEarned(userId)
	loadUserBalance(userId)
	
	// Применяем скрытый режим к шапке модалки после заполнения
	if (window.__HIDDEN_MODE__) {
		applyHiddenMode()
	}
	// Показываем модальное окно
	document.getElementById('userModal').style.display = 'block'
}

function closeUserModal() {
	document.getElementById('userModal').style.display = 'none'
	currentUserId = null
}

function banUser() {
	if (currentUserId && confirm('Вы уверены, что хотите забанить этого пользователя? Он не сможет пользоваться ботом.')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/ban/<int:user_id>
        form.action = `/users/ban/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function unbanUser() {
	if (currentUserId && confirm('Вы уверены, что хотите разбанить этого пользователя?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/unban/<int:user_id>
        form.action = `/users/unban/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function revokeKeys() {
	if (currentUserId && confirm('ВНИМАНИЕ! Это действие удалит ВСЕ ключи пользователя с серверов. Вы уверены?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/revoke/<int:user_id>
        form.action = `/users/revoke/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

async function resendNotification(notificationId) {
    try {
        const resp = await fetch(`/resend-notification/${notificationId}`, { method: 'POST' })
        const data = await resp.json()
        alert(data.message || 'Готово')
    } catch (e) {
        alert('Ошибка повторной отправки')
    }
}

// Функции для работы с вкладками
function switchTab(tabName) {
	// Скрываем все вкладки
	const tabs = document.querySelectorAll('.tab-content')
	tabs.forEach(tab => tab.classList.remove('active'))
	
	// Убираем активный класс с всех кнопок
	const buttons = document.querySelectorAll('.tab-button')
	buttons.forEach(button => button.classList.remove('active'))
	
	// Показываем выбранную вкладку
	document.getElementById(`tab-${tabName}`).classList.add('active')
	
	// Активируем соответствующую кнопку
	event.target.classList.add('active')
}

// Функции для загрузки данных
async function loadUserPayments(userId) {
	try {
		const response = await fetch(`/api/user-payments/${userId}`)
		const data = await response.json()
		
		const tbody = document.getElementById('modalPaymentsTable')
		tbody.innerHTML = ''
		
		if (data.payments && data.payments.length > 0) {
			data.payments.forEach(payment => {
				const row = document.createElement('tr')
				row.innerHTML = `
					<td>${payment.transaction_id}</td>
					<td>${payment.host_name || 'N/A'}</td>
					<td>${payment.plan_name || 'N/A'}</td>
					<td data-field="price">${payment.amount_rub ? payment.amount_rub.toFixed(2) + ' RUB' : 'N/A'}</td>
					<td>
						<span class="status-badge ${payment.status === 'paid' ? 'status-active' : 'status-pending'}">
							${payment.status === 'paid' ? 'Оплачено' : 'Ожидает'}
						</span>
					</td>
					<td>${payment.created_date ? new Date(payment.created_date).toLocaleString('ru-RU') : 'N/A'}</td>
				`
				tbody.appendChild(row)
			})
			applyHiddenMode()
		} else {
			tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">Нет платежей</td></tr>'
		}
	} catch (error) {
		console.error('Ошибка загрузки платежей:', error)
		document.getElementById('modalPaymentsTable').innerHTML = '<tr><td colspan="6" style="text-align: center; color: #dc3545;">Ошибка загрузки</td></tr>'
	}
}

async function loadUserKeys(userId) {
	try {
		const response = await fetch(`/api/user-keys/${userId}`)
		const data = await response.json()
		
		const tbody = document.getElementById('modalKeysTable')
		tbody.innerHTML = ''
		
		if (data.keys && data.keys.length > 0) {
			data.keys.forEach(key => {
				const row = document.createElement('tr')
				row.innerHTML = `
					<td>${key.key_id}</td>
					<td>${key.host_name || 'N/A'}</td>
					<td>${key.plan_name || 'N/A'}</td>
					<td>${key.price ? key.price + ' RUB' : 'N/A'}</td>
					<td>
						${key.connection_string ? 
							`<div class="key-cell">
								<span class="key-text" title="${key.connection_string}">${key.connection_string.substring(0, 30)}...</span>
								<button class="copy-btn" onclick="copyKey('${key.connection_string}')" title="Копировать ключ">📋</button>
							</div>` : 
							'-'
						}
					</td>
					<td>${key.created_date ? new Date(key.created_date).toLocaleString('ru-RU') : 'N/A'}</td>
				`
				tbody.appendChild(row)
			})
		} else {
			tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #999;">Нет ключей</td></tr>'
		}
	} catch (error) {
		console.error('Ошибка загрузки ключей:', error)
		document.getElementById('modalKeysTable').innerHTML = '<tr><td colspan="6" style="text-align: center; color: #dc3545;">Ошибка загрузки</td></tr>'
	}
}

async function loadUserNotifications(userId) {
    try {
        const response = await fetch(`/api/user-notifications/${userId}`)
        const data = await response.json()
        const tbody = document.getElementById('modalNotificationsTable')
        tbody.innerHTML = ''
        if (data.notifications && data.notifications.length > 0) {
            data.notifications.forEach(n => {
                const row = document.createElement('tr')
                row.innerHTML = `
                    <td>${n.notification_id}</td>
                    <td>${n.type || '-'}</td>
                    <td>${n.title || '-'}</td>
                    <td>
                        ${n.status === 'resent' ? '<span class="status-badge status-active">Повтор</span>' : (n.status === 'sent' ? '<span class="status-badge status-active">Отправлено</span>' : '<span class="status-badge">' + (n.status || '-') + '</span>')}
                    </td>
                    <td>${n.created_date || ''}</td>
                `
                tbody.appendChild(row)
            })
            applyHiddenMode()
        } else {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #999;">Нет уведомлений</td></tr>'
        }
    } catch (error) {
        console.error('Ошибка загрузки уведомлений:', error)
        document.getElementById('modalNotificationsTable').innerHTML = '<tr><td colspan="5" style="text-align: center; color: #dc3545;">Ошибка загрузки</td></tr>'
    }
}

function copyUsername() {
	const usernameElement = document.getElementById('modalUsername')
	if (usernameElement) {
		const username = usernameElement.textContent
		// Убираем @ если есть
		const cleanUsername = username.startsWith('@') ? username : '@' + username
		
		navigator.clipboard.writeText(cleanUsername).then(() => {
			// Показываем уведомление
			showNotification('Username скопирован: ' + cleanUsername)
		}).catch(err => {
			console.error('Ошибка копирования: ', err)
			showNotification('Ошибка копирования', 'error')
		})
	}
}

function openTelegramProfile() {
	const usernameElement = document.getElementById('modalUsername')
	if (usernameElement) {
		const username = usernameElement.textContent
		// Убираем @ если есть и создаем ссылку
		const cleanUsername = username.startsWith('@') ? username.substring(1) : username
		
		if (cleanUsername === 'N/A') {
			showNotification('Username недоступен', 'error')
			return
		}
		
		const telegramUrl = 'https://t.me/' + cleanUsername
		window.open(telegramUrl, '_blank')
	}
}

function showNotification(message, type = 'success') {
	// Создаем уведомление
	const notification = document.createElement('div')
	notification.style.cssText = `
		position: fixed;
		top: 20px;
		right: 20px;
		background: ${type === 'error' ? '#dc3545' : '#28a745'};
		color: white;
		padding: 12px 20px;
		border-radius: 4px;
		z-index: 10000;
		font-size: 14px;
		box-shadow: 0 4px 6px rgba(0,0,0,0.1);
	`
	notification.textContent = message
	
	document.body.appendChild(notification)
	
	// Убираем уведомление через 3 секунды
	setTimeout(() => {
		if (notification.parentNode) {
			notification.parentNode.removeChild(notification)
		}
	}, 3000)
}

async function loadUserEarned(userId) {
	try {
		const response = await fetch(`/api/user-earned/${userId}`)
		const data = await response.json()
		
		const earnedElement = document.getElementById('modalEarned')
		if (earnedElement) {
			const value = (data.earned ? data.earned.toFixed(2) : '0.00') + ' RUB'
			earnedElement.setAttribute('data-original', value)
			if (window.__HIDDEN_MODE__) {
				earnedElement.textContent = '*** RUB'
			} else {
				earnedElement.textContent = value
			}
		}
	} catch (error) {
		console.error('Ошибка загрузки заработанной суммы:', error)
		const earnedElement = document.getElementById('modalEarned')
		if (earnedElement) {
			earnedElement.setAttribute('data-original', 'Ошибка')
			earnedElement.textContent = window.__HIDDEN_MODE__ ? '*** RUB' : 'Ошибка'
		}
	}
}

async function loadUserBalance(userId) {
    try {
        const response = await fetch(`/api/user-balance/${userId}`);
        const data = await response.json();
        const balanceElement = document.getElementById('modalBalance');
        if (balanceElement) {
            const value = (data.balance ? data.balance.toFixed(2) : '0.00') + ' RUB';
            balanceElement.setAttribute('data-original', value);
            if (window.__HIDDEN_MODE__) {
                balanceElement.textContent = '*** RUB';
            } else {
                balanceElement.textContent = value;
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки баланса:', error);
        const balanceElement = document.getElementById('modalBalance');
        if (balanceElement) {
            balanceElement.setAttribute('data-original', 'Ошибка');
            balanceElement.textContent = window.__HIDDEN_MODE__ ? '*** RUB' : 'Ошибка';
        }
    }
}

// Загружаем заработанную сумму для всех пользователей на странице пользователей
async function loadAllUsersEarned() {
    const earnedElements = document.querySelectorAll('.user-earned');
    
    for (const element of earnedElements) {
        const userId = element.getAttribute('data-user-id');
        try {
            const response = await fetch(`/api/user-earned/${userId}`);
            const data = await response.json();
            
            if (data.earned !== undefined) {
                element.textContent = data.earned.toFixed(2) + ' RUB';
            } else {
                element.textContent = '0.00 RUB';
            }
        } catch (error) {
            console.error('Ошибка загрузки заработанной суммы для пользователя', userId, ':', error);
            element.textContent = 'Ошибка';
        }
    }
}

async function loadAllUsersBalances() {
    const balanceElements = document.querySelectorAll('.user-balance');
    for (const element of balanceElements) {
        const userId = element.getAttribute('data-user-id');
        try {
            const response = await fetch(`/api/user-balance/${userId}`);
            const data = await response.json();
            if (data.balance !== undefined) {
                element.textContent = data.balance.toFixed(2) + ' RUB';
            } else {
                element.textContent = '0.00 RUB';
            }
        } catch (error) {
            console.error('Ошибка загрузки баланса для пользователя', userId, ':', error);
            element.textContent = 'Ошибка';
        }
    }
}

// Функции для кнопок в таблице пользователей
function openTelegramProfileFromTable(username) {
    if (username === 'N/A') {
        showNotification('Username недоступен', 'error');
        return;
    }
    
    // Убираем @ если есть
    const cleanUsername = username.startsWith('@') ? username.substring(1) : username;
    const telegramUrl = 'https://t.me/' + cleanUsername;
    window.open(telegramUrl, '_blank');
}

function copyUsernameFromTable(username) {
    if (username === 'N/A') {
        showNotification('Username недоступен', 'error');
        return;
    }
    
    const cleanUsername = username.startsWith('@') ? username : '@' + username;
    
    navigator.clipboard.writeText(cleanUsername).then(() => {
        showNotification('Username скопирован: ' + cleanUsername);
    }).catch(err => {
        console.error('Ошибка копирования: ', err);
        showNotification('Ошибка копирования', 'error');
    });
}