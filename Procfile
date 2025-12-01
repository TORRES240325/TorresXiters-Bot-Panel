# Procfile
# El proceso "web" corre la página de administración
web: gunicorn admin_panel:app

# El proceso "worker" corre el bot de Telegram de forma continua
worker: python bot_main.py