#!/bin/bash

# 1. Navegar para a pasta do Docker
cd docker || exit

# 2. Iniciar os containers em background
echo "Iniciando os serviços do HealthOS (Database, Metabase, Streamlit)..."
docker compose --env-file ../.env up -d

# 3. Aguardar alguns segundos para a inicialização
echo "Aguardando o aplicativo ficar pronto..."
sleep 5

# 4. Abrir o navegador
echo "Abrindo o navegador..."
if command -v explorer.exe > /dev/null; then
    # Abre no navegador do Windows a partir do WSL
    explorer.exe "http://localhost:8502"
elif command -v xdg-open > /dev/null; then
    # Padrão para Linux
    xdg-open "http://localhost:8502"
else
    echo "Não foi possível abrir o navegador automaticamente. Acesse http://localhost:8502 manualmente."
fi

# 5. Monitorar o container do aplicativo
# O código no app.py irá parar o container 'healthos_app'
# automaticamente quando fechar as abas do navegador.
echo "Aplicativo rodando! O servidor será desligado automaticamente ao fechar o navegador."
docker wait healthos_app_github > /dev/null

# 6. Desligar tudo quando o container principal parar
echo "Aba fechada detectada. Desligando todos os containers..."
docker compose down

echo "HealthOS encerrado com sucesso."
exit
