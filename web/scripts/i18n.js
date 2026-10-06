(() => {
  "use strict";

  const messages = {
    en: {
      gridTitle: "Puzzle Grid",
      placedCorrectly: "Pokémon placed correctly",
      timerElapsed: "Elapsed time",
      language: "Language",
      toggleSound: "Toggle sound",
      cluesTitle: "📋 Clues",
      progressTitle: "Puzzle Progress",
      reopenVictory: "Reopen victory screen",
      victory: "VICTORY!",
      victorySubtitle: "You placed every Pokémon correctly!",
      time: "Time",
      moves: "Moves",
      accuracy: "Accuracy",
      playAgain: "Play Again",
      viewGrid: "View Grid",
      footerIntro: "A daily logic puzzle inspired by",
      reopenBanner: "🏆 Puzzle Complete! Click to see your stats",
      correctPosition: "Correct position!",
      incorrectPosition: "Incorrect position!",
      allInGrid: "Every Pokémon is on the grid! 🎉",
      lockedClue: "Solve this cell to reveal its clue",
      regular: "Regular",
      shiny: "✦ Shiny",
      soundOn: "Turn sound off",
      soundOff: "Turn sound on",
      clueCount: (n) => `${n} ${n === 1 ? "clue" : "clues"}`,
      undiscovered: (n) => `${n} to discover`,
      puzzleLoadError:
        "Today's puzzle could not be loaded. Please try again later.",
    },
    it: {
      gridTitle: "Griglia del puzzle",
      placedCorrectly: "Pokémon posizionati correttamente",
      timerElapsed: "Tempo trascorso",
      language: "Lingua",
      toggleSound: "Attiva/disattiva audio",
      cluesTitle: "📋 Indizi",
      progressTitle: "Progresso del puzzle",
      reopenVictory: "Riapri schermata vittoria",
      victory: "VITTORIA!",
      victorySubtitle: "Hai posizionato tutti i Pokémon al posto giusto!",
      time: "Tempo",
      moves: "Mosse",
      accuracy: "Correttezza",
      playAgain: "Rigioca",
      viewGrid: "Ammira la griglia",
      footerIntro: "Un puzzle logico giornaliero ispirato a",
      reopenBanner: "🏆 Puzzle completato! Clicca per vedere le statistiche",
      correctPosition: "Posizione corretta!",
      incorrectPosition: "Posizione errata",
      allInGrid: "Tutti i Pokémon sono nella griglia! 🎉",
      lockedClue: "Risolvi la cella per rivelare l'indizio",
      regular: "Regular",
      shiny: "✦ Shiny",
      soundOn: "Disattiva audio",
      soundOff: "Attiva audio",
      clueCount: (n) => `${n} ${n === 1 ? "indizio" : "indizi"}`,
      undiscovered: (n) => `${n} da scoprire`,
      puzzleLoadError:
        "Non è stato possibile caricare il puzzle di oggi. Riprova più tardi.",
    },
  };

  let locale = "en";
  try {
    const saved = localStorage.getItem("pokemon-clues-language");
    if (saved && messages[saved]) locale = saved;
  } catch (_) {
    /* Storage may be unavailable in private browsing. */
  }

  function t(key, ...args) {
    const value = messages[locale]?.[key] ?? messages.en[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  }

  function apply() {
    document.documentElement.lang = locale;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.title = t(element.dataset.i18nTitle);
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
    });
    const select = document.getElementById("language-select");
    if (select) select.value = locale;
  }

  document.addEventListener("DOMContentLoaded", () => {
    apply();
    const select = document.getElementById("language-select");
    select?.addEventListener("change", () => {
      locale = messages[select.value] ? select.value : "en";
      try {
        localStorage.setItem("pokemon-clues-language", locale);
      } catch (_) {
        /* Ignore unavailable storage. */
      }
      apply();
      document.dispatchEvent(new CustomEvent("pokemon-clues-language-changed"));
    });
  });

  window.PokemonCluesI18n = {
    t,
    get locale() {
      return locale;
    },
  };
})();
