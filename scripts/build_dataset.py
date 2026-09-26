"""
build_dataset.py

Legge tutti i file grezzi in data/raw/pokemon/ e data/raw/species/ (prodotti
da fetch_pokemon_data.py) più i dati evolutivi risolti in data/evolution_stages.json
(prodotti da fetch_evolution_chains.py + resolve_evolution_stages.py), ed
estrae SOLO i campi utili al generatore di puzzle, producendo un unico file
leggero: data/pokemon_curated.json.

Questo è l'unico file che generate_puzzle.py leggerà in seguito: niente
nel resto della pipeline tocca più i JSON grezzi di PokéAPI o fa
chiamate di rete.

Uso:
    python build_dataset.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POKEMON_DIR = DATA_DIR / "raw" / "pokemon"
SPECIES_DIR = DATA_DIR / "raw" / "species"
EVOLUTION_STAGES_FILE = DATA_DIR / "evolution_stages.json"
OUTPUT_FILE = DATA_DIR / "pokemon_curated.json"


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def extract_stats(pokemon_raw: dict) -> dict:
    stats = {}
    for entry in pokemon_raw.get("stats", []):
        stat_name = entry["stat"]["name"].replace("-", "_")
        stats[stat_name] = entry["base_stat"]
    return stats


def load_evolution_data() -> dict:
    """Carica la mappa nome_specie -> {stage, evolves_from, evolves_to}
    prodotta da resolve_evolution_stages.py."""
    if not EVOLUTION_STAGES_FILE.exists():
        return {}
    return json.loads(EVOLUTION_STAGES_FILE.read_text(encoding="utf-8"))


def build_entry(pokemon_id: int, evolution_data_map: dict) -> dict | None:
    pokemon_raw = load_json(POKEMON_DIR / f"{pokemon_id}.json")
    species_raw = load_json(SPECIES_DIR / f"{pokemon_id}.json")

    if pokemon_raw is None or species_raw is None:
        return None

    # i dati evolutivi vanno cercati per NOME DELLA SPECIE, non per nome del
    # pokemon: forme alternative (es. "raichu-alola") hanno pokemon_id
    # diverso ma condividono la specie base ("raichu") nella evolution chain.
    species_name = species_raw["name"]
    evolution_data = evolution_data_map.get(species_name, {})

    return {
        "id": pokemon_id,
        "name": pokemon_raw["name"],
        "generation": species_raw["generation"]["name"],
        "types": [t["type"]["name"] for t in pokemon_raw["types"]],
        "height_dm": pokemon_raw["height"],
        "weight_hg": pokemon_raw["weight"],
        "base_stats": extract_stats(pokemon_raw),
        "color": species_raw["color"]["name"],
        "egg_groups": [g["name"] for g in species_raw.get("egg_groups", [])],
        "abilities": [a["ability"]["name"] for a in pokemon_raw["abilities"]],
        "is_legendary": species_raw.get("is_legendary", False),
        "is_mythical": species_raw.get("is_mythical", False),
        "evolution_stage": evolution_data.get("stage"),
        "evolves_from": evolution_data.get("evolves_from"),
        "evolves_to": evolution_data.get("evolves_to", []),
    }


def build_dataset() -> list[dict]:
    evolution_data_map = load_evolution_data()

    if not evolution_data_map:
        print(
            "ATTENZIONE: evolution_stages.json non trovato o vuoto. "
            "Esegui prima fetch_evolution_chains.py e resolve_evolution_stages.py, "
            "altrimenti evolution_stage/evolves_from/evolves_to resteranno vuoti per tutti."
        )

    pokemon_ids = sorted(
        int(path.stem) for path in POKEMON_DIR.glob("*.json") if path.stem.isdigit()
    )

    entries = []
    for pokemon_id in pokemon_ids:
        entry = build_entry(pokemon_id, evolution_data_map)
        if entry is not None:
            entries.append(entry)

    return entries


def main() -> None:
    entries = build_dataset()

    OUTPUT_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Dataset curato scritto in {OUTPUT_FILE}")
    print(f"Totale Pokémon inclusi: {len(entries)}")


if __name__ == "__main__":
    main()