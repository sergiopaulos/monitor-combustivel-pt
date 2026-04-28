import os
import requests
import json
import streamlit as st
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import streamlit.components.v1 as components

# ── Load env vars ──────────────────────────────────────────────────────────────
load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Combustível Portugal",
    page_icon="⛽",
    layout="wide",
)

# ── Load data (needed for LLM context) ─────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/precos_combustivel"
            f"?select=*&limit={page_size}&offset={offset}"
        )
        r = requests.get(url, headers=SUPABASE_HEADERS, timeout=15)
        r.raise_for_status()

        data = r.json()
        if not data:
            break

        all_rows.extend(data)
        offset += page_size

    df = pd.DataFrame(all_rows)
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"])

    return df

# ── LLM: Text-to-SQL Agent ──────────────────────────────────────────────────────
SCHEMA = """
Tabela PostgreSQL: precos_combustivel
Colunas:
- data (date)
- nome_posto (text)
- marca (text)
- localidade (text)
- cod_postal (text)
- tipo_combustivel (text):
  'Gasolina simples 95', 'Gasolina simples 98', 'Gasóleo simples'
- preco (numeric)
"""

def generate_sql(question: str, client: Groq) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""
És um especialista em SQL para PostgreSQL.

Schema:
{SCHEMA}

Regras:
- Devolve APENAS a query SQL
- Sem explicações, sem markdown
- Usa LIMIT 20 no máximo
- Usa ILIKE para texto
- Usa sempre dados da data mais recente, se não indicado
- Arredonda preços a 3 casas decimais com ROUND(preco, 3)
"""
            },
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()

def run_sql(sql: str):
    url = f"{SUPABASE_URL}/rest/v1/rpc/executar_query"
    r = requests.post(
        url,
        headers=SUPABASE_HEADERS,
        data=json.dumps({"query": sql}),
        timeout=15,
    )
    if r.status_code == 200:
        return r.json()
    return None

def answer_question(question: str, df: pd.DataFrame) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    sql = generate_sql(question, client)
    results = run_sql(sql)

    if results is None:
        return f"❌ Erro ao executar SQL\n\nSQL gerado:\n{sql}"

    pretty = json.dumps(results, ensure_ascii=False, indent=2)
    return f"SQL gerado:\n{sql}\n\nResultados:\n{pretty}"

# ── UI ─────────────────────────────────────────────────────────────────────────
st.title("⛽ Monitor de Combustível Portugal")
st.caption("Dados atualizados diariamente · Análise assistida por IA")

with st.spinner("A carregar dados..."):
    df = load_data()

if df.empty:
    st.error("Sem dados disponíveis.")
    st.stop()

st.divider()

# ── Q&A ─────────────────────────────────────────────────────────────────────────
st.subheader("💬 Pergunta aos dados")

pergunta = st.text_input(
    "Escreve a tua pergunta:",
    placeholder="Qual é a localidade mais barata para gasóleo?"
)

if pergunta:
    with st.spinner("A pensar..."):
        try:
            resposta = answer_question(pergunta, df)
            st.success(resposta)
        except Exception as e:
            st.error(f"Erro: {e}")

st.divider()

# ── Power BI Embed ─────────────────────────────────────────────────────────────
st.subheader("📊 Análise detalhada (Power BI)")

POWERBI_EMBED_URL = "https://app.powerbi.com/view?r=eyJrIjoiNmMzZjMxMDEtMWI0Ny00ZThlLTg4OWYtMDY2MjMwY2U0MDhjIiwidCI6IjQwYzM3YmZhLTBjODUtNDU1Yi05YzY0LTVmNjQzNzY5NDJjNiIsImMiOjl9&pageName=783fe65ec005b6ca85b3"

components.iframe(
    src=POWERBI_EMBED_URL,
    height=900,
    scrolling=True,
)