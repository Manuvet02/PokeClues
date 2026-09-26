"""
generate_puzzle.py

Genera il puzzle "Pokémon Clues" del giorno: sceglie N Pokémon candidati dal
dataset curato, li dispone su una griglia nascosta, costruisce un pool di
clue vere (derivate dagli attributi reali della soluzione), e ne seleziona
il set minimo che solver.py riesce a risolvere per PURA DEDUZIONE, senza
mai dover indovinare.

NOTA DI SCOPO (v1): la griglia di default è volutamente piccola (3x3) e il
catalogo di clue è volutamente limitato (equality su tipo/colore/generazione/
stadio evolutivo, confronto statistiche fra celle adiacenti, conteggio
leggendari per riga). L'obiettivo di questa prima versione è validare che
l'intera pipeline generatore -> solver -> validazione funzioni end-to-end
su un caso semplice, prima di scalare a griglie più grandi e a un catalogo
di clue più ricco (non adiacenti, colonne, egg group, abilità...).

Uso:
    python generate_puzzle.py --date 2026-09-27 --rows 3 --cols 3
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path

from solver import (
    AttributeEquals,
    CompareStat,
    ExactCount,
    count_solutions,
    solve_by_deduction,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CURATED_FILE = DATA_DIR / "pokemon_curated.json"
PUZZLES_DIR = Path(__file__).resolve().parent.parent / "puzzles"

STATS_USED = ["hp", "attack", "defense", "speed"]
REQUIRED_FIELDS = ["types", "color", "generation", "evolution_stage", "base_stats"]


class PuzzleGenerationError(Exception):
    """Un tentativo di generazione non ha prodotto un puzzle valido
    (pool di clue insufficiente, o soluzione non unica). Chi chiama
    riprova con un altro seed, non è un errore fatale."""


def load_pokedex() -> dict[str, dict]:
    entries = json.loads(CURATED_FILE.read_text(encoding="utf-8"))
    pokedex = {}
    for entry in entries:
        if all(entry.get(field) not in (None, [], {}) for field in REQUIRED_FIELDS):
            pokedex[entry["name"]] = entry
    return pokedex


def grid_adjacent_pairs(rows: int, cols: int) -> list[tuple[int, int]]:
    """Coppie di celle adiacenti orizzontalmente o verticalmente (indice = riga*cols+colonna)."""
    pairs = []
    for r in range(rows):
        for c in range(cols):
            i = r * cols + c
            if c + 1 < cols:
                pairs.append((i, i + 1))
            if r + 1 < rows:
                pairs.append((i, i + cols))
    return pairs


def grid_rows(rows: int, cols: int) -> list[list[int]]:
    return [[r * cols + c for c in range(cols)] for r in range(rows)]


def build_clue_pool(solution: list[str], pokedex: dict, rows: int, cols: int) -> list:
    """Costruisce il pool di clue CANDIDATE, tutte vere rispetto alla `solution`
    generata. build_minimal_clue_set() ne selezionerà poi un sottoinsieme."""
    pool = []

    for cell, name in enumerate(solution):
        entry = pokedex[name]
        for type_name in entry["types"]:
            pool.append(AttributeEquals(cell, "types", type_name))
        pool.append(AttributeEquals(cell, "color", entry["color"]))
        pool.append(AttributeEquals(cell, "generation", entry["generation"]))
        pool.append(AttributeEquals(cell, "evolution_stage", entry["evolution_stage"]))

    for cell_a, cell_b in grid_adjacent_pairs(rows, cols):
        for stat in STATS_USED:
            value_a = pokedex[solution[cell_a]]["base_stats"][stat]
            value_b = pokedex[solution[cell_b]]["base_stats"][stat]
            if value_a == value_b:
                continue  # clue non informativa, si scarta
            pool.append(CompareStat(cell_a, cell_b, stat, greater=value_a > value_b))

    for row_cells in grid_rows(rows, cols):
        legendary_count = sum(1 for cell in row_cells if pokedex[solution[cell]]["is_legendary"])
        pool.append(ExactCount(row_cells, lambda p: p["is_legendary"], legendary_count))

    return pool


def _domain_size_sum(domains) -> int:
    return sum(len(d) for d in domains)


def build_clue_chain(candidate_names: list[str], pool: list, pokedex: dict, rng: random.Random) -> list[tuple]:
    """Costruisce il set di clue passo-passo, come una catena deduttiva
    (stile Clues by Sam), invece di aggiungere clue a caso e rimuovere le
    ridondanti dopo. Ad ogni passo sceglie, fra tutte quelle rimaste nel
    pool, la clue che fa avanzare di più la deduzione rispetto allo stato
    corrente:
      1. priorità a chi risolve più celle nuove per intero
      2. a parità (incluso il caso in cui nessuna risolve nulla del tutto),
         priorità a chi restringe di più la somma totale dei domini

    Ritorna una lista di (clue, celle_risolte_da_questa_clue) nell'ORDINE
    in cui sono state scelte: è già l'ordine naturale di rivelazione
    progressiva delle clue lato frontend."""
    remaining_pool = pool[:]
    rng.shuffle(remaining_pool)  # varia le scelte a parità di punteggio, tra run diverse

    chain: list[tuple] = []
    solved_cells: set[int] = set()

    initial_domains, _ = solve_by_deduction(candidate_names, [], pokedex)
    current_score = _domain_size_sum(initial_domains)

    while len(solved_cells) < len(candidate_names):
        best_clue = None
        best_new_solved: set[int] = set()
        best_score = current_score

        for clue in remaining_pool:
            trial = [c for c, _ in chain] + [clue]
            domains, _ = solve_by_deduction(candidate_names, trial, pokedex)
            newly_solved = {i for i, d in enumerate(domains) if len(d) == 1} - solved_cells
            score = _domain_size_sum(domains)

            is_better = False
            if best_clue is None:
                is_better = score < best_score
            elif len(newly_solved) != len(best_new_solved):
                is_better = len(newly_solved) > len(best_new_solved)
            else:
                is_better = score < best_score

            if is_better:
                best_clue = clue
                best_new_solved = newly_solved
                best_score = score

        if best_clue is None:
            raise PuzzleGenerationError(
                "nessuna clue nel pool fa avanzare la deduzione: il pool di clue è insufficiente"
            )

        chain.append((best_clue, sorted(best_new_solved)))
        remaining_pool.remove(best_clue)
        solved_cells |= best_new_solved
        current_score = best_score

    return chain


def _cell_label(cell_index: int, cols: int) -> str:
    """Converte un indice di cella (0-based) nella label griglia del frontend.
    Colonna = lettera (A, B, C, …), Riga = numero (1, 2, 3, …).
    Es. con cols=4:  0→A1, 1→B1, 2→C1, 3→D1, 4→A2, 5→B2, …"""
    col = cell_index % cols
    row = cell_index // cols
    return f"{chr(ord('A') + col)}{row + 1}"


def clue_to_text(clue, pokedex: dict, cols: int) -> str:
    """Traduce un oggetto Constraint in un testo leggibile per il giocatore.
    Volutamente un template semplice per tipo di clue: sufficiente per l'MVP,
    da arricchire quando aggiungeremo varietà lessicale."""
    if isinstance(clue, AttributeEquals):
        cell_label = _cell_label(clue.cell, cols)
        if clue.attribute == "types":
            return f"{cell_label} è di tipo {clue.value}."
        if clue.attribute == "color":
            return f"{cell_label} è di colore {clue.value}."
        if clue.attribute == "generation":
            return f"{cell_label} appartiene alla {clue.value}."
        if clue.attribute == "evolution_stage":
            return f"{cell_label} è allo stadio evolutivo {clue.value}."
        return f"{cell_label} ha {clue.attribute} = {clue.value}."

    if isinstance(clue, CompareStat):
        label_a = _cell_label(clue.cell_a, cols)
        label_b = _cell_label(clue.cell_b, cols)
        comparator = ">" if clue.greater else "<"
        return (
            f"{label_a} ({clue.stat}) {comparator} {label_b}"
        )

    if isinstance(clue, ExactCount):
        cells_label = ", ".join(_cell_label(c, cols) for c in clue.cells)
        return f"Esattamente {clue.count} Pokémon leggendari tra le celle {cells_label}."

    return "Clue non riconosciuta (manca un template in clue_to_text)."


def generate_puzzle(target_date: date, rows: int, cols: int, rng: random.Random) -> dict:
    pokedex = load_pokedex()
    n_cells = rows * cols

    if len(pokedex) < n_cells:
        raise PuzzleGenerationError(
            f"dataset troppo piccolo: servono almeno {n_cells} Pokémon con dati completi, trovati {len(pokedex)}"
        )

    candidate_names = rng.sample(list(pokedex.keys()), n_cells)
    solution = candidate_names[:]
    rng.shuffle(solution)  # solution[cella] = nome del pokemon in quella cella

    pool = build_clue_pool(solution, pokedex, rows, cols)
    chain = build_clue_chain(candidate_names, pool, pokedex, rng)
    active_clues = [clue for clue, _ in chain]

    n_solutions = count_solutions(
        [set(candidate_names) for _ in candidate_names], active_clues, pokedex, limit=2
    )
    if n_solutions != 1:
        raise PuzzleGenerationError(
            f"puzzle scartato: il backtracking trova {n_solutions} soluzioni valide (atteso 1)"
        )

    return {
        "date": target_date.isoformat(),
        "grid_size": [rows, cols],
        "candidates": [
            {"name": name, "id": pokedex[name]["id"]} for name in candidate_names
        ],
        "clues": [
            {
                "id": i,
                "text": clue_to_text(clue, pokedex, cols),
                "reveals_cells": [c + 1 for c in reveals],
            }
            for i, (clue, reveals) in enumerate(chain)
        ],
        "solution": solution,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera il puzzle Pokémon Clues del giorno")
    parser.add_argument("--date", type=str, default=date.today().isoformat())
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument(
        "--max-attempts", type=int, default=20,
        help="tentativi con seed diversi prima di rinunciare",
    )
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    seed_base = f"{target_date.isoformat()}-{args.rows}x{args.cols}"

    puzzle = None
    last_error = None
    for attempt in range(args.max_attempts):
        rng = random.Random(f"{seed_base}-{attempt}")
        try:
            puzzle = generate_puzzle(target_date, args.rows, args.cols, rng)
            break
        except PuzzleGenerationError as exc:
            last_error = exc
            print(f"tentativo {attempt}: {exc}")

    if puzzle is None:
        raise SystemExit(f"impossibile generare un puzzle valido dopo {args.max_attempts} tentativi: {last_error}")

    PUZZLES_DIR.mkdir(parents=True, exist_ok=True)
    output_file = PUZZLES_DIR / f"{target_date.isoformat()}.json"
    output_file.write_text(json.dumps(puzzle, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nPuzzle generato con {len(puzzle['clues'])} clue attive su {args.rows * args.cols} celle.")
    print(f"Scritto in {output_file}")


if __name__ == "__main__":
    main()
