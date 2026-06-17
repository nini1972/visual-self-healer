// State variables to store visual history details
let iterationsHistory = [];
let ws = null;
let currentCode = "";
let currentLogs = [];

// DOM Elements
const startBtn = document.getElementById("start-btn");
const promptInput = document.getElementById("prompt-input");
const apiKeyInput = document.getElementById("api-key-input");
const iterationsInput = document.getElementById("iterations-input");
const terminalLogs = document.getElementById("terminal-logs");
const statusBadge = document.getElementById("status-badge");
const loopStepDisplay = document.getElementById("loop-step-display");
const previewIframe = document.getElementById("preview-iframe");
const codeViewer = document.getElementById("code-viewer");
const critiqueViewer = document.getElementById("critique-viewer");
const timelineTrack = document.getElementById("timeline-track");

// Tabs
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

// Modal Elements
const modal = document.getElementById("iteration-modal");
const closeModalBtn = document.getElementById("close-modal-btn");
const modalTitle = document.getElementById("modal-title");
const modalImg = document.getElementById("modal-img");
const modalFeedback = document.getElementById("modal-feedback");
const modalLogs = document.getElementById("modal-logs");

// Tab Navigation logic
tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");
        
        tabButtons.forEach(b => b.classList.remove("active"));
        tabPanels.forEach(p => p.classList.remove("active"));
        
        btn.classList.add("active");
        document.getElementById(targetTab).classList.add("active");
    });
});

// Logs helper
function addLogLine(level, text) {
    const line = document.createElement("div");
    line.className = `terminal-line ${level.toLowerCase()}`;
    
    // Add timestamp
    const now = new Date();
    const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
    
    line.innerHTML = `<span class="time" style="color: var(--text-muted); margin-right: 0.5rem;">[${timeStr}]</span>${text}`;
    terminalLogs.appendChild(line);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
    
    // Accumulate logs for iteration details
    currentLogs.push(`[${level}] ${text}`);
}

// Set status badge style
function setStatus(statusClass, label) {
    statusBadge.className = `status-badge ${statusClass}`;
    statusBadge.innerText = label;
}

// Reset history visual timeline
function resetTimeline() {
    timelineTrack.innerHTML = "";
    iterationsHistory = [];
}

// Handle socket message events
function handleSocketMessage(event) {
    const data = JSON.parse(event.data);
    const type = data.type;
    
    switch (type) {
        case "log":
            const level = data.level || "INFO";
            const text = data.text || "";
            
            if (level === "STATUS") {
                setStatus(text.toLowerCase().includes("generating") ? "generating" : 
                          text.toLowerCase().includes("auditing") ? "auditing" : "critiquing", text);
                addLogLine("STATUS", text);
            } else if (level === "SUCCESS") {
                setStatus("complete", "Success");
                addLogLine("SUCCESS", text);
                stopLoadingState();
            } else if (level === "WARNING") {
                setStatus("failed", "Warning");
                addLogLine("WARNING", text);
                stopLoadingState();
            } else if (level === "ERROR") {
                setStatus("failed", "Error");
                addLogLine("ERROR", text);
                stopLoadingState();
            } else {
                addLogLine(level, text);
            }
            break;
            
        case "CODE_UPDATE":
            currentCode = data.code;
            codeViewer.value = currentCode;
            loopStepDisplay.innerText = `Iteration: ${data.iteration}`;
            
            // Reload Iframe preview
            previewIframe.src = `/sandbox/index.html?t=${new Date().getTime()}`;
            break;
            
        case "AUDIT_RESULT":
            const it = data.iteration;
            // Store details for this iteration in our local history state
            if (!iterationsHistory[it]) {
                iterationsHistory[it] = {
                    iteration: it,
                    screenshot: data.screenshot,
                    logs: [...currentLogs],
                    feedback: "Awaiting visual critique...",
                    code: currentCode
                };
            } else {
                iterationsHistory[it].screenshot = data.screenshot;
                iterationsHistory[it].logs = [...currentLogs];
            }
            break;
            
        case "HEAL_RESULT":
            const iterationIndex = data.iteration;
            const feedback = data.feedback;
            const isPerfect = data.is_perfect;
            currentCode = data.code;
            codeViewer.value = currentCode;
            
            // Update the history details
            if (!iterationsHistory[iterationIndex]) {
                iterationsHistory[iterationIndex] = {
                    iteration: iterationIndex,
                    feedback: feedback,
                    code: currentCode,
                    logs: [...currentLogs],
                    screenshot: ""
                };
            } else {
                iterationsHistory[iterationIndex].feedback = feedback;
                iterationsHistory[iterationIndex].code = currentCode;
            }
            
            // Display critique details in Librarian Critique tab
            critiqueViewer.innerHTML = `
                <div class="critique-card">
                    <h4>Iteration ${iterationIndex} Visual Assessment</h4>
                    <p>${feedback.replace(/\n/g, "<br>")}</p>
                </div>
                <div class="log-summary-title">Console Errors Detected During Audit:</div>
                <div class="logs-list">
                    ${iterationsHistory[iterationIndex].logs.filter(l => l.includes("EXCEPTION") || l.includes("ERROR") || l.includes("[WARNING]")).map(l => `<div style="color: var(--accent-red); margin-bottom:0.25rem;">${l}</div>`).join("") || '<div style="color: var(--accent-green)">No exceptions or syntax errors captured.</div>'}
                </div>
            `;
            
            // Update layout frame view
            previewIframe.src = `/sandbox/index.html?t=${new Date().getTime()}`;
            
            // Append thumbnail card to Evolution timeline
            appendTimelineItem(iterationIndex, iterationsHistory[iterationIndex].screenshot, isPerfect);
            break;
    }
}

// Add thumbnail card to visual timeline track
function appendTimelineItem(iteration, screenshotB64, isPerfect) {
    // Check if timeline is empty and clear it
    const emptyTimeline = timelineTrack.querySelector(".empty-timeline");
    if (emptyTimeline) {
        timelineTrack.removeChild(emptyTimeline);
    }
    
    // Check if item already exists and replace it, or append new
    let itemDiv = document.getElementById(`timeline-item-${iteration}`);
    if (!itemDiv) {
        itemDiv = document.createElement("div");
        itemDiv.id = `timeline-item-${iteration}`;
        timelineTrack.appendChild(itemDiv);
    }
    
    itemDiv.className = `timeline-item ${isPerfect ? 'perfect' : ''}`;
    
    // Set label and image
    const label = isPerfect ? `Iter ${iteration} (Perfect)` : `Iteration ${iteration}`;
    itemDiv.innerHTML = `
        <img src="data:image/png;base64,${screenshotB64}" alt="Iteration ${iteration}">
        <div class="timeline-item-label">${label}</div>
    `;
    
    // Detail click inspect listener
    itemDiv.addEventListener("click", () => {
        openModal(iteration);
    });
}

// Modal handling
function openModal(iteration) {
    const details = iterationsHistory[iteration];
    if (!details) return;
    
    modalTitle.innerText = `Iteration ${iteration} Details`;
    modalImg.src = `data:image/png;base64,${details.screenshot}`;
    modalFeedback.innerHTML = details.feedback.replace(/\n/g, "<br>");
    modalLogs.textContent = details.logs.join("\n");
    
    modal.style.display = "flex";
}

closeModalBtn.addEventListener("click", () => {
    modal.style.display = "none";
});

window.addEventListener("click", (e) => {
    if (e.target === modal) {
        modal.style.display = "none";
    }
});

// Setup socket interface connection
function connectWebSocket() {
    // Connect to local WebSocket server
    const socketUrl = `ws://${window.location.host}/ws`;
    ws = new WebSocket(socketUrl);
    
    ws.onopen = () => {
        addLogLine("SYSTEM", "WebSocket connection opened successfully.");
    };
    
    ws.onmessage = handleSocketMessage;
    
    ws.onclose = () => {
        addLogLine("ERROR", "WebSocket connection closed. Reconnecting...");
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket error:", err);
    };
}

// Button States
function startLoadingState() {
    startBtn.classList.add("loading");
    promptInput.disabled = true;
    apiKeyInput.disabled = true;
    iterationsInput.disabled = true;
}

function stopLoadingState() {
    startBtn.classList.remove("loading");
    promptInput.disabled = false;
    apiKeyInput.disabled = false;
    iterationsInput.disabled = false;
}

// Trigger loop
startBtn.addEventListener("click", () => {
    const promptVal = promptInput.value.trim();
    if (!promptVal) {
        alert("Please enter a visual UI prompt to build.");
        return;
    }
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        resetTimeline();
        currentLogs = [];
        startLoadingState();
        
        terminalLogs.innerHTML = "";
        addLogLine("SYSTEM", "Starting self-healing UI agent...");
        
        const payload = {
            action: "start",
            prompt: promptVal,
            apiKey: apiKeyInput.value.trim(),
            maxIterations: parseInt(iterationsInput.value)
        };
        
        ws.send(JSON.stringify(payload));
    } else {
        alert("WebSocket is not connected. Re-trying...");
    }
});

// Initialize on load
window.addEventListener("DOMContentLoaded", () => {
    connectWebSocket();
});
