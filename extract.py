"""
extract.py
Extrai preços de combustível da API da DGEG e insere no Supabase.
Usa apenas requests e json — sem biblioteca supabase.
Corre diariamente via GitHub Actions.
"""

import os
import json
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Headers para o Supabase REST API direto
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Headers para a API da DGEG
DGEG_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9",
    "Referer": "https://precoscombustiveis.dgeg.gov.pt/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
}

URL_LISTA_POSTOS = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/ListarDadosPostos"
URL_PRECO_POSTO  = "https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/GetDadosPostoMapa"

TIPOS_COMBUSTIVEL = ["Gasolina simples 95", "Gasolina simples 98", "Gasóleo simples"]


def fetch_all_posto_ids() -> list:
    """Obtém a lista de todos os postos."""
    print("A obter lista de postos...")
    all_postos = []
    page = 1

    while True:
        params = {"pagina": page, "qtdPorPagina": 500, "idioma": "pt", "f": "json"}
        r = requests.get(URL_LISTA_POSTOS, params=params, headers=DGEG_HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("resultado", [])
        if not items:
            break
        all_postos.extend(items)
        print(f"  Página {page}: {len(items)} postos")
        if len(items) < 500:
            break
        page += 1

    print(f"Total de postos: {len(all_postos)}")
    return all_postos


def fetch_preco_posto(posto_id: str) -> list:
    """Obtém os preços de um posto específico."""
    try:
        r = requests.get(URL_PRECO_POSTO, params={"id": posto_id, "f": "json"},
                         headers=DGEG_HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("resultado", {}).get("Combustiveis", [])
    except Exception:
        return []


def fetch_all_precos(postos: list) -> list:
    """Itera por todos os postos e recolhe preços."""
    today = date.today().isoformat()
    rows = []
    total = len(postos)

    for i, posto in enumerate(postos):
        posto_id = posto.get("Codigo") or posto.get("Id") or posto.get("id")
        if not posto_id:
            continue

        combustiveis = fetch_preco_posto(str(posto_id))

        for comb in combustiveis:
            tipo = comb.get("TipoCombustivel", "")
            if tipo not in TIPOS_COMBUSTIVEL:
                continue

            preco_str = str(comb.get("Preco", "")).replace(",", ".").replace(" €/litro", "").strip()
            try:
                preco = float(preco_str)
            except ValueError:
                continue

            rows.append({
                "data": today,
                "distrito": posto.get("DistritoDescritivo", "Desconhecido").strip(),
                "municipio": posto.get("MunicipioDescritivo", "Desconhecido").strip(),
                "nome_posto": posto.get("Nome", "").strip(),
                "tipo_combustivel": tipo,
                "preco": preco,
                "marca": posto.get("MarcaDescritivo", "").strip(),
            })

        if (i + 1) % 100 == 0:
            print(f"  Processados {i + 1}/{total} postos, {len(rows)} preços recolhidos")

    print(f"Total de preços recolhidos: {len(rows)}")
    return rows


def load_to_supabase(rows: list):
    """Insere os dados no Supabase via REST API direta."""
    url = f"{SUPABASE_URL}/rest/v1/precos_combustivel"
    batch_size = 100

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        r = requests.post(url, headers=SUPABASE_HEADERS, data=json.dumps(batch), timeout=30)
        if r.status_code in (200, 201):
            print(f"  Inseridos {min(i + batch_size, len(rows))}/{len(rows)} registos")
        else:
            print(f"  Erro ao inserir batch {i}: {r.status_code} — {r.text[:200]}")

    print("Carga concluída.")


def main():
    postos = fetch_all_posto_ids()
    if not postos:
        print("Sem postos. A terminar.")
        return
    rows = fetch_all_precos(postos)
    if not rows:
        print("Sem preços. A terminar.")
        return
    load_to_supabase(rows)


if __name__ == "__main__":
    main()
