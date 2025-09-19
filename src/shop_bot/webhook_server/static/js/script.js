document.addEventListener('DOMContentLoaded', function () {
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
			'#007bff'
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

	// Управление боковым меню (только для мобильных)
	function initializeSidebar() {
		const burgerMenu = document.getElementById('burgerMenu');
		const sidebar = document.getElementById('sidebar');
		
		if (!burgerMenu || !sidebar) return;
		
		// Функция переключения меню (только для мобильных)
		function toggleSidebar() {
			// Работает только на мобильных устройствах
			if (window.innerWidth <= 768) {
				sidebar.classList.toggle('sidebar-open');
				burgerMenu.classList.toggle('burger-active');
				
				// Блокируем скролл при открытом меню
				if (sidebar.classList.contains('sidebar-open')) {
					document.body.style.overflow = 'hidden';
				} else {
					document.body.style.overflow = '';
				}
			}
		}
		
		// Обработчик события для бургерного меню
		burgerMenu.addEventListener('click', toggleSidebar);
		
		// Закрытие меню при клике на overlay (только мобильные)
		document.addEventListener('click', function(e) {
			if (window.innerWidth <= 768 && 
				sidebar.classList.contains('sidebar-open') && 
				!sidebar.contains(e.target) && 
				!burgerMenu.contains(e.target)) {
				sidebar.classList.remove('sidebar-open');
				burgerMenu.classList.remove('burger-active');
				document.body.style.overflow = '';
			}
		});
		
		// Адаптация при изменении размера окна
		window.addEventListener('resize', function() {
			if (window.innerWidth > 768) {
				// На десктопе убираем все классы и блокировку скролла
				sidebar.classList.remove('sidebar-open');
				burgerMenu.classList.remove('burger-active');
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
				const statusText = this.closest('.bot-label-row').querySelector('.bot-status-text');
				const isChecked = this.checked;
				
				// Обновляем текст статуса только для ботов (Shop/Support)
				if (isChecked) {
					statusText.textContent = 'Запущен';
					statusText.className = 'bot-status-text status-running';
				} else {
					statusText.textContent = 'Остановлен';
					statusText.className = 'bot-status-text status-stopped';
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
						// Если запрос не удался, возвращаем чекбокс в исходное состояние
						this.checked = !isChecked;
						if (isChecked) {
							statusText.textContent = 'Остановлен';
							statusText.className = 'bot-status-text status-stopped';
						} else {
							statusText.textContent = 'Запущен';
							statusText.className = 'bot-status-text status-running';
						}
					}
				})
				.catch(error => {
					console.error('Error:', error);
					// В случае ошибки возвращаем чекбокс в исходное состояние
					this.checked = !isChecked;
					if (isChecked) {
						statusText.textContent = 'Остановлен';
						statusText.className = 'bot-status-text status-stopped';
					} else {
						statusText.textContent = 'Запущен';
						statusText.className = 'bot-status-text status-running';
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
	
	
	// Загружаем заработанную сумму для всех пользователей на странице пользователей
	loadAllUsersEarned()
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

// Скрытый режим
function initializeHiddenModeToggle() {
    const toggle = document.getElementById('hiddenModeToggle');
    const statusText = document.getElementById('hiddenModeStatus');
    if (!toggle || !statusText) return;

    window.__HIDDEN_MODE__ = !!toggle.checked;
    // Явно синхронизируем визуальное состояние
    toggle.checked = window.__HIDDEN_MODE__;
    applyHiddenMode();

    toggle.addEventListener('change', function() {
        const isOn = !!this.checked;
        window.__HIDDEN_MODE__ = isOn;
        // Форсируем визуальное положение переключателя
        toggle.checked = isOn;
        statusText.textContent = isOn ? 'Включен' : 'Отключен';
        statusText.className = 'bot-status-text ' + (isOn ? 'status-running' : 'status-stopped');
        applyHiddenMode();
        // сохраняем на сервере и синхронизируем по ответу (0/1)
        fetch('/toggle-hidden-mode', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            const serverOn = (String(data.hidden_mode) === '1');
            window.__HIDDEN_MODE__ = serverOn;
            toggle.checked = serverOn;
            statusText.textContent = serverOn ? 'Включен' : 'Отключен';
            statusText.className = 'bot-status-text ' + (serverOn ? 'status-running' : 'status-stopped');
            applyHiddenMode();
        })
        .catch(() => {});
        // Доп. гарантия после любого возможного перерендера
        setTimeout(() => { toggle.checked = window.__HIDDEN_MODE__; }, 50);
    });
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
            priceCell.textContent = hidden ? '*** RUB' : original;
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
	loadUserEarned(userId)
	
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
		form.action = `/ban-user/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function unbanUser() {
	if (currentUserId && confirm('Вы уверены, что хотите разбанить этого пользователя?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
		form.action = `/unban-user/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
	}
}

function revokeKeys() {
	if (currentUserId && confirm('ВНИМАНИЕ! Это действие удалит ВСЕ ключи пользователя с серверов. Вы уверены?')) {
		// Создаем форму и отправляем POST запрос
		const form = document.createElement('form')
		form.method = 'POST'
		form.action = `/revoke-keys/${currentUserId}`
		
		document.body.appendChild(form)
		form.submit()
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