"""
generate_shiny_puzzle.py

Variante "regular / shiny" stile Clues by Sam:
  - 20 Pokémon visibili in griglia, l'incognita è solo regular (0) o shiny (1)
  - ogni cella possiede UNA clue, visibile solo quando la cella è stata risolta
  - una cella iniziale è già svelata: la sua clue è la "clue 0" da cui parte il ragionamento
  - tutte le clue sono vere; ogni cella è deducibile senza tentativi

Uso:
    python generate_shiny_puzzle.py --date 2026-09-27
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path

from shiny_solver import (
    Clue, ContradictionError, at_least_clue, at_most_clue, compare_clue,
    conditional_clue, count_clue, count_solutions, different_clue,
    propagate_all, same_clue, simulate_player,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CURATED_FILE = DATA_DIR / "pokemon_curated.json"
PUZZLES_DIR = Path(__file__).resolve().parent.parent / "puzzles"

SHINY_RATIO = 0.35
MAX_GAIN = 3  # una clue può sbloccare da 1 a MAX_GAIN celle nuove: più alto = più rami
MAX_COMPARE_SHARE = 0.75
REQUIRED_FIELDS = ["id", "name"]


class PuzzleGenerationError(Exception):
    pass


def cell_label(index: int, cols: int) -> str:
    row, col = divmod(index, cols)
    return f"{chr(ord('A') + row)}{col + 1}"


def load_pokedex() -> list[dict]:
    entries = json.loads(CURATED_FILE.read_text(encoding="utf-8"))
    return [e for e in entries if all(e.get(f) not in (None, [], {}) for f in REQUIRED_FIELDS)]


# --- gruppi di celle (il "vocabolario" delle clue) ---------------------------

def legacy_build_groups(entries: list[dict], rows: int, cols: int) -> list[dict]:
    """Ogni gruppo: {cells, subject, noun}. `subject` è il soggetto da usare nei testi
    ("i Pokémon nella riga B"); `noun` (solo per gruppi da attributo) permette frasi
    tipo "i due Pokémon di tipo fuoco"."""
    n = rows * cols
    groups = []

    for r in range(rows):
        groups.append({"cells": [r * cols + c for c in range(cols)], "subject": f"i Pokémon nella riga {chr(ord('A') + r)}", "noun": None})
    for c in range(cols):
        groups.append({"cells": [r * cols + c for r in range(rows)], "subject": f"i Pokémon nella colonna {c + 1}", "noun": None})

    def add_attribute_group(cells, noun):
        if 2 <= len(cells) <= n - 2:
            groups.append({"cells": cells, "subject": f"i Pokémon {noun}", "noun": noun})

    all_types = sorted({t for e in entries for t in e["types"]})
    for t in all_types:
        add_attribute_group([i for i, e in enumerate(entries) if t in e["types"]], f"di tipo {t}")
    for color in sorted({e["color"] for e in entries}):
        add_attribute_group([i for i, e in enumerate(entries) if e["color"] == color], f"di colore {color}")
    for stage in sorted({e["evolution_stage"] for e in entries}):
        add_attribute_group([i for i, e in enumerate(entries) if e["evolution_stage"] == stage], f"allo stadio evolutivo {stage}")
    for egg in sorted({g for e in entries for g in e["egg_groups"]}):
        add_attribute_group([i for i, e in enumerate(entries) if egg in e["egg_groups"]], f"del gruppo uova {egg}")
    add_attribute_group([i for i, e in enumerate(entries) if e["is_legendary"]], "leggendari")
    add_attribute_group([i for i, e in enumerate(entries) if e["base_stats"]["speed"] >= 90], "con velocità base almeno 90")
    add_attribute_group([i for i, e in enumerate(entries) if e["base_stats"]["attack"] >= 100], "con attacco base almeno 100")
    add_attribute_group([i for i, e in enumerate(entries) if e["weight_hg"] >= 1000], "più pesanti di 100 kg")

    return groups


def build_groups(entries: list[dict], rows: int, cols: int) -> list[dict]:
    """Groups use board positions and facts inferable from the visible species names."""
    n = rows * cols
    groups = []

    def add(cells, subject, noun=None):
        if 2 <= len(cells) <= n - 2:
            groups.append({"cells": cells, "subject": subject, "noun": noun})

    for r in range(rows):
        add([r * cols + c for c in range(cols)],
            f"i Pokemon nella riga {chr(ord('A') + r)}")
    for c in range(cols):
        add([r * cols + c for r in range(rows)],
            f"i Pokemon nella colonna {c + 1}")

    add([0, cols - 1, (rows - 1) * cols, rows * cols - 1],
        "i Pokemon nei quattro angoli")
    edge_cells = [r * cols + c for r in range(rows) for c in range(cols)
                  if r == 0 or r == rows - 1 or c == 0 or c == cols - 1]
    add(edge_cells, "i Pokemon sul bordo")

    if min(rows, cols) >= 3:
        length = min(rows, cols)
        add([i * cols + i for i in range(length)],
            "i Pokemon sulla diagonale principale")
        add([i * cols + cols - 1 - i for i in range(length)],
            "i Pokemon sulla diagonale opposta")

    type_names = {
        "bug": "coleottero", "dark": "buio", "dragon": "drago", "electric": "elettro",
        "fairy": "folletto", "fighting": "lotta", "fire": "fuoco", "flying": "volante",
        "ghost": "spettro", "grass": "erba", "ground": "terra", "ice": "ghiaccio",
        "normal": "normale", "poison": "veleno", "psychic": "psico", "rock": "roccia",
        "steel": "acciaio", "water": "acqua",
    }
    for pokemon_type in sorted({t for entry in entries for t in entry.get("types", [])}):
        members = [i for i, entry in enumerate(entries) if pokemon_type in entry.get("types", [])]
        add(members, f"i Pokemon di tipo {type_names.get(pokemon_type, pokemon_type)}",
            f"di tipo {type_names.get(pokemon_type, pokemon_type)}")

    color_names = {"black": "nero", "blue": "blu", "brown": "marrone", "gray": "grigio",
                   "green": "verde", "pink": "rosa", "purple": "viola", "red": "rosso",
                   "white": "bianco", "yellow": "giallo"}
    for color in sorted({entry.get("color") for entry in entries if entry.get("color")}):
        members = [i for i, entry in enumerate(entries) if entry.get("color") == color]
        add(members, f"i Pokemon di colore {color_names.get(color, color)}",
            f"di colore {color_names.get(color, color)}")

    generation_names = {
        "generation-i": "prima", "generation-ii": "seconda", "generation-iii": "terza",
        "generation-iv": "quarta", "generation-v": "quinta", "generation-vi": "sesta",
        "generation-vii": "settima", "generation-viii": "ottava", "generation-ix": "nona",
    }
    for generation in sorted({entry.get("generation") for entry in entries if entry.get("generation")}):
        members = [i for i, entry in enumerate(entries) if entry.get("generation") == generation]
        label = generation_names.get(generation, generation.removeprefix("generation-").upper())
        add(members, f"i Pokemon della {label} generazione", f"della {label} generazione")

    stages = {1: "allo stadio base", 2: "allo stadio intermedio", 3: "allo stadio finale"}
    for stage, description in stages.items():
        members = [i for i, entry in enumerate(entries) if entry.get("evolution_stage") == stage]
        add(members, f"i Pokemon {description}", description)

    legendary = [i for i, entry in enumerate(entries) if entry.get("is_legendary")]
    mythical = [i for i, entry in enumerate(entries) if entry.get("is_mythical")]
    add(legendary, "i Pokemon leggendari", "leggendari")
    add(mythical, "i Pokemon misteriosi", "misteriosi")

    stat_groups = [
        ("speed", 90, "con Velocita base almeno 90"),
        ("attack", 100, "con Attacco base almeno 100"),
        ("defense", 100, "con Difesa base almeno 100"),
    ]
    for stat, threshold, description in stat_groups:
        members = [i for i, entry in enumerate(entries)
                   if entry.get("base_stats", {}).get(stat, 0) >= threshold]
        add(members, f"i Pokemon {description}", description)

    # Thresholds are deliberately broad enough to form useful, deducible groups.
    for stat, threshold, label in [
        ("hp", 80, "PS"), ("attack", 80, "Attacco"), ("defense", 80, "Difesa"),
        ("special_attack", 80, "Attacco Speciale"),
        ("special_defense", 80, "Difesa Speciale"), ("speed", 80, "Velocita"),
    ]:
        members = [i for i, entry in enumerate(entries)
                   if entry.get("base_stats", {}).get(stat, 0) >= threshold]
        add(members, f"i Pokemon con {label} almeno {threshold}",
            f"con {label} almeno {threshold}")

    total_stats = [sum(entry.get("base_stats", {}).values()) for entry in entries]
    for threshold in (400, 500):
        members = [i for i, total in enumerate(total_stats) if total >= threshold]
        add(members, f"i Pokemon con almeno {threshold} punti totali nelle statistiche",
            f"con almeno {threshold} punti totali nelle statistiche")

    for threshold_dm in (10, 20):
        members = [i for i, entry in enumerate(entries) if entry.get("height_dm", 0) >= threshold_dm]
        meters = threshold_dm / 10
        add(members, f"i Pokemon alti almeno {meters:g} m", f"alti almeno {meters:g} m")

    for threshold_hg in (1000, 5000):
        members = [i for i, entry in enumerate(entries) if entry.get("weight_hg", 0) >= threshold_hg]
        kg = threshold_hg / 10
        add(members, f"i Pokemon che pesano almeno {kg:g} kg", f"che pesano almeno {kg:g} kg")
    return groups


def neighbors(index: int, rows: int, cols: int) -> list[int]:
    r, c = divmod(index, cols)
    return [rr * cols + cc
            for rr in range(max(0, r - 1), min(rows, r + 2))
            for cc in range(max(0, c - 1), min(cols, c + 2))
            if (rr, cc) != (r, c)]


# --- pool di clue vere -------------------------------------------------------

def legacy_count_text(k: int, size: int, subject: str) -> str:
    if k == 0:
        return f"Nessuno tra {subject} è shiny."
    if k == size:
        return f"Tutti {subject} sono shiny."
    verb = "è" if k == 1 else "sono"
    return f"Esattamente {k} tra {subject} {verb} shiny."


def count_text(k: int, size: int, subject: str) -> str:
    if k == 0:
        return f"Tra {subject}, nessuno è shiny."
    if k == size:
        return f"Tra {subject}, tutti sono shiny."
    if k == 1:
        return f"Tra {subject}, esattamente un Pokémon è shiny."
    return f"Tra {subject}, esattamente {k} sono shiny."


def at_least_text(k: int, subject: str) -> str:
    if k == 1:
        return f"Tra {subject}, almeno un Pokémon è shiny."
    return f"Tra {subject}, almeno {k} sono shiny."


def at_most_text(k: int, subject: str) -> str:
    if k == 1:
        return f"Tra {subject}, al massimo un Pokémon è shiny."
    return f"Tra {subject}, al massimo {k} sono shiny."


def add_count_clues(pool: list[Clue], cells: list[int], k: int, subject: str) -> None:
    size = len(cells)
    pool.append(count_clue(cells, k, count_text(k, size, subject)))
    if 0 < k < size:
        pool.append(at_least_clue(cells, k, at_least_text(k, subject)))
        pool.append(at_most_clue(cells, k, at_most_text(k, subject)))


def build_pool(entries: list[dict], truth: list[int], rows: int, cols: int) -> list[Clue]:
    n = rows * cols
    groups = build_groups(entries, rows, cols)
    pool: list[Clue] = []

    # conteggi su righe, colonne e gruppi da attributo
    for g in groups:
        k = sum(truth[c] for c in g["cells"])
        add_count_clues(pool, g["cells"], k, g["subject"])

    # conteggi sui vicini di una cella
    for i in range(n):
        cells = neighbors(i, rows, cols)
        k = sum(truth[c] for c in cells)
        add_count_clues(pool, cells, k, f"i vicini di {cell_label(i, cols)}")

    # confronti fra gruppi: "più shiny in A che in B"
    for i, ga in enumerate(groups):
        for gb in groups[i + 1:]:
            ca = sum(truth[c] for c in ga["cells"])
            cb = sum(truth[c] for c in gb["cells"])
            if ca == cb:
                continue
            hi, lo = (ga, gb) if ca > cb else (gb, ga)
            pool.append(compare_clue(hi["cells"], lo["cells"], f"Ci sono più shiny tra {hi['subject']} che tra {lo['subject']}."))

    # coppie di celle adiacenti: stesso stato / stato diverso
    for i in range(n):
        for j in neighbors(i, rows, cols):
            if j > i:
                a, b = cell_label(i, cols), cell_label(j, cols)
                if truth[i] == truth[j]:
                    pool.append(same_clue(i, j, f"I Pokémon in {a} e {b} hanno lo stesso stato."))
                else:
                    pool.append(different_clue(i, j, f"I Pokémon in {a} e {b} hanno stato diverso."))

    # implicazioni tra due celle: la prima condizione è vera nella soluzione,
    # così la clue non risulta vera solo per un antecedente impossibile.
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            a, b = entries[i]["name"].capitalize(), entries[j]["name"].capitalize()
            a_status, b_status = truth[i], truth[j]
            a_text = "shiny" if a_status else "regular"
            b_text = "shiny" if b_status else "regular"
            text = f"Se {a} è {a_text}, {b} è {b_text}."
            pool.append(conditional_clue(i, a_status, j, b_status, text))

    # coppie "i due Pokémon di tipo X": stesso stato / diverso
    for g in groups:
        if g["noun"] and len(g["cells"]) == 2:
            i, j = g["cells"]
            if truth[i] == truth[j]:
                pool.append(same_clue(i, j, f"I due Pokémon {g['noun']} hanno lo stesso stato."))
            else:
                pool.append(different_clue(i, j, f"I due Pokémon {g['noun']} hanno stato diverso."))

    return pool


# --- costruzione della catena ------------------------------------------------

def determined(state: list) -> int:
    return sum(1 for s in state if s is not None)


def pick_clue(pool: list[Clue], active: list[Clue], state: list, rng: random.Random) -> Clue | None:
    """Fra le clue che sbloccano da 1 a MAX_GAIN celle nuove ne sceglie una a
    caso, con preferenza per gli sblocchi piccoli: il risultato è un albero
    che si ramifica ogni tanto invece di una catena lineare. Se nessuna clue
    entra in quell'intervallo prende quella con lo sblocco più piccolo; se
    nessuna sblocca nulla, ne prende una a caso che tocca celle ancora ignote
    (servirà in combinazione con le prossime)."""
    base = determined(state)
    candidates = []
    for clue in pool:
        trial = list(state)
        try:
            propagate_all(trial, active + [clue])
        except ContradictionError:
            continue
        gain = determined(trial) - base
        if gain > 0:
            candidates.append((gain, clue))
    if candidates:
        allowed = [(g, c) for g, c in candidates if g <= MAX_GAIN]
        if not allowed:
            min_gain = min(g for g, _ in candidates)
            allowed = [(g, c) for g, c in candidates if g == min_gain]
        weights = [1.0 / g for g, _ in allowed]  # sblocchi piccoli più probabili
        return rng.choices([c for _, c in allowed], weights=weights, k=1)[0]

    unknown = {i for i, s in enumerate(state) if s is None}
    useful = [c for c in pool if c.cells & unknown]
    return rng.choice(useful) if useful else None


def build_chain(entries: list[dict], truth: list[int], rows: int, cols: int,
                rng: random.Random, start_cell: int | None = None):
    n = rows * cols
    pool = build_pool(entries, truth, rows, cols)
    rng.shuffle(pool)

    if start_cell is None:
        start_cell = rng.randrange(n)
    state: list = [None] * n
    state[start_cell] = truth[start_cell]

    clue_of_cell: dict[int, Clue] = {}
    active: list[Clue] = []
    pending = [start_cell]

    while pending:
        owner = pending.pop(0)
        clue = pick_clue([c for c in pool if c not in active], active, state, rng)
        if clue is None:
            break
        before = [s is not None for s in state]
        active.append(clue)
        clue_of_cell[owner] = clue
        propagate_all(state, active)
        for cell in range(n):
            if state[cell] is not None and not before[cell]:
                pending.append(cell)

    if any(s is None for s in state):
        raise PuzzleGenerationError(f"catena bloccata: {determined(state)}/{n} celle risolte")

    return start_cell, clue_of_cell, pool


def refresh_existing_puzzle(puzzle: dict, rng: random.Random) -> dict:
    rows, cols = puzzle["grid_size"]
    cells = puzzle["cells"]
    truth = [1 if value == "shiny" else 0 for value in puzzle["solution"]]
    start_cell = next(i for i, cell in enumerate(cells) if cell["label"] == puzzle["start_cell"])
    catalog = {entry["id"]: entry for entry in load_pokedex()}
    entries = [catalog.get(cell["id"]) for cell in cells]
    if any(entry is None for entry in entries):
        raise PuzzleGenerationError("mancano dati Pokédex per uno o più Pokémon del puzzle")

    _, clue_of_cell, pool = build_chain(entries, truth, rows, cols, rng, start_cell)
    fill_remaining_clues(len(cells), clue_of_cell, pool, rng)
    solved, unlocked_by = simulate_player(len(cells), start_cell, truth[start_cell], clue_of_cell, truth)
    all_clues = list(clue_of_cell.values())
    if not solved or count_solutions(
        [truth[start_cell] if i == start_cell else None for i in range(len(cells))],
        all_clues, limit=2,
    ) != 1:
        raise PuzzleGenerationError("le nuove clues non producono una soluzione unica e deducibile")

    validate_clue_quality(all_clues, start_cell, unlocked_by)

    for i, cell in enumerate(cells):
        cell["clue"] = clue_of_cell[i].text
        cell["unlocked_by"] = None if unlocked_by[i] is None else cell_label(unlocked_by[i], cols)
        cell["logic"] = serialize_logic(clue_of_cell[i])
    return puzzle


def serialize_logic(clue: Clue) -> list[dict]:
    return [
        {"weights": {str(cell): weight for cell, weight in linear.weights.items()},
         "bound": linear.bound}
        for linear in clue.linears
    ]


def fill_remaining_clues(n: int, clue_of_cell: dict[int, Clue], pool: list[Clue], rng: random.Random) -> None:
    """Le celle risolte a fine catena non hanno ancora una clue: ne ricevono
    una vera qualsiasi (confermano quanto già dedotto). Nel gioco vero ogni
    cella ne mostra una."""
    used = set(map(id, clue_of_cell.values()))
    spare = [c for c in pool if id(c) not in used]
    rng.shuffle(spare)
    for cell in range(n):
        if cell not in clue_of_cell:
            clue_of_cell[cell] = spare.pop()


def validate_clue_quality(clues: list[Clue], start_cell: int,
                           unlocked_by: dict[int, int | None]) -> None:
    """Reject repetitive, overly revealing, or jargon-heavy clue sets."""
    texts = [" ".join(clue.text.casefold().split()) for clue in clues]
    if len(set(texts)) != len(texts):
        raise PuzzleGenerationError("clue ripetute")

    compare_share = sum(clue.kind == "compare" for clue in clues) / len(clues)
    if compare_share > MAX_COMPARE_SHARE:
        raise PuzzleGenerationError("troppi confronti tra gruppi; manca varietà di clue")

    unlock_counts: dict[int, int] = {}
    for cell, owner in unlocked_by.items():
        if cell != start_cell and owner is not None:
            unlock_counts[owner] = unlock_counts.get(owner, 0) + 1
    if max(unlock_counts.values(), default=0) > MAX_GAIN:
        raise PuzzleGenerationError(f"una clue sblocca più di {MAX_GAIN} celle")

    technical_terms = ("gruppo uova", "punti statistica base", "ps base", "abilità")
    if any(term in text for text in texts for term in technical_terms):
        raise PuzzleGenerationError("clue con terminologia troppo tecnica")


def generate_puzzle(target_date: date, rows: int, cols: int, rng: random.Random) -> dict:
    catalog = load_pokedex()
    n = rows * cols
    if len(catalog) < n:
        raise PuzzleGenerationError(f"dataset troppo piccolo: servono {n} Pokémon, trovati {len(catalog)}")

    entries = rng.sample(catalog, n)
    n_shiny = round(n * SHINY_RATIO)
    truth = [1] * n_shiny + [0] * (n - n_shiny)
    rng.shuffle(truth)

    start_cell, clue_of_cell, pool = build_chain(entries, truth, rows, cols, rng)
    fill_remaining_clues(n, clue_of_cell, pool, rng)

    # verifiche: clue vere, giocatore perfetto arriva a tutto, soluzione unica
    all_clues = list(clue_of_cell.values())
    if not all(c.holds(truth) for c in all_clues):
        raise PuzzleGenerationError("bug: una clue non è vera rispetto alla soluzione")

    solved, unlocked_by = simulate_player(n, start_cell, truth[start_cell], clue_of_cell, truth)
    if not solved:
        raise PuzzleGenerationError("il giocatore simulato non riesce a risolvere con le sole clue sbloccate")

    start_state = [None] * n
    start_state[start_cell] = truth[start_cell]
    if count_solutions(start_state, all_clues, limit=2) != 1:
        raise PuzzleGenerationError("soluzione non unica")

    validate_clue_quality(all_clues, start_cell, unlocked_by)

    return {
        "date": target_date.isoformat(),
        "grid_size": [rows, cols],
        "start_cell": cell_label(start_cell, cols),
        "start_status": "shiny" if truth[start_cell] else "regular",
        "cells": [
            {
                "label": cell_label(i, cols),
                "pokemon": entries[i]["name"],
                "id": entries[i]["id"],
                "clue": clue_of_cell[i].text,
                "unlocked_by": None if unlocked_by[i] is None else cell_label(unlocked_by[i], cols),
                "logic": serialize_logic(clue_of_cell[i]),
            }
            for i in range(n)
        ],
        # SOLO sviluppo: prima della pubblicazione va rimosso o cifrato
        "solution": ["shiny" if t else "regular" for t in truth],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera il puzzle regular/shiny del giorno")
    parser.add_argument("--date", type=str, default=date.today().isoformat())
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=30)
    parser.add_argument("--refresh-existing", action="store_true",
                        help="Rigenera solo le clues del puzzle esistente, mantenendo Pokemon e soluzione")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    out = PUZZLES_DIR / f"shiny-{target_date.isoformat()}.json"
    if args.refresh_existing:
        if not out.exists():
            raise SystemExit(f"puzzle non trovato: {out}")
        original = json.loads(out.read_text(encoding="utf-8"))
        refreshed, last_error = None, None
        for attempt in range(args.max_attempts):
            rng = random.Random(f"{target_date.isoformat()}-refresh-{attempt}")
            try:
                refreshed = refresh_existing_puzzle(original, rng)
                break
            except PuzzleGenerationError as exc:
                last_error = exc
        if refreshed is None:
            raise SystemExit(f"impossibile aggiornare le clues: {last_error}")
        out.write_text(json.dumps(refreshed, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Clues aggiornate in {out}; Pokemon, partenza e soluzione mantenuti.")
        return

    puzzle, last_error = None, None
    for attempt in range(args.max_attempts):
        rng = random.Random(f"{target_date.isoformat()}-{args.rows}x{args.cols}-shiny-{attempt}")
        try:
            puzzle = generate_puzzle(target_date, args.rows, args.cols, rng)
            break
        except PuzzleGenerationError as exc:
            last_error = exc
            print(f"tentativo {attempt}: {exc}")
    if puzzle is None:
        raise SystemExit(f"impossibile generare il puzzle: {last_error}")

    PUZZLES_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(puzzle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Puzzle generato: {args.rows * args.cols} celle, partenza {puzzle['start_cell']} ({puzzle['start_status']}). Scritto in {out}")


if __name__ == "__main__":
    main()
