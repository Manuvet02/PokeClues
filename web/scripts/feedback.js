import { game, dom, t } from "./game-state.js";

export function formatTime(totalSec) {
  const minutes = Math.floor(totalSec / 60).toString().padStart(2, "0");
  const seconds = (totalSec % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function startTimer() {
  if (game.timerRunning || game.won) return;
  game.timerRunning = true;
  game.timerInterval = setInterval(() => {
    game.timerSeconds++;
    dom.timer.textContent = `⏱️ ${formatTime(game.timerSeconds)}`;
  }, 1000);
}

export function stopTimer() {
  game.timerRunning = false;
  if (game.timerInterval) clearInterval(game.timerInterval);
  game.timerInterval = null;
}

export function resetTimer() {
  stopTimer();
  game.timerSeconds = 0;
  dom.timer.textContent = "⏱️ 00:00";
}

let audioContext = null;
function playTone(frequency, type, duration, delay = 0, gainLevel = 0.12) {
  if (!game.soundEnabled) return;
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!audioContext && AudioContextClass) audioContext = new AudioContextClass();
    if (!audioContext) return;
    if (audioContext.state === "suspended") audioContext.resume();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, audioContext.currentTime + delay);
    gain.gain.setValueAtTime(gainLevel, audioContext.currentTime + delay);
    gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + delay + duration);
    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(audioContext.currentTime + delay);
    oscillator.stop(audioContext.currentTime + delay + duration);
  } catch (_) { /* Audio may be unavailable or blocked by browser policy. */ }
}

export const playCorrectSound = () => {
  playTone(523.25, "sine", 0.14, 0, 0.12);
  playTone(659.25, "sine", 0.22, 0.08, 0.15);
};
export const playIncorrectSound = () => playTone(220, "triangle", 0.18, 0, 0.1);

export function toggleSound() {
  game.soundEnabled = !game.soundEnabled;
  dom.soundIcon.textContent = game.soundEnabled ? "🔊" : "🔇";
  dom.soundButton.title = t(game.soundEnabled ? "soundOn" : "soundOff");
}

let confettiAnimation = null;
export function celebrate() {
  if (!dom.confetti) return;
  const ctx = dom.confetti.getContext("2d");
  const width = (dom.confetti.width = window.innerWidth);
  const height = (dom.confetti.height = window.innerHeight);
  const colors = ["#fac83c", "#3fb950", "#388bfd", "#f85149", "#a371f7", "#39d2c0", "#ffffff"];
  const particles = Array.from({ length: 90 }, () => ({
    x: Math.random() * width, y: Math.random() * height - height,
    size: Math.random() * 8 + 6, color: colors[Math.floor(Math.random() * colors.length)],
    speedY: Math.random() * 3 + 2.5, speedX: (Math.random() - 0.5) * 2,
    angle: Math.random() * 360, angularSpeed: (Math.random() - 0.5) * 6,
  }));
  const startedAt = Date.now();
  function animate() {
    ctx.clearRect(0, 0, width, height);
    particles.forEach((p) => {
      p.y += p.speedY; p.x += p.speedX; p.angle += p.angularSpeed;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate((p.angle * Math.PI) / 180);
      ctx.fillStyle = p.color; ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2); ctx.restore();
      if (p.y > height && Date.now() - startedAt < 6000) { p.y = -10; p.x = Math.random() * width; }
    });
    if (Date.now() - startedAt < 7000) confettiAnimation = requestAnimationFrame(animate);
    else ctx.clearRect(0, 0, width, height);
  }
  if (confettiAnimation) cancelAnimationFrame(confettiAnimation);
  confettiAnimation = requestAnimationFrame(animate);
}

export function playVictoryFanfare() {
  [523.25, 659.25, 783.99, 1046.5, 1318.51].forEach((frequency, index) =>
    playTone(frequency, "triangle", 0.35, index * 0.12, 0.18),
  );
}
