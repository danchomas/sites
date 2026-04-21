// config.js - автоматическое определение окружения
const getApiBaseUrl = () => {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    
    console.log(`🌐 Текущий хост: ${hostname}, протокол: ${protocol}`);
    
    // Локальная разработка
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        console.log('🔧 Локальная разработка - используем localhost:8000');
        return 'http://localhost:8000';
    }
    
    // Cloudflare Pages (тестовый домен)
    if (hostname.includes('.pages.dev')) {
        console.log('☁️ Cloudflare Pages - используем Railway бекенд');
        // ВСТАВЬТЕ СЮДА ВАШ RAILWAY URL
        return 'https://finance-world-backend.up.railway.app';
    }
    
    // Продакшен домен (ваш собственный домен)
    if (hostname === 'finance-world.online' || hostname === 'www.finance-world.online') {
        console.log('🌐 Продакшен домен - используем Railway бекенд');
        return 'https://finance-world-backend.up.railway.app';
    }
    
    // По умолчанию для локальной разработки
    console.log('⚡ По умолчанию - используем Railway бекенд');
    return 'https://finance-world-backend.up.railway.app';
};

const CONFIG = {
    API_BASE_URL: getApiBaseUrl(),
    APP_NAME: 'Мир Финансов',
    VERSION: '1.0.0',
    
    // Функция для проверки доступности API
    checkApiHealth: async function() {
        try {
            console.log(`🔍 Проверка API: ${this.API_BASE_URL}/health`);
            
            const response = await fetch(`${this.API_BASE_URL}/health`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                console.log('✅ API доступен:', data);
                return true;
            }
            
            console.warn('⚠️ API не отвечает:', response.status);
            return false;
            
        } catch (error) {
            console.error('❌ Ошибка подключения к API:', error);
            return false;
        }
    }
};

// Экспортируем конфиг
window.CONFIG = CONFIG;
console.log('⚙️ Конфигурация загружена:', CONFIG);