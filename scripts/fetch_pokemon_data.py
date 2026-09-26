"""
fetch_pokemon_data.py

Scarica UNA TANTUM (o ogni volta che esce una nuova generazione) tutti i dati
grezzi di PokéAPI necessari al progetto, e li salva come JSON su disco in
data/raw/. Da quel momento in poi nessun altro script del progetto chiama
più PokéAPI: tutto lavora sulla cache locale.

Rispetta la fair use policy di PokéAPI:
- fa caching locale di ogni risorsa scaricata (non riscarica se già presente)
- usa uno user-agent identificativo
- introduce un piccolo delay tra le richieste per non sovraccaricare il server

"""

import argparse
import json
import time
from pathlib import Path

import requests

BASE_URL = "https://pokeapi.co/api/v2"
USER_AGENT = "pokemon-clues-project/0.1 (script di raccolta dati per progetto personale)"
REQUEST_DELAY_SECONDS = 0.3 

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
POKEMON_DIR = RAW_DIR / "pokemon"
SPECIES_DIR = RAW_DIR / "species"


def ensure_dirs() -> None:
    POKEMON_DIR.mkdir(parents=True, exist_ok=True)
    SPECIES_DIR.mkdir(parents=True, exist_ok=True)


def fetch_json(url: str) -> dict:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_resource(resource: str, pokemon_id: int, target_dir: Path) -> None:
    """Scarica una singola risorsa (pokemon o pokemon-species) se non è già in cache."""
    dest_file = target_dir / f"{pokemon_id}.json"

    if dest_file.exists():
        # già scaricato in una run precedente: non richiamare l'API
        return

    url = f"{BASE_URL}/{resource}/{pokemon_id}"
    data = fetch_json(url)

    dest_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    time.sleep(REQUEST_DELAY_SECONDS)


def fetch_all(count: int, start_id: int = 1) -> None:
    ensure_dirs()

    for pokemon_id in range(start_id, start_id + count):
        try:
            fetch_resource("pokemon", pokemon_id, POKEMON_DIR)
            fetch_resource("pokemon-species", pokemon_id, SPECIES_DIR)
            print(f"[{pokemon_id}/{start_id + count - 1}] ok")
        except requests.HTTPError as exc:
            # capita per id non assegnati (form speciali, gap nella numerazione):
            # si salta e si prosegue, non è un errore bloccante
            print(f"[{pokemon_id}] saltato ({exc})")
        except requests.RequestException as exc:
            print(f"[{pokemon_id}] errore di rete, riprovo tra 5s: {exc}")
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scarica e mette in cache i dati grezzi di PokéAPI")
    parser.add_argument("--count", type=int, default=1025, help="Numero di Pokémon da scaricare")
    parser.add_argument("--start-id", type=int, default=1, help="ID di partenza (utile per riprendere una run interrotta)")
    args = parser.parse_args()

    fetch_all(count=args.count, start_id=args.start_id)
    print("\nFatto. Dati grezzi salvati in:", RAW_DIR)


if __name__ == "__main__":
    main()