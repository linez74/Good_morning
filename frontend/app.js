// Configure this after deploying the FastAPI backend.
const API_BASE = "https://good-morning-1xie.onrender.com";
const DEMO = {
  sleepMinutes: 462, restingHeartRate: 62, steps: 8420,
  loveNote: "You make ordinary days feel like something worth remembering."
};
const $ = (id) => document.getElementById(id);
let sessionToken = sessionStorage.getItem("morning_session");

const notes = [
  "You make ordinary days feel like something worth remembering.",
  "A little reminder that someone is very, very glad you exist.",
  "I hope today is gentle with you. You deserve good things.",
  "If I could send you one thing this morning, it would be a little extra happiness.",
  "Whatever today brings, I hope you remember how loved you are."
];

function formatDuration(mins) {
  if (mins == null) return "—";
  const h = Math.floor(mins / 60), m = mins % 60;
  return `${h}h ${m}m`;
}
function showDashboard() {
  $("lock-screen").classList.add("hidden");
  $("dashboard").classList.remove("hidden");
  const now = new Date();
  $("today-label").textContent = now.toLocaleDateString(undefined, {weekday:"long", month:"long", day:"numeric"}).toUpperCase();
  $("date-pill").textContent = now.toLocaleDateString(undefined, {month:"short", day:"numeric", year:"numeric"});
  $("note-date").textContent = "TODAY'S LITTLE REMINDER";
  $("love-note").textContent = notes[now.getDate() % notes.length];
  renderMetrics(DEMO, true);
  if (sessionToken) refreshHealth();
}
function renderMetrics(data, demo=false) {
  const sleep = data.sleepMinutes ?? null;
  $("sleep-value").textContent = formatDuration(sleep);
  $("sleep-total").textContent = formatDuration(sleep);
  $("sleep-caption").textContent = sleep == null ? "No sleep summary available yet." : "A little time to recharge.";
  $("sleep-bar-fill").style.width = sleep == null ? "0%" : `${Math.min(100, sleep/540*100)}%`;
  $("heart-value").textContent = data.restingHeartRate ?? "—";
  $("heart-caption").textContent = data.restingHeartRate == null ? "No resting heart rate available." : "A quiet little rhythm.";
  $("steps-value").textContent = data.steps == null ? "—" : Number(data.steps).toLocaleString();
  $("last-sync").textContent = demo ? "Sample data · preview" : new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
}
async function api(path, options={}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options, headers: {...(options.headers||{}), "Content-Type":"application/json", "Authorization":`Bearer ${sessionToken}`}
  });
  const data = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(data.detail || "Something went wrong.");
  return data;
}
$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("login-error").textContent = "";
  try {
    const response = await fetch(`${API_BASE}/auth/password`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({password:$("password").value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "That password didn't work.");
    sessionToken = data.session_token;
    sessionStorage.setItem("morning_session", sessionToken);
    showDashboard();
  } catch (error) { $("login-error").textContent = error.message; }
});
$("logout-btn").addEventListener("click", () => {
  sessionToken = null; sessionStorage.removeItem("morning_session");
  $("dashboard").classList.add("hidden"); $("lock-screen").classList.remove("hidden"); $("password").value="";
});
async function refreshHealth() {
  try {
    const data = await api("/health/summary");
    renderMetrics(data, false);
    $("connection-status").innerHTML = "<i></i> Google Health connected";
    $("connection-status").classList.add("connected");
    $("connect-btn").textContent = "Google Health connected ✓";
  } catch (error) {
    $("last-sync").textContent = error.message;
  }
}
$("refresh-btn").addEventListener("click", refreshHealth);
$("connect-btn").addEventListener("click", async () => {
  if (!sessionToken) return;
  try {
    const data = await api("/auth/google/start");
    window.location.href = data.authorization_url;
  } catch (error) { alert(error.message); }
});
const params = new URLSearchParams(location.search);
if (params.get("oauth") === "success") {
  history.replaceState({}, "", location.pathname);
  showDashboard();
  setTimeout(refreshHealth, 400);
} else if (sessionToken) {
  showDashboard();
}
