"""
extract.py
Extrai preços de combustível de todos os postos de Portugal via API da DGEG.
Grava no Supabase via REST API directa (sem biblioteca supabase).
Corre diariamente via GitHub Actions.
"""

import os
import json
import time
import requests
import pandas as pd
from datetime import date
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

DGEG_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

URL_LISTA_POSTOS = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/ListarDadosPostos"
URL_PRECO_POSTO  = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/GetDadosPostoMapa"

TIPOS_COMBUSTIVEL = ["Gasolina simples 95", "Gasolina simples 98", "Gasóleo simples"]


def fetch_todos_postos() -> list:
    """Obtém todos os postos num único pedido."""
    print("A obter lista de postos...")
    session = requests.Session()
    session.headers.update(DGEG_HEADERS)

    r = session.get(
        URL_LISTA_POSTOS,
        params={"pagina": 1, "qtdPorPagina": 5000, "idioma": "pt", "f": "json"},
        timeout=30
    )
    r.raise_for_status()
    postos = r.json().get("resultado", [])
    print(f"Total de postos: {len(postos)}")
    return postos, session


def fetch_todos_precos(postos: list, session) -> list:
    """Recolhe preços de todos os postos."""
    today = date.today().isoformat()
    rows = []
    total = len(postos)

    for i, posto in enumerate(postos):
        try:
            r = session.get(
                URL_PRECO_POSTO,
                params={"id": posto["Id"], "f": "json"},
                timeout=10
            )
            if r.status_code != 200:
                continue

            data = r.json().get("resultado", {})
            morada = data.get("Morada") or {}
            localidade = morada.get("Localidade", "Desconhecido").strip()
            cod_postal = morada.get("CodPostal", "").strip()

            for comb in data.get("Combustiveis", []):
                if comb.get("TipoCombustivel") not in TIPOS_COMBUSTIVEL:
                    continue
                preco_str = comb["Preco"].replace(",", ".").replace(" €/litro", "").strip()
                try:
                    preco = float(preco_str)
                    if preco <= 0:
                        continue
                    rows.append({
                        "data": today,
                        "nome_posto": posto["Nome"].strip(),
                        "marca": data.get("Marca", "").strip(),
                        "localidade": localidade,
                        "cod_postal": cod_postal,
                        "tipo_combustivel": comb["TipoCombustivel"],
                        "preco": preco,
                    })
                except ValueError:
                    continue

        except Exception:
            continue

        time.sleep(0.2)

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{total} postos processados, {len(rows)} preços recolhidos")

    print(f"Total de preços recolhidos: {len(rows)}")
    return rows


def remove_duplicados(rows: list) -> list:
    """Remove duplicados antes de gravar."""
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["data", "nome_posto", "tipo_combustivel"])
    print(f"Após remoção de duplicados: {len(df)} registos")
    return df.to_dict(orient="records")


def load_to_supabase(rows: list):
    """Insere os dados no Supabase via REST API."""
    url = f"{SUPABASE_URL}/rest/v1/precos_combustivel"
    batch_size = 100
    total = len(rows)

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        r = requests.post(
            url,
            headers=SUPABASE_HEADERS,
            data=json.dumps(batch),
            timeout=30
        )
        if r.status_code in (200, 201):
            print(f"  Inseridos {min(i + batch_size, total)}/{total}")
        else:
            print(f"  Erro {r.status_code}: {r.text[:200]}")

    print("Carga concluída.")


def export_csv(rows: list):
    """Exporta os dados para CSV no repositório."""
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv("dados.csv", index=False, encoding="utf-8-sig")
    print(f"CSV exportado com {len(df)} registos.")


def main():
    postos, session = fetch_todos_postos()
    if not postos:
        print("Sem postos. A terminar.")
        return

    rows = fetch_todos_precos(postos, session)
    if not rows:
        print("Sem preços. A terminar.")
        return

    rows_clean = remove_duplicados(rows)
    load_to_supabase(rows_clean)
    export_csv(rows_clean)


if __name__ == "__main__":
    main()