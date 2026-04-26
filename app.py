"""
app.py
Dashboard Streamlit — Monitor de Combustível Portugal
Lê dados do Supabase e inclui agente Q&A com Groq.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Combustível Portugal",
    page_icon="⛽",
    layout="wide"
)

# ── Ligação ao Supabase ───────────────────────────────────────────────────────
@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_data(ttl=3600)  # cache por 1 hora
def load_data() -> pd.DataFrame:
    client = get_supabase()
    response = client.table("precos_combustivel").select("*").execute()
    df = pd.DataFrame(response.data)
    df["data"] = pd.to_datetime(df["data"])
    df["preco"] = df["preco"].astype(float)
    return df


# ── Agente Q&A ────────────────────────────────────────────────────────────────
def build_system_prompt(df: pd.DataFrame) -> str:
    distritos = df["distrito"].unique().tolist()
    tipos = df["tipo_combustivel"].unique().tolist()
    datas = df["data"].dt.date.unique().tolist()

    return f"""
És um assistente especializado em análise de preços de combustível em Portugal.
Tens acesso a dados com as seguintes características:
- Distritos disponíveis: {distritos}
- Tipos de combustível: {tipos}
- Datas disponíveis: {datas}
- Colunas: data, distrito, municipio, nome_posto, tipo_combustivel, preco, marca

Quando o utilizador fizer uma pergunta, responde de forma clara e direta em português.
Se precisares de fazer cálculos, usa os dados fornecidos no contexto.
Responde sempre com valores concretos quando possível.
"""


def answer_question(question: str, df: pd.DataFrame) -> str:
    """Envia a pergunta para o Groq com contexto dos dados."""
    client = Groq(api_key=GROQ_API_KEY)

    # Resume os dados para contexto (últimas estatísticas)
    stats = df.groupby(["distrito", "tipo_combustivel"])["preco"].agg(["mean", "min", "max"]).reset_index()
    stats_str = stats.to_string(index=False)

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": build_system_prompt(df)},
            {"role": "user", "content": f"""
Dados resumidos (média, mínimo, máximo por distrito e tipo de combustível):
{stats_str}

Pergunta: {question}
"""}
        ],
        temperature=0.1,
        max_tokens=500
    )

    return response.choices[0].message.content


# ── Interface Principal ───────────────────────────────────────────────────────
st.title("⛽ Monitor de Combustível Portugal")
st.caption("Dados atualizados diariamente via API da DGEG")

# Carrega dados
with st.spinner("A carregar dados..."):
    df = load_data()

if df.empty:
    st.error("Sem dados disponíveis. Verifica a ligação ao Supabase.")
    st.stop()

# ── Métricas topo ─────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    preco_medio = df["preco"].mean()
    st.metric("Preço Médio Nacional", f"{preco_medio:.3f}€")

with col2:
    mais_barato = df.groupby("distrito")["preco"].mean().idxmin()
    preco_mb = df.groupby("distrito")["preco"].mean().min()
    st.metric("Distrito Mais Barato", mais_barato, f"{preco_mb:.3f}€")

with col3:
    mais_caro = df.groupby("distrito")["preco"].mean().idxmax()
    preco_mc = df.groupby("distrito")["preco"].mean().max()
    st.metric("Distrito Mais Caro", mais_caro, f"{preco_mc:.3f}€")

with col4:
    total_postos = df["nome_posto"].nunique()
    st.metric("Total de Postos", f"{total_postos:,}")

st.divider()

# ── Filtros ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    tipos_disponiveis = sorted(df["tipo_combustivel"].unique())
    tipo_sel = st.selectbox("Tipo de Combustível", tipos_disponiveis)

with col_f2:
    distritos_disponiveis = ["Todos"] + sorted(df["distrito"].unique())
    distrito_sel = st.selectbox("Distrito", distritos_disponiveis)

with col_f3:
    datas_disponiveis = sorted(df["data"].dt.date.unique(), reverse=True)
    data_sel = st.selectbox("Data", datas_disponiveis)

# Aplica filtros
df_filtrado = df[
    (df["tipo_combustivel"] == tipo_sel) &
    (df["data"].dt.date == data_sel)
]

if distrito_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["distrito"] == distrito_sel]

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────
col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Preço Médio por Distrito")
    df_distrito = df_filtrado.groupby("distrito")["preco"].mean().reset_index()
    df_distrito = df_distrito.sort_values("preco")

    fig1 = px.bar(
        df_distrito,
        x="preco",
        y="distrito",
        orientation="h",
        color="preco",
        color_continuous_scale="RdYlGn_r",
        labels={"preco": "Preço (€/litro)", "distrito": "Distrito"}
    )
    fig1.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig1, use_container_width=True)

with col_g2:
    st.subheader("Evolução do Preço ao Longo do Tempo")
    df_tempo = df[df["tipo_combustivel"] == tipo_sel].groupby("data")["preco"].mean().reset_index()

    fig2 = px.line(
        df_tempo,
        x="data",
        y="preco",
        labels={"preco": "Preço Médio (€/litro)", "data": "Data"},
        markers=True
    )
    fig2.update_layout(height=400)
    st.plotly_chart(fig2, use_container_width=True)

# ── Tabela detalhada ──────────────────────────────────────────────────────────
with st.expander("📋 Ver dados detalhados"):
    st.dataframe(
        df_filtrado[["data", "distrito", "municipio", "nome_posto", "marca", "preco"]]
        .sort_values("preco")
        .reset_index(drop=True),
        use_container_width=True
    )

st.divider()

# ── Agente Q&A ────────────────────────────────────────────────────────────────
st.subheader("💬 Faz uma Pergunta sobre os Dados")
st.caption("Exemplos: 'Qual o distrito mais barato?', 'Onde está a Gasolina 95 mais cara?'")

pergunta = st.text_input("A tua pergunta:", placeholder="Ex: Qual o distrito com gasolina mais barata?")

if pergunta:
    with st.spinner("A pensar..."):
        try:
            resposta = answer_question(pergunta, df)
            st.success(resposta)
        except Exception as e:
            st.error(f"Erro ao contactar o agente: {e}")
