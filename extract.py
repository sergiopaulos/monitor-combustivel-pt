"""
extract.py
Extrai preços de combustível da API da DGEG e insere no Supabase.
Corre diariamente via GitHub Actions.
"""

import os
import requests
import pandas as pd
from supabase import create_client
from datetime import date
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# URL da API pública da DGEG
DGEG_URL = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/GetListPostos"

# Headers necessários para a API da DGEG não rejeitar o pedido
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

PARAMS = {
    "idsTiposComb": "3201,2101,2201",  # Gasóleo simples, Gasolina 95, Gasolina 98
    "idioma": "pt",
    "qtdPorPagina": 500,
    "pagina": 1,
    "f": "json"
}


def fetch_dgeg_data() -> list[dict]:
    """Chama a API da DGEG e devolve lista de postos com preços."""
    print("A chamar API da DGEG...")
    all_records = []
    page = 1

    while True:
        PARAMS["pagina"] = page
        response = requests.get(DGEG_URL, params=PARAMS, headers=HEADERS, timeout=30)

        print(f"  Status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type', 'desconhecido')}")

        if response.status_code != 200:
            print(f"  Erro HTTP {response.status_code}. A parar.")
            break

        content_type = response.headers.get("Content-Type", "")
        if "json" not in content_type:
            print(f"  A API não devolveu JSON. Resposta (primeiros 500 chars):")
            print(response.text[:500])
            raise ValueError("API da DGEG não devolveu JSON válido.")

        data = response.json()
        items = data.get("resultado", [])

        if not items:
            print(f"  Sem mais resultados na página {page}.")
            break

        all_records.extend(items)
        print(f"  Página {page}: {len(items)} postos obtidos")

        if len(items) < PARAMS["qtdPorPagina"]:
            break
        page += 1

    print(f"Total de registos obtidos: {len(all_records)}")
    return all_records


def transform(records: list[dict]) -> pd.DataFrame:
    """Limpa e estrutura os dados da DGEG."""
    rows = []
    today = date.today().isoformat()

    for r in records:
        preco_str = str(r.get("Preco", "")).replace(",", ".").replace("€/litro", "").strip()
        try:
            preco = float(preco_str)
        except ValueError:
            continue

        rows.append({
            "data": today,
            "distrito": r.get("Distrito", "Desconhecido").strip(),
            "municipio": r.get("Municipio", "Desconhecido").strip(),
            "nome_posto": r.get("Nome", "").strip(),
            "tipo_combustivel": r.get("TipoCombustivel", "").strip(),
            "preco": preco,
            "marca": r.get("Marca", "").strip(),
        })

    df = pd.DataFrame(rows)
    print(f"Registos válidos após limpeza: {len(df)}")
    return df


def load_to_supabase(df: pd.DataFrame):
    """Insere os dados no Supabase."""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    records = df.to_dict(orient="records")

    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table("precos_combustivel").upsert(batch).execute()
        print(f"  Inseridos {min(i + batch_size, len(records))}/{len(records)} registos")

    print("Carga concluída com sucesso.")


def main():
    records = fetch_dgeg_data()
    if not records:
        print("Sem dados para inserir. A terminar.")
        return
    df = transform(records)
    if df.empty:
        print("DataFrame vazio após limpeza. A terminar.")
        return
    load_to_supabase(df)


if __name__ == "__main__":
    main()
