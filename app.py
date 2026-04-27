"""
app.py
Dashboard Streamlit — Monitor de Combustível Portugal
Lê dados do Supabase e inclui agente Q&A com Groq.
"""

import os
import requests
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Combustível Portugal",
    page_icon="⛽",
    layout="wide"
)

# ── Carregar dados do Supabase ────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data() -> pd.DataFrame:
    all_rows = []
    offset = 0
    page_size = 1000

    while True:
        url = f"{SUPABASE_URL}/rest/v1/precos_combustivel?select=*&limit={page_size}&offset={offset}"
        r = requests.get(url, headers=SUPABASE_HEADERS, timeout=30)
        batch = r.json()
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(all_rows)
    df["data"] = pd.to_datetime(df["data"])
    df["preco"] = df["preco"].astype(float)
    return df

# ── Agente Text-to-SQL ───────────────────────────────────────────────────────
SCHEMA = """
Tabela PostgreSQL: precos_combustivel
Colunas:
- data (date): data do registo
- nome_posto (text): nome do posto de combustível
- marca (text): marca do posto (ex: GALP, BP, REPSOL, CEPSA, INTERMARCHÉ)
- localidade (text): localidade do posto
- cod_postal (text): código postal
- tipo_combustivel (text): valores possíveis: 'Gasolina simples 95', 'Gasolina simples 98', 'Gasóleo simples'
- preco (numeric): preço em euros por litro
"""

def generate_sql(question: str, client) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""És um especialista em SQL para PostgreSQL.
Dado o seguinte schema:
{SCHEMA}
Converte a pergunta do utilizador numa query SQL válida.
Regras:
- Devolve APENAS a query SQL, sem explicações, sem markdown, sem backticks
- Usa sempre LIMIT 20 no máximo
- Para comparações de texto usa ILIKE
- A data mais recente é a mais actual
- Quando não for especificado, usa a data mais recente disponível
- Arredonda preços a 3 casas decimais com ROUND(preco, 3)"""
            },
            {"role": "user", "content": question}
        ],
        temperature=0,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()


def run_sql(sql: str) -> list:
    url = f"{SUPABASE_URL}/rest/v1/rpc/executar_query"
    r = requests.post(
        url,
        headers=SUPABASE_HEADERS,
        data=json.dumps({"query": sql}),
        timeout=15
    )
    if r.status_code == 200:
        return r.json()
    return None


def format_answer(question: str, sql: str, results, client) -> str:
    if results is None:
        results_str = "Sem resultados disponíveis via SQL directo."
    else:
        results_str = json.dumps(results, ensure_ascii=False, indent=2)[:2000]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "És um assistente que responde em português de forma clara e directa sobre preços de combustível em Portugal."
            },
            {
                "role": "user",
                "content": f"Pergunta: {question}\nSQL gerado: {sql}\nResultado: {results_str}\n\nResponde à pergunta de forma clara em português."
            }
        ],
        temperature=0.1,
        max_tokens=400
    )
    return response.choices[0].message.content


def answer_question(question: str, df: pd.DataFrame) -> str:
    client = Groq(api_key=GROQ_API_KEY)
    sql = generate_sql(question, client)
    results = run_sql(sql)
    if results is None:
        results = [{"nota": "Query executada localmente", "sql": sql}]
    resposta = format_answer(question, sql, results, client)
    return f"{resposta}\n\n*SQL gerado: `{sql}`*"

# ── Interface ─────────────────────────────────────────────────────────────────
st.title("⛽ Monitor de Combustível Portugal")
st.caption("Dados atualizados diariamente via API da DGEG")

with st.spinner("A carregar dados..."):
    df = load_data()

if df.empty:
    st.error("Sem dados disponíveis.")
    st.stop()

# ── Métricas topo ─────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de Postos", f"{df['nome_posto'].nunique():,}")
with col2:
    preco_medio = df["preco"].mean()
    st.metric("Preço Médio Nacional", f"{preco_medio:.3f}€")
with col3:
    idx_min = df.groupby("localidade")["preco"].mean().idxmin()
    preco_min = df.groupby("localidade")["preco"].mean().min()
    st.metric("Localidade Mais Barata", idx_min, f"{preco_min:.3f}€")
with col4:
    idx_max = df.groupby("localidade")["preco"].mean().idxmax()
    preco_max = df.groupby("localidade")["preco"].mean().max()
    st.metric("Localidade Mais Cara", idx_max, f"{preco_max:.3f}€")

st.divider()

# ── Filtros ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    tipos = sorted(df["tipo_combustivel"].unique())
    tipo_sel = st.selectbox("Tipo de Combustível", tipos)

with col_f2:
    datas = sorted(df["data"].dt.date.unique(), reverse=True)
    data_sel = st.selectbox("Data", datas)

with col_f3:
    localidades = ["Todas"] + sorted(df["localidade"].dropna().unique())
    localidade_sel = st.selectbox("Localidade", localidades)

# Aplica filtros
df_filtrado = df[
    (df["tipo_combustivel"] == tipo_sel) &
    (df["data"].dt.date == data_sel)
]
if localidade_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["localidade"] == localidade_sel]

st.divider()

# ── Agente Q&A ────────────────────────────────────────────────────────────────
st.subheader("💬 Faz uma Pergunta sobre os Dados")
st.caption("Ex: 'Qual a localidade mais barata para gasolina 95?' ou 'Qual a marca mais cara?'")

pergunta = st.text_input("A tua pergunta:", placeholder="Qual o posto mais barato em Lisboa?")

if pergunta:
    with st.spinner("A pensar..."):
        try:
            resposta = answer_question(pergunta, df)
            st.success(resposta)
        except Exception as e:
            st.error(f"Erro: {e}")

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────
st.subheader("Top 5 Marcas Mais Baratas")
df_marca = df_filtrado.groupby("marca")["preco"].mean().reset_index()
df_marca = df_marca[df_marca["marca"] != ""].sort_values("preco").head(5)
fig2 = px.bar(
    df_marca,
    x="preco",
    y="marca",
    orientation="h",
    color="preco",
    color_continuous_scale="RdYlGn_r",
    labels={"preco": "Preço Médio (€/litro)", "marca": "Marca"}
)
fig2.update_layout(showlegend=False, height=300, yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig2, use_container_width=True)

# ── Evolução temporal ─────────────────────────────────────────────────────────
st.subheader("Evolução do Preço Médio ao Longo do Tempo")
df_tempo_filter = df[df["tipo_combustivel"] == tipo_sel]
if localidade_sel != "Todas":
    df_tempo_filter = df_tempo_filter[df_tempo_filter["localidade"] == localidade_sel]
df_tempo = df_tempo_filter.groupby("data")["preco"].mean().reset_index()
fig3 = px.line(
    df_tempo,
    x="data",
    y="preco",
    markers=True,
    labels={"preco": "Preço Médio (€/litro)", "data": "Data"}
)
st.plotly_chart(fig3, use_container_width=True)

# ── Tabela detalhada ──────────────────────────────────────────────────────────
with st.expander("📋 Ver todos os postos"):
    st.dataframe(
        df_filtrado[["nome_posto", "marca", "localidade", "cod_postal", "preco"]]
        .sort_values("preco")
        .reset_index(drop=True),
        use_container_width=True
    )
