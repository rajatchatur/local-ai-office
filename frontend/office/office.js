let websocket = null;

let agents = {};

let selectedAgent = null;

let taskCounter = 0;


/* =====================================================
   DOM
===================================================== */

const office =
    document.getElementById("office");

const agentLayer =
    document.getElementById("agent-layer");

const deskLayer =
    document.getElementById("desk-layer");

const messageLayer =
    document.getElementById("message-layer");

const agentList =
    document.getElementById("agent-list");

const agentCount =
    document.getElementById("agent-count");

const activityLog =
    document.getElementById("activity-log");

const taskList =
    document.getElementById("task-list");

const inspectorContent =
    document.getElementById(
        "inspector-content"
    );

const modalBackdrop =
    document.getElementById(
        "modal-backdrop"
    );

const connectionDot =
    document.getElementById(
        "connection-dot"
    );

const connectionText =
    document.getElementById(
        "connection-text"
    );


/* =====================================================
   POSITIONS
===================================================== */

const defaultPositions = {

    researcher: {
        x: 170,
        y: 390
    },

    coder: {
        x: 440,
        y: 400
    },

    analyst: {
        x: 710,
        y: 390
    }

};


const bossPosition = {
    x: 540,
    y: 165
};


function getWorkerPosition(
    index
) {

    const columns = 3;

    const column =
        index % columns;

    const row =
        Math.floor(index / columns);

    return {

        x:
            140 +
            column * 270,

        y:
            390 +
            row * 120

    };
}


/* =====================================================
   LOAD AGENTS
===================================================== */

async function loadAgents() {

    try {

        const response =
            await fetch(
                "/agents"
            );


        const data =
            await response.json();


        agents = {};


        agents.boss = {

            name: "boss",

            role: "Manager",

            status: "idle",

            position:
                { ...bossPosition },

            deskPosition:
                { ...bossPosition }

        };


        let index = 0;


        for (
            const agent
            of data.agents
        ) {

            const position =
                defaultPositions[
                    agent.name
                ] ||
                getWorkerPosition(
                    index
                );


            agents[
                agent.name
            ] = {

                ...agent,

                position:
                    { ...position },

                deskPosition:
                    { ...position }

            };


            index++;
        }


        renderOffice();

        renderAgentList();

    } catch (error) {

        console.error(
            "Could not load agents",
            error
        );

        addActivity(
            "Could not load agents"
        );
    }
}


/* =====================================================
   RENDER OFFICE
===================================================== */

function renderOffice() {

    deskLayer.innerHTML = "";

    agentLayer.innerHTML = "";


    Object.values(
        agents
    ).forEach(
        agent => {

            if (
                agent.name !== "boss"
            ) {

                createDesk(
                    agent
                );

            }

            createCharacter(
                agent
            );

        }
    );
}


/* =====================================================
   CREATE DESK
===================================================== */

function createDesk(
    agent
) {

    const desk =
        document.createElement(
            "div"
        );


    desk.className =
        "desk";


    desk.dataset.agent =
        agent.name;


    desk.style.left =
        `${agent.deskPosition.x - 40}px`;


    desk.style.top =
        `${agent.deskPosition.y + 30}px`;


    desk.innerHTML = `

        <div class="desk-top"></div>

        <div class="desk-leg left"></div>

        <div class="desk-leg right"></div>

        <div class="monitor">

            <div class="screen"></div>

        </div>

    `;


    deskLayer.appendChild(
        desk
    );
}


/* =====================================================
   CREATE CHARACTER
===================================================== */

function createCharacter(
    agent
) {

    const character =
        document.createElement(
            "div"
        );


    character.id =
        `character-${agent.name}`;


    character.className =
        `character ${agent.name}`;


    character.style.left =
        `${agent.position.x}px`;


    character.style.top =
        `${agent.position.y}px`;


    character.innerHTML = `

        <div class="character-label">
            ${displayName(agent.name)}
        </div>

        <div class="head"></div>

        <div class="body"></div>

        <div class="arm left-arm"></div>

        <div class="arm right-arm"></div>

        <div class="leg left-leg"></div>

        <div class="leg right-leg"></div>

    `;


    character.addEventListener(
        "click",
        () => {

            selectAgent(
                agent.name
            );

        }
    );


    agentLayer.appendChild(
        character
    );
}


/* =====================================================
   DISPLAY NAME
===================================================== */

function displayName(
    name
) {

    return name
        .replaceAll(
            "_",
            " "
        )
        .replace(
            /\b\w/g,
            letter =>
                letter.toUpperCase()
        );
}


/* =====================================================
   AGENT LIST
===================================================== */

function renderAgentList() {

    agentList.innerHTML = "";


    Object.values(
        agents
    ).forEach(
        agent => {

            const card =
                document.createElement(
                    "div"
                );


            card.className =
                "agent-card";


            card.innerHTML = `

                <div class="agent-avatar">
                    ${getAgentIcon(agent.name)}
                </div>

                <div class="agent-info">

                    <div class="agent-name">
                        ${displayName(agent.name)}
                    </div>

                    <div class="agent-role">
                        ${agent.role}
                    </div>

                    <div
                        class="agent-status"
                        data-status="${agent.name}"
                    >
                        ● ${agent.status || "idle"}
                    </div>

                </div>

            `;


            card.addEventListener(
                "click",
                () => {

                    selectAgent(
                        agent.name
                    );

                }
            );


            agentList.appendChild(
                card
            );

        }
    );


    agentCount.textContent =
        Object.keys(
            agents
        ).length;
}


/* =====================================================
   ICON
===================================================== */

function getAgentIcon(
    name
) {

    if (
        name.includes(
            "research"
        )
    ) {
        return "R";
    }

    if (
        name.includes(
            "code"
        )
    ) {
        return "</>";
    }

    if (
        name.includes(
            "anal"
        )
    ) {
        return "A";
    }

    if (
        name.includes(
            "data"
        )
    ) {
        return "D";
    }

    return "AI";
}


/* =====================================================
   SELECT AGENT
===================================================== */

function selectAgent(
    name
) {

    selectedAgent =
        name;


    const agent =
        agents[name];


    if (!agent) {
        return;
    }


    inspectorContent.innerHTML = `

        <div class="inspector-name">
            ${displayName(agent.name)}
        </div>

        <div class="inspector-role">
            ${agent.role}
        </div>

        <div class="inspector-status">
            ● ${agent.status || "idle"}
        </div>

        <div class="inspector-section">

            <div class="inspector-label">
                Current Status
            </div>

            <div class="inspector-value">
                ${agent.status || "idle"}
            </div>

        </div>

        <div class="inspector-section">

            <div class="inspector-label">
                Agent
            </div>

            <div class="inspector-value">
                ${agent.name}
            </div>

        </div>

        ${
            name !== "boss"
            ? `
                <button
                    class="remove-agent"
                    onclick="removeSelectedAgent()"
                >
                    Remove Agent
                </button>
            `
            : ""
        }

    `;
}


/* =====================================================
   ADD AGENT
===================================================== */

function openAddAgentModal() {

    modalBackdrop.classList.remove(
        "hidden"
    );
}


function closeAddAgentModal() {

    modalBackdrop.classList.add(
        "hidden"
    );
}


document
    .getElementById(
        "add-agent-button"
    )
    .addEventListener(
        "click",
        openAddAgentModal
    );


document
    .getElementById(
        "close-modal"
    )
    .addEventListener(
        "click",
        closeAddAgentModal
    );


document
    .getElementById(
        "cancel-agent"
    )
    .addEventListener(
        "click",
        closeAddAgentModal
    );


/* =====================================================
   CREATE AGENT
===================================================== */

document
    .getElementById(
        "create-agent"
    )
    .addEventListener(
        "click",
        async () => {

            const name =
                document
                    .getElementById(
                        "agent-name"
                    )
                    .value
                    .trim();

            const role =
                document
                    .getElementById(
                        "agent-role"
                    )
                    .value
                    .trim();

            const instructions =
                document
                    .getElementById(
                        "agent-instructions"
                    )
                    .value
                    .trim();


            if (
                !name ||
                !role
            ) {

                alert(
                    "Name and role are required."
                );

                return;
            }


            try {

                const response =
                    await fetch(
                        "/agents",
                        {

                            method:
                                "POST",

                            headers: {

                                "Content-Type":
                                    "application/json"

                            },

                            body:
                                JSON.stringify({

                                    name,

                                    role,

                                    instructions

                                })

                        }
                    );


                const data =
                    await response.json();


                if (
                    !response.ok
                ) {

                    throw new Error(
                        data.detail ||
                        "Could not create agent"
                    );

                }


                closeAddAgentModal();


                addActivity(
                    `Added agent: ${displayName(name)}`
                );


            } catch (error) {

                alert(
                    error.message
                );

            }

        }
    );


/* =====================================================
   REMOVE AGENT
===================================================== */

async function removeSelectedAgent() {

    if (
        !selectedAgent ||
        selectedAgent === "boss"
    ) {

        return;
    }


    const name =
        selectedAgent;


    try {

        const response =
            await fetch(
                `/agents/${encodeURIComponent(name)}`,
                {
                    method:
                        "DELETE"
                }
            );


        const data =
            await response.json();


        if (
            !response.ok
        ) {

            throw new Error(
                data.detail ||
                "Could not remove agent"
            );
        }


        selectedAgent =
            null;


        addActivity(
            `Removed agent: ${displayName(name)}`
        );


    } catch (error) {

        alert(
            error.message
        );
    }
}


/* =====================================================
   WEBSOCKET
===================================================== */

function connectWebSocket() {

    websocket =
        new WebSocket(
            `ws://${window.location.host}/ws`
        );


    websocket.onopen = () => {

        connectionDot.classList.add(
            "online"
        );

        connectionText.textContent =
            "System Online";

        addActivity(
            "Connected to Local AI Office"
        );
    };


    websocket.onclose = () => {

        connectionDot.classList.remove(
            "online"
        );

        connectionText.textContent =
            "Disconnected";

        setTimeout(
            connectWebSocket,
            2500
        );
    };


    websocket.onerror = () => {

        connectionText.textContent =
            "Connection Error";
    };


    websocket.onmessage = (
        message
    ) => {

        try {

            const event =
                JSON.parse(
                    message.data
                );


            handleEvent(
                event
            );

        } catch (error) {

            console.error(
                error
            );

        }

    };
}


/* =====================================================
   EVENT HANDLER
===================================================== */

function handleEvent(event) {

    const type =
        event.event_type;

    const agent =
        event.agent;

    const data =
        event.data || {};


    /* =================================================
       CONNECTION
    ================================================= */

    if (type === "connection") {
        return;
    }


    /* =================================================
       AGENT MANAGEMENT
    ================================================= */

    if (type === "agent_added") {

        handleAgentAdded(event);

        return;
    }


    if (type === "agent_removed") {

        handleAgentRemoved(event);

        return;
    }


    /* =================================================
       ARTIFACT
    ================================================= */

    if (type === "artifact_created") {

        showArtifact(data);

        addActivity(
            "Boss generated a project artifact"
        );

        return;
    }


    /* =================================================
       BOSS THINKING
    ================================================= */

    if (type === "agent_thinking") {

        setAgentState(
            agent,
            "thinking"
        );

        addActivity(
            `${displayName(agent)} is thinking`
        );

        return;
    }


    /* =================================================
       WORKING
    ================================================= */

    if (type === "agent_working") {

        setAgentState(
            agent,
            "working"
        );

        addActivity(
            `${displayName(agent)} is working`
        );

        return;
    }


    /* =================================================
       COMPLETED
    ================================================= */

    if (type === "agent_completed") {

        setAgentState(
            agent,
            "idle"
        );

        addActivity(
            `${displayName(agent)} completed the task`
        );

        return;
    }


    /* =================================================
       FAILED
    ================================================= */

    if (type === "agent_failed") {

        setAgentState(
            agent,
            "failed"
        );

        addActivity(
            `${displayName(agent)} failed`
        );

        return;
    }


    /* =================================================
       TASK ASSIGNED
    ================================================= */

    if (type === "task_assigned") {

        const assignedTo =
            data.assigned_to;


        addActivity(
            `Boss assigned a task to ${displayName(assignedTo)}`
        );


        addTask(data);


        /*
         * Physical office interaction:
         *
         * worker leaves desk
         *        ↓
         * walks to boss
         *        ↓
         * receives assignment
         *        ↓
         * walks back
         *        ↓
         * starts working
         */

        walkToBoss(
            assignedTo,
            () => {

                showMessage(
                    "boss",
                    "New task for you."
                );


                setAgentState(
                    assignedTo,
                    "working"
                );


                setTimeout(
                    () => {

                        walkToDesk(
                            assignedTo
                        );

                    },
                    900
                );

            }
        );

        return;
    }


    /* =================================================
       MESSAGE
    ================================================= */

    if (type === "message_sent") {

        const sender =
            data.sender;

        const receiver =
            data.receiver;

        const content =
            data.content;


        addActivity(
            `${displayName(sender)} → ${displayName(receiver)}`
        );


        /*
         * Worker delivering result
         */

        if (receiver === "boss") {

            walkToBoss(
                sender,
                () => {

                    showMessage(
                        sender,
                        truncate(
                            content,
                            90
                        )
                    );


                    setTimeout(
                        () => {

                            walkToDesk(
                                sender
                            );

                        },
                        1800
                    );

                }
            );
        }

        return;
    }

/* =================================================
   BOSS RESPONSE
================================================= */

if (type === "boss_response") {

    const message =
        data.message || "";

    const responseText =
        document.getElementById("boss-response-text");

    if (responseText) {
        responseText.textContent = message;
    }

    addActivity(
        `Boss → You: ${truncate(message, 180)}`
    );

    setAgentState(
        "boss",
        "idle"
    );

    showMessage(
        "boss",
        "Response ready"
    );

    return;
}

    /* =================================================
       REQUEST START
    ================================================= */

    if (type === "request_started") {

        setAgentState(
            "boss",
            "thinking"
        );

        addActivity(
            "Boss received a new request"
        );

        return;
    }


    /* =================================================
       REQUEST COMPLETE
    ================================================= */

    if (type === "request_completed") {

        setAgentState(
            "boss",
            "idle"
        );

        addActivity(
            "Boss completed the request"
        );

        return;
    }


    /* =================================================
       REQUEST FAILED
    ================================================= */

    if (type === "request_failed") {

    setAgentState(
        "boss",
        "failed"
    );

    const errorMessage =
        data.error || "Unknown error";

    addActivity(
        `Boss request failed: ${truncate(errorMessage, 160)}`
    );

    return;
}
}




/* =====================================================
   AGENT ADDED
===================================================== */

function handleAgentAdded(
    event
) {

    const data =
        event.data;


    const name =
        data.name;


    if (
        agents[name]
    ) {

        return;
    }


    const workerNames =
        Object.keys(
            agents
        ).filter(
            name =>
                name !== "boss"
        );


    const position =
        getWorkerPosition(
            workerNames.length
        );


    agents[name] = {

        name,

        role:
            data.role,

        status:
            "idle",

        position:
            { ...position },

        deskPosition:
            { ...position }

    };


    renderOffice();

    renderAgentList();


    addActivity(
        `${displayName(name)} joined the office`
    );
}


/* =====================================================
   AGENT REMOVED
===================================================== */

function handleAgentRemoved(
    event
) {

    const name =
        event.data?.name ||
        event.agent;


    delete agents[name];


    renderOffice();

    renderAgentList();


    if (
        selectedAgent === name
    ) {

        selectedAgent =
            null;


        inspectorContent.innerHTML = `

            <div class="empty-inspector">
                Select an agent to inspect it.
            </div>

        `;

    }


    addActivity(
        `${displayName(name)} left the office`
    );
}


/* =====================================================
   STATE
===================================================== */

function setAgentState(
    name,
    status
) {

    const agent =
        agents[name];


    if (!agent) {
        return;
    }


    agent.status =
        status;


    const character =
        document.getElementById(
            `character-${name}`
        );


    if (
        character
    ) {

        character.classList.remove(
            "working"
        );


        if (
            status === "working"
        ) {

            character.classList.add(
                "working"
            );

        }

    }


    renderAgentList();


    if (
        selectedAgent === name
    ) {

        selectAgent(
            name
        );

    }
}


/* =====================================================
   WALK TO BOSS
===================================================== */

function moveCharacter(
    name,
    target,
    duration = 1800,
    callback = null
) {

    const agent =
        agents[name];

    if (!agent) {
        return;
    }


    const character =
        document.getElementById(
            `character-${name}`
        );

    if (!character) {
        return;
    }


    /*
     * Determine walking direction.
     */

    const movingRight =
        target.x > agent.position.x;


    if (movingRight) {

        character.classList.add(
            "facing-right"
        );

        character.classList.remove(
            "facing-left"
        );

    } else {

        character.classList.add(
            "facing-left"
        );

        character.classList.remove(
            "facing-right"
        );
    }


    /*
     * Start walking animation.
     */

    character.classList.remove(
        "working"
    );

    character.classList.add(
        "walking"
    );


    /*
     * Tell browser how long
     * the movement should take.
     */

    character.style.setProperty(
        "--walk-duration",
        `${duration}ms`
    );


    /*
     * Update logical position.
     */

    agent.position = {
        x: target.x,
        y: target.y
    };


    /*
     * Physical movement.
     */

    character.style.left =
        `${target.x}px`;

    character.style.top =
        `${target.y}px`;


    /*
     * Wait until character reaches
     * destination.
     */

    setTimeout(
        () => {

            character.classList.remove(
                "walking"
            );


            if (callback) {
                callback();
            }

        },
        duration
    );
}


/* =====================================================
   WALK TO BOSS
===================================================== */

function walkToBoss(
    name,
    callback
) {

    const agent =
        agents[name];


    if (
        !agent ||
        name === "boss"
    ) {

        if (callback) {
            callback();
        }

        return;
    }


    const target = {

        x:
            bossPosition.x - 25,

        y:
            bossPosition.y + 92

    };


    moveCharacter(
        name,
        target,
        1800,
        callback
    );
}


/* =====================================================
   WALK TO DESK
===================================================== */

function walkToDesk(
    name,
    callback = null
) {

    const agent =
        agents[name];


    if (!agent) {
        return;
    }


    moveCharacter(
        name,
        {
            x:
                agent.deskPosition.x,

            y:
                agent.deskPosition.y

        },
        1800,
        callback
    );
}



/* =====================================================
   MESSAGE BUBBLE
===================================================== */

function showMessage(
    agentName,
    content
) {

    const agent =
        agents[agentName];


    if (!agent) {
        return;
    }


    const bubble =
        document.createElement(
            "div"
        );


    bubble.className =
        "message";


    bubble.textContent =
        content;


    bubble.style.left =
        `${agent.position.x + 40}px`;


    bubble.style.top =
        `${agent.position.y - 40}px`;


    messageLayer.appendChild(
        bubble
    );


    setTimeout(
        () => {

            bubble.remove();

        },
        3000
    );
}


/* =====================================================
   TASKS
===================================================== */

function addTask(
    data
) {

    taskCounter++;


    const row =
        document.createElement(
            "div"
        );


    row.className =
        "task-row";


    row.innerHTML = `

        <span>
            ${truncate(
                data.description || "Task",
                55
            )}
        </span>

        <span class="task-status">
            Assigned
        </span>

    `;


    taskList.prepend(
        row
    );


    while (
        taskList.children.length > 5
    ) {

        taskList.lastChild.remove();

    }
}


/* =====================================================
   ACTIVITY
===================================================== */

function addActivity(
    text
) {

    const item =
        document.createElement(
            "div"
        );


    item.className =
        "activity-item";


    const time =
        new Date()
            .toLocaleTimeString(
                [],
                {
                    hour: "2-digit",
                    minute: "2-digit"
                }
            );


    item.innerHTML = `

        <div class="activity-time">
            ${time}
        </div>

        <div class="activity-message">
            ${escapeHtml(text)}
        </div>

    `;


    activityLog.prepend(
        item
    );


    while (
        activityLog.children.length > 25
    ) {

        activityLog.lastChild.remove();

    }
}


/* =====================================================
   CHAT
===================================================== */

async function sendMessage() {

    const input =
        document.getElementById(
            "chat-input"
        );


    const message =
        input.value.trim();


    if (!message) {
        return;
    }


    if (
        !websocket ||
        websocket.readyState !== WebSocket.OPEN
    ) {

        addActivity(
            "Boss connection is not available."
        );

        return;
    }


    input.value = "";


    addActivity(
        `You → Boss: ${message}`
    );


    websocket.send(message);
}


document
    .getElementById(
        "send-button"
    )
    .addEventListener(
        "click",
        sendMessage
    );


document
    .getElementById(
        "chat-input"
    )
    .addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                sendMessage();

            }

        }
    );


/* =====================================================
   HELPERS
===================================================== */

function truncate(
    text,
    length
) {

    if (
        !text
    ) {

        return "";

    }


    if (
        text.length <= length
    ) {

        return text;

    }


    return (
        text.substring(
            0,
            length
        ) +
        "..."
    );
}


function escapeHtml(
    text
) {

    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        text;


    return div.innerHTML;
}


/* =====================================================
   START
===================================================== */

loadAgents();

connectWebSocket();

const workspace = document.getElementById("workspace");
const selectedAgentLabel = document.getElementById("selected-agent-label");

let currentArtifact = null;



function showArtifact(artifact) {

    if (!artifact) {
        return;
    }

    currentArtifact = artifact;

    selectedAgentLabel.textContent =
        `${artifact.project_name} · Generated project`;

    workspace.innerHTML = "";

    const projectCard =
        document.createElement("div");

    projectCard.className =
        "workspace-card";

    projectCard.innerHTML = `
        <div class="label">PROJECT</div>

        <div class="value">
            ${escapeHtml(
                artifact.project_name
            )}
        </div>
    `;

    workspace.appendChild(
        projectCard
    );
    const statusCard = document.createElement("div");
    statusCard.className = "workspace-card";

    const execution = artifact.execution_summary || {};
    const status = artifact.status || "unknown";

    let statusLabel = "Execution status unavailable";

    if (status === "success" && execution.return_code === 0) {
        statusLabel = "Execution check passed";
    } else if (status === "failed" || (
        typeof execution.return_code === "number" &&
        execution.return_code !== 0
    )) {
        statusLabel = "Execution check failed";
    } else if (status === "success") {
        statusLabel = "Execution reported successful";
    }

    statusCard.innerHTML = `
        <div class="label">EXECUTION</div>
        <div class="value">${escapeHtml(statusLabel)}</div>
    `;

    workspace.appendChild(statusCard);

    const outputCard = document.createElement("div");
    outputCard.className = "workspace-card";

    const stdout = execution.stdout || "";
    const stderr = execution.stderr || "";

    outputCard.innerHTML = `
        <div class="label">PROGRAM OUTPUT</div>
        <pre class="value program-output"></pre>
    `;

    outputCard.querySelector("pre").textContent =
        stdout || "(No standard output)";

    workspace.appendChild(outputCard);

    if (stderr) {
        const errorCard = document.createElement("div");
        errorCard.className = "workspace-card";

        errorCard.innerHTML = `
            <div class="label">ERROR OUTPUT</div>
            <pre class="value program-output"></pre>
        `;

        errorCard.querySelector("pre").textContent = stderr;
        workspace.appendChild(errorCard);
    }

    if (typeof execution.return_code === "number") {
        const exitCard = document.createElement("div");
        exitCard.className = "workspace-card";

        exitCard.innerHTML = `
            <div class="label">EXIT CODE</div>
            <div class="value"></div>
        `;

        exitCard.querySelector(".value").textContent =
            String(execution.return_code);

        workspace.appendChild(exitCard);
    }

    const title =
        document.createElement("div");

    title.className =
        "panel-title";

    title.textContent =
        "FILES";

    title.style.margin =
        "18px 0 10px";

    workspace.appendChild(
        title
    );

    const fileList =
        document.createElement("div");

    fileList.className =
        "file-list";

    for (
        const file
        of artifact.files || []
    ) {

        const button =
            document.createElement(
                "button"
            );

        button.className =
            "file-item";

        button.textContent =
            file.path;

        button.addEventListener(
            "click",
            () => openProjectFile(
                artifact.request_id,
                artifact.project_name,
                file.path
            )
        );

        fileList.appendChild(
            button
        );
    }

    workspace.appendChild(
        fileList
    );
}


async function openProjectFile(
    requestId,
    projectName,
    path
) {

    try {

        const query =
            new URLSearchParams({
                project: projectName,
                path,
            });

        const response =
            await fetch(
                `/projects/${encodeURIComponent(
                    requestId
                )}/file?${query}`
            );

        if (!response.ok) {

            throw new Error(
                await response.text()
            );
        }

        const data =
            await response.json();

        workspace.innerHTML = `
            <button
                id="back-to-files"
                class="back-button"
            >
                ← Files
            </button>

            <div class="code-title">
                ${escapeHtml(data.path)}
            </div>

            <pre class="code-viewer"><code>${escapeHtml(
                data.content
            )}</code></pre>
        `;

        document
            .getElementById(
                "back-to-files"
            )
            .addEventListener(
                "click",
                () => showArtifact(
                    currentArtifact
                )
            );

    } catch (error) {

        addActivity(
            `Could not open ${path}: ${error.message}`
        );
    }
}