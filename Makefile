.PHONY: deploy stop status

# Команда для запуска всех сайтов
deploy:
	@echo "Создаем сеть для прокси-сервера..."
	@docker network create nginx-proxy 2>/dev/null || true
	
	@echo "Запускаем главный Nginx-Proxy..."
	@docker run -d -p 80:80 -v /var/run/docker.sock:/tmp/docker.sock:ro \
		--name nginx-proxy --network nginx-proxy --restart always \
		jwilder/nginx-proxy 2>/dev/null || echo "Прокси уже запущен."

	@echo "Чтение domains.conf и деплой сайтов..."
	@while IFS='=' read -r site domain || [ -n "$$site" ]; do \
		if [ ! -z "$$site" ] && [ ! -z "$$domain" ] && [ ! "$${site:0:1}" = "#" ]; then \
			if [ -d "$$site" ]; then \
				echo "\n=============================================="; \
				echo "🚀 Деплой сайта из папки [$$site] на домен [$$domain]"; \
				echo "DOMAIN=$$domain" > "$$site/.env"; \
				cd "$$site" && docker compose up -d --build && cd ..; \
			else \
				echo "⚠️ Папка $$site не найдена, пропускаем."; \
			fi \
		fi \
	done < domains.conf
	@echo "\n✅ Все сайты успешно запущены!"

# Команда для остановки всех сайтов
stop:
	@while IFS='=' read -r site domain || [ -n "$$site" ]; do \
		if [ ! -z "$$site" ] && [ ! "$${site:0:1}" = "#" ] && [ -d "$$site" ]; then \
			echo "🛑 Остановка сайта [$$site]..."; \
			cd "$$site" && docker compose down && cd ..; \
		fi \
	done < domains.conf
	@echo "Удаление главного прокси..."
	@docker rm -f nginx-proxy 2>/dev/null || true
	@echo "✅ Все сайты остановлены."

# Команда чтобы посмотреть статус контейнеров
status:
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"