"""
shiny_solver.py

Solver per la variante "regular / shiny" (stile Clues by Sam): ogni cella ha
un Pokémon visibile e una sola incognita binaria, 0 = regular, 1 = shiny.

Tutte le clue si riducono a disuguaglianze lineari su variabili 0/1:
    sum(peso_i * stato_i) >= bound
Per una singola disuguaglianza di questo tipo la propagazione qui sotto è
esatta (bound-consistency), quindi non servono classi di vincolo diverse per
conteggi, confronti e relazioni fra coppie: cambia solo come si costruiscono.

Stato di una cella: None (ignoto), 0 (regular), 1 (shiny).
"""

from __future__ import annotations

State = list  # list[int | None]


class ContradictionError(Exception):
    """Le clue attive sono incompatibili con lo stato corrente. Con clue tutte
    vere rispetto a una soluzione reale non deve mai succedere: se succede,
    c'è un bug nella costruzione della clue."""


class Linear:
    """sum(weights[c] * stato[c]) >= bound"""

    def __init__(self, weights: dict[int, int], bound: int):
        self.weights = weights
        self.bound = bound

    def propagate(self, state: State) -> bool:
        max_sum = 0
        for cell, w in self.weights.items():
            s = state[cell]
            if w > 0:
                max_sum += w if s != 0 else 0
            else:
                max_sum += w if s == 1 else 0
        slack = max_sum - self.bound
        if slack < 0:
            raise ContradictionError("vincolo non soddisfacibile")

        changed = False
        for cell, w in self.weights.items():
            if state[cell] is None:
                if w > 0 and w > slack:
                    state[cell] = 1  # se fosse regular, il massimo scenderebbe sotto il bound
                    changed = True
                elif w < 0 and -w > slack:
                    state[cell] = 0
                    changed = True
        return changed

    def holds(self, truth: list[int]) -> bool:
        return sum(w * truth[c] for c, w in self.weights.items()) >= self.bound


class Clue:
    """Una clue = testo per il giocatore + una o più disuguaglianze lineari."""

    def __init__(self, kind: str, linears: list[Linear], text: str, cells: set[int]):
        self.kind = kind
        self.linears = linears
        self.text = text
        self.cells = cells  # celle a cui la clue si riferisce

    def holds(self, truth: list[int]) -> bool:
        return all(l.holds(truth) for l in self.linears)


# --- costruttori di clue -----------------------------------------------------

def count_clue(cells: list[int], k: int, text: str) -> Clue:
    """Esattamente k shiny fra `cells`."""
    up = Linear({c: 1 for c in cells}, k)
    down = Linear({c: -1 for c in cells}, -k)
    return Clue("count", [up, down], text, set(cells))


def compare_clue(cells_a: list[int], cells_b: list[int], text: str) -> Clue:
    """Più shiny in A che in B (le celle in comune si annullano)."""
    weights: dict[int, int] = {}
    for c in cells_a:
        weights[c] = weights.get(c, 0) + 1
    for c in cells_b:
        weights[c] = weights.get(c, 0) - 1
    weights = {c: w for c, w in weights.items() if w != 0}
    return Clue("compare", [Linear(weights, 1)], text, set(cells_a) | set(cells_b))


def same_clue(a: int, b: int, text: str) -> Clue:
    return Clue("same", [Linear({a: 1, b: -1}, 0), Linear({a: -1, b: 1}, 0)], text, {a, b})


def different_clue(a: int, b: int, text: str) -> Clue:
    return Clue("different", [Linear({a: 1, b: 1}, 1), Linear({a: -1, b: -1}, -1)], text, {a, b})


# --- propagazione e verifica -------------------------------------------------

def propagate_all(state: State, clues: list[Clue]) -> None:
    linears = [l for clue in clues for l in clue.linears]
    changed = True
    while changed:
        changed = False
        for l in linears:
            if l.propagate(state):
                changed = True


def count_solutions(state: State, clues: list[Clue], limit: int = 2) -> int:
    """Backtracking con propagazione, solo per validare l'unicità offline."""
    state = list(state)
    try:
        propagate_all(state, clues)
    except ContradictionError:
        return 0
    if all(s is not None for s in state):
        return 1
    cell = next(i for i, s in enumerate(state) if s is None)
    found = 0
    for value in (0, 1):
        branch = list(state)
        branch[cell] = value
        found += count_solutions(branch, clues, limit - found)
        if found >= limit:
            break
    return found


def simulate_player(n_cells: int, start_cell: int, start_value: int, clue_of_cell: dict[int, Clue],
                    truth: list[int]) -> tuple[bool, dict[int, int | None]]:
    """Simula un giocatore perfetto: vede solo le clue delle celle già risolte
    e deduce tutto ciò che è forzato. Ritorna (risolto?, unlocked_by), dove
    unlocked_by[cella] è la cella la cui clue ha fatto scattare la deduzione
    (None per la cella iniziale). È questo il vero test di 'nessun tentativo
    a caso': ogni cella deve essere raggiungibile con le sole clue già viste."""
    state: State = [None] * n_cells
    state[start_cell] = start_value
    resolved_order = [start_cell]
    unlocked_by: dict[int, int | None] = {start_cell: None}
    visible: list[Clue] = []
    queue = [start_cell]

    while queue:
        owner = queue.pop(0)
        visible.append(clue_of_cell[owner])
        before = [s is not None for s in state]
        propagate_all(state, visible)
        for cell in range(n_cells):
            if state[cell] is not None and not before[cell]:
                unlocked_by[cell] = owner
                resolved_order.append(cell)
                queue.append(cell)

    solved = all(s is not None for s in state) and all(state[i] == truth[i] for i in range(n_cells))
    return solved, unlocked_by

