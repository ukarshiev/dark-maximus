#!/bin/bash
cd /e/GitHub/dark-maximus

echo "Начинаю исправление коммитов..."

# Создаем скрипт для автоматического изменения сообщений
cat > rebase-script.sh << 'EOF'
#!/bin/sh
COMMIT_HASH=`git rev-parse --short HEAD`

case "$COMMIT_HASH" in
    d71b457)
        echo "Обновлен CHANGELOG.md: упрощены workflows, отключен Dependabot"
        ;;
    4fd8c5f)
        echo "Отключен Dependabot для приватного репозитория"
        ;;
    3f7b0a2)
        echo "Упрощены GitHub Actions workflows для стабильной работы CI/CD"
        ;;
    3284f84)
        echo "feat: добавлены улучшения безопасности, система бэкапов и обновления UI"
        ;;
    f62986f)
        echo "Полностью решена проблема с кодировкой UTF-8 в PowerShell и Git"
        ;;
    1e09369)
        echo "Исправлена проблема с кодировкой в Git и PowerShell: добавлены настройки UTF-8"
        ;;
    *)
        cat
        ;;
esac
EOF

chmod +x rebase-script.sh

echo "Запускаю git filter-branch..."
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --msg-filter "sh rebase-script.sh" HEAD~10..HEAD

echo "Удаляю временные файлы..."
rm -f rebase-script.sh

echo "Готово! Проверьте результат: git log --oneline -10"

