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

PARAMS = {
    "idsTiposComb": "3201,2101,2201",  # Gasóleo, Gasolina 95, Gasolina 98
    "idioma": "pt",
    "qtdPorPagina": 500,
    "pagina": 1
}


def fetch_dgeg_data() -> list[dict]:
    """Chama a API da DGEG e devolve lista de postos com preços."""
    print("A chamar API da DGEG...")
    all_records = []
    page = 1

    while True:
        PARAMS["pagina"] = page
        response = requests.get(DGEG_URL, params=PARAMS, timeout=30)
        response.raise_for_status()
        data = response.json()

        items = data.get("resultado", [])
        if not items:
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
        preco_str = r.get("Preco", "").replace(",", ".").strip()
        try:
            preco = float(preco_str)
        except ValueError:
            continue  # ignora registos sem preço válido

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

    # Insere em lotes de 100 para evitar timeouts
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        client.table("precos_combustivel").insert(batch).execute()
        print(f"  Inseridos {min(i + batch_size, len(records))}/{len(records)} registos")

    print("Carga concluída com sucesso.")


def main():
    records = fetch_dgeg_data()
    df = transform(records)
    load_to_supabase(df)


if __name__ == "__main__":
    main()
