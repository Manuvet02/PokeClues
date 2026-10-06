import { game, dom, t, typeColors, typeNames, spriteUrl, formatName } from "./game-state.js";

function renderGrid(onGuess) {
  dom.grid.innerHTML = "";
  game.cells.forEach((pokemon, index) => {
    const solved = game.revealed.has(index);
    const cell = document.createElement("article");
    cell.className = `grid-cell shiny-cell${solved ? " is-correct" : ""}`;
    cell.dataset.index = index;

    const label = document.createElement("span");
    label.className = "cell-label";
    label.textContent = pokemon.label;
    cell.appendChild(label);

    const cardName = document.createElement("div");
    cardName.className = "shiny-card-name";
    cardName.textContent = formatName(pokemon.pokemon);
    const typeList = document.createElement("div");
    typeList.className = "shiny-type-list";
    if (solved) (pokemon.types || []).forEach((type) => {
      const badge = document.createElement("span");
      badge.className = "shiny-type-badge";
      badge.textContent = typeNames[type]?.[window.PokemonCluesI18n.locale] || formatName(type);
      badge.style.setProperty("--type-color", typeColors[type] || "#667085");
      typeList.appendChild(badge);
    });
    const heading = document.createElement("div");
    heading.className = "shiny-card-heading";
    heading.append(cardName, typeList);
    cell.appendChild(heading);

    const main = document.createElement("div");
    main.className = "shiny-card-main";
    const visual = document.createElement("div");
    visual.className = "shiny-pokemon-visual";
    if (solved) {
      const image = document.createElement("img");
      image.className = "cell-sprite";
      image.src = spriteUrl(pokemon.id, game.statuses[index] === 1);
      image.alt = formatName(pokemon.pokemon);
      image.loading = "lazy";
      visual.appendChild(image);
    } else {
      const silhouette = document.createElement("span");
      silhouette.className = "shiny-silhouette";
      silhouette.setAttribute("aria-hidden", "true");
      silhouette.textContent = "?";
      visual.appendChild(silhouette);
    }
    main.appendChild(visual);

    const clue = document.createElement("p");
    clue.className = `cell-clue${solved ? "" : " clue-locked"}`;
    clue.textContent = solved ? pokemon.clue || "" : t("lockedClue");
    if (!solved) cell.classList.add("clue-locked-cell");
    main.appendChild(clue);
    cell.appendChild(main);

    const choices = document.createElement("div");
    choices.className = "shiny-choices";
    ["regular", "shiny"].forEach((status) => {
      const button = document.createElement("button");
      button.type = "button";
      const selected = solved && (game.statuses[index] === (status === "shiny" ? 1 : 0) || game.solution[index] === status);
      button.className = `shiny-choice${selected ? " selected" : ""}`;
      button.textContent = t(status);
      button.disabled = solved;
      button.setAttribute("aria-pressed", String(selected));
      button.addEventListener("click", () => onGuess(index, status, cell));
      choices.appendChild(button);
    });
    cell.appendChild(choices);
    dom.grid.appendChild(cell);
  });
}

function renderClues() {
  dom.clues.innerHTML = "";
  if (game.error) {
    const message = document.createElement("p");
    message.className = "clue-text";
    message.textContent = t("puzzleLoadError");
    dom.clues.appendChild(message);
  }
}

function updateCounts() {
  dom.correctCount.textContent = `${game.revealed.size} / ${game.totalCells}`;
  dom.clueCount.textContent = t("clueCount", game.totalCells);
  dom.progressCount.textContent = t("undiscovered", Math.max(0, game.totalCells - game.revealed.size));
}

export function renderGame(onGuess) {
  renderGrid(onGuess);
  renderClues();
  updateCounts();
}
