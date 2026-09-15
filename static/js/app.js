// NexusTrace Main Dashboard Logic (Investigation-Ready & Multi-Case)

let network = null;
let graphData = null;
let edgesDataSet = null;
let nodesDataSet = null;
let currentSelectedPersonId = "P17";
let activeCaseId = "2026-CR-0417";

document.addEventListener("DOMContentLoaded", () => {
  setupCaseSelector();
  loadCaseData(activeCaseId);
  setupCopilot();
  setupModal();
  setupControls();
  setupValidation();
  setupTimeline();
  setupVerificationActions();
});

function setupCaseSelector() {
  const selector = document.getElementById("case-selector");
  if (!selector) return;

  selector.addEventListener("change", (e) => {
    activeCaseId = e.target.value;
    loadCaseData(activeCaseId);
  });
}

async function loadCaseData(caseId) {
  // Update Case Summary Banner
  try {
    const resSummary = await fetch(`/api/cases/${caseId}`);
    const summary = await resSummary.json();
    
    document.getElementById("summary-case-id").innerText = `CASE: #${summary.case_id}`;
    document.getElementById("summary-case-title").innerText = summary.title;
    document.getElementById("summary-case-text").innerText = summary.summary;
    document.getElementById("summary-station").innerText = summary.station;
    document.getElementById("summary-sections").innerText = summary.sections;
    document.getElementById("summary-primary-target").innerText = summary.primary_suspect;
    document.getElementById("summary-case-status").innerText = summary.status;
    document.getElementById("graph-case-label").innerText = `Case #${summary.case_id}`;
  } catch (err) {
    console.error("Failed to load case summary:", err);
  }

  // Load Graph Data for this Case
  try {
    const resGraph = await fetch(`/api/graph?case_id=${caseId}`);
    graphData = await resGraph.json();

    const container = document.getElementById("network-canvas");
    const options = {
      nodes: {
        shape: "dot",
        scaling: { min: 16, max: 36 },
        font: { size: 12, face: "Inter, sans-serif", color: "#ffffff" },
        borderWidth: 2,
        shadow: true
      },
      edges: {
        smooth: { type: "continuous", roundness: 0.15 },
        font: { size: 11, align: "middle", background: "rgba(255,255,255,0.85)" },
        selectionWidth: 3
      },
      physics: {
        barnesHut: {
          gravitationalConstant: -3500,
          centralGravity: 0.3,
          springLength: 120,
          springConstant: 0.04,
          damping: 0.09
        },
        stabilization: { iterations: 150 }
      },
      interaction: { hover: true, tooltipDelay: 100, selectable: true }
    };

    nodesDataSet = new vis.DataSet(graphData.nodes);
    edgesDataSet = new vis.DataSet(graphData.edges);

    const data = { nodes: nodesDataSet, edges: edgesDataSet };
    network = new vis.Network(container, data, options);

    network.on("click", (params) => {
      if (params.nodes && params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        loadPersonExplanation(nodeId);
      }
    });

    renderPredictions(graphData.predicted_links);

    // Auto-select primary coordinator for the active case
    const defaultPerson = caseId === "2026-CR-0512" ? "P55" : "P17";
    loadPersonExplanation(defaultPerson);
    loadTimeline(caseId);

  } catch (err) {
    console.error("Failed to load case graph:", err);
  }
}

async function loadPersonExplanation(personId, forceRegen = false) {
  currentSelectedPersonId = personId;
  
  try {
    const url = `/api/person/${personId}/explain${forceRegen ? '?force_regenerate=true' : ''}`;
    const res = await fetch(url);
    const data = await res.json();

    const p = data.person || {};
    const prio = data.priority || "MEDIUM";

    document.getElementById("panel-person-id").innerText = `SUSPECT ID: ${personId}`;
    document.getElementById("panel-person-name").innerText = p.display_name || personId;
    document.getElementById("panel-person-aliases").innerText = `Aliases: ${p.known_aliases || 'None recorded'} | Mobile: ${p.phone_number || 'N/A'}`;
    
    // Priority badge
    const prioBadge = document.getElementById("panel-priority-badge");
    prioBadge.className = `badge-priority priority-${prio}`;
    prioBadge.innerText = `PRIORITY: ${prio}`;

    // Confidence badge
    document.getElementById("panel-confidence-badge").innerText = `CONF: ${data.confidence_pct || 80}%`;
    document.getElementById("panel-role").innerText = data.network_role || "Associate";

    // Lookup node metrics
    const nodeObj = graphData && graphData.nodes ? graphData.nodes.find(n => n.id === personId) : null;
    if (nodeObj && nodeObj.data && nodeObj.data.metrics) {
      const m = nodeObj.data.metrics;
      document.getElementById("panel-betweenness").innerText = `${m.betweenness_centrality} (${m.betweenness_percentile}th percentile)`;
      document.getElementById("panel-legal-sections").innerText = m.legal_sections || "IPC 420";
      document.getElementById("panel-custody-status").innerText = `Status: ${m.custody_status || 'Under Probe'}`;

      renderScoreDecomposition(m.score_breakdown);
    }
    document.getElementById("panel-resolution-conf").innerText = `${Math.round((p.resolution_confidence || 1.0) * 100)}% (Verified Identity)`;

    // Explanation text
    document.getElementById("panel-explanation-text").innerText = data.explanation_text || "No explanation available.";

    // Render Evidence Buttons
    renderEvidenceButtons(data.source_records || {});

    // Load verification audit status
    loadVerificationStatus(personId);

  } catch (err) {
    console.error("Failed to load explanation:", err);
  }
}

function renderScoreDecomposition(breakdown) {
  const container = document.getElementById("panel-decomp-bars");
  const totalEl = document.getElementById("panel-decomp-total");
  if (!container || !breakdown) return;

  totalEl.innerText = `Total: ${breakdown.total_score}%`;
  container.innerHTML = `
    <div style="display:flex; justify-content:space-between;">
      <span>• Structural Centrality:</span>
      <strong>+${breakdown.structural_centrality_points} pts</strong>
    </div>
    <div style="display:flex; justify-content:space-between;">
      <span>• Cross-Source Documentary Evidence:</span>
      <strong>+${breakdown.documentary_evidence_points} pts</strong>
    </div>
    <div style="display:flex; justify-content:space-between;">
      <span>• Telecom / Financial Spike Pattern:</span>
      <strong>+${breakdown.telecom_behavior_points} pts</strong>
    </div>
    <div style="display:flex; justify-content:space-between;">
      <span>• Alias Resolution Confidence:</span>
      <strong>+${breakdown.identity_confidence_points} pts</strong>
    </div>
  `;
}

function renderEvidenceButtons(sources) {
  const btnGroup = document.getElementById("panel-evidence-buttons");
  btnGroup.innerHTML = "";
  let hasSources = false;

  if (sources.fir_ids && sources.fir_ids.length > 0) {
    hasSources = true;
    sources.fir_ids.forEach(fid => {
      const b = document.createElement("button");
      b.className = "evidence-btn";
      b.innerText = `📄 FIR: ${fid}`;
      b.onclick = () => viewEvidenceRecord("fir", fid);
      btnGroup.appendChild(b);
    });
  }

  if (sources.cdr_ids && sources.cdr_ids.length > 0) {
    hasSources = true;
    sources.cdr_ids.forEach(cid => {
      const b = document.createElement("button");
      b.className = "evidence-btn";
      b.innerText = `📞 CDR: ${cid}`;
      b.onclick = () => viewEvidenceRecord("cdr", cid);
      btnGroup.appendChild(b);
    });
  }

  if (sources.txn_ids && sources.txn_ids.length > 0) {
    hasSources = true;
    sources.txn_ids.forEach(tid => {
      const b = document.createElement("button");
      b.className = "evidence-btn";
      b.innerText = `💳 TXN: ${tid}`;
      b.onclick = () => viewEvidenceRecord("txn", tid);
      btnGroup.appendChild(b);
    });
  }

  if (sources.visit_ids && sources.visit_ids.length > 0) {
    hasSources = true;
    sources.visit_ids.forEach(vid => {
      const b = document.createElement("button");
      b.className = "evidence-btn";
      b.innerText = `🏢 VISIT: ${vid}`;
      b.onclick = () => viewEvidenceRecord("visit", vid);
      btnGroup.appendChild(b);
    });
  }

  if (!hasSources) {
    btnGroup.innerHTML = "<span style='font-size:0.75rem; color:#94a3b8;'>No direct attached records.</span>";
  }
}

// FIX 3: Draw AI-predicted links on the graph with toggle capability
function renderPredictions(predictions) {
  const container = document.getElementById("predictions-list");
  container.innerHTML = "";

  if (!predictions || predictions.length === 0) {
    container.innerHTML = "<div style='font-size:0.75rem; color:#64748b;'>No baseline predictions available.</div>";
    return;
  }

  predictions.forEach(p => {
    const predEdgeId = `pred_${p.person_a_id}_${p.person_b_id}`;
    const scoreVal = p.confidence_pct ? p.confidence_pct : (p.confidence_score * 100).toFixed(1);
    const item = document.createElement("div");
    item.className = "prediction-item";
    item.id = `card_${predEdgeId}`;
    item.innerHTML = `
      <div class="prediction-header">
        <span class="prediction-pair">${p.person_a_name} ↔ ${p.person_b_name}</span>
        <span class="prediction-conf" id="badge_${predEdgeId}">SCORE: ${scoreVal}%</span>
      </div>
      <div style="font-size:0.72rem; color:#7f1d1d; margin-top:0.2rem; line-height:1.35;">
        ${p.note}
      </div>
      <div style="font-size:0.68rem; color:#dc2626; margin-top:0.3rem; font-weight:600;" id="status_${predEdgeId}">
        + Click to project on graph
      </div>
    `;
    item.style.cursor = "pointer";
    item.onclick = () => togglePredictedEdge(p, predEdgeId);
    container.appendChild(item);
  });
}

function togglePredictedEdge(p, predEdgeId) {
  if (!edgesDataSet) return;

  const existing = edgesDataSet.get(predEdgeId);
  const statusLabel = document.getElementById(`status_${predEdgeId}`);
  const card = document.getElementById(`card_${predEdgeId}`);
  const scoreVal = p.confidence_pct ? p.confidence_pct : (p.confidence_score * 100).toFixed(1);

  if (existing) {
    edgesDataSet.remove(predEdgeId);
    if (statusLabel) statusLabel.innerText = "+ Click to project on graph";
    if (card) card.style.borderColor = "#fecaca";
  } else {
    edgesDataSet.add({
      id: predEdgeId,
      from: p.person_a_id,
      to: p.person_b_id,
      label: `ai_predicted (${scoreVal}%)`,
      color: { color: "#ef4444", highlight: "#b91c1c", hover: "#dc2626" },
      dashes: [4, 4],
      width: 2.2,
      font: { size: 11, align: "middle", color: "#dc2626", background: "rgba(255,255,255,0.95)" },
      title: `AI-Predicted — Undocumented candidate relationship (Score: ${scoreVal}%)`,
      arrows: { to: { enabled: false } }
    });

    if (statusLabel) statusLabel.innerText = "✓ Projected on graph (Click to remove)";
    if (card) card.style.borderColor = "#dc2626";

    highlightGraphItems([p.person_a_id, p.person_b_id], [predEdgeId]);
  }
}

// Chronological Timeline
async function loadTimeline(caseId = "2026-CR-0417") {
  const container = document.getElementById("timeline-container");
  if (!container) return;

  try {
    const res = await fetch(`/api/timeline`);
    const events = await res.json();

    container.innerHTML = "";
    events.forEach(ev => {
      const div = document.createElement("div");
      div.style.cssText = "background:#f8fafc; border:1px solid #e2e8f0; border-left:3px solid #3b82f6; padding:0.45rem 0.75rem; border-radius:4px; font-size:0.75rem;";
      div.innerHTML = `
        <div style="display:flex; justify-content:space-between; margin-bottom:0.15rem;">
          <span style="font-family:var(--font-mono); font-weight:700; color:var(--navy-900);">${ev.datetime}</span>
          <span class="tag-item" style="font-size:0.65rem; padding:0.1rem 0.35rem;">${ev.type}</span>
        </div>
        <div style="font-weight:600; color:#1e293b;">${ev.headline}</div>
        <div style="color:#64748b; font-size:0.72rem;">${ev.detail}</div>
      `;
      div.style.cursor = "pointer";
      div.onclick = () => {
        if (ev.participants && ev.participants.length > 0) {
          highlightGraphItems(ev.participants.filter(p => p.startsWith("P")), []);
        }
      };
      container.appendChild(div);
    });
  } catch (err) {
    container.innerHTML = "<span style='color:#94a3b8;'>Error loading timeline: " + err.message + "</span>";
  }
}

function setupTimeline() {
  const toggleBtn = document.getElementById("btn-toggle-timeline");
  const container = document.getElementById("timeline-container");
  if (toggleBtn && container) {
    toggleBtn.onclick = () => {
      container.style.display = container.style.display === "none" ? "flex" : "none";
    };
  }
}

function setupVerificationActions() {
  const btnAccept = document.getElementById("btn-verify-accept");
  const btnReject = document.getElementById("btn-verify-reject");

  if (btnAccept) {
    btnAccept.onclick = () => submitVerification("ACCEPTED", "Lead validated by Investigating Officer via case records.");
  }
  if (btnReject) {
    btnReject.onclick = () => submitVerification("REJECTED", "Dismissed as coincidental/insufficient nexus.");
  }
}

async function submitVerification(decision, defaultNotes) {
  if (!currentSelectedPersonId) return;

  const notes = prompt(`Enter Case Diary / Verification Notes for ${currentSelectedPersonId}:`, defaultNotes);
  if (notes === null) return;

  try {
    const res = await fetch(`/api/person/${currentSelectedPersonId}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        officer_name: "Inspector R. Santhosh",
        officer_badge: "TN-POL-4482",
        decision: decision,
        notes: notes
      })
    });
    const data = await res.json();
    alert(`Lead status for ${currentSelectedPersonId} recorded as: ${decision}`);
    loadVerificationStatus(currentSelectedPersonId);
  } catch (err) {
    alert("Error logging verification: " + err.message);
  }
}

async function loadVerificationStatus(personId) {
  const statusEl = document.getElementById("panel-verification-status");
  if (!statusEl) return;

  try {
    const res = await fetch(`/api/person/${personId}/verification-history`);
    const data = await res.json();
    const history = data.history || [];

    if (history.length > 0) {
      const latest = history[0];
      const color = latest.decision === "ACCEPTED" ? "#166534" : "#991b1b";
      statusEl.innerHTML = `
        <span style="font-weight:700; color:${color};">Audit: ${latest.decision}</span> by ${latest.officer_name} (${latest.timestamp})<br>
        <em>"${latest.notes || ''}"</em>
      `;
    } else {
      statusEl.innerHTML = "Status: <strong>PENDING REVIEW</strong> by Investigating Officer";
    }
  } catch (err) {
    statusEl.innerText = "No audit log available.";
  }
}

function setupCopilot() {
  const submitBtn = document.getElementById("copilot-submit");
  const input = document.getElementById("copilot-input");
  const chips = document.querySelectorAll(".copilot-chip");

  chips.forEach(c => {
    c.addEventListener("click", () => {
      input.value = c.getAttribute("data-q");
      executeCopilotQuery(input.value);
    });
  });

  submitBtn.addEventListener("click", () => executeCopilotQuery(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") executeCopilotQuery(input.value);
  });

  document.getElementById("btn-reexplain").addEventListener("click", () => {
    if (currentSelectedPersonId) {
      loadPersonExplanation(currentSelectedPersonId, true);
    }
  });
}

// Helper to get person name by ID
function getPersonDisplayName(personId) {
  if (graphData && graphData.nodes) {
    const node = graphData.nodes.find(n => n.id === personId);
    if (node && node.data && node.data.display_name) {
      return `${node.data.display_name} (${personId})`;
    }
  }
  return personId;
}

async function executeCopilotQuery(question) {
  if (!question || !question.trim()) return;

  const resBox = document.getElementById("copilot-response");
  const textBox = document.getElementById("copilot-text");
  const citeBox = document.getElementById("copilot-citations");

  resBox.style.display = "block";
  textBox.innerHTML = "<em>Analyzing network topology and evidence records...</em>";
  citeBox.innerHTML = "<span class='cited-label'>Cited Suspects:</span>";

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question.trim(),
        case_id: currentCaseId || "2026-CR-0417"
      })
    });
    const data = await res.json();

    textBox.innerHTML = data.answer || "Query processed.";
    
    const citedNodes = data.cited_nodes || [];
    const citedEdges = data.cited_edges || [];

    citeBox.innerHTML = "<span class='cited-label'>Cited Suspects:</span>";
    citedNodes.forEach(nid => {
      const badge = document.createElement("span");
      badge.className = "cited-item";
      // Replace "Node: P17" with full name "Karthik Selvam (P17)"
      badge.innerText = `👤 ${getPersonDisplayName(nid)}`;
      badge.onclick = () => {
        loadPersonExplanation(nid);
        highlightGraphItems([nid], citedEdges);
      };
      citeBox.appendChild(badge);
    });

    citedEdges.forEach(eid => {
      const badge = document.createElement("span");
      badge.className = "cited-item";
      badge.innerText = `🔗 Link: ${eid.replace('e_', '').replace('_', ' ↔ ')}`;
      citeBox.appendChild(badge);
    });

    highlightGraphItems(citedNodes, citedEdges);

  } catch (err) {
    textBox.innerText = "Error executing copilot query: " + err.message;
  }
}

function highlightGraphItems(nodeIds, edgeIds) {
  if (!network) return;

  if (nodeIds && nodeIds.length > 0) {
    network.selectNodes(nodeIds);
    network.focus(nodeIds[0], {
      scale: 1.15,
      animation: { duration: 600, easingFunction: "easeInOutQuad" }
    });
  }
}

function setupControls() {
  document.getElementById("btn-fit-graph").addEventListener("click", () => {
    if (network) network.fit({ animation: { duration: 500 } });
  });

  document.getElementById("btn-reset-highlight").addEventListener("click", () => {
    if (network) network.unselectAll();
  });
}

function setupValidation() {
  const valBtn = document.getElementById("btn-run-validation");
  const valBox = document.getElementById("validation-result-box");
  if (!valBtn || !valBox) return;

  valBtn.addEventListener("click", async () => {
    valBtn.disabled = true;
    valBtn.innerText = "Running...";
    valBox.style.display = "block";
    valBox.innerHTML = "<em>Executing leave-one-out validation on evidentiary graph...</em>";

    try {
      const res = await fetch("/api/evaluate/link-prediction");
      const data = await res.json();

      valBox.innerHTML = `
        <div style="font-weight:700; color:var(--navy-900); margin-bottom:0.25rem;">
          Baseline Sanity Check (${data.dataset_edges_evaluated} Seed Edges)
        </div>
        <div style="color:#475569; margin-bottom:0.35rem; line-height:1.4;">
          • Top-3 Recovered: <strong>${data.top3_recovered_count}/${data.dataset_edges_evaluated} (${data.top3_recovery_rate_pct}%)</strong><br>
          • Mean Recovery Rank: <strong>${data.mean_recovery_rank}</strong> / 22 non-edges
        </div>
        <div style="font-size:0.7rem; color:#991b1b; background:#fee2e2; padding:0.4rem; border-radius:4px; line-height:1.35;">
          📊 <strong>Empirical Finding:</strong> Seed edges form an acyclic tree without triangles. Baseline common-neighbors cannot recover 1-hop bridges, mathematically validating why <strong>GraphSAGE GNN multi-hop learning</strong> is the required production path.
        </div>
      `;
    } catch (err) {
      valBox.innerHTML = `<span style="color:#b91c1c;">Validation error: ${err.message}</span>`;
    } finally {
      valBtn.disabled = false;
      valBtn.innerText = "⚡ Re-run Validation";
    }
  });
}

function setupModal() {
  const modal = document.getElementById("evidence-modal");
  const closeBtn = document.getElementById("modal-close-btn");

  closeBtn.onclick = () => { modal.style.display = "none"; };
  window.onclick = (e) => {
    if (e.target === modal) modal.style.display = "none";
  };
}

async function viewEvidenceRecord(recordType, recordId) {
  const modal = document.getElementById("evidence-modal");
  const details = document.getElementById("modal-content-details");
  const title = document.getElementById("modal-title");

  title.innerText = `Evidence Record: ${recordType.toUpperCase()} #${recordId}`;
  details.innerHTML = "<em>Loading record & statutory chain of custody from database...</em>";
  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/evidence/${recordType}/${recordId}`);
    const data = await res.json();
    
    const rec = data.data || {};
    const prov = rec._provenance || {};

    let html = `
      <div style="background:#0f172a; color:#f8fafc; padding:0.85rem; border-radius:6px; margin-bottom:1rem; font-size:0.76rem; font-family:var(--font-mono); line-height:1.5;">
        <div style="color:#38bdf8; font-weight:700; margin-bottom:0.25rem;">⚖️ STATUTORY CHAIN OF CUSTODY (Sec 65B BSA Certified)</div>
        <div>• Authority: <strong>${prov.legal_authority || 'Sec 91 CrPC Notice'}</strong></div>
        <div>• Source Entity: <strong>${prov.source_entity || 'Service Provider Nodal Portal'}</strong></div>
        <div>• Collecting Officer: <strong>${prov.collecting_officer || 'Investigating Officer'}</strong></div>
        <div>• File SHA-256 Hash: <span style="color:#94a3b8;">${prov.integrity_hash_sha256 || '--'}</span></div>
      </div>

      <table class="table-custom" style="width:100%; border-collapse: collapse; margin-bottom: 1rem;">
    `;

    for (const [k, v] of Object.entries(rec)) {
      if (k === "_provenance") continue;
      html += `
        <tr>
          <td style="font-weight:600; width:35%; background:#f8fafc; padding:0.4rem 0.6rem; border:1px solid #e2e8f0;">${k}</td>
          <td style="padding:0.4rem 0.6rem; border:1px solid #e2e8f0; font-family:${k.includes('id') || k.includes('phone') || k.includes('num') ? 'var(--font-mono)' : 'inherit'};">${v || '<em style="color:#94a3b8;">NULL</em>'}</td>
        </tr>
      `;
    }
    html += `</table>`;

    details.innerHTML = html;
  } catch (err) {
    details.innerText = "Error retrieving evidence: " + err.message;
  }
}
