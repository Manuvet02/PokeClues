const encoder = new TextEncoder();

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

function base64UrlEncode(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(value) {
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64 + "=".repeat((4 - (base64.length % 4)) % 4));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function signingKey(secret) {
  return crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

async function signState(state, secret) {
  const payload = base64UrlEncode(encoder.encode(JSON.stringify(state)));
  const key = await signingKey(secret);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(payload));
  return `${payload}.${base64UrlEncode(new Uint8Array(signature))}`;
}

async function readState(token, date, secret) {
  if (!token || !secret) return null;
  const [payload, signature, extra] = token.split(".");
  if (!payload || !signature || extra) return null;
  try {
    const key = await signingKey(secret);
    const valid = await crypto.subtle.verify(
      "HMAC",
      key,
      base64UrlDecode(signature),
      encoder.encode(payload),
    );
    if (!valid) return null;
    const state = JSON.parse(new TextDecoder().decode(base64UrlDecode(payload)));
    if (state.date !== date || !state.solved || typeof state.solved !== "object") return null;
    return state;
  } catch {
    return null;
  }
}

async function loadPuzzle(env, date) {
  const raw = await env.PUZZLES_PRIVATE.get(`shiny:${date}`);
  return raw ? JSON.parse(raw) : null;
}

function startState(puzzle) {
  const startIndex = puzzle.cells.findIndex((cell) => cell.label === puzzle.start_cell);
  if (startIndex < 0) return null;
  const status = puzzle.start_status === "shiny" ? 1 : 0;
  return { date: puzzle.date, solved: { [startIndex]: status } };
}

function clueData(puzzle, solved) {
  return Object.entries(solved).map(([index, status]) => {
    const cell = puzzle.cells[Number(index)];
    return {
      index: Number(index),
      status: status === 1 ? "shiny" : "regular",
      clue: cell.clue,
      logic: cell.logic,
    };
  });
}

function deduce(puzzle, solved) {
  const state = new Array(puzzle.cells.length).fill(null);
  for (const [index, value] of Object.entries(solved)) {
    const cellIndex = Number(index);
    if (!Number.isInteger(cellIndex) || cellIndex < 0 || cellIndex >= state.length || ![0, 1].includes(value)) {
      throw new Error("Invalid signed game state");
    }
    state[cellIndex] = value;
  }

  const constraints = Object.entries(solved).flatMap(([index]) =>
    puzzle.cells[Number(index)].logic || [],
  );
  let changed = true;
  while (changed) {
    changed = false;
    for (const constraint of constraints) {
      const weights = Object.entries(constraint.weights || {}).map(([cell, weight]) => [
        Number(cell), Number(weight),
      ]);
      let maxSum = 0;
      for (const [cell, weight] of weights) {
        if (weight > 0 && state[cell] !== 0) maxSum += weight;
        else if (weight < 0 && state[cell] === 1) maxSum += weight;
      }
      const slack = maxSum - Number(constraint.bound);
      if (slack < 0) throw new Error("Puzzle constraints contradict the signed state");
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

function getDate(request) {
  const date = new URL(request.url).searchParams.get("date");
  return /^\d{4}-\d{2}-\d{2}$/.test(date || "") ? date : null;
}

export async function onRequestGet({ request, env }) {
  const date = getDate(request);
  if (!date) return json({ error: "invalid_date" }, 400);
  if (!env.PUZZLES_PRIVATE || !env.GAME_STATE_SECRET) {
    return json({ error: "server_not_configured" }, 503);
  }

  const puzzle = await loadPuzzle(env, date);
  if (!puzzle) return json({ error: "puzzle_not_found" }, 404);

  const token = new URL(request.url).searchParams.get("state");
  let state = token ? await readState(token, date, env.GAME_STATE_SECRET) : null;
  if (token && !state) return json({ error: "invalid_state" }, 400);
  if (!state) state = startState(puzzle);
  if (!state) return json({ error: "invalid_puzzle" }, 500);

  return json({
    date: puzzle.date,
    grid_size: puzzle.grid_size,
    start_cell: puzzle.start_cell,
    cells: puzzle.cells.map(({ label, pokemon, id }) => ({ label, pokemon, id })),
    revealed: clueData(puzzle, state.solved),
    stateToken: await signState(state, env.GAME_STATE_SECRET),
  });
}

export async function onRequestPost({ request, env }) {
  if (!env.PUZZLES_PRIVATE || !env.GAME_STATE_SECRET) {
    return json({ error: "server_not_configured" }, 503);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }
  const { date, index, status, stateToken } = body;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "") || !Number.isInteger(index) ||
      !["regular", "shiny"].includes(status)) {
    return json({ error: "invalid_request" }, 400);
  }

  const puzzle = await loadPuzzle(env, date);
  if (!puzzle) return json({ error: "puzzle_not_found" }, 404);
  const state = await readState(stateToken, date, env.GAME_STATE_SECRET);
  if (!state) return json({ error: "invalid_state" }, 400);
  if (index < 0 || index >= puzzle.cells.length) return json({ error: "invalid_cell" }, 400);
  if (Object.hasOwn(state.solved, index)) return json({ error: "already_solved" }, 409);

  let deduced;
  try {
    deduced = deduce(puzzle, state.solved);
  } catch {
    return json({ error: "invalid_puzzle_state" }, 500);
  }
  if (deduced[index] === null) return json({ error: "not_deducible" }, 409);
  const value = status === "shiny" ? 1 : 0;
  if (deduced[index] !== value) return json({ error: "incorrect" }, 422);

  state.solved[index] = value;
  const cell = puzzle.cells[index];
  return json({
    index,
    status,
    clue: cell.clue,
    logic: cell.logic,
    stateToken: await signState(state, env.GAME_STATE_SECRET),
  });
}
