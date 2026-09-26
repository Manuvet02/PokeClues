"""
resolve_evolution_stages.py

Cammina ogni evolution chain grezza in data/raw/evolution-chain/ e calcola,
per ogni specie:
  - stage:        1 = forma base, 2 = prima evoluzione, 3 = evoluzione finale...
  - evolves_from: nome della specie precedente nella catena, o null se è la forma base
  - evolves_to:   lista dei nomi delle specie immediatamente successive
                  (lista con più elementi per le catene ramificate, es. Eevee)

Gestisce le catene ramificate: tutti i rami allo stesso livello di
profondità ricevono lo stesso stage.

Produce data/evolution_stages.json:
    {
      "bulbasaur": {"stage": 1, "evolves_from": null, "evolves_to": ["ivysaur"]},
      "ivysaur":   {"stage": 2, "evolves_from": "bulbasaur", "evolves_to": ["venusaur"]},
      "venusaur":  {"stage": 3, "evolves_from": "ivysaur", "evolves_to": []},
      "eevee":     {"stage": 1, "evolves_from": null, "evolves_to": ["vaporeon", "jolteon"]}
    }

Va eseguito DOPO fetch_evolution_chains.py.

Uso:
    python resolve_evolution_stages.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHAIN_DIR = DATA_DIR / "raw" / "evolution-chain"
OUTPUT_FILE = DATA_DIR / "evolution_stages.json"


def walk_chain_node(node: dict, stage: int, evolves_from: str | None, evolution_data: dict) -> None:
    """Popola evolution_data per la specie corrente e ricorre sui rami evolutivi."""
    species_name = node["species"]["name"]
    children = node.get("evolves_to", [])

    evolution_data[species_name] = {
        "stage": stage,
        "evolves_from": evolves_from,
        "evolves_to": [child["species"]["name"] for child in children],
    }

    for child_node in children:
        walk_chain_node(child_node, stage + 1, species_name, evolution_data)


def resolve_all_evolution_data() -> dict:
    evolution_data: dict[str, dict] = {}

    for chain_file in CHAIN_DIR.glob("*.json"):
        chain_raw = json.loads(chain_file.read_text(encoding="utf-8"))
        root_node = chain_raw["chain"]
        walk_chain_node(root_node, stage=1, evolves_from=None, evolution_data=evolution_data)

    return evolution_data


def main() -> None:
    evolution_data = resolve_all_evolution_data()

    OUTPUT_FILE.write_text(
        json.dumps(evolution_data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Dati evolutivi risolti per {len(evolution_data)} specie.")
    print(f"Scritto in {OUTPUT_FILE}")


if __name__ == "__main__":
    main()