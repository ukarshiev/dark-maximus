/**
 * Минимальный JavaScript для сохранения выбора темы
 * Основная логика переключения темы реализована через CSS
 */
(function() {
  'use strict';

  // Функция для установки темы
  function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }

  // Получить сохраненную тему или системную
  function getTheme() {
    const saved = localStorage.getItem('theme');
    if (saved) {
      return saved;
    }
    
    // Проверить системные настройки
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    
    return 'light';
  }

  // Инициализация при загрузке
  function init() {
    const theme = getTheme();
    setTheme(theme);
    
    // Установить состояние checkbox
    const checkbox = document.querySelector('.docs-theme-toggle__input');
    if (checkbox) {
      checkbox.checked = (theme === 'dark');
      
      // Добавить обработчик клика
      checkbox.addEventListener('change', function() {
        const newTheme = this.checked ? 'dark' : 'light';
        setTheme(newTheme);
      });
    }
    
    // Обработчик изменения системной темы
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        // Обновляем только если пользователь не выбрал тему вручную
        if (!localStorage.getItem('theme')) {
          setTheme(e.matches ? 'dark' : 'light');
        }
      });
    }
  }

  // Запуск при загрузке DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Экспорт для глобального использования
  window.ThemeUtils = {
    setTheme: setTheme,
    getTheme: getTheme
  };
})();

