/* =========================================================
   LOCAL AI OFFICE — frontend
   Sections: state · helpers · scene scaling · sprites ·
   agents · movement · tasks · events · websocket · chat ·
   workspace · navigation · settings · boot
========================================================= */

"use strict";

/* =========================================================
   STATE
========================================================= */

const STAGE_W = 1080;
const STAGE_H = 660;

let websocket = null;
let reconnectAttempts = 0;
let pendingRequests = 0;

let agents = {};            // name -> { name, role, status, position, deskPosition }
let selectedAgent = null;

let tasks = [];             // newest first
let taskFilter = "all";
let currentArtifact = null;

const moveTokens = {};      // name -> latest move id
const KNOWN_STATES = ["idle", "thinking", "working", "failed"];

const bossPosition = { x: 540, y: 268 };


/* =========================================================
   DOM
========================================================= */

const $ = id => document.getElementById(id);

const office = $("office");
const stage = $("stage");
const agentLayer = $("agent-layer");
const deskLayer = $("desk-layer");
const messageLayer = $("message-layer");
const agentList = $("agent-list");
const agentCount = $("agent-count");
const activityLog = $("activity-log");
const taskList = $("task-list");
const inspectorContent = $("inspector-content");
const modalBackdrop = $("modal-backdrop");
const connectionDot = $("connection-dot");
const connectionText = $("connection-text");
const workspace = $("workspace");
const selectedAgentLabel = $("selected-agent-label");


/* =========================================================
   HELPERS
========================================================= */

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
}

function truncate(text, length) {
    if (!text) return "";
    return text.length <= length ? text : text.substring(0, length) + "...";
}

function displayName(name) {
    return String(name || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, letter => letter.toUpperCase());
}

function hash(text) {
    let h = 2166136261;
    for (let i = 0; i < text.length; i++) {
        h ^= text.charCodeAt(i);
        h = Math.imul(h, 16777619);
    }
    return h >>> 0;
}

function pick(list, seed) {
    return list[seed % list.length];
}

function storageGet(key, fallback) {
    try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
    } catch (error) {
        return fallback;
    }
}

function storageSet(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (error) { /* storage unavailable — settings just won't persist */ }
}

let toastTimer = null;

function toast(message, isError = false) {
    const el = $("toast");
    el.textContent = message;
    el.classList.toggle("bad", isError);
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3800);
}

function reducedMotion() {
    return document.body.classList.contains("reduce-motion") ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}


/* =========================================================
   SCENE SCALING + CLOCK
========================================================= */

function fitStage() {
    const width = office.clientWidth;
    if (!width) return;
    stage.style.setProperty("--scale", (width / STAGE_W).toFixed(4));
}

if ("ResizeObserver" in window) {
    new ResizeObserver(fitStage).observe(office);
} else {
    window.addEventListener("resize", fitStage);
}

function tickClock() {
    const now = new Date();
    const minutes = now.getMinutes();
    const hours = (now.getHours() % 12) + minutes / 60;

    $("clock-minute").setAttribute("transform", `rotate(${minutes * 6} 540 70)`);
    $("clock-hour").setAttribute("transform", `rotate(${hours * 30} 540 70)`);
}


/* =========================================================
   LOOK & FEEL: palettes, characters, desks
========================================================= */

const SHIRTS = ["#d9534f", "#2f8f83", "#6d4fd1", "#e07a3f", "#3d7bd9", "#c2578a", "#4c9a5b", "#b8892f"];
const HAIRS = ["#2b2118", "#6b3f23", "#1b1b22", "#d9a441", "#8a3b2a", "#4a4a52"];
const SKINS = ["#f1c9a5", "#e7b48f", "#c98f69", "#9a6a47", "#7b4f33"];
const ACCESSORIES = ["glasses", "cap", "bun", "plain", "headphones"];

const PRESETS = {
    boss: { shirt: "#1f2a44", pants: "#242a36", hair: "#2b2118", skin: "#e7b48f", accessory: "tie", glow: "#e9c46a" },
    researcher: { shirt: "#2f8f83", pants: "#2b3442", hair: "#6b3f23", skin: "#f1c9a5", accessory: "glasses", glow: "#7be0cf" },
    coder: { shirt: "#6d4fd1", pants: "#232a38", hair: "#1b1b22", skin: "#c98f69", accessory: "headphones", glow: "#b7a2ff" },
    analyst: { shirt: "#e07a3f", pants: "#2b3442", hair: "#d9a441", skin: "#9a6a47", accessory: "bun", glow: "#ffb98a" },
};

function paletteFor(name) {
    if (PRESETS[name]) return PRESETS[name];

    const seed = hash(name);

    return {
        shirt: pick(SHIRTS, seed),
        pants: "#2b3442",
        hair: pick(HAIRS, seed >> 3),
        skin: pick(SKINS, seed >> 5),
        accessory: pick(ACCESSORIES, seed >> 7),
        glow: "#8fd0ff",
    };
}

function avatarColor(name) {
    return paletteFor(name).shirt;
}

function accessorySVG(kind, palette) {
    switch (kind) {
        case "glasses":
            return `<g fill="none" stroke="#25303c" stroke-width="1.6">
                <circle cx="26.5" cy="23" r="4.6"/><circle cx="37.5" cy="23" r="4.6"/><path d="M31 23h2"/></g>`;
        case "headphones":
            return `<path d="M17.5 22a14.5 14.5 0 0 1 29 0" fill="none" stroke="#2a2f3a" stroke-width="3.2" stroke-linecap="round"/>
                <rect x="14" y="20" width="6" height="10" rx="3" fill="#cfd6e2"/><rect x="44" y="20" width="6" height="10" rx="3" fill="#cfd6e2"/>`;
        case "cap":
            return `<path d="M17 18a15 13 0 0 1 30 0z" fill="#d9534f"/><rect x="30" y="16" width="22" height="4" rx="2" fill="#b7403d"/>`;
        case "bun":
            return `<circle cx="32" cy="3.5" r="5.5" fill="${palette.hair}"/>`;
        case "tie":
            return "";
        default:
            return "";
    }
}

function characterSVG(name) {
    const p = paletteFor(name);
    const hairFront = p.accessory === "cap" ? "" :
        `<path d="M17.4 21c0-9 6-13.5 14.6-13.5S46.6 12 46.6 21c-3-5-8-7-14.6-7s-11.6 2-14.6 7z" fill="${p.hair}"/>`;

    const tie = p.accessory === "tie"
        ? `<path d="M32 36l-4 5 4 22 4-22z" fill="#c9a85c"/><path d="M28 36h8l-4 5z" fill="#a98a3d"/>`
        : "";

    const hoodie = p.accessory === "headphones"
        ? `<path d="M26 36q6 6 12 0" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="2"/>`
        : "";

    return `
<svg viewBox="0 0 64 96" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <ellipse cx="32" cy="92" rx="18" ry="4.5" fill="#000" opacity=".3"/>

    <g class="leg left-leg">
        <rect x="21" y="62" width="9.5" height="26" rx="4.5" fill="${p.pants}"/>
        <rect x="19" y="83" width="13" height="8" rx="4" fill="#161a22"/>
    </g>
    <g class="leg right-leg">
        <rect x="33.5" y="62" width="9.5" height="26" rx="4.5" fill="${p.pants}"/>
        <rect x="32" y="83" width="13" height="8" rx="4" fill="#161a22"/>
    </g>

    <g class="torso">
        <rect x="15" y="33" width="34" height="36" rx="12" fill="${p.shirt}"/>
        <rect x="15" y="33" width="34" height="14" rx="9" fill="#fff" opacity=".1"/>
        ${tie}${hoodie}
    </g>

    <g class="arm left-arm">
        <rect x="8" y="36" width="9.5" height="26" rx="4.75" fill="${p.shirt}"/>
        <circle cx="12.75" cy="63" r="4.7" fill="${p.skin}"/>
    </g>
    <g class="arm right-arm">
        <rect x="46.5" y="36" width="9.5" height="26" rx="4.75" fill="${p.shirt}"/>
        <circle cx="51.25" cy="63" r="4.7" fill="${p.skin}"/>
    </g>

    <g class="head-g">
        <rect x="27.5" y="31" width="9" height="7" rx="3" fill="${p.skin}"/>
        <circle cx="32" cy="22" r="14.5" fill="${p.skin}"/>
        ${hairFront}
        <g class="eyes" fill="#1c222b">
            <ellipse cx="26.5" cy="23" rx="1.8" ry="2.2"/>
            <ellipse cx="37.5" cy="23" rx="1.8" ry="2.2"/>
        </g>
        <path d="M28.5 29.5q3.5 3 7 0" fill="none" stroke="#7a3f30" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="22.5" cy="27.5" r="2.4" fill="#ff8a8a" opacity=".28"/>
        <circle cx="41.5" cy="27.5" r="2.4" fill="#ff8a8a" opacity=".28"/>
        ${accessorySVG(p.accessory, p)}
    </g>
</svg>`;
}

function deskItems(name) {
    if (name.includes("research")) {
        return `<rect x="12" y="20" width="30" height="8" rx="1.5" fill="#d9534f"/>
                <rect x="14" y="13" width="26" height="8" rx="1.5" fill="#2f6fd6"/>
                <rect x="16" y="6" width="22" height="8" rx="1.5" fill="#f2b84b"/>`;
    }
    if (name.includes("code")) {
        return `<rect x="14" y="14" width="10" height="14" rx="2.5" fill="#4fd1a1"/>
                <rect x="14" y="14" width="10" height="4" rx="1.5" fill="#c9fff0"/>
                <rect x="28" y="20" width="12" height="9" rx="1" fill="#ffd966" transform="rotate(-8 34 24)"/>`;
    }
    if (name.includes("anal")) {
        return `<rect x="10" y="9" width="30" height="20" rx="2" fill="#fbfcfd" transform="rotate(-4 25 19)"/>
                <g fill="#2f6fd6" transform="rotate(-4 25 19)">
                    <rect x="14" y="21" width="4" height="6"/><rect x="20" y="16" width="4" height="11" fill="#e07a3f"/>
                    <rect x="26" y="12" width="4" height="15" fill="#4fd1a1"/><rect x="32" y="18" width="4" height="9"/>
                </g>`;
    }
    return `<path d="M26 28c-3-8-9-8-10-16 6 0 10 5 10 16zM26 28c3-9 9-9 11-17-6 1-11 6-11 17z" fill="#3f9a63"/>
            <rect x="19" y="26" width="14" height="6" rx="2" fill="#c9693e"/>`;
}

function deskSVG(name, isBoss = false) {
    const w = isBoss ? 210 : 160;
    const mid = w / 2;
    const glow = paletteFor(name).glow;

    const bossExtras = isBoss
        ? `<rect x="${w - 62}" y="14" width="46" height="14" rx="3" fill="#c9a85c"/>
           <text x="${w - 39}" y="24.5" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="7.5" font-weight="800" letter-spacing="1.2" fill="#3b2f12">BOSS</text>
           <path d="M22 28v-10h-4q-3 0-3 5t5 5h-4v5h14v-5h-4q5 0 5-5t-3-5h-4" fill="#e9c46a" opacity=".95" transform="translate(4 -4) scale(.8)"/>
           <rect x="${w - 100}" y="18" width="24" height="10" rx="1.5" fill="#fbfcfd" transform="rotate(5 ${w - 88} 23)"/>`
        : deskItems(name);

    return `
<svg viewBox="0 0 ${w} 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="--accent-c:${glow}">
    <ellipse cx="${mid}" cy="95" rx="${mid - 4}" ry="6" fill="#000" opacity=".3"/>

    <rect x="8" y="58" width="${w - 16}" height="33" rx="4" fill="#8a5a35"/>
    <rect x="14" y="64" width="${isBoss ? 56 : 40}" height="21" rx="2.5" fill="#774b2a"/>
    <rect x="${w - (isBoss ? 70 : 54)}" y="64" width="${isBoss ? 56 : 40}" height="21" rx="2.5" fill="#774b2a"/>
    <rect x="${14 + (isBoss ? 22 : 14)}" y="73" width="12" height="3" rx="1.5" fill="#d9b36c"/>
    <rect x="${w - (isBoss ? 48 : 40)}" y="73" width="12" height="3" rx="1.5" fill="#d9b36c"/>

    <rect x="2" y="28" width="${w - 4}" height="32" rx="7" fill="#c99663"/>
    <rect x="2" y="28" width="${w - 4}" height="5" rx="3" fill="#e2b684"/>
    <rect x="2" y="55" width="${w - 4}" height="5" rx="2.5" fill="#a77347"/>

    ${bossExtras}

    <!-- laptop (seen from behind) -->
    <ellipse class="screen-glow" cx="${mid}" cy="8" rx="40" ry="14" fill="url(#glowGrad)"/>
    <rect x="${mid - 33}" y="8" width="66" height="34" rx="4.5" fill="#363c47"/>
    <rect x="${mid - 31}" y="10" width="62" height="30" rx="3.5" fill="#444b58"/>
    <circle class="logo" cx="${mid}" cy="25" r="6"/>
    <circle class="led" cx="${mid + 24}" cy="14" r="1.8"/>
    <rect x="${mid - 38}" y="41" width="76" height="5" rx="2.5" fill="#2a2f38"/>

    <!-- coffee mug -->
    <g transform="translate(${w - (isBoss ? 112 : 36)} 29)">
        <rect width="11" height="12" rx="2.5" fill="#f4eee2"/>
        <path d="M11 3.5q5 0 5 4t-5 3.5" fill="none" stroke="#f4eee2" stroke-width="2"/>
        <rect x="1.5" y="1.5" width="8" height="3" rx="1.5" fill="#6b4a2f"/>
        <path class="steam" d="M3 -1q-2-3 0-6M7 -1q-2-3 0-6" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round"/>
    </g>
</svg>`;
}


/* =========================================================
   POSITIONS
========================================================= */

// Desk slots: three in the front row, then staggered between them so
// seated agents never stand on top of another desk.
const DESK_SLOTS = [
    { x: 190, y: 480 }, { x: 540, y: 480 }, { x: 890, y: 480 },
    { x: 365, y: 595 }, { x: 715, y: 595 },
    { x: 95, y: 595 }, { x: 985, y: 595 },
];

function slotFor(index) {
    if (index < DESK_SLOTS.length) return DESK_SLOTS[index];

    // overflow: reuse the layout, nudged so extra agents stay visible
    const extra = index - DESK_SLOTS.length;
    const base = DESK_SLOTS[extra % DESK_SLOTS.length];
    const shift = (Math.floor(extra / DESK_SLOTS.length) + 1) * 45;

    return { x: Math.min(STAGE_W - 90, base.x + shift), y: base.y };
}

function nextFreeSlot() {
    const taken = Object.values(agents)
        .filter(agent => agent.name !== "boss")
        .map(agent => `${agent.deskPosition.x},${agent.deskPosition.y}`);

    for (let i = 0; i < 40; i++) {
        const slot = slotFor(i);
        if (!taken.includes(`${slot.x},${slot.y}`)) return slot;
    }

    return slotFor(0);
}

function workerNames() {
    return Object.keys(agents).filter(name => name !== "boss");
}

function registerAgent(info) {
    const isBoss = info.name === "boss";
    const spot = isBoss ? { ...bossPosition } : nextFreeSlot();

    agents[info.name] = {
        name: info.name,
        role: info.role || "Agent",
        status: info.status || "idle",
        position: { ...spot },
        deskPosition: { ...spot },
    };

    return agents[info.name];
}


/* =========================================================
   SPRITES
========================================================= */

function createDesk(agent) {
    const isBoss = agent.name === "boss";
    const desk = document.createElement("div");

    desk.className = isBoss ? "desk boss" : "desk";
    desk.dataset.agent = agent.name;
    desk.style.left = `${agent.deskPosition.x - (isBoss ? 105 : 80)}px`;
    desk.style.top = `${agent.deskPosition.y - 34}px`;
    desk.style.zIndex = Math.round(agent.deskPosition.y + 40);
    desk.innerHTML = deskSVG(agent.name, isBoss);

    deskLayer.appendChild(desk);
    syncDesk(agent.name);
}

function createCharacter(agent) {
    const character = document.createElement("div");

    character.id = `character-${agent.name}`;
    character.className = `character ${agent.name}`;
    character.style.left = `${agent.position.x}px`;
    character.style.top = `${agent.position.y}px`;
    character.style.zIndex = Math.round(agent.position.y);
    character.title = `${displayName(agent.name)} — ${agent.role}`;

    character.innerHTML = `
        <div class="character-label">${escapeHtml(displayName(agent.name))}</div>
        <div class="badge"><i></i><i></i><i></i></div>
        <div class="ring"></div>
        <div class="sprite">${characterSVG(agent.name)}</div>
    `;

    character.addEventListener("click", () => selectAgent(agent.name));

    agentLayer.appendChild(character);
    applyStateClasses(agent.name);
}

function removeSprites(name) {
    $(`character-${name}`)?.remove();
    deskLayer.querySelector(`.desk[data-agent="${CSS.escape(name)}"]`)?.remove();
}

function renderOffice() {
    deskLayer.innerHTML = "";
    agentLayer.innerHTML = "";

    Object.values(agents).forEach(agent => {
        createDesk(agent);
        createCharacter(agent);
    });
}

function applyStateClasses(name) {
    const agent = agents[name];
    const character = $(`character-${name}`);

    if (!agent || !character) return;

    KNOWN_STATES.forEach(state => character.classList.remove(state));
    character.classList.add(agent.status);

    syncDesk(name);
}

function syncDesk(name) {
    const agent = agents[name];
    const desk = deskLayer.querySelector(`.desk[data-agent="${CSS.escape(name)}"]`);

    if (!agent || !desk) return;

    const walkingAway = $(`character-${name}`)?.classList.contains("walking");

    desk.classList.toggle("active", agent.status === "working" && !walkingAway);
    desk.classList.toggle("thinking", agent.status === "thinking");
    desk.classList.toggle("failed", agent.status === "failed");
}


/* =========================================================
   AGENT LISTS (sidebar, agents view, inspector, stats)
========================================================= */

function getAgentIcon(name) {
    if (name === "boss") return "B";
    if (name.includes("research")) return "R";
    if (name.includes("code")) return "</>";
    if (name.includes("anal")) return "A";
    if (name.includes("data")) return "D";
    return displayName(name).charAt(0) || "AI";
}

function avatarHtml(name) {
    return `<div class="agent-avatar" style="--av:${avatarColor(name)}">${escapeHtml(getAgentIcon(name))}</div>`;
}

function renderAgentList() {
    agentList.innerHTML = "";

    Object.values(agents).forEach(agent => {
        const card = document.createElement("div");

        card.className = "agent-card" + (selectedAgent === agent.name ? " selected" : "");
        card.dataset.state = agent.status;

        card.innerHTML = `
            ${avatarHtml(agent.name)}
            <div class="agent-info">
                <div class="agent-name">${escapeHtml(displayName(agent.name))}</div>
                <div class="agent-role">${escapeHtml(agent.role)}</div>
                <div class="agent-status ${escapeHtml(agent.status)}">● ${escapeHtml(agent.status || "idle")}</div>
            </div>
        `;

        card.addEventListener("click", () => selectAgent(agent.name));
        agentList.appendChild(card);
    });

    agentCount.textContent = Object.keys(agents).length;
    renderAgentsGrid();
    updateStats();
}

function renderAgentsGrid() {
    const grid = $("agents-grid");
    grid.innerHTML = "";

    Object.values(agents).forEach(agent => {
        const tile = document.createElement("div");
        const done = tasks.filter(t => t.agent === agent.name && t.status === "done").length;
        const active = tasks.filter(t => t.agent === agent.name && t.status === "assigned").length;

        tile.className = "agent-tile";
        tile.innerHTML = `
            ${avatarHtml(agent.name)}
            <h3>${escapeHtml(displayName(agent.name))}</h3>
            <div class="role">${escapeHtml(agent.role)}</div>
            <div class="meta">
                <span class="inspector-status ${escapeHtml(agent.status)}" style="margin:0">● ${escapeHtml(agent.status)}</span>
                <span class="task-who">${done} done · ${active} active</span>
            </div>
        `;

        tile.addEventListener("click", () => {
            showView("office");
            selectAgent(agent.name);
        });

        grid.appendChild(tile);
    });
}

function updateStats() {
    const all = Object.values(agents);

    $("stat-agents").textContent = all.length;
    $("stat-busy").textContent = all.filter(a => a.status === "working" || a.status === "thinking").length;
    $("stat-tasks").textContent = tasks.length;
    $("set-agents").textContent = all.length;
}

function selectAgent(name) {
    const agent = agents[name];
    if (!agent) return;

    selectedAgent = name;

    document.querySelectorAll(".character.selected").forEach(el => el.classList.remove("selected"));
    $(`character-${name}`)?.classList.add("selected");

    const mine = tasks.filter(t => t.agent === name);
    const latest = mine[0];

    inspectorContent.innerHTML = `
        <div class="inspector-head">
            ${avatarHtml(name)}
            <div>
                <div class="inspector-name">${escapeHtml(displayName(agent.name))}</div>
                <div class="inspector-role">${escapeHtml(agent.role)}</div>
            </div>
        </div>

        <div class="inspector-status ${escapeHtml(agent.status)}">● ${escapeHtml(agent.status || "idle")}</div>

        <div class="inspector-section">
            <div class="inspector-label">Latest task</div>
            <div class="inspector-value">${latest ? escapeHtml(truncate(latest.description, 140)) : "No tasks yet."}</div>
        </div>

        <div class="inspector-section">
            <div class="inspector-label">Session stats</div>
            <div class="inspector-value">
                ${mine.filter(t => t.status === "done").length} completed ·
                ${mine.filter(t => t.status === "failed").length} failed
            </div>
        </div>

        <div class="inspector-section">
            <div class="inspector-label">Agent ID</div>
            <div class="inspector-value" style="font-family:var(--mono)">${escapeHtml(agent.name)}</div>
        </div>

        ${name !== "boss" ? `<button class="remove-agent" id="remove-agent-btn">Remove agent</button>` : ""}
    `;

    $("remove-agent-btn")?.addEventListener("click", removeSelectedAgent);

    document.querySelectorAll(".agent-card").forEach(card => {
        card.classList.toggle("selected", card.querySelector(".agent-name")?.textContent === displayName(name));
    });
}

function clearInspector() {
    selectedAgent = null;
    document.querySelectorAll(".character.selected").forEach(el => el.classList.remove("selected"));
    inspectorContent.innerHTML = `<div class="empty-inspector">Select an agent to inspect it.</div>`;
}


/* =========================================================
   LOAD AGENTS
========================================================= */

async function loadAgents() {
    try {
        const response = await fetch("/agents");

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        agents = {};
        registerAgent({ name: "boss", role: "Manager", status: "idle" });

        for (const info of data.agents || []) {
            if (info.name !== "boss") registerAgent(info);
        }

        renderOffice();
        renderAgentList();

    } catch (error) {
        console.error("Could not load agents", error);
        addActivity("Could not load agents — retrying…");

        if (!agents.boss) {
            registerAgent({ name: "boss", role: "Manager", status: "idle" });
            renderOffice();
            renderAgentList();
        }

        setTimeout(loadAgents, 4000);
    }
}


/* =========================================================
   ADD / REMOVE AGENT
========================================================= */

function openAddAgentModal() {
    $("modal-error").classList.add("hidden");
    modalBackdrop.classList.remove("hidden");
    $("agent-name").focus();
}

function closeAddAgentModal() {
    modalBackdrop.classList.add("hidden");
}

function showModalError(message) {
    const el = $("modal-error");
    el.textContent = message;
    el.classList.remove("hidden");
}

async function createAgent() {
    const name = $("agent-name").value.trim();
    const role = $("agent-role").value.trim();
    const instructions = $("agent-instructions").value.trim();
    const button = $("create-agent");

    if (!name || !role) {
        showModalError("Name and role are required.");
        return;
    }

    button.disabled = true;

    try {
        const response = await fetch("/agents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, role, instructions }),
        });

        const data = await response.json();

        if (!response.ok) throw new Error(data.detail || "Could not create agent");

        closeAddAgentModal();
        $("agent-name").value = "";
        $("agent-role").value = "";
        $("agent-instructions").value = "";

        addActivity(`Added agent: ${displayName(name)}`);
        toast(`${displayName(name)} joined the team`);

    } catch (error) {
        showModalError(error.message);
    } finally {
        button.disabled = false;
    }
}

async function removeSelectedAgent() {
    if (!selectedAgent || selectedAgent === "boss") return;

    const name = selectedAgent;

    if (!confirm(`Remove ${displayName(name)} from the office?`)) return;

    try {
        const response = await fetch(`/agents/${encodeURIComponent(name)}`, { method: "DELETE" });
        const data = await response.json();

        if (!response.ok) throw new Error(data.detail || "Could not remove agent");

        addActivity(`Removed agent: ${displayName(name)}`);

    } catch (error) {
        toast(error.message, true);
    }
}

function handleAgentAdded(event) {
    const data = event.data || {};
    const name = data.name;

    if (!name || agents[name]) return;

    const agent = registerAgent({ name, role: data.role, status: "idle" });

    createDesk(agent);
    createCharacter(agent);
    renderAgentList();

    addActivity(`${displayName(name)} joined the office`);
}

function handleAgentRemoved(event) {
    const name = event.data?.name || event.agent;

    if (!agents[name]) return;

    delete agents[name];
    removeSprites(name);

    if (selectedAgent === name) clearInspector();

    renderAgentList();
    addActivity(`${displayName(name)} left the office`);
}


/* =========================================================
   STATE + MOVEMENT
========================================================= */

function setAgentState(name, status) {
    const agent = agents[name];
    if (!agent) return;

    agent.status = KNOWN_STATES.includes(status) ? status : "idle";

    applyStateClasses(name);
    renderAgentList();

    if (selectedAgent === name) selectAgent(name);
}

function moveCharacter(name, target, callback = null) {
    const agent = agents[name];
    const character = $(`character-${name}`);

    if (!agent || !character) {
        if (callback) callback();
        return;
    }

    const token = (moveTokens[name] || 0) + 1;
    moveTokens[name] = token;

    const dx = target.x - agent.position.x;
    const dy = target.y - agent.position.y;
    const distance = Math.hypot(dx, dy);

    const duration = reducedMotion() ? 200 : Math.min(2800, Math.max(700, distance * 4.6));

    character.classList.toggle("facing-right", dx > 6);
    character.classList.toggle("facing-left", dx < -6);

    character.classList.add("walking");
    character.style.setProperty("--walk-duration", `${duration}ms`);
    character.style.zIndex = 1000;

    agent.position = { x: target.x, y: target.y };

    character.style.left = `${target.x}px`;
    character.style.top = `${target.y}px`;

    syncDesk(name);

    setTimeout(() => {
        if (moveTokens[name] === token) {
            character.classList.remove("walking", "facing-left", "facing-right");
            character.style.zIndex = Math.round(target.y);
            syncDesk(name);
        }

        if (callback) callback();
    }, duration);
}

function bossQueueSpot(name) {
    const index = Math.max(0, workerNames().indexOf(name));

    return {
        x: bossPosition.x - 120 + (index % 3) * 120,
        y: bossPosition.y + 88 + Math.floor(index / 3) * 22,
    };
}

function walkToBoss(name, callback) {
    if (!agents[name] || name === "boss") {
        if (callback) callback();
        return;
    }

    moveCharacter(name, bossQueueSpot(name), callback);
}

function walkToDesk(name, callback = null) {
    const agent = agents[name];
    if (!agent) return;

    moveCharacter(name, { ...agent.deskPosition }, callback);
}


/* =========================================================
   SPEECH BUBBLES
========================================================= */

function showMessage(agentName, content) {
    const agent = agents[agentName];
    if (!agent || !content) return;

    messageLayer.querySelectorAll(`.message[data-agent="${CSS.escape(agentName)}"]`).forEach(el => el.remove());

    const bubble = document.createElement("div");

    bubble.className = "message" + (agentName === "boss" ? " boss" : "");
    bubble.dataset.agent = agentName;
    bubble.textContent = content;

    bubble.style.left = `${Math.min(STAGE_W - 120, Math.max(120, agent.position.x))}px`;
    bubble.style.top = `${agent.position.y - 126}px`;

    messageLayer.appendChild(bubble);

    setTimeout(() => {
        bubble.classList.add("leaving");
        setTimeout(() => bubble.remove(), 260);
    }, 3200);
}


/* =========================================================
   TASKS
========================================================= */

function taskLabel(status) {
    return status === "done" ? "Done" : status === "failed" ? "Failed" : "In progress";
}

function addTask(data) {
    tasks.unshift({
        id: data.task_id || `local-${Date.now()}`,
        agent: data.assigned_to,
        description: data.description || "Task",
        status: "assigned",
        time: new Date(),
    });

    onTasksChanged();
}

function resolveTask(data, agent, status) {
    let task = data.task_id && tasks.find(t => t.id === data.task_id);

    if (!task) task = tasks.find(t => t.agent === agent && t.status === "assigned");
    if (!task) return;

    task.status = status;
    onTasksChanged();
}

function taskRowHtml(task) {
    return `
        <div class="task-row">
            <span class="task-text" title="${escapeHtml(task.description)}">${escapeHtml(truncate(task.description, 90))}</span>
            <span class="task-who">${escapeHtml(displayName(task.agent))}</span>
            <span class="task-status ${task.status}">${taskLabel(task.status)}</span>
        </div>`;
}

function onTasksChanged() {
    const recent = tasks.slice(0, 6);

    taskList.innerHTML = recent.length
        ? recent.map(taskRowHtml).join("")
        : `<div class="empty-row">No tasks yet — ask the Boss for something.</div>`;

    const filtered = tasks.filter(t => taskFilter === "all" || t.status === taskFilter);

    $("task-history").innerHTML = filtered.length
        ? filtered.map(taskRowHtml).join("")
        : `<div class="empty-row">Nothing to show here yet.</div>`;

    const count = tasks.length;
    $("board-count").textContent = `${count} task${count === 1 ? "" : "s"} today`;

    updateStats();
    renderAgentsGrid();
}


/* =========================================================
   ACTIVITY LOG
========================================================= */

function addActivity(text) {
    const item = document.createElement("div");

    item.className = "activity-item";

    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    item.innerHTML = `
        <div class="activity-time">${time}</div>
        <div class="activity-message">${escapeHtml(text)}</div>
    `;

    activityLog.prepend(item);

    while (activityLog.children.length > 40) activityLog.lastChild.remove();
}


/* =========================================================
   EVENTS
========================================================= */

function handleEvent(event) {
    const type = event.event_type;
    const agent = event.agent;
    const data = event.data || {};

    switch (type) {

        case "connection":
        case "user_request":
            return;

        case "agent_added":
            return handleAgentAdded(event);

        case "agent_removed":
            return handleAgentRemoved(event);

        case "artifact_created":
            showArtifact(data);
            addActivity("Coder generated a project artifact");
            toast(`Project ready: ${data.project_name || "new project"}`);
            return;

        case "agent_thinking":
        case "agent_working":
        case "agent_idle": {
            const status = type.replace("agent_", "");
            setAgentState(agent, status);
            if (status !== "idle") addActivity(`${displayName(agent)} is ${status}`);
            return;
        }

        case "agent_completed":
            setAgentState(agent, "idle");
            resolveTask(data, agent, "done");
            addActivity(`${displayName(agent)} completed the task`);
            return;

        case "agent_failed":
            setAgentState(agent, "failed");
            resolveTask(data, agent, "failed");
            addActivity(`${displayName(agent)} failed${data.error ? `: ${truncate(data.error, 120)}` : ""}`);
            return;

        case "task_assigned": {
            const assignedTo = data.assigned_to;

            addActivity(`Boss assigned a task to ${displayName(assignedTo)}`);
            addTask(data);

            // worker walks to the boss, receives the task, returns to the desk
            walkToBoss(assignedTo, () => {
                showMessage("boss", "New task for you.");
                setAgentState(assignedTo, "working");
                setTimeout(() => walkToDesk(assignedTo), 900);
            });
            return;
        }

        case "message_sent": {
            const { sender, receiver, content } = data;

            addActivity(`${displayName(sender)} → ${displayName(receiver)}`);

            if (receiver === "boss") {
                walkToBoss(sender, () => {
                    showMessage(sender, truncate(content, 90));
                    setTimeout(() => walkToDesk(sender), 1800);
                });
            }
            return;
        }

        case "boss_response": {
            const message = data.message || "";

            $("boss-response-text").textContent = message;

            pendingRequests = Math.max(0, pendingRequests - 1);
            syncTyping();

            addActivity(`Boss → You: ${truncate(message, 180)}`);
            setAgentState("boss", "idle");
            showMessage("boss", "Response ready");
            return;
        }

        case "request_started":
            setAgentState("boss", "thinking");
            addActivity("Boss received a new request");
            return;

        case "request_completed":
            setAgentState("boss", "idle");
            addActivity("Boss completed the request");
            return;

        case "request_failed":
            pendingRequests = Math.max(0, pendingRequests - 1);
            syncTyping();
            setAgentState("boss", "failed");
            $("boss-response-text").textContent =
                data.error || "Request failed.";
            addActivity(`Boss request failed: ${truncate(data.error || "Unknown error", 160)}`);
            return;

        default:
            return;
    }
}


/* =========================================================
   WEBSOCKET
========================================================= */

function wsUrl() {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${window.location.host}/ws`;
}

function setConnection(state) {
    const online = state === "online";

    connectionDot.classList.toggle("online", online);
    connectionText.textContent =
        online ? "System online" :
        state === "error" ? "Connection error" :
        state === "connecting" ? "Connecting…" : "Disconnected";

    $("set-ws").textContent = online ? "connected" : state;
    $("set-endpoint").textContent = wsUrl();
}

function connectWebSocket() {
    setConnection("connecting");

    websocket = new WebSocket(wsUrl());

    websocket.onopen = () => {
        reconnectAttempts = 0;
        setConnection("online");
        addActivity("Connected to Local AI Office");
    };

    websocket.onclose = () => {
        setConnection("disconnected");

        pendingRequests = 0;
        syncTyping();

        const delay = Math.min(10000, 1500 * 2 ** reconnectAttempts++);
        setTimeout(connectWebSocket, delay);
    };

    websocket.onerror = () => setConnection("error");

    websocket.onmessage = message => {
        try {
            handleEvent(JSON.parse(message.data));
        } catch (error) {
            console.error(error);
        }
    };
}


/* =========================================================
   CHAT
========================================================= */

function syncTyping() {
    $("boss-typing").classList.toggle("hidden", pendingRequests === 0);
}

function sendMessage() {
    const input = $("chat-input");
    const message = input.value.trim();

    if (!message) return;

    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
        toast("Boss connection is not available yet.", true);
        addActivity("Boss connection is not available.");
        return;
    }

    input.value = "";

    pendingRequests++;
    syncTyping();

    $("boss-response-text").textContent = "On it — let me get the team working…";

    addActivity(`You → Boss: ${truncate(message, 160)}`);

    websocket.send(message);
}

$("send-button").addEventListener("click", sendMessage);

$("chat-input").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

$("quick-prompts").addEventListener("click", event => {
    const button = event.target.closest("button[data-prompt]");
    if (!button) return;

    const input = $("chat-input");
    input.value = button.dataset.prompt;
    input.focus();
});


/* =========================================================
   WORKSPACE (generated projects)
========================================================= */

function showArtifact(artifact) {
    if (!artifact) return;

    currentArtifact = artifact;

    selectedAgentLabel.textContent = `${artifact.project_name} · Generated project`;
    workspace.innerHTML = "";

    const execution = artifact.execution_summary || {};
    const status = artifact.status || "unknown";

    let statusLabel = "Execution status unavailable";
    let statusClass = "";

    if (execution.skipped) {
        statusLabel = "Execution skipped";
        statusClass = "";
    } else if (status === "success" && execution.return_code === 0) {
        statusLabel = "Execution check passed";
        statusClass = "ok";
    } else if (status === "failed" || (typeof execution.return_code === "number" && execution.return_code !== 0)) {
        statusLabel = "Execution check failed";
        statusClass = "bad";
    } else if (status === "success") {
        statusLabel = "Execution reported successful";
        statusClass = "ok";
    }

    workspace.insertAdjacentHTML("beforeend", `
        <div class="workspace-card">
            <div class="label">PROJECT</div>
            <div class="value">${escapeHtml(artifact.project_name)}</div>
        </div>
        <div class="workspace-card ${statusClass}">
            <div class="label">EXECUTION</div>
            <div class="value">${escapeHtml(statusLabel)}</div>
        </div>
        <div class="inspector-label" style="margin:16px 0 8px">Files</div>
    `);

    const fileList = document.createElement("div");
    fileList.className = "file-list";

    for (const file of artifact.files || []) {
        const button = document.createElement("button");

        button.className = "file-item";
        button.textContent = file.path;
        button.addEventListener("click", () =>
            openProjectFile(artifact.request_id, artifact.project_name, file.path));

        fileList.appendChild(button);
    }

    workspace.appendChild(fileList);
}

async function openProjectFile(requestId, projectName, path) {
    try {
        const query = new URLSearchParams({ project: projectName, path });
        const response = await fetch(`/projects/${encodeURIComponent(requestId)}/file?${query}`);

        if (!response.ok) throw new Error(await response.text());

        const data = await response.json();

        workspace.innerHTML = `
            <button id="back-to-files" class="back-button">← Files</button>
            <div class="code-title">${escapeHtml(data.path)}</div>
            <pre class="code-viewer"><code>${escapeHtml(data.content)}</code></pre>
        `;

        $("back-to-files").addEventListener("click", () => showArtifact(currentArtifact));

    } catch (error) {
        addActivity(`Could not open ${path}: ${error.message}`);
        toast(`Could not open ${path}`, true);
    }
}


/* =========================================================
   NAVIGATION
========================================================= */

function showView(view) {
    document.querySelectorAll(".view").forEach(el => el.classList.toggle("active", el.id === `view-${view}`));
    document.querySelectorAll(".nav-item").forEach(el => el.classList.toggle("active", el.dataset.view === view));

    if (view === "office") requestAnimationFrame(fitStage);
    if (view === "settings") checkHealth();
}

document.querySelectorAll(".nav-item").forEach(item =>
    item.addEventListener("click", () => showView(item.dataset.view)));

$("task-filters").addEventListener("click", event => {
    const chip = event.target.closest(".chip");
    if (!chip) return;

    taskFilter = chip.dataset.filter;

    document.querySelectorAll("#task-filters .chip").forEach(c => c.classList.toggle("active", c === chip));
    onTasksChanged();
});


/* =========================================================
   MODAL WIRING
========================================================= */

$("add-agent-button").addEventListener("click", openAddAgentModal);
$("add-agent-button-2").addEventListener("click", openAddAgentModal);
$("close-modal").addEventListener("click", closeAddAgentModal);
$("cancel-agent").addEventListener("click", closeAddAgentModal);
$("create-agent").addEventListener("click", createAgent);

modalBackdrop.addEventListener("mousedown", event => {
    if (event.target === modalBackdrop) closeAddAgentModal();
});

["agent-name", "agent-role"].forEach(id =>
    $(id).addEventListener("keydown", event => {
        if (event.key === "Enter") createAgent();
    }));

document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !modalBackdrop.classList.contains("hidden")) closeAddAgentModal();
});


/* =========================================================
   SETTINGS
========================================================= */

const settings = Object.assign(
    { reduceMotion: false, nameTags: true, lighting: true },
    storageGet("lao.settings", {})
);

function applySettings() {
    document.body.classList.toggle("reduce-motion", settings.reduceMotion);
    document.body.classList.toggle("no-tags", !settings.nameTags);
    document.body.classList.toggle("no-lighting", !settings.lighting);

    $("opt-reduce-motion").checked = settings.reduceMotion;
    $("opt-name-tags").checked = settings.nameTags;
    $("opt-lighting").checked = settings.lighting;
}

[
    ["opt-reduce-motion", "reduceMotion"],
    ["opt-name-tags", "nameTags"],
    ["opt-lighting", "lighting"],
].forEach(([id, key]) =>
    $(id).addEventListener("change", event => {
        settings[key] = event.target.checked;
        storageSet("lao.settings", settings);
        applySettings();
    }));

async function checkHealth() {
    const el = $("set-health");
    el.textContent = "checking…";

    try {
        const response = await fetch("/health");
        const data = await response.json();
        el.textContent = data.status || "ok";
    } catch (error) {
        el.textContent = "unreachable";
    }
}

$("recheck-health").addEventListener("click", checkHealth);


/* =========================================================
   BOOT
========================================================= */

applySettings();
fitStage();
tickClock();
setInterval(tickClock, 30000);
onTasksChanged();

loadAgents();
connectWebSocket();
