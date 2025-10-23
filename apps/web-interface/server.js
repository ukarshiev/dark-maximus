const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3003;

const server = http.createServer((req, res) => {
    let filePath = path.join(__dirname, 'src', req.url === '/' ? 'index.html' : req.url);
    
    // Проверяем существование файла
    fs.access(filePath, fs.constants.F_OK, (err) => {
        if (err) {
            res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
            res.end('<h1>404 - Страница не найдена</h1>');
            return;
        }
        
        // Определяем MIME тип
        const ext = path.extname(filePath);
        let contentType = 'text/html';
        
        switch (ext) {
            case '.js':
                contentType = 'text/javascript';
                break;
            case '.css':
                contentType = 'text/css';
                break;
            case '.json':
                contentType = 'application/json';
                break;
            case '.png':
                contentType = 'image/png';
                break;
            case '.jpg':
                contentType = 'image/jpg';
                break;
        }
        
        // Читаем и отправляем файл
        fs.readFile(filePath, (err, data) => {
            if (err) {
                res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
                res.end('<h1>500 - Ошибка сервера</h1>');
                return;
            }
            
            res.writeHead(200, { 
                'Content-Type': `${contentType}; charset=utf-8`,
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
                'Access-Control-Allow-Headers': 'Content-Type'
            });
            res.end(data);
        });
    });
});

server.listen(PORT, () => {
    console.log(`🚀 Nx Test Server запущен на http://localhost:${PORT}`);
    console.log(`📊 Откройте браузер для тестирования интерфейса`);
    console.log(`🛠️  Для остановки нажмите Ctrl+C`);
});

// Обработка ошибок
server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
        console.log(`❌ Порт ${PORT} уже используется. Попробуйте другой порт.`);
    } else {
        console.log(`❌ Ошибка сервера: ${err.message}`);
    }
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Остановка сервера...');
    server.close(() => {
        console.log('✅ Сервер остановлен');
        process.exit(0);
    });
});
