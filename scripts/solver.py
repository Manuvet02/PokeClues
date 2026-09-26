"""
solver.py

Motore di propagazione dei vincoli per il puzzle "Pokémon Clues": N Pokémon
candidati vanno assegnati a N celle di una griglia (un problema di
assegnazione/permutazione, come un Sudoku). Ogni cella parte con un dominio
= insieme di tutti i candidati ancora possibili; le clue e la regola
all-different (ogni candidato in una sola cella) restringono i domini finché
- idealmente - ogni cella resta con un solo candidato possibile.

Due usi distinti, volutamente separati:

1. solve_by_deduction()  -> SOLO propagazione logica, mai backtracking.
   È la funzione che generate_puzzle.py userà per verificare che un set di
   clue basti a risolvere tutto il puzzle senza mai dover indovinare
   (esattamente la garanzia che rende speciale Clues by Sam).

2. count_solutions()     -> backtracking completo con limite, usato SOLO in
   fase di validazione offline per controllare che un puzzle abbia
   un'unica soluzione globale (anche se la propagazione pura da sola
   non bastasse a dimostrarlo).

Il motore NON conosce nulla di specifico dei Pokémon: lavora su "pokedex",
un dizionario {nome_candidato: dati_curati}, e su una lista di oggetti
Constraint. Le clue testuali vere e proprie (generate_puzzle.py) sono
costruite SOPRA queste classi, non dentro di esse.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

Domain = set[str]
Domains = list[Domain]
Pokedex = dict[str, dict]


class ContradictionError(Exception):
    """Sollevata quando la propagazione svuota il dominio di una cella:
    significa che il set di clue corrente è inconsistente (non dovrebbe mai
    succedere su un puzzle costruito correttamente, ma il generatore deve
    poterlo rilevare per scartare i tentativi difettosi)."""


# ---------------------------------------------------------------------------
# Vincoli (ogni clue testuale del puzzle è costruita a partire da uno di questi)
# ---------------------------------------------------------------------------

class Constraint:
    def propagate(self, domains: Domains, pokedex: Pokedex) -> bool:
        """Riduce i domini coinvolti. Ritorna True se qualcosa è cambiato."""
        raise NotImplementedError

    def is_satisfied(self, assignment: dict[int, str], pokedex: Pokedex) -> bool:
        """Verifica il vincolo su un'assegnazione COMPLETA (usato solo dal
        backtracking di verifica, mai durante il gioco)."""
        raise NotImplementedError


class AttributeEquals(Constraint):
    """Es: il Pokémon nella cella X è di tipo 'dragon'."""

    def __init__(self, cell: int, attribute: str, value):
        self.cell = cell
        self.attribute = attribute
        self.value = value

    def propagate(self, domains, pokedex):
        domain = domains[self.cell]
        filtered = {c for c in domain if self.value in _attr(pokedex[c], self.attribute)}
        if filtered != domain:
            domains[self.cell] = filtered
            return True
        return False

    def is_satisfied(self, assignment, pokedex):
        return self.value in _attr(pokedex[assignment[self.cell]], self.attribute)


class AttributeNotEquals(Constraint):
    """Es: il Pokémon nella cella X NON ha l'abilità 'levitate'."""

    def __init__(self, cell: int, attribute: str, value):
        self.cell = cell
        self.attribute = attribute
        self.value = value

    def propagate(self, domains, pokedex):
        domain = domains[self.cell]
        filtered = {c for c in domain if self.value not in _attr(pokedex[c], self.attribute)}
        if filtered != domain:
            domains[self.cell] = filtered
            return True
        return False

    def is_satisfied(self, assignment, pokedex):
        return self.value not in _attr(pokedex[assignment[self.cell]], self.attribute)


class CompareStat(Constraint):
    """Es: la Velocità del Pokémon in cell_a è maggiore di quella in cell_b."""

    def __init__(self, cell_a: int, cell_b: int, stat: str, greater: bool = True):
        self.cell_a = cell_a
        self.cell_b = cell_b
        self.stat = stat
        self.greater = greater  # True: a > b ; False: a < b

    def _value(self, pokedex, name):
        return pokedex[name]["base_stats"][self.stat]

    def propagate(self, domains, pokedex):
        domain_a, domain_b = domains[self.cell_a], domains[self.cell_b]
        values_a = {c: self._value(pokedex, c) for c in domain_a}
        values_b = {c: self._value(pokedex, c) for c in domain_b}

        if self.greater:
            threshold_low = min(values_b.values())
            threshold_high = max(values_a.values())
            new_a = {c for c, v in values_a.items() if v > threshold_low}
            new_b = {c for c, v in values_b.items() if v < threshold_high}
        else:
            threshold_high = max(values_b.values())
            threshold_low = min(values_a.values())
            new_a = {c for c, v in values_a.items() if v < threshold_high}
            new_b = {c for c, v in values_b.items() if v > threshold_low}

        changed = False
        if new_a != domain_a:
            domains[self.cell_a] = new_a
            changed = True
        if new_b != domain_b:
            domains[self.cell_b] = new_b
            changed = True
        return changed

    def is_satisfied(self, assignment, pokedex):
        value_a = self._value(pokedex, assignment[self.cell_a])
        value_b = self._value(pokedex, assignment[self.cell_b])
        return value_a > value_b if self.greater else value_a < value_b


class PairExclusion(Constraint):
    """Es (adiacenza): due celle non possono avere ENTRAMBE una proprietà vera
    ("il tipo Drago non è adiacente a chi ha Levitazione"). `predicate` è una
    funzione che riceve i dati curati di un Pokémon e ritorna un bool."""

    def __init__(self, cell_a: int, cell_b: int, predicate: Callable[[dict], bool], description: str = ""):
        self.cell_a = cell_a
        self.cell_b = cell_b
        self.predicate = predicate
        self.description = description  # utile per debug/log, non usato in logica

    def _all_true(self, domain, pokedex):
        return all(self.predicate(pokedex[c]) for c in domain)

    def propagate(self, domains, pokedex):
        domain_a, domain_b = domains[self.cell_a], domains[self.cell_b]
        changed = False

        if self._all_true(domain_a, pokedex):
            new_b = {c for c in domain_b if not self.predicate(pokedex[c])}
            if new_b != domain_b:
                domains[self.cell_b] = new_b
                changed = True

        if self._all_true(domain_b, pokedex):
            new_a = {c for c in domain_a if not self.predicate(pokedex[c])}
            if new_a != domain_a:
                domains[self.cell_a] = new_a
                changed = True

        return changed

    def is_satisfied(self, assignment, pokedex):
        a_true = self.predicate(pokedex[assignment[self.cell_a]])
        b_true = self.predicate(pokedex[assignment[self.cell_b]])
        return not (a_true and b_true)


class ExactCount(Constraint):
    """Es (come in Clues by Sam): "esattamente K celle di questo gruppo
    hanno la proprietà P" (es. K Pokémon leggendari in una riga)."""

    def __init__(self, cells: list[int], predicate: Callable[[dict], bool], count: int, description: str = ""):
        self.cells = cells
        self.predicate = predicate
        self.count = count
        self.description = description

    def _classify(self, domains, pokedex):
        forced_true, forced_false, ambiguous = [], [], []
        for cell in self.cells:
            domain = domains[cell]
            all_true = all(self.predicate(pokedex[c]) for c in domain)
            all_false = all(not self.predicate(pokedex[c]) for c in domain)
            if all_true:
                forced_true.append(cell)
            elif all_false:
                forced_false.append(cell)
            else:
                ambiguous.append(cell)
        return forced_true, forced_false, ambiguous

    def propagate(self, domains, pokedex):
        forced_true, forced_false, ambiguous = self._classify(domains, pokedex)
        changed = False

        if len(forced_true) == self.count:
            # tutte le altre celle ambigue devono essere false
            for cell in ambiguous:
                new_domain = {c for c in domains[cell] if not self.predicate(pokedex[c])}
                if new_domain != domains[cell]:
                    domains[cell] = new_domain
                    changed = True

        remaining_true_needed = self.count - len(forced_true)
        if remaining_true_needed == len(ambiguous) and remaining_true_needed > 0:
            # tutte le celle ambigue rimaste devono essere vere per raggiungere il conteggio
            for cell in ambiguous:
                new_domain = {c for c in domains[cell] if self.predicate(pokedex[c])}
                if new_domain != domains[cell]:
                    domains[cell] = new_domain
                    changed = True

        return changed

    def is_satisfied(self, assignment, pokedex):
        total = sum(1 for cell in self.cells if self.predicate(pokedex[assignment[cell]]))
        return total == self.count


def _attr(entry: dict, attribute: str):
    """Normalizza l'accesso: attributi lista (types, abilities...) o scalari
    (color, generation...) si comportano allo stesso modo con l'operatore 'in'."""
    value = entry.get(attribute)
    if isinstance(value, list):
        return value
    return [value]


# ---------------------------------------------------------------------------
# Regola implicita di "all-different" (è un problema di permutazione)
# ---------------------------------------------------------------------------

def _apply_naked_single_elimination(domains: Domains) -> bool:
    """Se una cella ha un solo candidato possibile, quel candidato non può
    più comparire nel dominio di nessun'altra cella."""
    singles = {next(iter(d)) for d in domains if len(d) == 1}
    changed = False
    for i, domain in enumerate(domains):
        if len(domain) > 1:
            reduced = domain - singles
            if reduced != domain:
                if not reduced:
                    raise ContradictionError(f"cella {i}: nessun candidato valido rimasto")
                domains[i] = reduced
                changed = True
    return changed


def _apply_hidden_singles(domains: Domains) -> bool:
    """Se un candidato compare nel dominio di una sola cella (fra tutte),
    quella cella deve essere per forza quel candidato."""
    occurrences: Counter[str] = Counter()
    location: dict[str, int] = {}
    for i, domain in enumerate(domains):
        for candidate in domain:
            occurrences[candidate] += 1
            location[candidate] = i

    changed = False
    for candidate, count in occurrences.items():
        if count == 1:
            i = location[candidate]
            if len(domains[i]) > 1:
                domains[i] = {candidate}
                changed = True
    return changed


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def _raise_if_any_domain_empty(domains: Domains) -> None:
    for i, domain in enumerate(domains):
        if not domain:
            raise ContradictionError(f"cella {i}: dominio svuotato dalla propagazione")


def propagate_all(domains: Domains, constraints: list[Constraint], pokedex: Pokedex, max_iterations: int = 1000) -> None:
    """Applica tutte le clue e la regola all-different ripetutamente fino a
    quando i domini smettono di cambiare (fixpoint). Modifica `domains` in
    place. Solleva ContradictionError se un set di clue è inconsistente
    (anche quando la contraddizione nasce da una singola constraint custom,
    non solo dalla naked-single elimination)."""
    for _ in range(max_iterations):
        changed = False
        for constraint in constraints:
            if constraint.propagate(domains, pokedex):
                changed = True
        _raise_if_any_domain_empty(domains)
        if _apply_naked_single_elimination(domains):
            changed = True
        if _apply_hidden_singles(domains):
            changed = True
        _raise_if_any_domain_empty(domains)
        if not changed:
            return
    raise RuntimeError("propagazione non convergente: possibile bug in una constraint")


def solve_by_deduction(candidate_names: list[str], constraints: list[Constraint], pokedex: Pokedex) -> tuple[Domains, bool]:
    """SOLO propagazione logica, nessun backtracking. Usata dal generatore
    per controllare se un set di clue basta a risolvere tutto il puzzle
    senza dover mai tirare a indovinare.

    NOTA IMPORTANTE: a differenza della versione precedente, qui
    ContradictionError NON viene più catturata: se le clue passate sono
    tutte vere rispetto a un'unica soluzione reale (come sono sempre quelle
    generate da generate_puzzle.py), una contraddizione non può mai
    verificarsi a meno che una constraint non abbia un bug e rimuova per
    errore il candidato corretto. In quel caso vogliamo un crash rumoroso
    e diagnosticabile, non un silenzioso 'solved=False' indistinguibile
    da un normale 'servono più clue'."""
    domains: Domains = [set(candidate_names) for _ in candidate_names]
    propagate_all(domains, constraints, pokedex)
    return domains, all(len(d) == 1 for d in domains)


def count_solutions(domains: Domains, constraints: list[Constraint], pokedex: Pokedex, limit: int = 2) -> int:
    """Backtracking completo con limite, usato SOLO in fase di validazione
    offline per confermare che un puzzle abbia un'unica soluzione globale.
    Non va mai chiamata durante il gioco vero e proprio."""
    domains = [set(d) for d in domains]
    try:
        propagate_all(domains, constraints, pokedex)
    except ContradictionError:
        return 0

    if all(len(d) == 1 for d in domains):
        assignment = {i: next(iter(d)) for i, d in enumerate(domains)}
        is_valid = len(set(assignment.values())) == len(assignment) and all(
            c.is_satisfied(assignment, pokedex) for c in constraints
        )
        return 1 if is_valid else 0

    branch_cell = min((i for i, d in enumerate(domains) if len(d) > 1), key=lambda i: len(domains[i]))

    found = 0
    for candidate in domains[branch_cell]:
        branch_domains = [set(d) for d in domains]
        branch_domains[branch_cell] = {candidate}
        found += count_solutions(branch_domains, constraints, pokedex, limit=limit - found)
        if found >= limit:
            break
    return found
