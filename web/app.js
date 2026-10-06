/* ========================================
   POKÉMON CLUES - Application Logic
   Drag & Drop grid with sprite pool,
   real-time JSON position validation,
   and victory screen celebration
   ======================================== */

(() => {
  "use strict";

  // ---- Configuration ----
  let GRID_ROWS = 5;
  let GRID_COLS = 4;
  let TOTAL_CELLS = GRID_ROWS * GRID_COLS;

  // Row letters for cell labels (A1, B1, C1, ...)
  const ROW_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"];

  // ---- State ----
  let gridState = new Array(TOTAL_CELLS).fill(null); // { name, id, spriteUrl } | null
  let poolItems = []; // candidates not yet placed
  let allCandidates = []; // full list of candidates
  let clues = [];
  let solution = []; // Pokémon names in correct cell order from JSON
  let shinyPuzzleCells = null;
  let revealedCells = new Set();
  let shinyStatuses = [];
  let shinyStateToken = null;
  let shinyApiEnabled = false;
  let shinyPuzzleDate = "";
  const pokemonTypesRequests = new Map();
  let isGameWon = false;
  let movesCount = 0;
  let timerSeconds = 0;
  let timerInterval = null;
  let isTimerRunning = false;
  let soundEnabled = true;

  // ---- DOM References ----
  const gridEl = document.getElementById("puzzle-grid");
  const poolEl = document.getElementById("sprite-pool");
  const cluesListEl = document.getElementById("clues-list");
  const clueCountEl = document.getElementById("clue-count");
  const poolCountEl = document.getElementById("pool-count");
  const correctCountTextEl = document.getElementById("correct-count-text");
  const gameTimerEl = document.getElementById("game-timer");
  const btnClear = document.getElementById("btn-clear");
  const btnShuffle = document.getElementById("btn-shuffle");
  const btnSound = document.getElementById("btn-sound");
  const soundIcon = document.getElementById("sound-icon");

  // Victory Modal Elements
  const victoryModalEl = document.getElementById("victory-modal");
  const victoryTimeEl = document.getElementById("victory-time");
  const victoryMovesEl = document.getElementById("victory-moves");
  const victoryAccuracyEl = document.getElementById("victory-accuracy");
  const btnPlayAgain = document.getElementById("btn-play-again");
  const btnCloseVictory = document.getElementById("btn-close-victory");
  const btnShowVictory = document.getElementById("btn-show-victory");
  const confettiCanvas = document.getElementById("confetti-canvas");

  // ---- Sprite URL Helper ----
  function getSpriteUrl(pokemonId) {
    return `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/${pokemonId}.png`;
  }

  const pokemonTypeColors = {
    normal: "#a8a77a", fire: "#ee8130", water: "#6390f0", electric: "#f7d02c",
    grass: "#7ac74c", ice: "#96d9d6", fighting: "#c22e28", poison: "#a33ea1",
    ground: "#e2bf65", flying: "#a98ff3", psychic: "#f95587", bug: "#a6b91a",
    rock: "#b6a136", ghost: "#735797", dragon: "#6f35fc", dark: "#705746",
    steel: "#b7b7ce", fairy: "#d685ad",
  };

  const pokemonTypeNames = {
    normal: "Normale", fire: "Fuoco", water: "Acqua", electric: "Elettro",
    grass: "Erba", ice: "Ghiaccio", fighting: "Lotta", poison: "Veleno",
    ground: "Terra", flying: "Volante", psychic: "Psico", bug: "Coleottero",
    rock: "Roccia", ghost: "Spettro", dragon: "Drago", dark: "Buio",
    steel: "Acciaio", fairy: "Folletto",
  };

  function fetchPokemonTypes(pokemonId) {
    if (!pokemonTypesRequests.has(pokemonId)) {
      const request = fetch(`https://pokeapi.co/api/v2/pokemon/${pokemonId}`)
        .then((response) => response.ok ? response.json() : null)
        .then((data) => data?.types?.map(({ type }) => type.name) || [])
        .catch(() => []);
      pokemonTypesRequests.set(pokemonId, request);
    }
    return pokemonTypesRequests.get(pokemonId);
  }

  // ---- Timer Logic ----
  function startTimer() {
    if (isTimerRunning || isGameWon) return;
    isTimerRunning = true;
    timerInterval = setInterval(() => {
      timerSeconds++;
      if (gameTimerEl) {
        gameTimerEl.textContent = `⏱️ ${formatTime(timerSeconds)}`;
      }
    }, 1000);
  }

  function stopTimer() {
    isTimerRunning = false;
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function resetTimer() {
    stopTimer();
    timerSeconds = 0;
    if (gameTimerEl) {
      gameTimerEl.textContent = "⏱️ 00:00";
    }
  }

  function formatTime(totalSec) {
    const m = Math.floor(totalSec / 60)
      .toString()
      .padStart(2, "0");
    const s = (totalSec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  // ---- Audio Synthesizer (Web Audio API) ----
  let audioCtx = null;

  function getAudioContext() {
    if (!audioCtx) {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (AudioCtxClass) {
        audioCtx = new AudioCtxClass();
      }
    }
    if (audioCtx && audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playTone(freq, type, duration, delay = 0, gainLevel = 0.12) {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, ctx.currentTime + delay);

      gain.gain.setValueAtTime(gainLevel, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(
        0.001,
        ctx.currentTime + delay + duration,
      );

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + duration);
    } catch (e) {
      // Audio autoplay policies or unsupported browser
    }
  }

  function playCorrectSound() {
    // Upbeat pleasant two-tone chime
    playTone(523.25, "sine", 0.14, 0, 0.12); // C5
    playTone(659.25, "sine", 0.22, 0.08, 0.15); // E5
  }

  function playIncorrectSound() {
    // Soft muted error tone
    playTone(220, "triangle", 0.18, 0, 0.1);
  }

  function playVictoryFanfare() {
    // Celebratory victory melody
    const notes = [523.25, 659.25, 783.99, 1046.5, 1318.51];
    notes.forEach((freq, idx) => {
      playTone(freq, "triangle", 0.35, idx * 0.12, 0.18);
    });
  }

  // ---- Confetti Animation ----
  let confettiAnimId = null;

  function startConfetti() {
    if (!confettiCanvas) return;
    const ctx = confettiCanvas.getContext("2d");
    const width = (confettiCanvas.width = window.innerWidth);
    const height = (confettiCanvas.height = window.innerHeight);

    const colors = [
      "#fac83c",
      "#3fb950",
      "#388bfd",
      "#f85149",
      "#a371f7",
      "#39d2c0",
      "#ffffff",
    ];
    const particles = [];
    const count = 90;

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height - height,
        size: Math.random() * 8 + 6,
        color: colors[Math.floor(Math.random() * colors.length)],
        speedY: Math.random() * 3 + 2.5,
        speedX: (Math.random() - 0.5) * 2,
        angle: Math.random() * 360,
        angularSpeed: (Math.random() - 0.5) * 6,
      });
    }

    const startTime = Date.now();

    function animate() {
      ctx.clearRect(0, 0, width, height);

      particles.forEach((p) => {
        p.y += p.speedY;
        p.x += p.speedX;
        p.angle += p.angularSpeed;

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.angle * Math.PI) / 180);
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
        ctx.restore();

        if (p.y > height && Date.now() - startTime < 6000) {
          p.y = -10;
          p.x = Math.random() * width;
        }
      });

      if (Date.now() - startTime < 7000) {
        confettiAnimId = requestAnimationFrame(animate);
      } else {
        ctx.clearRect(0, 0, width, height);
      }
    }

    if (confettiAnimId) cancelAnimationFrame(confettiAnimId);
    confettiAnimId = requestAnimationFrame(animate);
  }

  // ---- Load Puzzle Data ----
  async function loadPuzzle() {
    try {
      const dateParts = new Intl.DateTimeFormat("en", {
        timeZone: "Europe/Rome",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).formatToParts(new Date());
      const dateValues = Object.fromEntries(dateParts.map(({ type, value }) => [type, value]));
      const today = `${dateValues.year}-${dateValues.month}-${dateValues.day}`;
      shinyPuzzleDate = today;
      let data = null;
      const savedToken = localStorage.getItem(`pokemon-clues-state-${today}`);
      const tokenQuery = savedToken ? `&state=${encodeURIComponent(savedToken)}` : "";
      let response = await fetch(`/api/puzzle?date=${today}${tokenQuery}`);
      if (response.ok) {
        data = await response.json();
        shinyApiEnabled = true;
      } else if (savedToken && response.status === 400) {
        localStorage.removeItem(`pokemon-clues-state-${today}`);
        response = await fetch(`/api/puzzle?date=${today}`);
        if (response.ok) {
          data = await response.json();
          shinyApiEnabled = true;
        }
      }

      // Local static preview only. Production never falls back to public answer JSON.
      if (!data && ["localhost", "127.0.0.1"].includes(location.hostname)) {
        const localResponse = await fetch(`../puzzles/shiny-${today}.json`);
        if (localResponse.ok) data = await localResponse.json();
      }
      if (!data) throw new Error(`Puzzle API returned ${response.status}`);

      if (data) {
        if (data.grid_size && data.grid_size.length === 2) {
          GRID_ROWS = data.grid_size[0];
          GRID_COLS = data.grid_size[1];
          TOTAL_CELLS = GRID_ROWS * GRID_COLS;
          gridState = new Array(TOTAL_CELLS).fill(null);
        }

        shinyPuzzleCells = Array.isArray(data.cells) ? data.cells : null;
        revealedCells = new Set();
        if (shinyPuzzleCells) {
          solution = data.solution || new Array(shinyPuzzleCells.length).fill(null);
          shinyStatuses = new Array(shinyPuzzleCells.length).fill(null);
          shinyStateToken = data.stateToken || null;
          shinyPuzzleCells.forEach((pokemon, index) => {
            pokemon.spriteUrl = getSpriteUrl(pokemon.id);
          });
          if (Array.isArray(data.revealed)) {
            data.revealed.forEach(({ index, status, clue, logic }) => {
              revealedCells.add(index);
              shinyStatuses[index] = status === "shiny" ? 1 : 0;
              shinyPuzzleCells[index].clue = clue;
              shinyPuzzleCells[index].logic = logic;
            });
          } else {
            shinyPuzzleCells.forEach((pokemon, index) => {
              if (pokemon.label === data.start_cell && solution[index] === data.start_status) {
                revealedCells.add(index);
                shinyStatuses[index] = solution[index] === "shiny" ? 1 : 0;
              }
            });
          }
          if (shinyStateToken) localStorage.setItem(`pokemon-clues-state-${today}`, shinyStateToken);
          clues = [];
        } else {
          solution = data.solution || [];

          allCandidates = (data.candidates || []).map((c) => ({
            name: c.name,
            id: c.id,
            spriteUrl: getSpriteUrl(c.id),
          }));
          clues = data.clues || [];
        }
      } else {
        loadPlaceholders();
      }
    } catch (err) {
      console.warn("Could not load puzzle, using placeholders:", err);
      loadPlaceholders();
    }

    poolItems = [...allCandidates];
    if (shinyPuzzleCells) {
      document.getElementById("site-header").classList.add("shiny-game-header");
      document.querySelector("#site-header .subtitle").textContent =
        "Leggi gli indizi e scopri quali Pokémon sono shiny";
      document.querySelector("#grid-section h2").textContent = "Indovina lo stato shiny";
      document.querySelector(".grid-controls").classList.add("legacy-controls");
    }
    renderAll();
  }

  // ---- Placeholder Data ----
  function loadPlaceholders() {
    const placeholders = [
      { name: "pikachu", id: 25 },
      { name: "charizard", id: 6 },
      { name: "bulbasaur", id: 1 },
      { name: "squirtle", id: 7 },
      { name: "eevee", id: 133 },
      { name: "mewtwo", id: 150 },
      { name: "gengar", id: 94 },
      { name: "snorlax", id: 143 },
      { name: "dragonite", id: 149 },
      { name: "lucario", id: 448 },
      { name: "gardevoir", id: 282 },
      { name: "umbreon", id: 197 },
      { name: "gyarados", id: 130 },
      { name: "scizor", id: 212 },
      { name: "arcanine", id: 59 },
      { name: "togekiss", id: 468 },
      { name: "garchomp", id: 445 },
      { name: "blaziken", id: 257 },
      { name: "mimikyu", id: 778 },
      { name: "sylveon", id: 700 },
    ];

    allCandidates = placeholders.map((p) => ({
      name: p.name,
      id: p.id,
      spriteUrl: getSpriteUrl(p.id),
    }));

    solution = placeholders.map((p) => p.name);

    clues = [
      { id: 0, text: "Carica un file puzzle per vedere gli indizi qui." },
    ];
  }

  // ---- Render Functions ----
  function renderAll() {
    if (shinyPuzzleCells) {
      renderShinyGrid();
      renderClues();
      updateCounts();
      return;
    }
    renderGrid();
    renderPool();
    renderClues();
    updateCounts();
  }

  function renderShinyGrid() {
    gridEl.innerHTML = "";
    const deducedStatuses = getDeducedStatuses();
    shinyPuzzleCells.forEach((pokemon, index) => {
      const cell = document.createElement("article");
      const solved = revealedCells.has(index);
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
      if (solved) {
        if ((!Array.isArray(pokemon.types) || pokemon.types.length === 0) &&
            !pokemonTypesRequests.has(pokemon.id)) {
          fetchPokemonTypes(pokemon.id).then((types) => {
            pokemon.types = types;
            if (revealedCells.has(index)) renderAll();
          });
        }
        (pokemon.types || []).forEach((type) => {
          const badge = document.createElement("span");
          badge.className = "shiny-type-badge";
          badge.textContent = pokemonTypeNames[type] || formatName(type);
          badge.style.setProperty("--type-color", pokemonTypeColors[type] || "#667085");
          typeList.appendChild(badge);
        });
      }

      const cardHeading = document.createElement("div");
      cardHeading.className = "shiny-card-heading";
      cardHeading.append(cardName, typeList);
      cell.appendChild(cardHeading);

      const cardMain = document.createElement("div");
      cardMain.className = "shiny-card-main";
      const pokemonVisual = document.createElement("div");
      pokemonVisual.className = "shiny-pokemon-visual";

      if (solved) {
        const img = document.createElement("img");
        img.className = "cell-sprite";
        img.src = shinyStatuses[index] === 1 || solution[index] === "shiny"
          ? `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/shiny/${pokemon.id}.png`
          : pokemon.spriteUrl;
        img.alt = formatName(pokemon.pokemon);
        img.loading = "lazy";
        pokemonVisual.appendChild(img);

      } else {
        const silhouette = document.createElement("span");
        silhouette.className = "shiny-silhouette";
        silhouette.setAttribute("aria-hidden", "true");
        silhouette.textContent = "?";
        pokemonVisual.appendChild(silhouette);
      }
      cardMain.appendChild(pokemonVisual);

      const clueVisible = solved;
      if (!solved) cell.classList.add("clue-locked-cell");
      const clue = document.createElement("p");
      clue.className = `cell-clue${clueVisible ? "" : " clue-locked"}`;
      clue.textContent = clueVisible ? pokemon.clue : "Risolvi la cella per rivelare l'indizio";
      cardMain.appendChild(clue);
      cell.appendChild(cardMain);

      const choices = document.createElement("div");
      choices.className = "shiny-choices";
      ["regular", "shiny"].forEach((status) => {
        const button = document.createElement("button");
        button.type = "button";
        const selected = solved && (shinyStatuses[index] === (status === "shiny" ? 1 : 0) || solution[index] === status);
        button.className = `shiny-choice${selected ? " selected" : ""}`;
        button.textContent = status === "shiny" ? "✦ Shiny" : "Regular";
        button.disabled = solved;
        button.setAttribute("aria-pressed", String(selected));
        button.addEventListener("click", () => guessShinyStatus(index, status, cell));
        choices.appendChild(button);
      });
      cell.appendChild(choices);
      gridEl.appendChild(cell);
    });
  }

  function getDeducedStatuses() {
    const state = new Array(shinyPuzzleCells.length).fill(null);
    revealedCells.forEach((index) => {
      state[index] = shinyStatuses[index] ?? (solution[index] === "shiny" ? 1 : 0);
    });

    const constraints = [];
    shinyPuzzleCells.forEach((cell, index) => {
      if (!revealedCells.has(index)) return;
      (cell.logic || []).forEach((constraint) => constraints.push(constraint));
    });

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

  async function guessShinyStatus(index, status, cell) {
    const forcedStatus = getDeducedStatuses()[index];
    const selectedStatus = status === "shiny" ? 1 : 0;
    if (revealedCells.has(index)) return;
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
    movesCount++;
    if (shinyApiEnabled) {
      const buttons = [...cell.querySelectorAll("button")];
      buttons.forEach((button) => { button.disabled = true; });
      try {
        const response = await fetch("/api/puzzle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            date: shinyPuzzleDate,
            index,
            status,
            stateToken: shinyStateToken,
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
        shinyStateToken = result.stateToken;
        localStorage.setItem(`pokemon-clues-state-${shinyPuzzleDate}`, result.stateToken);
        shinyStatuses[index] = result.status === "shiny" ? 1 : 0;
        shinyPuzzleCells[index].clue = result.clue;
        shinyPuzzleCells[index].logic = result.logic;
        revealedCells.add(index);
        playCorrectSound();
        renderAll();
        checkVictoryCondition();
      } catch (error) {
        console.error("Could not verify answer:", error);
        cell.classList.remove("guess-wrong");
        void cell.offsetWidth;
        cell.classList.add("guess-wrong");
      } finally {
        buttons.forEach((button) => { button.disabled = revealedCells.has(index); });
      }
      return;
    }
    if (status === solution[index]) {
      revealedCells.add(index);
      shinyStatuses[index] = status === "shiny" ? 1 : 0;
      playCorrectSound();
      renderAll();
      checkVictoryCondition();
    } else {
      playIncorrectSound();
      cell.classList.remove("guess-wrong");
      void cell.offsetWidth;
      cell.classList.add("guess-wrong");
    }
  }

  function renderGrid() {
    gridEl.innerHTML = "";
    for (let i = 0; i < TOTAL_CELLS; i++) {
      const row = Math.floor(i / GRID_COLS);
      const col = i % GRID_COLS;
      const label = `${ROW_LETTERS[col]}${row + 1}`;

      const cell = document.createElement("div");
      cell.className = "grid-cell";
      cell.dataset.index = i;

      // Cell coordinate label (e.g. A1, B2)
      const labelEl = document.createElement("span");
      labelEl.className = "cell-label";
      labelEl.textContent = label;
      cell.appendChild(labelEl);

      if (gridState[i]) {
        cell.classList.add("filled");
        cell.draggable = true;

        // Check if placed in the right position according to JSON solution
        const isCorrect =
          solution.length > i && gridState[i].name === solution[i];
        cell.classList.add(isCorrect ? "is-correct" : "is-incorrect");

        // Status badge (✓ / ✕)
        const badgeEl = document.createElement("span");
        badgeEl.className = `cell-status-badge ${isCorrect ? "correct" : "incorrect"}`;
        badgeEl.textContent = isCorrect ? "✓" : "✕";
        badgeEl.title = isCorrect ? "Posizione corretta!" : "Posizione errata";
        cell.appendChild(badgeEl);

        // Filled cell sprite
        const img = document.createElement("img");
        img.className = "cell-sprite";
        img.src = gridState[i].spriteUrl;
        img.alt = gridState[i].name;
        img.loading = "lazy";
        cell.appendChild(img);

        const nameEl = document.createElement("span");
        nameEl.className = "cell-name";
        nameEl.textContent = formatName(gridState[i].name);
        cell.appendChild(nameEl);

        // Allow dragging from cell to another cell or back to pool
        cell.addEventListener("dragstart", handleCellDragStart);
        cell.addEventListener("dragend", handleDragEnd);
      } else {
        // Empty cell placeholder
        const placeholder = document.createElement("span");
        placeholder.className = "cell-placeholder";
        placeholder.textContent = "?";
        cell.appendChild(placeholder);
      }

      // Drop target events
      cell.addEventListener("dragover", handleDragOver);
      cell.addEventListener("dragenter", handleDragEnter);
      cell.addEventListener("dragleave", handleDragLeave);
      cell.addEventListener("drop", handleDrop);

      // Click to remove Pokémon from cell
      cell.addEventListener("click", () => handleCellClick(i));

      gridEl.appendChild(cell);
    }
  }

  function renderPool() {
    poolEl.innerHTML = "";

    if (poolItems.length === 0) {
      const emptyMsg = document.createElement("div");
      emptyMsg.className = "pool-empty";
      emptyMsg.textContent = "Tutti i Pokémon sono nella griglia! 🎉";
      poolEl.appendChild(emptyMsg);
      return;
    }

    poolItems.forEach((item, idx) => {
      const el = document.createElement("div");
      el.className = "pool-item";
      el.draggable = true;
      el.dataset.poolIndex = idx;
      el.dataset.name = item.name;
      el.dataset.id = item.id;

      const img = document.createElement("img");
      img.className = "pool-sprite";
      img.src = item.spriteUrl;
      img.alt = item.name;
      img.loading = "lazy";
      el.appendChild(img);

      const nameEl = document.createElement("span");
      nameEl.className = "pool-name";
      nameEl.textContent = formatName(item.name);
      el.appendChild(nameEl);

      // Drag events
      el.addEventListener("dragstart", handlePoolDragStart);
      el.addEventListener("dragend", handleDragEnd);

      poolEl.appendChild(el);
    });
  }

  function renderClues() {
    cluesListEl.innerHTML = "";
    clues.forEach((clue, idx) => {
      const item = document.createElement("div");
      item.className = "clue-item";

      const num = document.createElement("span");
      num.className = "clue-number";
      num.textContent = idx + 1;
      item.appendChild(num);

      const text = document.createElement("span");
      text.className = "clue-text";
      // Highlight cell references like "cella A1" in clue text
      text.innerHTML = clue.text.replace(/([A-Z]\d+)/gi, "<strong>$1</strong>");
      item.appendChild(text);

      cluesListEl.appendChild(item);
    });
  }

  function updateCounts() {
    clueCountEl.textContent = `${clues.length} indizi`;
    poolCountEl.textContent = `${poolItems.length} disponibili`;

    // Calculate correctly placed count
    if (shinyPuzzleCells) {
      const correctCount = revealedCells.size;
      if (correctCountTextEl) correctCountTextEl.textContent = `${correctCount} / ${TOTAL_CELLS}`;
      clueCountEl.textContent = `${TOTAL_CELLS} indizi`;
      poolCountEl.textContent = `${TOTAL_CELLS - correctCount} da scoprire`;
      return;
    }
    let correctCount = 0;
    for (let i = 0; i < TOTAL_CELLS; i++) {
      if (gridState[i] && solution[i] && gridState[i].name === solution[i]) {
        correctCount++;
      }
    }

    if (correctCountTextEl) {
      correctCountTextEl.textContent = `${correctCount} / ${TOTAL_CELLS}`;
    }
  }

  // ---- Victory Check ----
  function checkVictoryCondition() {
    if (shinyPuzzleCells) {
      if (revealedCells.size === shinyPuzzleCells.length && !isGameWon) {
        isGameWon = true;
        stopTimer();
        triggerVictory();
      }
      return;
    }
    if (!solution || solution.length === 0) return;

    // Must have all cells filled
    const allFilled = gridState.every((item) => item !== null);
    if (!allFilled) return;

    // Check if each Pokémon is in its exact solution cell
    const allCorrect = gridState.every(
      (item, idx) => item && item.name === solution[idx],
    );

    if (allCorrect && !isGameWon) {
      isGameWon = true;
      stopTimer();
      triggerVictory();
    }
  }

  function triggerVictory() {
    if (victoryTimeEl) victoryTimeEl.textContent = formatTime(timerSeconds);
    if (victoryMovesEl) victoryMovesEl.textContent = movesCount;
    if (victoryAccuracyEl)
      victoryAccuracyEl.textContent = `${TOTAL_CELLS} / ${TOTAL_CELLS}`;

    if (victoryModalEl) {
      victoryModalEl.classList.remove("hidden");
      victoryModalEl.setAttribute("aria-hidden", "false");
    }

    if (btnShowVictory) {
      btnShowVictory.classList.add("hidden");
    }

    startConfetti();
    playVictoryFanfare();
  }

  // ---- Formatting ----
  function formatName(name) {
    return name.replace(/-/g, " ");
  }

  // ---- Drag & Drop Handlers ----
  let draggedData = null; // { source: 'pool'|'grid', index: number, item: {...} }

  function handlePoolDragStart(e) {
    const poolIndex = parseInt(e.currentTarget.dataset.poolIndex);
    draggedData = {
      source: "pool",
      index: poolIndex,
      item: poolItems[poolIndex],
    };
    e.currentTarget.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";

    const ghost = e.currentTarget.cloneNode(true);
    ghost.style.position = "absolute";
    ghost.style.top = "-1000px";
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 45, 45);
    setTimeout(() => {
      if (ghost.parentNode) ghost.parentNode.removeChild(ghost);
    }, 0);
  }

  function handleCellDragStart(e) {
    const cellIndex = parseInt(e.currentTarget.dataset.index);
    if (!gridState[cellIndex]) return;

    draggedData = {
      source: "grid",
      index: cellIndex,
      item: gridState[cellIndex],
    };
    e.currentTarget.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";

    const ghost = e.currentTarget.cloneNode(true);
    ghost.style.position = "absolute";
    ghost.style.top = "-1000px";
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 45, 45);
    setTimeout(() => {
      if (ghost.parentNode) ghost.parentNode.removeChild(ghost);
    }, 0);
  }

  function handleDragEnd(e) {
    e.currentTarget.classList.remove("dragging");
    draggedData = null;
    document
      .querySelectorAll(".grid-cell.drag-over")
      .forEach((c) => c.classList.remove("drag-over"));
  }

  function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  function handleDragEnter(e) {
    e.preventDefault();
    e.currentTarget.classList.add("drag-over");
  }

  function handleDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
  }

  function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");

    if (!draggedData) return;

    startTimer();
    movesCount++;

    const targetCellIndex = parseInt(e.currentTarget.dataset.index);
    const placedItem = draggedData.item;

    // Check if placement in this cell matches the JSON solution
    const isCorrect =
      solution.length > targetCellIndex &&
      placedItem.name === solution[targetCellIndex];
    if (isCorrect) {
      playCorrectSound();
    } else {
      playIncorrectSound();
    }

    if (draggedData.source === "pool") {
      const prevInTarget = gridState[targetCellIndex];
      gridState[targetCellIndex] = placedItem;
      poolItems.splice(draggedData.index, 1);
      if (prevInTarget) {
        poolItems.push(prevInTarget);
      }
    } else if (draggedData.source === "grid") {
      const sourceIndex = draggedData.index;
      if (sourceIndex !== targetCellIndex) {
        const temp = gridState[targetCellIndex];
        gridState[targetCellIndex] = gridState[sourceIndex];
        gridState[sourceIndex] = temp;
      }
    }

    draggedData = null;
    renderAll();
    checkVictoryCondition();
  }

  // Drop back to pool from grid
  poolEl.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  });

  poolEl.addEventListener("drop", (e) => {
    e.preventDefault();
    if (!draggedData) return;

    if (draggedData.source === "grid") {
      const cellIndex = draggedData.index;
      if (gridState[cellIndex]) {
        poolItems.push(gridState[cellIndex]);
        gridState[cellIndex] = null;
        renderAll();
        checkVictoryCondition();
      }
    }
    draggedData = null;
  });

  // ---- Cell Click: Remove Pokémon ----
  function handleCellClick(cellIndex) {
    if (gridState[cellIndex]) {
      poolItems.push(gridState[cellIndex]);
      gridState[cellIndex] = null;
      renderAll();
      checkVictoryCondition();
    }
  }

  // ---- Control Buttons ----
  btnClear.addEventListener("click", () => {
    resetTimer();
    movesCount = 0;
    isGameWon = false;
    if (btnShowVictory) btnShowVictory.classList.add("hidden");
    if (victoryModalEl) victoryModalEl.classList.add("hidden");

    for (let i = 0; i < TOTAL_CELLS; i++) {
      if (gridState[i]) {
        poolItems.push(gridState[i]);
        gridState[i] = null;
      }
    }
    renderAll();
  });

  btnShuffle.addEventListener("click", () => {
    for (let i = poolItems.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [poolItems[i], poolItems[j]] = [poolItems[j], poolItems[i]];
    }
    renderPool();
  });

  if (btnSound) {
    btnSound.addEventListener("click", () => {
      soundEnabled = !soundEnabled;
      if (soundIcon) {
        soundIcon.textContent = soundEnabled ? "🔊" : "🔇";
      }
      btnSound.title = soundEnabled ? "Disattiva audio" : "Attiva audio";
    });
  }

  // ---- Victory Modal Buttons ----
  if (btnPlayAgain) {
    btnPlayAgain.addEventListener("click", async () => {
      if (victoryModalEl) {
        victoryModalEl.classList.add("hidden");
        victoryModalEl.setAttribute("aria-hidden", "true");
      }
      if (btnShowVictory) {
        btnShowVictory.classList.add("hidden");
      }
      isGameWon = false;
      movesCount = 0;
      resetTimer();

      if (shinyPuzzleCells) {
        if (shinyPuzzleDate) {
          localStorage.removeItem(`pokemon-clues-state-${shinyPuzzleDate}`);
        }
        shinyStateToken = null;
        revealedCells = new Set();
        shinyStatuses = new Array(shinyPuzzleCells.length).fill(null);
        await loadPuzzle();
        return;
      }

      // Return all Pokémon to pool
      for (let i = 0; i < TOTAL_CELLS; i++) {
        if (gridState[i]) {
          poolItems.push(gridState[i]);
          gridState[i] = null;
        }
      }
      // Shuffle pool
      for (let i = poolItems.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [poolItems[i], poolItems[j]] = [poolItems[j], poolItems[i]];
      }
      renderAll();
    });
  }

  if (btnCloseVictory) {
    btnCloseVictory.addEventListener("click", () => {
      if (victoryModalEl) {
        victoryModalEl.classList.add("hidden");
        victoryModalEl.setAttribute("aria-hidden", "true");
      }
      if (isGameWon && btnShowVictory) {
        btnShowVictory.classList.remove("hidden");
      }
    });
  }

  if (btnShowVictory) {
    btnShowVictory.addEventListener("click", () => {
      if (victoryModalEl) {
        victoryModalEl.classList.remove("hidden");
        victoryModalEl.setAttribute("aria-hidden", "false");
      }
      btnShowVictory.classList.add("hidden");
    });
  }

  // ---- Initialize ----
  loadPuzzle();
})();
