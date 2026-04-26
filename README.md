# ⛽ Monitor de Combustível Portugal

Dashboard gratuito que monitoriza os preços de combustível em Portugal, com agente Q&A em linguagem natural.

## Stack
- **Dados**: API pública da DGEG
- **Agendamento**: GitHub Actions (diário)
- **Base de dados**: Supabase (PostgreSQL)
- **Dashboard + Agente**: Streamlit + Groq (LLaMA 3)

---

## Setup Passo a Passo

### 1. Supabase

1. Cria conta em [supabase.com](https://supabase.com) (gratuito)
2. Cria um novo projeto
3. Vai a **SQL Editor** e corre o conteúdo de `supabase_schema.sql`
4. Vai a **Project Settings → API** e copia:
   - `Project URL` → é o teu `SUPABASE_URL`
   - `anon public key` → é o teu `SUPABASE_KEY`

### 2. Groq

1. Cria conta em [console.groq.com](https://console.groq.com) (gratuito)
2. Vai a **API Keys** e cria uma nova key
3. Guarda o valor → é o teu `GROQ_API_KEY`

### 3. GitHub

1. Cria um repositório novo em [github.com](https://github.com)
2. Faz clone localmente:
   ```bash
   git clone https://github.com/teu-username/monitor-combustivel-pt.git
   ```
3. Copia todos estes ficheiros para a pasta do repositório
4. Adiciona os secrets no GitHub:
   - Repositório → **Settings → Secrets and variables → Actions**
   - Adiciona: `SUPABASE_URL`, `SUPABASE_KEY`
5. Faz push:
   ```bash
   git add .
   git commit -m "primeiro commit"
   git push
   ```

### 4. Primeira Extração (manual)

No GitHub, vai a **Actions → Extração Diária DGEG → Run workflow**
Isto corre o `extract.py` e popula a base de dados pela primeira vez.

### 5. Streamlit Cloud

1. Vai a [share.streamlit.io](https://share.streamlit.io) e liga a tua conta GitHub
2. Clica em **New app**
3. Seleciona o teu repositório e o ficheiro `app.py`
4. Em **Advanced settings → Secrets**, adiciona:
   ```toml
   SUPABASE_URL = "https://xxxxxxxx.supabase.co"
   SUPABASE_KEY = "eyJxxxxxxxx"
   GROQ_API_KEY = "gsk_xxxxxxxx"
   ```
5. Clica **Deploy**

A app fica disponível em `https://monitor-combustivel.streamlit.app` (ou similar).

---

## Estrutura do Projeto

```
monitor-combustivel/
│
├── extract.py                          ← extração DGEG → Supabase
├── app.py                              ← dashboard Streamlit + agente
├── supabase_schema.sql                 ← SQL para criar a tabela
├── requirements.txt                    ← dependências Python
├── .env.example                        ← variáveis de ambiente (exemplo)
└── .github/
    └── workflows/
        └── daily_extract.yml           ← GitHub Actions (cron diário)
```

---

## Desenvolvimento Local

```bash
# Instala dependências
pip install -r requirements.txt

# Copia e preenche as variáveis de ambiente
cp .env.example .env

# Testa a extração
python extract.py

# Corre o dashboard localmente
streamlit run app.py
```

---

## Custos

| Ferramenta | Custo |
|---|---|
| GitHub Actions | Gratuito |
| Supabase | Gratuito (até 500MB) |
| Streamlit Cloud | Gratuito |
| Groq API | Gratuito (14.400 req/dia) |
| **Total** | **0€** |
