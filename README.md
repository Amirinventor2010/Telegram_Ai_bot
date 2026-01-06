# Telegram AI Bot

## Run (Local)

1) Create `.env` from `.env.example`
2) Start PostgreSQL (Docker)
3) Run bot

## PostgreSQL

docker run --name tg-ai-postgres -e POSTGRES_PASSWORD=StrongPasswordHere -e POSTGRES_USER=telegram_ai_user -e POSTGRES_DB=telegram_ai_bot -p 5432:5432 -d postgres:16
