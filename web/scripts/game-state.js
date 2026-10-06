export const t = (...args) => window.PokemonCluesI18n.t(...args);

export const game = {
  totalCells: 20,
  cells: [],
  solution: [],
  revealed: new Set(),
  statuses: [],
  stateToken: null,
  apiEnabled: false,
  date: "",
  won: false,
  moves: 0,
  timerSeconds: 0,
  timerInterval: null,
  timerRunning: false,
  soundEnabled: true,
  error: "",
};

export const dom = {
  grid: document.getElementById("puzzle-grid"),
  clues: document.getElementById("clues-list"),
  clueCount: document.getElementById("clue-count"),
  progressCount: document.getElementById("progress-count"),
  correctCount: document.getElementById("correct-count-text"),
  timer: document.getElementById("game-timer"),
  soundButton: document.getElementById("btn-sound"),
  soundIcon: document.getElementById("sound-icon"),
  victoryModal: document.getElementById("victory-modal"),
  victoryTime: document.getElementById("victory-time"),
  victoryMoves: document.getElementById("victory-moves"),
  victoryAccuracy: document.getElementById("victory-accuracy"),
  playAgain: document.getElementById("btn-play-again"),
  closeVictory: document.getElementById("btn-close-victory"),
  showVictory: document.getElementById("btn-show-victory"),
  confetti: document.getElementById("confetti-canvas"),
};

export const typeColors = {
  normal: "#aab09f", fire: "#ea7a3c", water: "#539ae2", electric: "#e5c531",
  grass: "#71c558", ice: "#70cbd4", fighting: "#cb5f48", poison: "#b468b7",
  ground: "#cc9f4f", flying: "#7da6de", psychic: "#e5709b", bug: "#94bc4a",
  rock: "#b2a061", ghost: "#846ab6", dragon: "#6a7baf", dark: "#736c75",
  steel: "#89a1b0", fairy: "#e397d1",
};

export const typeNames = {
  normal: { en: "Normal", it: "Normale" }, fire: { en: "Fire", it: "Fuoco" },
  water: { en: "Water", it: "Acqua" }, electric: { en: "Electric", it: "Elettro" },
  grass: { en: "Grass", it: "Erba" }, ice: { en: "Ice", it: "Ghiaccio" },
  fighting: { en: "Fighting", it: "Lotta" }, poison: { en: "Poison", it: "Veleno" },
  ground: { en: "Ground", it: "Terra" }, flying: { en: "Flying", it: "Volante" },
  psychic: { en: "Psychic", it: "Psico" }, bug: { en: "Bug", it: "Coleottero" },
  rock: { en: "Rock", it: "Roccia" }, ghost: { en: "Ghost", it: "Spettro" },
  dragon: { en: "Dragon", it: "Drago" }, dark: { en: "Dark", it: "Buio" },
  steel: { en: "Steel", it: "Acciaio" }, fairy: { en: "Fairy", it: "Folletto" },
};

export const spriteUrl = (id, shiny = false) =>
  `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${shiny ? "shiny/" : ""}${id}.png`;

export const formatName = (name = "") => name.replace(/-/g, " ");
