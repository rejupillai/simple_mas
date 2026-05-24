/* ----------------------------------------------------------------------
   Aura Luxury Swarm Console - Interactive JS Controller
   Orchestrates WebSockets / SSE Streams and SVG Swarm Net
   ---------------------------------------------------------------------- */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Application State Variables
    let agents = [];
    let activeAgentName = 'AuraTriage';
    let lastActiveAgentName = null;
    let sessionId = localStorage.getItem('aura_session_id');
    let isStreaming = false;

    // Generate custom session ID if not present
    if (!sessionId) {
        sessionId = 'AURA_' + Math.random().toString(36).substring(2, 8).toUpperCase();
        localStorage.setItem('aura_session_id', sessionId);
    }
    document.getElementById('session-id-display').innerText = sessionId;

    // Direct pixel-perfect coordinate mapping for the 5 Swarm nodes
    function getAgentCoords(agentName) {
        const coords = {
            "AuraTriage": { x: 170, y: 45 },
            "SuiteBooking": { x: 260, y: 110 },
            "DiningAndSpa": { x: 225, y: 195 },
            "VIPActivities": { x: 115, y: 195 },
            "BillingAndCustom": { x: 80, y: 110 }
        };
        return coords[agentName] || { x: 170, y: 120 };
    }

    // ----------------------------------------------------------------------
    // 2. Fetch Agents & Initialize Dashboard
    // ----------------------------------------------------------------------
    async function initializeDashboard() {
        try {
            const res = await fetch('/api/agents');
            agents = await res.json();
            
            // Draw static/interactive elements
            drawTopology();
            updateActiveAgentUI(activeAgentName);
            drawMiniIndicators();
            
            // Initial state pull
            await refreshTelemetry();
            
            // Set up clean background poller (every 4 seconds)
            setInterval(() => {
                if (!isStreaming) {
                    refreshTelemetry();
                }
            }, 4000);
            
        } catch (err) {
            console.error("Dashboard initialization failed:", err);
            addLocalAuditLog("System", "ERROR", "Failed to retrieve swarm agent definitions from server.");
        }
    }

    // ----------------------------------------------------------------------
    // 3. SVG Topology Dynamic Drawing
    // ----------------------------------------------------------------------
    function drawTopology() {
        const svg = document.getElementById('topology-svg');
        if (!svg) return;

        svg.innerHTML = '';

        // Draw reusable definitions (Glow filters, marker heads)
        const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.innerHTML = `
            <filter id="glow-filter" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="3.5" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
        `;
        svg.appendChild(defs);

        const activeAgentObj = agents.find(a => a.name === activeAgentName) || { accent: "hsl(38, 92%, 50%)" };
        const activeAccent = activeAgentObj.accent;

        // Connections mapping - 10 peer relationships in fully decentralized mesh
        const connections = [
            ["AuraTriage", "SuiteBooking"],
            ["AuraTriage", "DiningAndSpa"],
            ["AuraTriage", "VIPActivities"],
            ["AuraTriage", "BillingAndCustom"],
            ["SuiteBooking", "DiningAndSpa"],
            ["SuiteBooking", "VIPActivities"],
            ["SuiteBooking", "BillingAndCustom"],
            ["DiningAndSpa", "VIPActivities"],
            ["DiningAndSpa", "BillingAndCustom"],
            ["VIPActivities", "BillingAndCustom"]
        ];

        // Draw standard faint network background lines
        connections.forEach(([n1, n2]) => {
            const p1 = getAgentCoords(n1);
            const p2 = getAgentCoords(n2);
            
            // Skip drawing if it is currently an active handoff link (we draw glowing link instead)
            if (lastActiveAgentName && 
                ((lastActiveAgentName === n1 && activeAgentName === n2) || 
                 (lastActiveAgentName === n2 && activeAgentName === n1))) {
                return;
            }

            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", p1.x);
            line.setAttribute("y1", p1.y);
            line.setAttribute("x2", p2.x);
            line.setAttribute("y2", p2.y);
            line.setAttribute("class", "svg-link");
            line.setAttribute("stroke", "rgba(255, 255, 255, 0.05)");
            line.setAttribute("stroke-width", "1");
            svg.appendChild(line);
        });

        // Draw ACTIVE dynamic handoff laser line + traveling animation
        if (lastActiveAgentName && lastActiveAgentName !== activeAgentName) {
            const src = getAgentCoords(lastActiveAgentName);
            const dst = getAgentCoords(activeAgentName);
            const activePathId = `handoff-path-${lastActiveAgentName}-${activeAgentName}`;

            // Pulse handoff line
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("id", activePathId);
            path.setAttribute("d", `M ${src.x} ${src.y} L ${dst.x} ${dst.y}`);
            path.setAttribute("class", "svg-link active");
            path.setAttribute("stroke", activeAccent);
            path.setAttribute("stroke-width", "2.5");
            path.setAttribute("fill", "none");
            path.style.filter = "drop-shadow(0 0 4px " + activeAccent + ")";
            svg.appendChild(path);

            // Laser glowing traveling particle dot
            const travellingDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            travellingDot.setAttribute("r", "5");
            travellingDot.setAttribute("fill", activeAccent);
            travellingDot.setAttribute("filter", "url(#glow-filter)");

            const animMotion = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
            animMotion.setAttribute("dur", "1.4s");
            animMotion.setAttribute("repeatCount", "indefinite");

            const mpath = document.createElementNS("http://www.w3.org/2000/svg", "mpath");
            mpath.setAttributeNS("http://www.w3.org/1999/xlink", "href", `#${activePathId}`);
            
            animMotion.appendChild(mpath);
            travellingDot.appendChild(animMotion);
            svg.appendChild(travellingDot);
        }

        // Draw Swarm Nodes (Agent Circles)
        agents.forEach(agent => {
            const coord = getAgentCoords(agent.name);
            const isActive = (agent.name === activeAgentName);

            const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
            group.setAttribute("class", `svg-node ${isActive ? 'active' : ''}`);
            group.setAttribute("transform", `translate(${coord.x}, ${coord.y})`);
            
            // Hover / click handler to inspect node
            group.addEventListener('click', () => {
                updateActiveAgentUI(agent.name);
            });

            // Outer dashed glowing breathing ring
            const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            ring.setAttribute("class", "svg-node-ring");
            ring.setAttribute("r", isActive ? "24" : "21");
            ring.setAttribute("fill", "none");
            ring.setAttribute("stroke", agent.accent);
            ring.setAttribute("stroke-width", isActive ? "2" : "1");
            ring.setAttribute("stroke-opacity", isActive ? "0.9" : "0.35");
            if (isActive) {
                ring.setAttribute("stroke-dasharray", "4, 2");
                ring.style.filter = "drop-shadow(0 0 6px " + agent.accent + ")";
            }
            group.appendChild(ring);

            // Inner solid capsule core
            const core = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            core.setAttribute("r", "16");
            core.setAttribute("fill", "#050811");
            core.setAttribute("stroke", agent.accent);
            core.setAttribute("stroke-width", isActive ? "2" : "1.5");
            group.appendChild(core);

            // Agent Emblem/Icon
            const iconText = document.createElementNS("http://www.w3.org/2000/svg", "text");
            iconText.setAttribute("y", "5");
            iconText.setAttribute("text-anchor", "middle");
            iconText.setAttribute("font-size", isActive ? "16" : "14");
            iconText.style.cursor = "pointer";
            iconText.textContent = agent.icon;
            group.appendChild(iconText);

            // Agent Label
            const labelText = document.createElementNS("http://www.w3.org/2000/svg", "text");
            labelText.setAttribute("y", "31");
            labelText.setAttribute("text-anchor", "middle");
            labelText.setAttribute("fill", isActive ? "#ffffff" : "var(--text-muted)");
            labelText.setAttribute("font-size", "8.5");
            labelText.setAttribute("font-family", "var(--font-heading)");
            labelText.setAttribute("font-weight", isActive ? "700" : "600");
            labelText.textContent = agent.name;
            group.appendChild(labelText);

            svg.appendChild(group);
        });
    }

    // ----------------------------------------------------------------------
    // 4. Update Left Panel Profiler UI
    // ----------------------------------------------------------------------
    function updateActiveAgentUI(agentName) {
        const agent = agents.find(a => a.name === agentName);
        if (!agent) return;

        // Set layout design token accents dynamically
        document.documentElement.style.setProperty('--agent-accent', agent.accent);
        
        const cardGlowMap = {
            "AuraTriage": "var(--glow-gold)",
            "SuiteBooking": "var(--glow-green)",
            "DiningAndSpa": "var(--glow-pink)",
            "VIPActivities": "var(--glow-purple)",
            "BillingAndCustom": "var(--glow-blue)"
        };
        document.documentElement.style.setProperty('--agent-glow', cardGlowMap[agent.name] || 'var(--glow-gold)');

        // Left Panel Elements
        document.getElementById('active-agent-avatar').innerText = agent.icon;
        document.getElementById('active-agent-name').innerText = agent.name;
        document.getElementById('active-agent-title').innerText = agent.title_desc;
        document.getElementById('active-agent-desc').innerText = agent.description;
        
        // System Directives scroll
        document.getElementById('active-agent-directives').textContent = agent.instruction;

        // Fill Agent Capabilities
        const toolsContainer = document.getElementById('active-agent-tools');
        toolsContainer.innerHTML = '';
        agent.tools.forEach(tool => {
            const pill = document.createElement('div');
            pill.className = 'tool-pill';
            
            pill.innerHTML = `
                <div class="tool-header-row">
                    <span class="tool-name-code">${tool.name}</span>
                    <span class="tool-args-code">${tool.args}</span>
                </div>
                <div class="tool-desc-text">${tool.doc}</div>
            `;
            toolsContainer.appendChild(pill);
        });

        // Sync viewport statuses
        document.getElementById('current-agent-status').innerText = `${agent.name} is currently listening...`;
        
        // Update top-right mini viewport status rows
        drawMiniIndicators();
    }

    // ----------------------------------------------------------------------
    // 5. Draw Mini Agent Viewport Indicators
    // ----------------------------------------------------------------------
    function drawMiniIndicators() {
        const container = document.getElementById('active-indicator-row');
        if (!container) return;

        container.innerHTML = '';
        agents.forEach(agent => {
            const isActive = (agent.name === activeAgentName);
            const indicator = document.createElement('div');
            indicator.className = `agent-mini-indicator ${isActive ? 'active' : ''}`;
            indicator.style.setProperty('--mini-accent', agent.accent);
            indicator.setAttribute('title', `${agent.name}: ${agent.title_desc}`);
            indicator.innerHTML = agent.icon;
            
            // Clicking a mini-avatar can inspect them
            indicator.addEventListener('click', () => {
                updateActiveAgentUI(agent.name);
            });

            container.appendChild(indicator);
        });
    }

    // ----------------------------------------------------------------------
    // 6. Local Markdown Parser
    // ----------------------------------------------------------------------
    function parseMarkdown(text) {
        if (!text) return "";
        let html = text;
        
        // Escape HTML
        html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Bold formatting
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Italic formatting
        html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Code formatting
        html = html.replace(/`(.*?)`/g, '<code class="code-inline" style="background: rgba(0,0,0,0.3); padding: 2px 5px; border-radius: 4px; font-family: var(--font-mono); font-size: 11.5px; color: #38bdf8;">$1</code>');
        
        // Bullet points
        html = html.replace(/^\s*[-*]\s+(.*)$/gm, '<li style="margin-left: 15px; margin-bottom: 3px;">$1</li>');
        
        // Linebreaks
        html = html.replace(/\n/g, '<br>');
        
        return html;
    }

    // ----------------------------------------------------------------------
    // 7. Chat Streaming Handler & SSE Engine
    // ----------------------------------------------------------------------
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const messagesContainer = document.getElementById('chat-messages');

    // Create & manage typing indicator
    function showTypingIndicator() {
        removeTypingIndicator();
        const indicator = document.createElement('div');
        indicator.id = 'typing-indicator';
        indicator.className = 'typing-bubble';
        indicator.innerHTML = `
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        `;
        messagesContainer.appendChild(indicator);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function removeTypingIndicator() {
        const ind = document.getElementById('typing-indicator');
        if (ind) ind.remove();
    }

    // Dynamic handoff card announcements in Chat stream
    function appendHandoffCard(sourceAgent, targetAgentName) {
        const tgtAgent = agents.find(a => a.name === targetAgentName) || { accent: "hsl(38, 92%, 50%)" };
        
        const card = document.createElement('div');
        card.className = 'handoff-card';
        card.style.setProperty('--handoff-color', tgtAgent.accent);
        card.innerHTML = `
            <span class="handoff-text">Handoff Control: ${sourceAgent}</span>
            <span class="btn-icon">➔</span>
            <span class="handoff-to-agent">${targetAgentName}</span>
        `;
        messagesContainer.appendChild(card);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Get or update message bubble
    function appendOrUpdateAgentMessage(author, text) {
        const agent = agents.find(a => a.name === author) || { accent: "hsl(38, 92%, 50%)" };
        
        // See if the last bubble is from the same agent
        const lastChild = messagesContainer.lastElementChild;
        if (lastChild && lastChild.classList.contains('msg-bubble') && 
            lastChild.classList.contains('agent-msg') && 
            lastChild.getAttribute('data-author') === author) {
            
            // Accumulate stream
            const body = lastChild.querySelector('.msg-body');
            const originalText = lastChild.getAttribute('data-raw-text') || "";
            const newText = originalText + text;
            lastChild.setAttribute('data-raw-text', newText);
            body.innerHTML = parseMarkdown(newText);
        } else {
            // Create a brand new bubble
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble agent-msg';
            bubble.setAttribute('data-author', author);
            bubble.setAttribute('data-raw-text', text);
            bubble.style.setProperty('--msg-accent', agent.accent);
            
            bubble.innerHTML = `
                <div class="msg-meta" style="color: ${agent.accent};">${author}</div>
                <div class="msg-body">${parseMarkdown(text)}</div>
            `;
            messagesContainer.appendChild(bubble);
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Add User input bubble
    function appendUserMessage(messageText) {
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble user-msg';
        bubble.innerHTML = `
            <div class="msg-meta">Elite Guest</div>
            <div class="msg-body">${parseMarkdown(messageText)}</div>
        `;
        messagesContainer.appendChild(bubble);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Tool execution tracking block builder
    function createOrUpdateTraceBlock(invocationId, agentName, toolName, args, response) {
        const traceId = `trace-${invocationId}`;
        let block = document.getElementById(traceId);
        
        if (!block) {
            block = document.createElement('div');
            block.id = traceId;
            block.className = 'trace-block';
            
            const argString = typeof args === 'object' ? JSON.stringify(args, null, 2) : args;
            
            block.innerHTML = `
                <div class="trace-header">
                    <div class="trace-spinner"></div>
                    <span>${agentName} calls ${toolName}...</span>
                </div>
                <div class="trace-body-expand">
                    <div class="trace-args">Arguments: ${argString}</div>
                </div>
            `;
            messagesContainer.appendChild(block);
        }

        // If response is present, update trace block to completed state
        if (response) {
            const spinner = block.querySelector('.trace-spinner');
            if (spinner) {
                // Swap spinner out for elegant checkmark
                spinner.remove();
                const checkmark = document.createElement('span');
                checkmark.style.color = '#10b981';
                checkmark.style.marginRight = '6px';
                checkmark.innerText = '✓';
                block.querySelector('.trace-header').prepend(checkmark);
            }
            
            // Append response block
            let respDiv = block.querySelector('.trace-response');
            if (!respDiv) {
                const expandBody = block.querySelector('.trace-body-expand');
                
                const label = document.createElement('div');
                label.className = 'trace-response-label';
                label.innerText = 'System Output';
                expandBody.appendChild(label);

                respDiv = document.createElement('div');
                respDiv.className = 'trace-response';
                expandBody.appendChild(respDiv);
            }
            respDiv.innerText = typeof response === 'object' ? JSON.stringify(response, null, 2) : response;
        }
        
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Submit handler
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg || isStreaming) return;

        chatInput.value = '';
        appendUserMessage(msg);
        showTypingIndicator();
        
        isStreaming = true;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: msg, session_id: sessionId })
            });

            if (!response.ok) {
                throw new Error(`HTTP network error: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            removeTypingIndicator();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Hold back incomplete line chunks

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith('data: ')) {
                        const jsonStr = trimmed.substring(6).trim();
                        try {
                            const event = JSON.parse(jsonStr);
                            
                            // Process SSE event details
                            if (event.error) {
                                appendOrUpdateAgentMessage('System', event.text);
                                continue;
                            }

                            // 1. Tool execution call logs
                            if (event.function_calls && event.function_calls.length > 0) {
                                event.function_calls.forEach(fc => {
                                    createOrUpdateTraceBlock(event.invocation_id, event.author, fc.name, fc.args, null);
                                    addLocalAuditLog(event.author, "TOOL_CALL", `Executing ${fc.name}`);
                                });
                            }

                            // 2. Tool execution response logs
                            if (event.function_responses && event.function_responses.length > 0) {
                                event.function_responses.forEach(fr => {
                                    createOrUpdateTraceBlock(event.invocation_id, event.author, fr.name, null, fr.response);
                                    addLocalAuditLog(event.author, "TOOL_RESPONSE", `Received response from ${fr.name}`);
                                });
                                // Force state update since a tool just updated the DB!
                                refreshTelemetry();
                            }

                            // 3. Dynamic Handoff transfer
                            if (event.transfer_to_agent) {
                                const target = event.transfer_to_agent;
                                lastActiveAgentName = activeAgentName;
                                activeAgentName = target;

                                appendHandoffCard(event.author, target);
                                drawTopology();
                                updateActiveAgentUI(target);
                                addLocalAuditLog(event.author, "SWARM_HANDOFF", `Transferring control to -> ${target}`);
                            }

                            // 4. Content streams
                            if (event.text) {
                                appendOrUpdateAgentMessage(event.author, event.text);
                            }

                        } catch (parseErr) {
                            console.error("Chunk decoding failed:", parseErr, jsonStr);
                        }
                    }
                }
            }

        } catch (err) {
            console.error("Communications channel interrupted:", err);
            appendOrUpdateAgentMessage('System', `The communication channel was interrupted. Detail: ${err.message}`);
        } finally {
            isStreaming = false;
            removeTypingIndicator();
            // Pull final telemetry to make sure billing matches
            refreshTelemetry();
        }
    });

    // ----------------------------------------------------------------------
    // 8. Telemetry & State Refresh Engine
    // ----------------------------------------------------------------------
    async function refreshTelemetry() {
        try {
            const res = await fetch('/api/state');
            if (!res.ok) return;

            const state = await res.json();
            
            updateResortLedger(state);
            updateAuditLogsUI(state.audit_logs);
        } catch (err) {
            console.error("Failed to sync state telemetry:", err);
        }
    }

    // Premium structured formatter for Resort Ledger State View
    function updateResortLedger(state) {
        const viewer = document.getElementById('json-viewer');
        if (!viewer) return;

        let html = '<div class="json-tree">';

        // 1. Bookings Section
        html += `
            <div class="json-section">
                <div class="json-section-header">🛎️ Active Guest Ledgers</div>
        `;
        if (state.bookings && Object.keys(state.bookings).length > 0) {
            for (const [id, bk] of Object.entries(state.bookings)) {
                html += `
                    <div class="json-item">
                        <span class="json-key">"${id}":</span>
                        <span class="json-val">"${bk.guest_name}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Suite:</span>
                        <span class="json-val">"${bk.suite}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Balance:</span>
                        <span class="json-val" style="color: hsl(38, 92%, 50%); font-weight: 600;">$${bk.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Amenities:</span>
                        <span class="json-val-array">[${bk.amenities.map(a => `"${a}"`).join(', ')}]</span>
                    </div>
                    ${bk.late_checkout ? `
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Late Checkout:</span>
                        <span class="json-val" style="color: #10b981; font-weight: 600;">"${bk.late_checkout}"</span>
                    </div>
                    ` : ''}
                `;
            }
        } else {
            html += '<div class="json-item"><span class="json-muted">No guest records.</span></div>';
        }
        html += '</div>';

        // 2. Dining Reservations Section
        html += `
            <div class="json-section">
                <div class="json-section-header">🍽️ Culinary Reservations</div>
        `;
        if (state.dining_reservations && state.dining_reservations.length > 0) {
            state.dining_reservations.forEach((res, i) => {
                html += `
                    <div class="json-item">
                        <span class="json-key">[Reservation ${i + 1}]:</span>
                        <span class="json-val">"${res.restaurant}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Table size:</span>
                        <span class="json-val">${res.party_size} guests</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Schedule:</span>
                        <span class="json-val">${res.date} at ${res.time}</span>
                    </div>
                `;
            });
        } else {
            html += '<div class="json-item"><span style="color: var(--text-muted); font-size: 10.5px;">No fine dining reservations.</span></div>';
        }
        html += '</div>';

        // 3. Spa Sessions Section
        html += `
            <div class="json-section">
                <div class="json-section-header">🌸 Serenity Spa Bookings</div>
        `;
        if (state.spa_bookings && state.spa_bookings.length > 0) {
            state.spa_bookings.forEach((spa, i) => {
                html += `
                    <div class="json-item">
                        <span class="json-key">[Booking ${i + 1}]:</span>
                        <span class="json-val">"${spa.treatment}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Schedule:</span>
                        <span class="json-val">${spa.date} at ${spa.time}</span>
                    </div>
                `;
            });
        } else {
            html += '<div class="json-item"><span style="color: var(--text-muted); font-size: 10.5px;">No spa treatments scheduled.</span></div>';
        }
        html += '</div>';

        // 4. VIP Yacht & Heli Charters Section
        html += `
            <div class="json-section">
                <div class="json-section-header">🚁 VIP Activities & Excursions</div>
        `;
        let hasVip = false;
        if (state.yacht_charters && state.yacht_charters.length > 0) {
            hasVip = true;
            state.yacht_charters.forEach((yc, i) => {
                html += `
                    <div class="json-item">
                        <span class="json-key">Yacht Yacht [${i + 1}]:</span>
                        <span class="json-val">"${yc.yacht_type}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Charter:</span>
                        <span class="json-val">${yc.duration_hours}h on ${yc.date}</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Yacht Fee:</span>
                        <span class="json-val" style="color: #a855f7;">$${yc.total_cost.toLocaleString()}</span>
                    </div>
                `;
            });
        }
        if (state.helicopter_tours && state.helicopter_tours.length > 0) {
            hasVip = true;
            state.helicopter_tours.forEach((hc, i) => {
                html += `
                    <div class="json-item">
                        <span class="json-key">Heli Flight [${i + 1}]:</span>
                        <span class="json-val">"${hc.tour_name}"</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Passengers:</span>
                        <span class="json-val">${hc.guest_count} on ${hc.date}</span>
                    </div>
                    <div class="json-item" style="padding-left: 24px;">
                        <span class="json-key">Flight Fee:</span>
                        <span class="json-val" style="color: #a855f7;">$${hc.cost.toLocaleString()}</span>
                    </div>
                `;
            });
        }
        if (!hasVip) {
            html += '<div class="json-item"><span style="color: var(--text-muted); font-size: 10.5px;">No private charters scheduled.</span></div>';
        }
        html += '</div>';

        html += '</div>'; // close json-tree
        viewer.innerHTML = html;
    }

    // Refresh Swarm Audit Terminal
    function updateAuditLogsUI(logs) {
        const auditContainer = document.getElementById('audit-logs');
        if (!auditContainer) return;

        auditContainer.innerHTML = '';
        logs.forEach(log => {
            let rowClass = 'sys-log';
            if (log.event_type === 'USER_INPUT') rowClass = 'user-log';
            else if (log.event_type === 'MODEL_RESPONSE') rowClass = 'model-log';
            else if (log.event_type === 'TOOL_CALL') rowClass = 'tool-log';
            else if (log.event_type === 'TOOL_RESPONSE') rowClass = 'tool-log';
            else if (log.event_type === 'SWARM_HANDOFF') rowClass = 'handoff-log';
            else if (log.event_type === 'RESET') rowClass = 'sys-log';

            const div = document.createElement('div');
            div.className = `log-row ${rowClass}`;
            div.innerText = `[${log.agent}] ${log.event_type}: ${log.detail}`;
            auditContainer.appendChild(div);
        });
        auditContainer.scrollTop = auditContainer.scrollHeight;
    }

    // Inject immediate local log before fetching backend sync
    function addLocalAuditLog(agent, eventType, detail) {
        const auditContainer = document.getElementById('audit-logs');
        if (!auditContainer) return;

        let rowClass = 'sys-log';
        if (eventType === 'USER_INPUT') rowClass = 'user-log';
        else if (eventType === 'MODEL_RESPONSE') rowClass = 'model-log';
        else if (eventType === 'TOOL_CALL') rowClass = 'tool-log';
        else if (eventType === 'TOOL_RESPONSE') rowClass = 'tool-log';
        else if (eventType === 'SWARM_HANDOFF') rowClass = 'handoff-log';

        const div = document.createElement('div');
        div.className = `log-row ${rowClass}`;
        div.innerText = `[${agent}] ${eventType}: ${detail}`;
        auditContainer.appendChild(div);
        auditContainer.scrollTop = auditContainer.scrollHeight;
    }

    // ----------------------------------------------------------------------
    // 9. Reset State Engine
    // ----------------------------------------------------------------------
    const resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async () => {
            if (isStreaming) return;
            
            const confirmReset = confirm("Are you sure you want to completely wipe the resort database and clear the chat session?");
            if (!confirmReset) return;

            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                const data = await res.json();
                
                if (data.status === 'success') {
                    // Clear message container except welcome card
                    const welcomeCard = messagesContainer.querySelector('.chat-welcome-card');
                    messagesContainer.innerHTML = '';
                    if (welcomeCard) {
                        messagesContainer.appendChild(welcomeCard);
                    }
                    
                    // Reset agent nodes
                    activeAgentName = 'AuraTriage';
                    lastActiveAgentName = null;
                    
                    drawTopology();
                    updateActiveAgentUI(activeAgentName);
                    
                    // Force state sync
                    await refreshTelemetry();
                    
                    addLocalAuditLog("System", "RESET", "Console flushed. Resort database restored to base conditions.");
                    alert("Aura Swarm Console reset complete.");
                }
            } catch (err) {
                console.error("Flush attempt failed:", err);
                alert("Flushing failed. Check network log console.");
            }
        });
    }

    // Suggested prompts trigger
    window.applyPrompt = function(text) {
        if (isStreaming) return;
        const input = document.getElementById('chat-input');
        if (input) {
            input.value = text;
            chatForm.dispatchEvent(new Event('submit'));
        }
    };

    // ----------------------------------------------------------------------
    // 10. Ignite Core Initializations
    // ----------------------------------------------------------------------
    initializeDashboard();
});
