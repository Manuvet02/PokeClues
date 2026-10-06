import { game, spriteUrl } from "./game-state.js";
import {
  playCorrectSound,
  playIncorrectSound,
  startTimer,
} from "./feedback.js";

function getPuzzleDate() {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(
    parts.map(({ type, value }) => [type, value]),
  );
  return `${values.year}-${values.month}-${values.day}`;
}

export async function loadPuzzle() {
  game.error = "";
  game.apiEnabled = false;
  game.date = getPuzzleDate();
  let data = null;
  let response;

  try {
    const savedToken = localStorage.getItem(`pokemon-clues-state-${game.date}`);
    const tokenQuery = savedToken
      ? `&state=${encodeURIComponent(savedToken)}`
      : "";
    response = await fetch(`/api/puzzle?date=${game.date}${tokenQuery}`);
    if (response.ok) {
      data = await response.json();
      game.apiEnabled = true;
    } else if (savedToken && response.status === 400) {
      localStorage.removeItem(`pokemon-clues-state-${game.date}`);
      response = await fetch(`/api/puzzle?date=${game.date}`);
      if (response.ok) {
        data = await response.json();
        game.apiEnabled = true;
      }
    }

    // Static answer data is used only for local development previews.
    if (
      !data &&
      ["localhost", "127.0.0.1", "192.168.1.9"].includes(location.hostname)
    ) {
      const localResponse = await fetch(`../puzzles/shiny-${game.date}.json`);
      if (localResponse.ok) data = await localResponse.json();
    }
    if (!data || !Array.isArray(data.cells)) {
      throw new Error(
        `Puzzle API returned ${response?.status ?? "no response"}`,
      );
    }

    game.cells = data.cells;
    game.totalCells = game.cells.length;
    game.solution = data.solution || new Array(game.totalCells).fill(null);
    game.stateToken = data.stateToken || null;
    game.revealed = new Set();
    game.statuses = new Array(game.totalCells).fill(null);

    if (Array.isArray(data.revealed)) {
      data.revealed.forEach(({ index, status, clue, logic }) => {
        game.revealed.add(index);
        game.statuses[index] = status === "shiny" ? 1 : 0;
        game.cells[index].clue = clue;
        game.cells[index].logic = logic;
      });
    } else {
      game.cells.forEach((cell, index) => {
        if (
          cell.label === data.start_cell &&
          game.solution[index] === data.start_status
        ) {
          game.revealed.add(index);
          game.statuses[index] = data.start_status === "shiny" ? 1 : 0;
        }
      });
    }
    if (game.stateToken)
      localStorage.setItem(`pokemon-clues-state-${game.date}`, game.stateToken);
  } catch (error) {
    console.warn("Could not load the daily puzzle:", error);
    game.cells = [];
    game.solution = [];
    game.revealed = new Set();
    game.statuses = [];
    game.error = true;
  }
}

export function getDeducedStatuses() {
  const state = new Array(game.cells.length).fill(null);
  game.revealed.forEach((index) => {
    state[index] =
      game.statuses[index] ?? (game.solution[index] === "shiny" ? 1 : 0);
  });
  const constraints = [];
  game.cells.forEach((cell, index) => {
    if (game.revealed.has(index))
      (cell.logic || []).forEach((constraint) => constraints.push(constraint));
  });

  let changed = true;
  while (changed) {
    changed = false;
    for (const constraint of constraints) {
      const weights = Object.entries(constraint.weights || {}).map(
        ([cell, weight]) => [Number(cell), Number(weight)],
      );
      let maxSum = 0;
      for (const [cell, weight] of weights) {
        if (weight > 0 && state[cell] !== 0) maxSum += weight;
        else if (weight < 0 && state[cell] === 1) maxSum += weight;
      }
      const slack = maxSum - constraint.bound;
      if (slack < 0) return state;
      for (const [cell, weight] of weights) {
        if (state[cell] !== null) continue;
        if (weight > 0 && weight > slack) {
          state[cell] = 1;
          changed = true;
        } else if (weight < 0 && -weight > slack) {
          state[cell] = 0;
          changed = true;
        }
      }
    }
  }
  return state;
}

export async function submitGuess(
  index,
  status,
  cell,
  { render, checkVictory },
) {
  if (game.revealed.has(index)) return;
  const forcedStatus = getDeducedStatuses()[index];
  const selectedStatus = status === "shiny" ? 1 : 0;
  if (forcedStatus == null) {
    cell.classList.remove("deduction-pending");
    void cell.offsetWidth;
    cell.classList.add("deduction-pending");
    return;
  }
  if (forcedStatus !== selectedStatus) {
    playIncorrectSound();
    cell.classList.remove("guess-wrong");
    void cell.offsetWidth;
    cell.classList.add("guess-wrong");
    return;
  }

  startTimer();
  game.moves++;
  if (!game.apiEnabled) {
    game.revealed.add(index);
    game.statuses[index] = selectedStatus;
    playCorrectSound();
    render();
    checkVictory();
    return;
  }

  const buttons = [...cell.querySelectorAll("button")];
  buttons.forEach((button) => {
    button.disabled = true;
  });
  try {
    const response = await fetch("/api/puzzle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        date: game.date,
        index,
        status,
        stateToken: game.stateToken,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      playIncorrectSound();
      cell.classList.remove("guess-wrong");
      void cell.offsetWidth;
      cell.classList.add("guess-wrong");
      return;
    }
    game.stateToken = result.stateToken;
    localStorage.setItem(`pokemon-clues-state-${game.date}`, result.stateToken);
    game.statuses[index] = result.status === "shiny" ? 1 : 0;
    game.cells[index].clue = result.clue;
    game.cells[index].logic = result.logic;
    game.revealed.add(index);
    playCorrectSound();
    render();
    checkVictory();
  } catch (error) {
    console.error("Could not verify answer:", error);
    cell.classList.remove("guess-wrong");
    void cell.offsetWidth;
    cell.classList.add("guess-wrong");
  } finally {
    buttons.forEach((button) => {
      button.disabled = game.revealed.has(index);
    });
  }
}
