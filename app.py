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
@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    url = f"{SUPABASE_URL}/rest/v1/precos_combustivel?select=*&limit=100000"
    r = requests.get(url, headers=SUPABASE_HEADERS, timeout=30)
    df = pd.DataFrame(r.json())
    df["data"] = pd.to_datetime(df["data"])
    df["preco"] = df["preco"].astype(float)
    return df

# ── Agente Q&A ────────────────────────────────────────────────────────────────
def answer_question(question: str, df: pd.DataFrame) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    stats = df.groupby(["localidade", "tipo_combustivel"])["preco"].agg(["mean", "min", "max"]).reset_index()
    stats.columns = ["localidade", "tipo_combustivel", "preco_medio", "preco_min", "preco_max"]
    stats = stats.round(3)
    stats_str = stats.to_string(index=False)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"""És um assistente especializado em preços de combustível em Portugal.
Tens acesso a dados de {df['nome_posto'].nunique()} postos em todo o país.
Tipos de combustível: {df['tipo_combustivel'].unique().tolist()}
Datas disponíveis: {df['data'].dt.date.unique().tolist()}
Responde sempre em português de forma clara e directa com valores concretos."""
            },
            {
                "role": "user",
                "content": f"Dados resumidos por localidade e combustível:\n{stats_str}\n\nPergunta: {question}"
            }
        ],
        temperature=0.1,
        max_tokens=500
    )
    return response.choices[0].message.content

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
col_f1, col_f2 = st.columns(2)

with col_f1:
    tipos = sorted(df["tipo_combustivel"].unique())
    tipo_sel = st.selectbox("Tipo de Combustível", tipos)

with col_f2:
    datas = sorted(df["data"].dt.date.unique(), reverse=True)
    data_sel = st.selectbox("Data", datas)

df_filtrado = df[
    (df["tipo_combustivel"] == tipo_sel) &
    (df["data"].dt.date == data_sel)
]

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Top 20 Postos Mais Baratos")
    top_baratos = df_filtrado.nsmallest(20, "preco")[["nome_posto", "localidade", "marca", "preco"]]
    fig1 = px.bar(
        top_baratos,
        x="preco",
        y="nome_posto",
        orientation="h",
        color="preco",
        color_continuous_scale="RdYlGn_r",
        hover_data=["localidade", "marca"],
        labels={"preco": "Preço (€/litro)", "nome_posto": "Posto"}
    )
    fig1.update_layout(showlegend=False, height=500, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig1, use_container_width=True)

with col_g2:
    st.subheader("Preço Médio por Marca")
    df_marca = df_filtrado.groupby("marca")["preco"].mean().reset_index()
    df_marca = df_marca[df_marca["marca"] != ""].sort_values("preco")
    fig2 = px.bar(
        df_marca,
        x="preco",
        y="marca",
        orientation="h",
        color="preco",
        color_continuous_scale="RdYlGn_r",
        labels={"preco": "Preço Médio (€/litro)", "marca": "Marca"}
    )
    fig2.update_layout(showlegend=False, height=500)
    st.plotly_chart(fig2, use_container_width=True)

# ── Evolução temporal ─────────────────────────────────────────────────────────
st.subheader("Evolução do Preço Médio ao Longo do Tempo")
df_tempo = df[df["tipo_combustivel"] == tipo_sel].groupby("data")["preco"].mean().reset_index()
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
