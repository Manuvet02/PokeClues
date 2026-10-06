import { game, dom, t } from "./game-state.js";
import {
  celebrate,
  formatTime,
  playVictoryFanfare,
  resetTimer,
  stopTimer,
  toggleSound,
} from "./feedback.js";
import { loadPuzzle, submitGuess } from "./puzzle.js";
import { renderGame } from "./render.js";

function render() {
  renderGame((index, status, cell) =>
    submitGuess(index, status, cell, { render, checkVictory }),
  );
}

function checkVictory() {
  if (
    !game.cells.length ||
    game.revealed.size !== game.cells.length ||
    game.won
  )
    return;
  game.won = true;
  stopTimer();
  dom.victoryTime.textContent = formatTime(game.timerSeconds);
  dom.victoryMoves.textContent = game.moves;
  dom.victoryAccuracy.textContent = `${game.totalCells} / ${game.totalCells}`;
  dom.victoryModal.classList.remove("hidden");
  dom.victoryModal.setAttribute("aria-hidden", "false");
  dom.showVictory.classList.add("hidden");
  celebrate();
  playVictoryFanfare();
}

function hideVictory() {
  dom.victoryModal.classList.add("hidden");
  dom.victoryModal.setAttribute("aria-hidden", "true");
  if (game.won) dom.showVictory.classList.remove("hidden");
}

async function replay() {
  dom.victoryModal.classList.add("hidden");
  dom.victoryModal.setAttribute("aria-hidden", "true");
  dom.showVictory.classList.add("hidden");
  game.won = false;
  game.moves = 0;
  game.stateToken = null;
  resetTimer();
  if (game.date) localStorage.removeItem(`pokemon-clues-state-${game.date}`);
  await loadPuzzle();
  render();
}

dom.soundButton.addEventListener("click", toggleSound);
dom.playAgain.addEventListener("click", replay);
dom.closeVictory.addEventListener("click", hideVictory);
dom.showVictory.addEventListener("click", () => {
  dom.victoryModal.classList.remove("hidden");
  dom.victoryModal.setAttribute("aria-hidden", "false");
  dom.showVictory.classList.add("hidden");
});

document.addEventListener("pokemon-clues-language-changed", () => {
  dom.soundButton.title = t(game.soundEnabled ? "soundOn" : "soundOff");
  render();
});

dom.soundButton.title = t("soundOn");
await loadPuzzle();
render();
checkVictory();
