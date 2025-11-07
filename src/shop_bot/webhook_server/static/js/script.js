// Глобальная функция для копирования текста в буфер обмена
function copyKey(key) {
	// Проверяем доступность Clipboard API
	if (navigator.clipboard && window.isSecureContext) {
		// Используем современный Clipboard API
		navigator.clipboard.writeText(key).then(() => {
			showCopyNotification('Ключ скопирован!');
		}).catch(err => {
			console.error('Ошибка копирования через Clipboard API: ', err);
			// Fallback к старому методу
			fallbackCopyTextToClipboard(key);
		});
	} else {
		// Fallback для старых браузеров или небезопасного контекста
		fallbackCopyTextToClipboard(key);
	}
}

// Глобальные функции для работы с кебаб-меню
function toggleKebabMenu(menuId) {
	// Закрываем все другие кебаб-меню
	const allMenus = document.querySelectorAll('.kebab-menu')
	allMenus.forEach(menu => {
		if (menu.id !== menuId) {
			menu.classList.remove('active')
		}
	})
	
	// Переключаем текущее меню
	const menu = document.getElementById(menuId)
	if (menu) {
		menu.classList.toggle('active')
	}
}

function closeKebabMenu(menuId) {
	const menu = document.getElementById(menuId)
	if (menu) {
		menu.classList.remove('active')
	}
}

const PANEL_LOCALE = 'ru-RU'
const PANEL_TIMEZONE = window.panelTimeZone || 'Europe/Moscow'

function parseToPanelDate(value) {
	try {
		if (!value && value !== 0) {
			return null
		}

		if (value instanceof Date) {
			return isNaN(value.getTime()) ? null : value
		}

		const date = new Date(value)
		return isNaN(date.getTime()) ? null : date
	} catch (error) {
		console.warn('parseToPanelDate error:', error, value)
		return null
	}
}

function formatPanelDate(value, options = {}) {
	try {
		const date = parseToPanelDate(value)
		if (!date) {
			return 'N/A'
		}

		const formatter = new Intl.DateTimeFormat(PANEL_LOCALE, {
			timeZone: PANEL_TIMEZONE,
			...options,
		})

		return formatter.format(date)
	} catch (error) {
		console.warn('formatPanelDate error:', error, value)
		return 'N/A'
	}
}

function formatPanelDateTime(value, options = {}) {
	try {
		const defaultOptions = {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
		}
		return formatPanelDate(value, { ...defaultOptions, ...options })
	} catch (error) {
		console.warn('formatPanelDateTime error:', error, value)
		return 'N/A'
	}
}

function formatPanelTime(value, options = {}) {
	try {
		const defaultOptions = {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
		}
		return formatPanelDate(value, { ...defaultOptions, ...options })
	} catch (error) {
		console.warn('formatPanelTime error:', error, value)
		return 'N/A'
	}
}

// Fallback функция для копирования текста
function fallbackCopyTextToClipboard(text) {
	const textArea = document.createElement("textarea");
	textArea.value = text;
	
	// Избегаем прокрутки к элементу
	textArea.style.top = "0";
	textArea.style.left = "0";
	textArea.style.position = "fixed";
	textArea.style.opacity = "0";
	
	document.body.appendChild(textArea);
	textArea.focus();
	textArea.select();
	
	try {
		const successful = document.execCommand('copy');
		if (successful) {
			showCopyNotification('Ключ скопирован!');
		} else {
			showCopyNotification('Не удалось скопировать ключ', 'error');
		}
	} catch (err) {
		console.error('Ошибка fallback копирования: ', err);
		showCopyNotification('Не удалось скопировать ключ', 'error');
	}
	
	document.body.removeChild(textArea);
}

// Функция для показа уведомления о копировании
function showCopyNotification(message, type = 'success') {
	const notification = document.createElement('div');
	notification.textContent = message;
	notification.style.cssText = `
		position: fixed;
		top: 20px;
		right: 20px;
		background: ${type === 'error' ? '#dc3545' : '#28a745'};
		color: white;
		padding: 10px 20px;
		border-radius: 5px;
		z-index: 10000;
		font-size: 14px;
		box-shadow: 0 2px 4px rgba(0,0,0,0.2);
	`;
	document.body.appendChild(notification);
	
	setTimeout(() => {
		if (notification.parentNode) {
			document.body.removeChild(notification);
		}
	}, 2000);
}

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
		
		// Проверяем, находимся ли мы на странице авторизации
		const isLoginPage = document.body.classList.contains('login-page');
		
		if (!sidebar && !isLoginPage) return;
		
		// Загружаем сохраненное состояние меню
		const savedState = localStorage.getItem('sidebarState');
		const isMobile = window.innerWidth <= 599;
		const isTablet = window.innerWidth <= 899 && window.innerWidth >= 600;
		const isDesktop = window.innerWidth >= 900;
		
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
		if (isMobile && sidebar) {
			sidebar.classList.remove('sidebar-mobile-open');
		}
		
		// Специальная обработка для страницы авторизации
		if (isLoginPage) {
			const headerPanel = document.querySelector('.header-panel');
			if (headerPanel) {
				// На странице авторизации header-panel всегда занимает всю ширину
				headerPanel.style.left = '0';
				headerPanel.classList.add('header-panel-login');
			}
		}
		
		// Функция переключения меню для мобильных устройств
		// На мобильных устройствах sidebar полностью скрыт через CSS
		function toggleSidebarMobile() {
			// На мобильных устройствах sidebar скрыт, ничего не делаем
			if (window.innerWidth <= 599) {
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
				// Определяем ширину sidebar в зависимости от размера экрана
				let sidebarWidth = '280px'; // По умолчанию для десктопа
				if (window.innerWidth <= 1199 && window.innerWidth >= 900) {
					sidebarWidth = '260px'; // Планшеты в альбомной ориентации
				} else if (window.innerWidth <= 899 && window.innerWidth >= 600) {
					sidebarWidth = '240px'; // Планшеты в портретной ориентации
				}
				headerPanel.style.left = sidebarWidth;
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
				// Определяем ширину sidebar в зависимости от размера экрана
				let sidebarWidth = '280px'; // По умолчанию для десктопа
				if (window.innerWidth <= 1199 && window.innerWidth >= 900) {
					sidebarWidth = '260px'; // Планшеты в альбомной ориентации
				} else if (window.innerWidth <= 899 && window.innerWidth >= 600) {
					sidebarWidth = '240px'; // Планшеты в портретной ориентации
				}
				headerPanel.style.left = sidebarWidth;
			}
			// Сохраняем состояние
			localStorage.setItem('sidebarState', JSON.stringify({ hidden: false, collapsed: false }));
		}
		
		// Обработчик события для мобильного бургерного меню (теперь только через sidebarBurger)
		// burgerMenu удален, используем только sidebarBurger
		
		// Обработчик события для бургера в боковом меню (только для десктопа)
		if (sidebarBurger) {
			sidebarBurger.addEventListener('click', function() {
				if (window.innerWidth > 599) {
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
				if (window.innerWidth <= 599) {
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
				if (window.innerWidth <= 599) {
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
			if (window.innerWidth <= 599) {
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
			const headerPanel = document.querySelector('.header-panel');
			
			// Специальная обработка для страницы авторизации
			if (isLoginPage && headerPanel) {
				// На странице авторизации header-panel всегда занимает всю ширину
				headerPanel.style.left = '0';
				headerPanel.classList.add('header-panel-login');
				return;
			}
			
			if (window.innerWidth > 599) {
				// На десктопе убираем мобильные классы и блокировку скролла
				if (sidebar) {
					sidebar.classList.remove('sidebar-mobile-open');
				}
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
				if (sidebar) {
					sidebar.classList.remove('sidebar-mobile-open');
				}
				if (headerBurger) {
					headerBurger.classList.remove('burger-active');
				}
				document.body.style.overflow = '';
				
				// На мобильных устройствах header-panel занимает всю ширину
				if (headerPanel) {
					headerPanel.style.left = '0';
				}
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
	initializeTransactionsTableInteractions()
	initializeTopupBalanceModal()
	initializeTrialResetModal()
	
	// Закрываем все кебаб-меню при клике вне их
	document.addEventListener('click', function(event) {
		if (!event.target.closest('.kebab-wrapper')) {
			const allMenus = document.querySelectorAll('.kebab-menu')
			allMenus.forEach(menu => {
				menu.classList.remove('active')
			})
		}
	})
	
	// Загружаем заработанную сумму для всех пользователей на странице пользователей
	loadAllUsersEarned()
	loadAllUsersBalances()
})

// Функции для модального окна пользователя
// Объявляем переменную в глобальной области видимости
window.currentUserId = window.currentUserId || null;

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
let userSearchTimeout = null
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
    console.log('Initializing users table interactions...')
    
    // Открытие карточки по дабл-клику по строке
    const userRows = document.querySelectorAll('.users-table .user-row')
    console.log('Found user rows:', userRows.length)
    
    userRows.forEach(row => {
        row.addEventListener('dblclick', (e) => {
            console.log('Double click on user row:', row)
            e.preventDefault()
            e.stopPropagation()
            
            const userId = parseInt(row.getAttribute('data-user-id'))
            const username = row.getAttribute('data-username') || 'N/A'
            const isBanned = (row.getAttribute('data-is-banned') === 'true')
            const keysCount = parseInt(row.getAttribute('data-keys-count') || '0')
            
            console.log('Opening user modal for:', { userId, username, isBanned, keysCount })
            
            if (!isNaN(userId)) {
                openUserModal(userId, username, isBanned, isNaN(keysCount) ? 0 : keysCount)
            }
        })
    })

    console.log('Users table interactions initialized')
}

// Хелперы: открытие карточки пользователя и пополнения баланса из кнопки в строке таблицы
function openUserModalFromElement(buttonEl) {
    const row = buttonEl && buttonEl.closest ? buttonEl.closest('.user-row') : null;
    if (!row) return;
    const userId = parseInt(row.getAttribute('data-user-id'));
    const username = row.getAttribute('data-username') || 'N/A';
    const isBanned = row.getAttribute('data-is-banned') === 'true';
    const keysCount = parseInt(row.getAttribute('data-keys-count') || '0');
    if (!isNaN(userId)) {
        openUserModal(userId, username, isBanned, isNaN(keysCount) ? 0 : keysCount);
    }
}

function openTopupBalanceModalFromElement(buttonEl) {
    const row = buttonEl && buttonEl.closest ? buttonEl.closest('.user-row') : null;
    if (!row) return;
    const userId = parseInt(row.getAttribute('data-user-id'));
    const username = (row.getAttribute('data-username') || 'N/A').replace(/^@/, '');
    if (!isNaN(userId)) {
        openTopupBalanceModal(userId, username);
    } else {
        openTopupBalanceModal();
    }
}

// Инициализация действий таблицы транзакций: кебаб-меню
function initializeTransactionsTableInteractions() {
    // Кебаб-меню теперь работают на чистом CSS
}

// Кебаб-меню теперь работают на чистом CSS без JavaScript

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
        if (label) {
            label.textContent = ''
            label.style.display = 'none'
        }
        if (sugg) {
            sugg.innerHTML = ''
            sugg.style.display = 'none'
        }
        modal.style.display = 'flex'
    }
}

function closeCreateNotificationModal() {
    const modal = document.getElementById('createNotificationModal')
    if (modal) modal.style.display = 'none'
}

// Универсальная функция поиска пользователей
function debouncedUserSearch(query, context) {
    console.log('debouncedUserSearch вызвана с параметрами:', query, context)
    clearTimeout(userSearchTimeout)
    userSearchTimeout = setTimeout(() => searchUsers(query, context), 300)
}

async function searchUsers(query, context) {
    console.log('searchUsers вызвана с параметрами:', query, context)
    // Определяем элементы в зависимости от контекста
    let sugg, label, selectedId, input
    
    if (context === 'notification') {
        sugg = document.getElementById('notifUserSuggestions')
        label = document.getElementById('notifSelectedUserLabel')
        selectedId = document.getElementById('notifSelectedUserId')
        input = document.getElementById('notifUserSearch')
    } else if (context === 'topup') {
        sugg = document.getElementById('topupUserSuggestions')
        label = document.getElementById('topupSelectedUserLabel')
        selectedId = document.getElementById('topupSelectedUserId')
        input = document.getElementById('topupUserSearch')
    } else if (context === 'trialReset') {
        sugg = document.getElementById('trialResetUserSuggestions')
        label = document.getElementById('trialResetSelectedUserLabel')
        selectedId = document.getElementById('trialResetSelectedUserId')
        input = document.getElementById('trialResetUserSearch')
    } else {
        console.error('Неизвестный контекст поиска:', context)
        return
    }
    
    if (!sugg) {
        console.log('Элемент sugg не найден для контекста:', context)
        return
    }
    sugg.innerHTML = ''
    sugg.style.display = 'none'
    if (!query || query.trim().length < 1) {
        return
    }
    
    try {
        const resp = await fetch(`/api/search-users?q=${encodeURIComponent(query)}`)
        const data = await resp.json()
        const users = data.users || []
        
        if (users.length === 0) {
            sugg.innerHTML = '<div style="color:#999; padding:6px;">Не найдено</div>'
            sugg.style.display = 'block'
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
                if (label) {
                    label.textContent = `Выбрано: ${u.telegram_id} · @${u.username || 'N/A'}`
                    label.style.display = 'block'
                }
                if (input) input.value = `${u.telegram_id} · @${u.username || 'N/A'}`
                sugg.innerHTML = ''
                sugg.style.display = 'none'
            }
            sugg.appendChild(div)
        })
        sugg.style.display = 'block'
    } catch (e) {
        sugg.innerHTML = '<div style="color:#dc3545; padding:6px;">Ошибка поиска</div>'
        sugg.style.display = 'block'
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
	window.currentUserId = userId
	
	// Заполняем основную информацию пользователя (будет обновлено при загрузке данных)
	const modalUserIdEl = document.getElementById('modalUserId')
	if (modalUserIdEl) {
		modalUserIdEl.setAttribute('data-original', String(userId))
		modalUserIdEl.textContent = String(userId)
	}
	
	document.getElementById('modalStatus').innerHTML = isBanned ? 
		'<span class="status-badge status-banned">Забанен</span>' : 
		'<span class="status-badge status-active">Активен</span>'
	
	// Показываем/скрываем кнопки в кебаб-меню в зависимости от статуса
	const drawerBanButton = document.getElementById('drawerBanButton')
	const drawerUnbanButton = document.getElementById('drawerUnbanButton')
	const drawerRevokeConsentButton = document.getElementById('drawerRevokeConsentButton')
	
	if (isBanned) {
		drawerBanButton.style.display = 'none'
		drawerUnbanButton.style.display = 'block'
	} else {
		drawerBanButton.style.display = 'block'
		drawerUnbanButton.style.display = 'none'
	}
	
	// Проверяем согласие с документами для показа кнопки отзыва
	// Это будет обновлено после загрузки данных пользователя
	
	// Переключаемся на первую вкладку (userdata)
	switchTab('userdata')
	
	// Загружаем данные для всех вкладок
	loadUserDetails(userId)
	loadUserPayments(userId)
	loadUserKeys(userId)
	loadUserNotifications(userId)
	
	// Показываем drawer с анимацией
	const drawer = document.getElementById('userDrawer')
	drawer.style.display = 'block'
	// Небольшая задержка для запуска анимации
	setTimeout(() => {
		drawer.classList.add('active')
	}, 10)
	
	// Применяем скрытый режим после заполнения
	if (window.__HIDDEN_MODE__) {
		applyHiddenMode()
	}
}

function closeUserModal() {
	const drawer = document.getElementById('userDrawer')
	drawer.classList.remove('active')
	// Ждем завершения анимации перед скрытием
	setTimeout(() => {
		drawer.style.display = 'none'
		window.currentUserId = null
	}, 300)
}

// Закрытие drawer при клике на overlay
document.addEventListener('DOMContentLoaded', function() {
	const drawerOverlay = document.getElementById('userDrawer')
	if (drawerOverlay) {
		drawerOverlay.addEventListener('click', function(e) {
			if (e.target === drawerOverlay) {
				closeUserModal()
			}
		})
	}
	
	// Закрытие drawer транзакций при клике на overlay
	const transactionDrawerOverlay = document.getElementById('transactionDrawer')
	if (transactionDrawerOverlay) {
		transactionDrawerOverlay.addEventListener('click', function(e) {
			if (e.target === transactionDrawerOverlay) {
				closeTransactionModal()
			}
		})
	}
})

// ============================================
// Функции для работы с Transaction Drawer
// ============================================

let currentTransactionId = null;

function openTransactionModal(transactionId) {
	currentTransactionId = transactionId;
	
	// Показываем drawer
	const drawer = document.getElementById('transactionDrawer');
	if (!drawer) {
		console.error('Transaction drawer not found');
		return;
	}
	
	drawer.style.display = 'flex';
	// Небольшая задержка для анимации
	setTimeout(() => {
		drawer.classList.add('active');
	}, 10);
	
	// Загружаем данные транзакции
	loadTransactionDetails(transactionId);
}

function closeTransactionModal() {
	const drawer = document.getElementById('transactionDrawer');
	if (!drawer) return;
	
	drawer.classList.remove('active');
	// Ждем завершения анимации перед скрытием
	setTimeout(() => {
		drawer.style.display = 'none';
		currentTransactionId = null;
	}, 300);
}

function loadTransactionDetails(transactionId) {
	// Показываем индикатор загрузки
	const detailElements = [
		'txModalId', 'txModalStatus', 'txModalAmount', 'txModalPaymentMethod',
		'txDetailId', 'txDetailPaymentId', 'txDetailDate', 'txDetailStatus',
		'txDetailUserId', 'txDetailUsername', 'txDetailAmountRub', 'txDetailAmountCurrency',
		'txDetailCurrencyName', 'txDetailPaymentMethod', 'txDetailHash', 'txDetailPaymentLink',
		'txDetailOperationType', 'txDetailHost', 'txDetailPlan', 'txDetailConnectionString',
		'txDetailMetadata'
	];
	
	detailElements.forEach(id => {
		const el = document.getElementById(id);
		if (el) el.textContent = 'Загрузка...';
	});
	
	// Запрос данных транзакции
	fetch(`/api/transaction/${transactionId}`)
		.then(response => {
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			return response.json();
		})
		.then(data => {
			if (data.status === 'success' && data.transaction) {
				populateTransactionDrawer(data.transaction);
			} else {
				console.error('Failed to load transaction:', data.message);
				showErrorInDrawer('Ошибка загрузки данных транзакции');
			}
		})
		.catch(error => {
			console.error('Error loading transaction:', error);
			showErrorInDrawer('Ошибка соединения с сервером');
		});
}

function populateTransactionDrawer(tx) {
	// Безопасная функция для установки значения
	const setValue = (id, value, defaultValue = '—') => {
		const el = document.getElementById(id);
		if (el) {
			el.textContent = value !== null && value !== undefined && value !== '' ? value : defaultValue;
		}
	};
	
	// Безопасная функция для установки HTML
	const setHTML = (id, html, defaultValue = '—') => {
		const el = document.getElementById(id);
		if (el) {
			el.innerHTML = html || defaultValue;
		}
	};
	
	// Парсим metadata если это строка
	let metadata = tx.metadata;
	if (typeof metadata === 'string') {
		try {
			metadata = JSON.parse(metadata);
		} catch (e) {
			console.error('Failed to parse metadata:', e);
			metadata = {};
		}
	}
	
	// Заполняем верхнюю часть (закрепленная информация)
	setValue('txModalId', tx.transaction_id);
	
	// Статус с badge
	let statusBadge = '—';
	if (tx.status) {
		const statusClass = tx.status === 'paid' ? 'status-paid' : 
						   tx.status === 'pending' ? 'status-pending' : 
						   `status-${tx.status}`;
		const statusText = tx.status === 'paid' ? 'Оплачено' : 
						  tx.status === 'pending' ? 'Ожидает' : 
						  tx.status;
		statusBadge = `<span class="status-badge ${statusClass}">${statusText}</span>`;
	}
	setHTML('txModalStatus', statusBadge);
	
	// Сумма
	let amountText = '—';
	if (tx.amount_rub !== null && tx.amount_rub !== undefined) {
		amountText = `${parseFloat(tx.amount_rub).toFixed(2)} RUB`;
		if (tx.payment_method === 'Stars' && tx.amount_currency) {
			amountText += ` (${parseInt(tx.amount_currency)}⭐️)`;
		}
	}
	setValue('txModalAmount', amountText);
	setValue('txModalPaymentMethod', tx.payment_method);
	
	// Заполняем детальную информацию
	// Основное
	setValue('txDetailId', tx.transaction_id);
	setValue('txDetailPaymentId', tx.payment_id);
	
	// Дата
	let dateText = formatPanelDateTime(tx.created_date);
	if (dateText === 'N/A') {
		dateText = tx.created_date || '—';
	}
	setValue('txDetailDate', dateText);
	setHTML('txDetailStatus', statusBadge);
	
	// Пользователь
	setValue('txDetailUserId', tx.user_id);
	setValue('txDetailUsername', tx.username ? `@${tx.username}` : '—');
	
	// Платеж
	setValue('txDetailAmountRub', tx.amount_rub !== null ? `${parseFloat(tx.amount_rub).toFixed(2)} RUB` : '—');
	setValue('txDetailAmountCurrency', tx.amount_currency || '—');
	setValue('txDetailCurrencyName', tx.currency_name || '—');
	setValue('txDetailPaymentMethod', tx.payment_method);
	
	// Хеш транзакции с возможностью копирования
	if (tx.transaction_hash) {
		const hashEl = document.getElementById('txDetailHash');
		if (hashEl) {
			if (tx.payment_method === 'TON Connect') {
				hashEl.innerHTML = `<a href="https://tonscan.org/tx/${tx.transaction_hash}" target="_blank" class="transaction-link">${tx.transaction_hash}</a>`;
			} else {
				hashEl.textContent = tx.transaction_hash;
			}
		}
	} else {
		setValue('txDetailHash', '—');
	}
	
	// Ссылка на оплату
	setValue('txDetailPaymentLink', tx.payment_link);
	
	// Детали заказа
	// Тип операции
	let operationType = '—';
	if (metadata) {
		if (metadata.operation === 'topup' || metadata.type === 'balance_topup') {
			operationType = 'Зачисление';
		} else if (metadata.action) {
			operationType = metadata.action === 'new' ? 'Новый' : 'Продление';
		}
	}
	setValue('txDetailOperationType', operationType);
	
	// Хост и план
	setValue('txDetailHost', metadata?.host_name || '—');
	
	let planText = '—';
	if (metadata && (metadata.operation === 'topup' || metadata.type === 'balance_topup')) {
		planText = '—';
	} else if (metadata?.is_trial === 1) {
		planText = 'Триал';
	} else {
		planText = metadata?.plan_name || '—';
	}
	setValue('txDetailPlan', planText);
	
	// Ключ подключения
	setValue('txDetailConnectionString', metadata?.connection_string || '—');
	
	// Метаданные (JSON)
	const metadataEl = document.getElementById('txDetailMetadata');
	if (metadataEl) {
		if (metadata && Object.keys(metadata).length > 0) {
			metadataEl.textContent = JSON.stringify(metadata, null, 2);
		} else {
			metadataEl.textContent = '—';
		}
	}
}

function showErrorInDrawer(message) {
	const detailElements = [
		'txModalId', 'txModalStatus', 'txModalAmount', 'txModalPaymentMethod',
		'txDetailId', 'txDetailPaymentId', 'txDetailDate', 'txDetailStatus',
		'txDetailUserId', 'txDetailUsername', 'txDetailAmountRub', 'txDetailAmountCurrency',
		'txDetailCurrencyName', 'txDetailPaymentMethod', 'txDetailHash', 'txDetailPaymentLink',
		'txDetailOperationType', 'txDetailHost', 'txDetailPlan', 'txDetailConnectionString',
		'txDetailMetadata'
	];
	
	detailElements.forEach(id => {
		const el = document.getElementById(id);
		if (el) el.textContent = message;
	});
}

// ============================================

function banUser() {
	if (window.currentUserId && confirm('Вы уверены, что хотите забанить этого пользователя? Он не сможет пользоваться ботом.')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/ban/<int:user_id>
        form.action = `/users/ban/${window.currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function unbanUser() {
	if (window.currentUserId && confirm('Вы уверены, что хотите разбанить этого пользователя?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/unban/<int:user_id>
        form.action = `/users/unban/${window.currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function revokeKeys() {
	if (window.currentUserId && confirm('ВНИМАНИЕ! Это действие удалит ВСЕ ключи пользователя с серверов. Вы уверены?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        // Совместить с существующим Flask-роутом /users/revoke/<int:user_id>
        form.action = `/users/revoke/${window.currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function revokeConsent() {
	if (window.currentUserId && confirm('Вы уверены, что хотите отозвать согласие этого пользователя с документами?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
        form.action = `/users/revoke-consent/${window.currentUserId}`
		
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
	const activeButton = document.querySelector(`[onclick="switchTab('${tabName}')"]`)
	if (activeButton) {
		activeButton.classList.add('active')
	}
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
				
				// Определяем тип операции и описание
				let operationType = 'N/A'
				let description = ''
				
				if (payment.metadata) {
					try {
						const metadata = typeof payment.metadata === 'string' ? JSON.parse(payment.metadata) : payment.metadata
						if (metadata.type === 'balance_topup' || metadata.operation === 'topup') {
							operationType = 'Зачисление'
							description = 'Пополнение баланса'
						} else if (metadata.action) {
							operationType = metadata.action === 'new' ? 'Новый' : 'Продление'
							description = `${metadata.host_name || 'N/A'} · ${metadata.plan_name || 'N/A'}`
						}
					} catch (e) {
						// не критично
					}
				} else if (payment.payment_method === 'Balance') {
					operationType = 'Зачисление'
					description = 'Пополнение баланса'
				} else {
					description = `${payment.host_name || 'N/A'} · ${payment.plan_name || 'N/A'}`
				}
				
			const formattedPaymentDate = formatPanelDateTime(payment.created_date)
			const dateCell = formattedPaymentDate !== 'N/A' ? formattedPaymentDate : (payment.created_date || 'N/A')
				const amountCell = payment.amount_rub ? payment.amount_rub.toFixed(2) + ' RUB' : 'N/A'
				
				row.innerHTML = `
					<td>${dateCell}</td>
					<td>${operationType}</td>
					<td data-field="price">${amountCell}</td>
					<td>${description}</td>
				`
				tbody.appendChild(row)
			})
			applyHiddenMode()
		} else {
			tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #999;">Нет платежей</td></tr>'
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
				const planName = key.is_trial == 1 ? 'Триал' : (key.plan_name || 'N/A')
			const keyCreatedDisplay = (() => {
				const formatted = formatPanelDateTime(key.created_date)
				return formatted !== 'N/A' ? formatted : (key.created_date || 'N/A')
			})()

				row.innerHTML = `
					<td>${key.key_id}</td>
					<td>${key.host_name || 'N/A'}</td>
					<td>${planName}</td>
					<td>
						${key.connection_string ? 
							`<div class="key-cell">
								<span class="key-text" title="${key.connection_string}">${key.connection_string.substring(0, 30)}...</span>
								<button class="copy-btn" onclick="copyKey('${key.connection_string.replace(/'/g, "\\'")}')" title="Копировать ключ">📋</button>
							</div>` : 
							'-'
						}
					</td>
				<td>${keyCreatedDisplay}</td>
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
					<td>${n.created_date || ''}</td>
					<td>${n.type || '-'}</td>
					<td>${n.title || '-'}</td>
					<td>
						${n.status === 'resent' ? '<span class="status-badge status-active">Повтор</span>' : (n.status === 'sent' ? '<span class="status-badge status-active">Отправлено</span>' : '<span class="status-badge">' + (n.status || '-') + '</span>')}
					</td>
				`
				tbody.appendChild(row)
			})
			applyHiddenMode()
		} else {
            			tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #999;">Нет уведомлений</td></tr>'
        }
    } catch (error) {
        console.error('Ошибка загрузки уведомлений:', error)
        document.getElementById('modalNotificationsTable').innerHTML = '<tr><td colspan="5" style="text-align: center; color: #dc3545;">Ошибка загрузки</td></tr>'
    }
}

// Функция для загрузки полных данных пользователя
async function loadUserDetails(userId) {
	try {
		const response = await fetch(`/api/user-details/${userId}`)
		const data = await response.json()
		
		if (data.error) {
			console.error('Ошибка:', data.error)
			return
		}
		
		const user = data.user
		
		// Обновляем закрепленную информацию
		const modalFullname = document.getElementById('modalFullname')
		if (modalFullname) {
			const fullnameText = user.fullname || 'N/A'
			modalFullname.setAttribute('data-original', fullnameText)
			modalFullname.textContent = fullnameText
		}
		
		const modalBalance = document.getElementById('modalBalance')
		if (modalBalance) {
			const balanceText = (user.balance || 0).toFixed(2) + ' RUB'
			modalBalance.setAttribute('data-original', balanceText)
			modalBalance.textContent = balanceText
		}
		
		const modalEarned = document.getElementById('modalEarned')
		if (modalEarned) {
			const earnedText = (user.earned || 0).toFixed(2) + ' RUB'
			modalEarned.setAttribute('data-original', earnedText)
			modalEarned.textContent = earnedText
		}
		
		// Заполняем детальную информацию на вкладке "Данные пользователя"
		document.getElementById('detailUserId').textContent = user.user_id || '—'
		document.getElementById('detailTelegramId').textContent = user.telegram_id || '—'
		
		const usernameEl = document.getElementById('detailUsername')
		const usernameText = user.username ? '@' + user.username : 'N/A'
		usernameEl.setAttribute('data-original', usernameText)
		usernameEl.textContent = usernameText
		
		const fullnameEl = document.getElementById('detailFullname')
		const fullnameDetailText = user.fullname || 'N/A'
		fullnameEl.setAttribute('data-original', fullnameDetailText)
		fullnameEl.textContent = fullnameDetailText
		
		// Заполняем input поля напрямую (span элементы скрыты)
		const fioInputEl = document.getElementById('detailFioInput')
		if (fioInputEl) {
			fioInputEl.value = user.fio || ''
			fioInputEl.defaultValue = user.fio || ''
		}
		
		const emailInputEl = document.getElementById('detailEmailInput')
		if (emailInputEl) {
			emailInputEl.value = user.email || ''
			emailInputEl.defaultValue = user.email || ''
		}
		
		// Загружаем группы пользователей и заполняем select после загрузки
		loadUserGroups().then(() => {
			const groupSelectEl = document.getElementById('detailGroupInput')
			if (groupSelectEl && user.group_id) {
				groupSelectEl.value = user.group_id
				groupSelectEl.defaultValue = user.group_id
			}
		}).catch(error => {
			console.error('Ошибка загрузки групп:', error)
		})
		
		const detailBalance = document.getElementById('detailBalance')
		const detailBalanceText = (user.balance || 0).toFixed(2) + ' RUB'
		detailBalance.setAttribute('data-original', detailBalanceText)
		detailBalance.textContent = detailBalanceText
		
		const detailReferralBalance = document.getElementById('detailReferralBalance')
		const detailReferralBalanceText = (user.referral_balance || 0).toFixed(2) + ' RUB'
		detailReferralBalance.setAttribute('data-original', detailReferralBalanceText)
		detailReferralBalance.textContent = detailReferralBalanceText
		
		const detailReferralBalanceAll = document.getElementById('detailReferralBalanceAll')
		const detailReferralBalanceAllText = (user.referral_balance_all || 0).toFixed(2) + ' RUB'
		detailReferralBalanceAll.setAttribute('data-original', detailReferralBalanceAllText)
		detailReferralBalanceAll.textContent = detailReferralBalanceAllText
		
		const detailTotalSpent = document.getElementById('detailTotalSpent')
		const detailTotalSpentText = (user.total_spent || 0).toFixed(2) + ' RUB'
		detailTotalSpent.setAttribute('data-original', detailTotalSpentText)
		detailTotalSpent.textContent = detailTotalSpentText
		
		const detailEarned = document.getElementById('detailEarned')
		const detailEarnedText = (user.earned || 0).toFixed(2) + ' RUB'
		detailEarned.setAttribute('data-original', detailEarnedText)
		detailEarned.textContent = detailEarnedText
		
		const detailAutoRenewal = document.getElementById('detailAutoRenewal')
		const autoRenewalEnabled = user.auto_renewal_enabled !== undefined ? user.auto_renewal_enabled : true
		const detailAutoRenewalText = autoRenewalEnabled ? 'Включено' : 'Отключено'
		detailAutoRenewal.setAttribute('data-original', detailAutoRenewalText)
		detailAutoRenewal.textContent = detailAutoRenewalText
		
		document.getElementById('detailTotalMonths').textContent = user.total_months || '0'
		document.getElementById('detailTrialUsed').textContent = user.trial_used ? 'Да' : 'Нет'
		document.getElementById('detailTrialDaysGiven').textContent = user.trial_days_given || '0'
		document.getElementById('detailTrialReusesCount').textContent = user.trial_reuses_count || '0'
		document.getElementById('detailAgreedToTerms').textContent = user.agreed_to_terms ? 'Да' : 'Нет'
		document.getElementById('detailAgreedToDocuments').textContent = user.agreed_to_documents ? 'Да' : 'Нет'
		
		// Показываем/скрываем кнопку отзыва согласия в кебаб-меню
		const drawerRevokeConsentButton = document.getElementById('drawerRevokeConsentButton')
		if (user.agreed_to_documents) {
			drawerRevokeConsentButton.style.display = 'block'
		} else {
			drawerRevokeConsentButton.style.display = 'none'
		}
		
		// Статус подписки
		let subscriptionStatusText = 'Не проверено'
		if (user.subscription_status === 'subscribed') {
			subscriptionStatusText = '✅ Подписан'
		} else if (user.subscription_status === 'not_subscribed') {
			subscriptionStatusText = '❌ Не подписан'
		}
		document.getElementById('detailSubscriptionStatus').textContent = subscriptionStatusText
		
		// Дата регистрации
	const registrationDateFormatted = formatPanelDateTime(user.registration_date)
	const registrationDate = registrationDateFormatted !== 'N/A' ? registrationDateFormatted : (user.registration_date || 'N/A')
		document.getElementById('detailRegistrationDate').textContent = registrationDate
		
		document.getElementById('detailIsBanned').innerHTML = user.is_banned ? 
			'<span class="status-badge status-banned">Да</span>' : 
			'<span class="status-badge status-active">Нет</span>'
		
		document.getElementById('detailReferredBy').textContent = 'N/A'
		document.getElementById('detailKeysCount').textContent = user.keys_count || '0'
		document.getElementById('detailNotificationsCount').textContent = user.notifications_count || '0'
		
		// Применяем скрытый режим после заполнения
		if (window.__HIDDEN_MODE__) {
			applyHiddenMode()
		}
	} catch (error) {
		console.error('Ошибка загрузки данных пользователя:', error)
	}
}

// Функции для кебаб-меню в drawer
function toggleDrawerKebabMenu(menuId) {
	// Закрываем все другие кебаб-меню
	const allMenus = document.querySelectorAll('.kebab-menu')
	allMenus.forEach(menu => {
		if (menu.id !== menuId) {
			menu.classList.remove('active')
		}
	})
	
	// Переключаем текущее меню
	const menu = document.getElementById(menuId)
	if (menu) {
		menu.classList.toggle('active')
	}
}

function closeDrawerKebabMenu() {
	const menu = document.getElementById('drawer-kebab-menu')
	if (menu) {
		menu.classList.remove('active')
	}

}

// Функция загрузки групп пользователей
async function loadUserGroups() {
	try {
		const response = await fetch('/api/user-groups');
		const data = await response.json();
		
		if (data.success) {
			// Заполняем select в карточке пользователя
			const groupSelect = document.getElementById('detailGroupInput');
			if (groupSelect) {
				// Сохраняем текущее значение перед перезаписью
				const currentValue = groupSelect.value;
				
				groupSelect.innerHTML = '<option value="">Выберите группу</option>';
				data.groups.forEach(group => {
					const option = document.createElement('option');
					option.value = group.group_id;
					option.textContent = group.group_name;
					groupSelect.appendChild(option);
				});
				
				// Восстанавливаем значение, если оно было установлено
				if (currentValue && currentValue !== '') {
					groupSelect.value = currentValue;
				}
			}
			
			return data.groups;
		} else {
			console.error('Ошибка загрузки групп:', data.error);
			return [];
		}
	} catch (error) {
		console.error('Ошибка загрузки групп:', error);
		return [];
	}
}

// Функции для редактирования полей
function makeFieldEditable(fieldName) {
	console.log('makeFieldEditable called for:', fieldName)
	
	const displayField = document.getElementById(`detail${fieldName}`)
	const inputField = document.getElementById(`detail${fieldName}Input`)
	const container = displayField ? displayField.closest('.editable-item') : null
	
	console.log('Elements found:', { displayField, inputField, container })
	
	if (!displayField || !inputField || !container) {
		console.error('Required elements not found for field:', fieldName)
		return
	}
	
	// Сначала выходим из режима редактирования других полей
	const allEditingFields = document.querySelectorAll('.editable-item.editing')
	allEditingFields.forEach(item => {
		const fieldContainer = item
		const fieldInput = fieldContainer.querySelector('.editable-field')
		if (fieldInput && fieldInput._keyHandler) {
			fieldInput.removeEventListener('keydown', fieldInput._keyHandler)
			fieldInput._keyHandler = null
		}
		fieldContainer.classList.remove('editing')
	})
	
	// Переключаем в режим редактирования
	container.classList.add('editing')
	console.log('Added editing class to container')
	
	// Устанавливаем текущее значение в input
	const currentValue = displayField.textContent === '—' ? '' : displayField.textContent
	
	if (fieldName === 'Group') {
		// Для группы находим option по тексту
		const options = inputField.querySelectorAll('option')
		let selectedValue = ''
		options.forEach(option => {
			if (option.textContent === currentValue) {
				selectedValue = option.value
			}
		})
		inputField.value = selectedValue
		
		// Если группы не загружены, загружаем их
		if (options.length <= 1) { // Только "Выберите группу"
			loadUserGroups().then(() => {
				// После загрузки групп восстанавливаем выбранное значение
				if (selectedValue) {
					inputField.value = selectedValue;
				}
			});
		}
	} else {
		inputField.value = currentValue
	}
	
	inputField.style.display = 'block'
	displayField.style.display = 'none'
	
	console.log('Input field value set to:', currentValue)
	
	// Фокусируемся и выделяем текст
	setTimeout(() => {
		console.log('Attempting to focus input field')
		inputField.focus()
		
		// Для select элемента не вызываем select()
		if (inputField.tagName !== 'SELECT') {
			inputField.select()
			
			// Убеждаемся, что каретка видна
			inputField.setSelectionRange(0, inputField.value.length)
		}
		
		// Принудительно показываем каретку
		inputField.click()
		inputField.focus()
		
		// Дополнительная проверка для браузеров
		if (document.activeElement !== inputField) {
			console.log('Input not focused, trying again')
			inputField.focus()
		}
		
		console.log('Active element:', document.activeElement)
		console.log('Input field focused:', document.activeElement === inputField)
	}, 100)
	
	// Показываем кнопку сохранения
	const saveButton = document.getElementById('saveUserButton')
	if (saveButton) {
		saveButton.style.display = 'inline-block'
		console.log('Save button shown')
	}
	
	// Обработчик для сохранения по Enter
	const handleKeyPress = (e) => {
		if (e.key === 'Enter') {
			e.preventDefault()
			saveUserChanges()
		} else if (e.key === 'Escape') {
			e.preventDefault()
			cancelEdit(fieldName)
		}
	}
	
	// Для select добавляем обработчик изменения
	if (fieldName === 'Group') {
		const handleChange = () => {
			saveUserChanges()
		}
		inputField.addEventListener('change', handleChange)
		inputField._changeHandler = handleChange
	}
	
	inputField.addEventListener('keydown', handleKeyPress)
	inputField._keyHandler = handleKeyPress
}

function cancelEdit(fieldName) {
	const displayField = document.getElementById(`detail${fieldName}`)
	const inputField = document.getElementById(`detail${fieldName}Input`)
	const container = displayField.closest('.editable-item')
	
	if (displayField && inputField && container) {
		// Возвращаем исходное значение
		const originalValue = displayField.getAttribute('data-original') || '—'
		inputField.value = originalValue
		displayField.textContent = originalValue
		
		// Переключаем обратно в режим отображения
		container.classList.remove('editing')
		inputField.style.display = 'none'
		displayField.style.display = 'inline'
		
		// Убираем обработчик событий
		if (inputField._keyHandler) {
			inputField.removeEventListener('keydown', inputField._keyHandler)
			inputField._keyHandler = null
		}
		
		if (inputField._changeHandler) {
			inputField.removeEventListener('change', inputField._changeHandler)
			inputField._changeHandler = null
		}
		
		// Скрываем кнопку сохранения если нет других редактируемых полей
		const editingFields = document.querySelectorAll('.editable-item.editing')
		if (editingFields.length === 0) {
			const saveButton = document.getElementById('saveUserButton')
			if (saveButton) {
				saveButton.style.display = 'none'
			}
		}
	}
}

// Функция для инициализации обработчиков редактирования
function initializeEditableFields() {
	// Удаляем старые обработчики если есть
	if (window.editableClickHandler) {
		document.removeEventListener('click', window.editableClickHandler)
	}
	
	// Создаем новый обработчик
	window.editableClickHandler = function(e) {
		// Проверяем, что клик не по input полю
		if (e.target.classList.contains('editable-field') || e.target.tagName === 'INPUT') {
			return
		}
		
		// Проверяем, что клик не по кебаб-меню или его элементам
		if (e.target.closest('.kebab-wrapper') || e.target.closest('.kebab-menu') || e.target.closest('.kebab-btn')) {
			return
		}
		
		// Проверяем, что клик не по строке таблицы (для открытия карточки пользователя)
		if (e.target.closest('.user-row')) {
			return
		}
		
		// Ищем ближайший редактируемый элемент
		const editableItem = e.target.closest('.editable-item')
		
		if (!editableItem) {
			return
		}
		
		console.log('Found editable item:', editableItem)
		
		// Если элемент уже в режиме редактирования - ничего не делаем
		if (editableItem.classList.contains('editing')) {
			console.log('Item already in editing mode')
			return
		}
		
		e.preventDefault()
		e.stopPropagation()
		
		// Определяем тип поля по ID элемента
		const displayField = editableItem.querySelector('[id^="detail"]:not([id$="Input"])')
		if (!displayField) {
			console.log('No display field found')
			return
		}
		
		const fieldId = displayField.id
		console.log('Clicked on field:', fieldId)
		
		if (fieldId === 'detailFio') {
			makeFieldEditable('Fio')
		} else if (fieldId === 'detailEmail') {
			makeFieldEditable('Email')
		} else if (fieldId === 'detailGroup') {
			makeFieldEditable('Group')
		}
	}
	
	// Добавляем обработчик
	document.addEventListener('click', window.editableClickHandler, true)
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
	// Закрытие кебаб-меню при клике вне его
	document.addEventListener('click', function(e) {
		if (!e.target.closest('.kebab-wrapper')) {
			closeDrawerKebabMenu()
		}
	})
})

// Функция сохранения изменений пользователя
async function saveUserChanges() {
	if (!window.currentUserId) return
	
	const fioInput = document.getElementById('detailFioInput')
	const emailInput = document.getElementById('detailEmailInput')
	const groupInput = document.getElementById('detailGroupInput')
	
	const changes = {}
	
	if (fioInput && fioInput.value !== fioInput.defaultValue) {
		changes.fio = fioInput.value
	}
	
	if (emailInput && emailInput.value !== emailInput.defaultValue) {
		changes.email = emailInput.value
	}
	
	if (groupInput && groupInput.value !== groupInput.defaultValue && groupInput.value !== '') {
		// Используем value напрямую, так как в loadUserGroups мы установили group_id как value
		changes.group_id = parseInt(groupInput.value) || groupInput.value
	}
	
	if (Object.keys(changes).length === 0) {
		showNotification('Нет изменений для сохранения', 'info')
		return
	}
	
	try {
		const response = await fetch(`/api/update-user/${window.currentUserId}`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(changes)
		})
		
		const data = await response.json()
		
		if (response.ok) {
			// Обновляем defaultValue для отслеживания изменений
			if (changes.fio !== undefined) {
				const fioInput = document.getElementById('detailFioInput')
				if (fioInput) {
					fioInput.defaultValue = changes.fio || ''
				}
			}
			
			if (changes.email !== undefined) {
				const emailInput = document.getElementById('detailEmailInput')
				if (emailInput) {
					emailInput.defaultValue = changes.email || ''
				}
			}
			
			if (changes.group_id !== undefined) {
				const groupInput = document.getElementById('detailGroupInput')
				if (groupInput) {
					groupInput.defaultValue = changes.group_id
				}
			}
			
			// Обновляем строку в таблице пользователей
			updateUserRowInTable(window.currentUserId, changes)
			
			// Показываем уведомление без alert
			showNotification('Изменения сохранены успешно', 'success')
			
			// Применяем скрытый режим
			if (window.__HIDDEN_MODE__) {
				applyHiddenMode()
			}
		} else {
			showNotification(data.error || 'Ошибка сохранения изменений', 'error')
		}
	} catch (error) {
		console.error('Ошибка сохранения:', error)
		showNotification('Ошибка сохранения изменений', 'error')
	}
}

// Функция обновления строки пользователя в таблице
function updateUserRowInTable(userId, changes) {
	const userRow = document.querySelector(`tr.user-row[data-user-id="${userId}"]`)
	if (!userRow) return
	
	// Обновляем ФИО
	if (changes.fio !== undefined) {
		const fioCell = userRow.querySelector('td[data-field="fio"]')
		if (fioCell) {
			const fioSpan = fioCell.querySelector('span')
			if (fioSpan) {
				fioSpan.textContent = changes.fio || 'N/A'
			}
			fioCell.setAttribute('data-original', changes.fio || '')
		}
	}
	
	// Обновляем группу
	if (changes.group_id !== undefined) {
		const groupCell = userRow.querySelector('td[data-field="group"]')
		if (groupCell) {
			const groupSpan = groupCell.querySelector('.group-badge')
			if (groupSpan) {
				// Находим название группы по ID
				const groupSelect = document.getElementById('detailGroupInput')
				if (groupSelect) {
					const selectedOption = groupSelect.querySelector(`option[value="${changes.group_id}"]`)
					const groupName = selectedOption ? selectedOption.textContent : 'N/A'
					groupSpan.textContent = groupName
				}
			}
			groupCell.setAttribute('data-original', changes.group_id || '')
		}
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

// Функции для модального окна пополнения баланса
function initializeTopupBalanceModal() {
    // Закрытие по клику вне окна
    window.addEventListener('click', function (event) {
        const modal = document.getElementById('topupBalanceModal');
        if (!modal) return;
        if (event.target === modal) {
            closeTopupBalanceModal();
        }
    });
}

function openTopupBalanceModal(userId = null, username = null) {
    const modal = document.getElementById('topupBalanceModal');
    if (modal) {
        // Сброс полей
        const input = document.getElementById('topupUserSearch');
        const selectedId = document.getElementById('topupSelectedUserId');
        const label = document.getElementById('topupSelectedUserLabel');
        const sugg = document.getElementById('topupUserSuggestions');
        const amount = document.getElementById('topupAmount');
        
        if (input) input.value = '';
        if (selectedId) selectedId.value = '';
        if (label) {
            label.textContent = ''
            label.style.display = 'none'
        }
        if (sugg) {
            sugg.innerHTML = ''
            sugg.style.display = 'none'
        }
        if (amount) amount.value = '';
        
        // Если передан userId, заполняем поля
        if (userId && username) {
            if (selectedId) selectedId.value = String(userId);
            if (label) {
                label.textContent = `Выбрано: ${userId} · @${username}`;
                label.style.display = 'block';
            }
            if (input) input.value = `${userId} · @${username}`;
        }
        
        // Поиск пользователей инициализируется через inline обработчик oninput
        
        modal.style.display = 'flex';
    }
}

function openTopupBalanceModalFromUserModal() {
    // Получаем данные из модального окна пользователя
    const modalUserIdEl = document.getElementById('modalUserId');
    const modalUsernameEl = document.getElementById('modalUsername');
    
    if (modalUserIdEl && modalUsernameEl) {
        const userId = modalUserIdEl.textContent.trim();
        const username = modalUsernameEl.textContent.trim().replace('@', '');
        openTopupBalanceModal(userId, username);
    } else {
        openTopupBalanceModal();
    }
}

function closeTopupBalanceModal() {
    const modal = document.getElementById('topupBalanceModal');
    if (modal) modal.style.display = 'none';
}


async function submitTopupBalance() {
    const userIdEl = document.getElementById('topupSelectedUserId');
    const amountEl = document.getElementById('topupAmount');
    const userId = userIdEl && userIdEl.value ? parseInt(userIdEl.value) : null;
    const amount = amountEl ? parseFloat(amountEl.value) : null;
    
    if (!userId || !amount || amount <= 0) {
        alert('Выберите пользователя и введите корректную сумму');
        return;
    }
    
    try {
        const resp = await fetch('/api/topup-balance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId, amount: amount })
        });
        const data = await resp.json();
        if (resp.ok) {
            alert(data.message || 'Баланс успешно пополнен');
            closeTopupBalanceModal();
            // Перезагрузим страницу, чтобы увидеть обновленный баланс
            window.location.reload();
        } else {
            alert(data.message || 'Ошибка пополнения баланса');
        }
    } catch (e) {
        alert('Ошибка пополнения баланса');
    }
}

// Добавляем обработчики событий для поиска пользователей
// Функция обновления текущей страницы из header
function refreshCurrentPage() {
    const refreshBtn = document.getElementById('headerRefreshBtn');
    const refreshIcon = document.getElementById('headerRefreshIcon');
    const refreshText = document.getElementById('headerRefreshText');
    
    if (!refreshBtn || !refreshIcon || !refreshText) return;
    
    // Блокируем кнопку и показываем анимацию
    refreshBtn.disabled = true;
    refreshIcon.classList.add('spinning');
    refreshText.textContent = 'Обновляем...';
    
    // Определяем текущую страницу и вызываем соответствующую функцию обновления
    const currentPath = window.location.pathname;
    
    if (currentPath.includes('/transactions')) {
        // Для страницы транзакций
        if (typeof refreshTransactions === 'function') {
            refreshTransactions();
        } else {
            location.reload();
        }
    } else if (currentPath.includes('/keys')) {
        // Для страницы ключей
        if (typeof refreshKeys === 'function') {
            refreshKeys();
        } else {
            location.reload();
        }
    } else if (currentPath.includes('/notifications')) {
        // Для страницы уведомлений
        if (typeof refreshNotificationsPage === 'function') {
            refreshNotificationsPage();
        } else {
            location.reload();
        }
    } else {
        // Для остальных страниц просто перезагружаем
        location.reload();
    }
    
    // Возвращаем кнопку в исходное состояние через 2 секунды
    setTimeout(() => {
        refreshBtn.disabled = false;
        refreshIcon.classList.remove('spinning');
        refreshText.textContent = 'Обновить';
    }, 2000);
}

// УДАЛЕНО: функции перенесены в глобальную область

// Функции для модального окна сброса триала
function initializeTrialResetModal() {
    // Закрытие по клику вне окна
    window.addEventListener('click', function (event) {
        const modal = document.getElementById('trialResetModal');
        if (!modal) return;
        if (event.target === modal) {
            closeTrialResetModal();
        }
    });
    
    // Валидация формы
    const confirmCheckbox = document.getElementById('confirmTrialReset');
    const submitButton = document.getElementById('submitTrialResetButton');
    const userSearchInput = document.getElementById('trialResetUserSearch');
    
    function validateTrialResetForm() {
        const selectedUserId = document.getElementById('trialResetSelectedUserId');
        const isConfirmed = confirmCheckbox && confirmCheckbox.checked;
        
        if (selectedUserId && selectedUserId.value && isConfirmed) {
            submitButton.disabled = false;
        } else {
            submitButton.disabled = true;
        }
    }
    
    // Обработчики событий
    if (confirmCheckbox) {
        confirmCheckbox.addEventListener('change', validateTrialResetForm);
    }
    if (userSearchInput) {
        userSearchInput.addEventListener('input', validateTrialResetForm);
    }
}

function openTrialResetModal(userId = null, username = null) {
    const modal = document.getElementById('trialResetModal');
    if (modal) {
        // Сброс полей
        const input = document.getElementById('trialResetUserSearch');
        const selectedId = document.getElementById('trialResetSelectedUserId');
        const label = document.getElementById('trialResetSelectedUserLabel');
        const sugg = document.getElementById('trialResetUserSuggestions');
        const confirmCheckbox = document.getElementById('confirmTrialReset');
        const submitButton = document.getElementById('submitTrialResetButton');
        
        if (input) input.value = '';
        if (selectedId) selectedId.value = '';
        if (label) {
            label.textContent = '';
            label.style.display = 'none';
        }
        if (sugg) {
            sugg.innerHTML = '';
            sugg.style.display = 'none';
        }
        if (confirmCheckbox) confirmCheckbox.checked = false;
        if (submitButton) submitButton.disabled = true;
        
        // Если передан userId, заполняем поля
        if (userId && username) {
            if (selectedId) selectedId.value = String(userId);
            if (label) {
                label.textContent = `Выбрано: ${userId} · @${username}`;
                label.style.display = 'block';
            }
            if (input) input.value = `${userId} · @${username}`;
        }
        
        modal.style.display = 'flex';
    }
}

function closeTrialResetModal() {
    const modal = document.getElementById('trialResetModal');
    if (modal) modal.style.display = 'none';
}

async function submitTrialReset() {
    const userIdEl = document.getElementById('trialResetSelectedUserId');
    const confirmCheckbox = document.getElementById('confirmTrialReset');
    const submitButton = document.getElementById('submitTrialResetButton');
    
    const userId = userIdEl && userIdEl.value ? parseInt(userIdEl.value) : null;
    const isConfirmed = confirmCheckbox && confirmCheckbox.checked;
    
    if (!userId || !isConfirmed) {
        alert('Выберите пользователя и подтвердите действие');
        return;
    }
    
    // Финальное подтверждение
    if (!confirm(`Вы уверены, что хотите сбросить триал для пользователя ${userId}?\n\nЭто действие необратимо!`)) {
        return;
    }
    
    try {
        // Блокируем кнопку отправки
        submitButton.disabled = true;
        submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Выполняется...';
        
        const resp = await fetch('/admin/trial-reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ telegram_id: userId })
        });
        
        const data = await resp.json();
        if (resp.ok) {
            alert(data.message || 'Триал пользователя успешно сброшен');
            closeTrialResetModal();
            // Перезагрузим страницу, чтобы увидеть изменения
            window.location.reload();
        } else {
            alert(data.message || 'Ошибка сброса триала');
        }
    } catch (e) {
        alert('Ошибка сброса триала');
    } finally {
        // Восстанавливаем кнопку
        submitButton.disabled = false;
        submitButton.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Сбросить триал';
    }
}

// Функция переключения режима YooKassa
function toggleYooKassaMode() {
    const testModeCheckbox = document.getElementById('yookassa_test_mode');
    const productionMode = document.getElementById('yookassa_production_mode');
    const testModeFields = document.getElementById('yookassa_test_mode_fields');
    
    if (testModeCheckbox.checked) {
        // Подсвечиваем тестовый режим как активный
        productionMode.style.opacity = '0.5';
        productionMode.style.border = '2px solid #28a745';
        testModeFields.style.opacity = '1';
        testModeFields.style.border = '2px solid #28a745';
    } else {
        // Подсвечиваем боевой режим как активный
        productionMode.style.opacity = '1';
        productionMode.style.border = '2px solid #dc3545';
        testModeFields.style.opacity = '0.5';
        testModeFields.style.border = '2px solid #6c757d';
    }
}

// ============================================
// Функции для работы с Key Drawer
// ============================================

let currentKeyDrawerId = null;
let currentKeyDrawerUserId = null;
let currentKeyDrawerEnabled = false;

// Функция для открытия Drawer с деталями ключа
async function openKeyDrawer(keyId) {
	currentKeyDrawerId = keyId;
	
	try {
		const response = await fetch(`/api/key/${keyId}`);
		const data = await response.json();
		
		if (!data.key) {
			alert('Ошибка загрузки данных ключа');
			return;
		}
		
		const key = data.key;
		currentKeyDrawerUserId = key.user_id;
		currentKeyDrawerEnabled = key.enabled;
		
		// Показываем drawer
		const drawer = document.getElementById('keyDrawer');
		if (!drawer) {
			console.error('Key drawer not found');
			return;
		}
		
		drawer.style.display = 'flex';
		// Небольшая задержка для анимации
		setTimeout(() => {
			drawer.classList.add('active');
		}, 10);
		
		// Заполняем данные
		fillKeyDrawerData(key);
		
	} catch (error) {
		console.error('Ошибка загрузки данных ключа:', error);
		alert('Ошибка загрузки данных ключа');
	}
}

// Функция для заполнения данных в drawer
function fillKeyDrawerData(key) {
	// Основная информация
	document.getElementById('keyModalTelegramId').textContent = key.telegram_id || '—';
	document.getElementById('keyModalFullName').textContent = key.fullname || '—';
	document.getElementById('keyModalFio').textContent = key.fio || '—';
	document.getElementById('keyModalStatus').textContent = key.status || '—';
	
	// Данные ключа
	document.getElementById('keyDetailHost').textContent = key.host_name || '—';
	document.getElementById('keyDetailPlan').textContent = key.plan_name || '—';
	document.getElementById('keyDetailPrice').textContent = key.price ? `${key.price} RUB` : '—';
	document.getElementById('keyDetailStatusInTab').textContent = key.status || '—';
	document.getElementById('keyDetailProtocol').textContent = key.protocol || '—';
	document.getElementById('keyDetailEnabled').textContent = key.enabled ? 'Да' : 'Нет';
	document.getElementById('keyDetailTrial').textContent = key.is_trial ? 'Да' : 'Нет';
	const createdDateFormatted = formatPanelDateTime(key.created_date)
	const expiryDateFormatted = formatPanelDateTime(key.expiry_date)
	document.getElementById('keyDetailCreatedDate').textContent = createdDateFormatted !== 'N/A' ? createdDateFormatted : (key.created_date || '—')
	document.getElementById('keyDetailExpiryDate').textContent = expiryDateFormatted !== 'N/A' ? expiryDateFormatted : (key.expiry_date || '—')
	
	// Оставшееся время
	if (key.remaining_seconds !== null && key.remaining_seconds !== undefined) {
		const days = Math.floor(key.remaining_seconds / 86400);
		const hours = Math.floor((key.remaining_seconds % 86400) / 3600);
		const minutes = Math.floor((key.remaining_seconds % 3600) / 60);
		document.getElementById('keyDetailRemaining').textContent = `${days}д ${hours}ч ${minutes}м`;
	} else {
		document.getElementById('keyDetailRemaining').textContent = '—';
	}
	
	// Новые поля
	document.getElementById('keyDetailSubscription').textContent = key.subscription || '—';
	document.getElementById('keyDetailTelegramChatId').textContent = key.telegram_chat_id || '—';
	document.getElementById('keyDetailComment').textContent = key.comment || '—';
	
	// Трафик
	document.getElementById('keyDetailQuotaTotal').textContent = key.quota_total_gb ? `${key.quota_total_gb} GB` : '∞';
	document.getElementById('keyDetailTrafficDown').textContent = key.traffic_down_bytes ? `${(key.traffic_down_bytes / 1024 / 1024 / 1024).toFixed(2)} GB` : '0 GB';
	document.getElementById('keyDetailQuotaRemaining').textContent = key.quota_remaining_bytes ? `${(key.quota_remaining_bytes / 1024 / 1024 / 1024).toFixed(2)} GB` : '∞';
	
	// Подключение
	document.getElementById('keyDetailEmail').textContent = key.key_email || '—';
	document.getElementById('keyDetailUuid').textContent = key.xui_client_uuid || '—';
	document.getElementById('keyDetailConnectionString').textContent = key.connection_string || '—';
	
	// Обновляем кнопку переключения
	const toggleBtn = document.getElementById('keyDrawerToggleBtn');
	const toggleText = document.getElementById('keyDrawerToggleText');
	if (toggleBtn && toggleText) {
		toggleBtn.innerHTML = `<i class="fas fa-toggle-${key.enabled ? 'on' : 'off'}"></i>`;
		toggleText.textContent = key.enabled ? 'Отключить' : 'Включить';
	}
}

// Функция для закрытия Key Drawer
function closeKeyDrawer() {
	const drawer = document.getElementById('keyDrawer');
	if (!drawer) return;
	
	drawer.classList.remove('active');
	// Ждем завершения анимации перед скрытием
	setTimeout(() => {
		drawer.style.display = 'none';
	}, 300);
	
	currentKeyDrawerId = null;
	currentKeyDrawerUserId = null;
	currentKeyDrawerEnabled = false;
}

// Функция для обновления данных ключа из 3x-ui
async function keyDrawerRefresh() {
	if (currentKeyDrawerUserId) {
		refreshUserKey(currentKeyDrawerUserId);
		// Перезагружаем данные Drawer после небольшой задержки
		setTimeout(() => {
			if (currentKeyDrawerId) {
				openKeyDrawer(currentKeyDrawerId);
			}
		}, 2000);
	}
}

// Функция для переключения включения/отключения ключа из Drawer
function keyDrawerToggle() {
	if (currentKeyDrawerId) {
		const newEnabled = !currentKeyDrawerEnabled;
		toggleKeyEnabled(currentKeyDrawerId, newEnabled);
		// Перезагружаем данные Drawer после небольшой задержки
		setTimeout(() => {
			if (currentKeyDrawerId) {
				openKeyDrawer(currentKeyDrawerId);
			}
		}, 1500);
	}
}

// Функция для копирования поля из Drawer ключа
function copyKeyField(elementId) {
	const element = document.getElementById(elementId);
	if (element) {
		const text = element.textContent;
		navigator.clipboard.writeText(text).then(() => {
			showNotification(`Скопировано: ${text.substring(0, 50)}${text.length > 50 ? '...' : ''}`);
		}).catch(err => {
			console.error('Ошибка копирования: ', err);
			showNotification('Ошибка копирования', 'error');
		});
	}
}