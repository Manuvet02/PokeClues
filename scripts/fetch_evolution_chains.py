"""
fetch_evolution_chains.py

Le evolution chain sono risorse condivise: più specie puntano alla stessa
chain (es. bulbasaur/ivysaur/venusaur puntano tutte a evolution-chain/1).
Questo script:
  1. legge tutti i file già scaricati in data/raw/species/
  2. estrae l'ID della evolution chain di ciascuna specie
  3. deduplica gli ID
  4. scarica solo le catene non ancora in cache in data/raw/evolution-chain/

Va eseguito DOPO fetch_pokemon_data.py, perché legge i file species già
presenti su disco invece di richiamare l'API per scoprire quali id esistono.

Uso:
    python fetch_evolution_chains.py
"""

import json
import re
import time
from pathlib import Path

import requests

USER_AGENT = "pokemon-clues-project/0.1 (script di raccolta dati per progetto personale)"
REQUEST_DELAY_SECONDS = 0.3

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SPECIES_DIR = DATA_DIR / "raw" / "species"
CHAIN_DIR = DATA_DIR / "raw" / "evolution-chain"

CHAIN_ID_PATTERN = re.compile(r"/evolution-chain/(\d+)/?$")


def extract_chain_ids() -> set[int]:
    """Legge ogni species raw e ne estrae l'id della evolution chain associata."""
    chain_ids: set[int] = set()

    for species_file in SPECIES_DIR.glob("*.json"):
        species_raw = json.loads(species_file.read_text(encoding="utf-8"))
        chain_url = species_raw.get("evolution_chain", {}).get("url")

        if not chain_url:
            continue

        match = CHAIN_ID_PATTERN.search(chain_url)
        if match:
            chain_ids.add(int(match.group(1)))

    return chain_ids


def fetch_chain(chain_id: int) -> None:
    dest_file = CHAIN_DIR / f"{chain_id}.json"

    if dest_file.exists():
        return  # già in cache

    url = f"https://pokeapi.co/api/v2/evolution-chain/{chain_id}"
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()

    dest_file.write_text(
        json.dumps(response.json(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    time.sleep(REQUEST_DELAY_SECONDS)


def main() -> None:
    CHAIN_DIR.mkdir(parents=True, exist_ok=True)

    chain_ids = extract_chain_ids()
    print(f"Trovate {len(chain_ids)} evolution chain distinte da scaricare.")

    for i, chain_id in enumerate(sorted(chain_ids), start=1):
        try:
            fetch_chain(chain_id)
            print(f"[{i}/{len(chain_ids)}] chain {chain_id} ok")
        except requests.RequestException as exc:
            print(f"[{i}/{len(chain_ids)}] chain {chain_id} errore: {exc}")

    print("\nFatto. Catene evolutive salvate in:", CHAIN_DIR)


if __name__ == "__main__":
    main()
