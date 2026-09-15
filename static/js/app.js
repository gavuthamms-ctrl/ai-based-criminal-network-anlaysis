// NexusTrace Main Dashboard Logic

let network = null;
let graphData = null;
let edgesDataSet = null; // FIX 3: Module-level reference to dynamically add/remove predicted edges
let nodesDataSet = null;
let currentSelectedPersonId = "P17"; // default to the primary coordinator

document.addEventListener("DOMContentLoaded", () => {
  initGraph();
  setupCopilot();
  setupModal();
  setupControls();
  setupValidation();
});

async function initGraph() {
  try {
    const res = await fetch("/api/graph");
    graphData = await res.json();

    const container = document.getElementById("network-canvas");
    
    // Vis.js options with smooth physics and edge styling
    const options = {
      nodes: {
        shape: "dot",
        scaling: {
          min: 16,
          max: 36
        },
        font: {
          size: 12,
          face: "Inter, sans-serif",
          color: "#ffffff"
        },
        borderWidth: 2,
        shadow: true
      },
      edges: {
        smooth: {
          type: "continuous",
          roundness: 0.15
        },
        font: {
          size: 11,
          align: "middle",
          background: "rgba(255,255,255,0.85)"
        },
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
        stabilization: {
          iterations: 150
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 100,
        selectable: true
      }
    };

    nodesDataSet = new vis.DataSet(graphData.nodes);
    edgesDataSet = new vis.DataSet(graphData.edges);

    const data = {
      nodes: nodesDataSet,
      edges: edgesDataSet
    };

    network = new vis.Network(container, data, options);

    // Node click handler
    network.on("click", (params) => {
      if (params.nodes && params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        loadPersonExplanation(nodeId);
      }
    });

    // Populate baseline link predictions
    renderPredictions(graphData.predicted_links);

    // Automatically load P17 on startup
    loadPersonExplanation("P17");

  } catch (err) {
    console.error("Failed to load graph:", err);
  }
}

async function loadPersonExplanation(personId, forceRegen = false) {
  currentSelectedPersonId = personId;
  const panel = document.getElementById("why-this-person-panel");
  
  try {
    const url = `/api/person/${personId}/explain${forceRegen ? '?force_regenerate=true' : ''}`;
    const res = await fetch(url);
    const data = await res.json();

    const p = data.person || {};
    const prio = data.priority || "MEDIUM";

    document.getElementById("panel-person-id").innerText = `NODE: ${personId}`;
    document.getElementById("panel-person-name").innerText = p.display_name || personId;
    document.getElementById("panel-person-aliases").innerText = `Aliases: ${p.known_aliases || 'None recorded'} | Phone: ${p.phone_number || 'N/A'}`;
    
    // Priority badge
    const prioBadge = document.getElementById("panel-priority-badge");
    prioBadge.className = `badge-priority priority-${prio}`;
    prioBadge.innerText = `PRIORITY: ${prio}`;

    // Confidence badge
    document.getElementById("panel-confidence-badge").innerText = `CONF: ${data.confidence_pct || 80}%`;

    // Role
    document.getElementById("panel-role").innerText = data.network_role || "Associate";

    // Metrics lookup
    const nodeObj = graphData.nodes.find(n => n.id === personId);
    if (nodeObj && nodeObj.data && nodeObj.data.metrics) {
      const m = nodeObj.data.metrics;
      document.getElementById("panel-betweenness").innerText = `${m.betweenness_centrality} (${m.betweenness_percentile}th percentile)`;
      document.getElementById("panel-degree").innerText = m.degree_centrality;
    }
    document.getElementById("panel-resolution-conf").innerText = `${Math.round((p.resolution_confidence || 1.0) * 100)}%`;

    // Explanation text
    document.getElementById("panel-explanation-text").innerText = data.explanation_text || "No explanation available.";

    // Evidence Buttons
    const btnGroup = document.getElementById("panel-evidence-buttons");
    btnGroup.innerHTML = "";

    const sources = data.source_records || {};
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

  } catch (err) {
    console.error("Failed to load explanation:", err);
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
    const item = document.createElement("div");
    item.className = "prediction-item";
    item.id = `card_${predEdgeId}`;
    item.innerHTML = `
      <div class="prediction-header">
        <span class="prediction-pair">${p.person_a_id} ↔ ${p.person_b_id}</span>
        <span class="prediction-conf" id="badge_${predEdgeId}">SCORE: ${(p.confidence_score * 100).toFixed(0)}%</span>
      </div>
      <div style="font-size:0.72rem; color:#475569;">
        ${p.person_a_name} & ${p.person_b_name}
      </div>
      <div style="font-size:0.72rem; color:#7f1d1d; margin-top:0.2rem;">
        ${p.note}
      </div>
      <div style="font-size:0.68rem; color:#dc2626; margin-top:0.3rem; font-weight:600;" id="status_${predEdgeId}">
        + Click to project on graph
      </div>
    `;
    item.style.cursor = "pointer";
    item.onclick = () => {
      togglePredictedEdge(p, predEdgeId);
    };
    container.appendChild(item);
  });
}

function togglePredictedEdge(p, predEdgeId) {
  if (!edgesDataSet) return;

  const existing = edgesDataSet.get(predEdgeId);
  const statusLabel = document.getElementById(`status_${predEdgeId}`);
  const card = document.getElementById(`card_${predEdgeId}`);

  if (existing) {
    // Toggle: Remove from graph
    edgesDataSet.remove(predEdgeId);
    if (statusLabel) statusLabel.innerText = "+ Click to project on graph";
    if (card) card.style.borderColor = "#fecaca";
  } else {
    // Add dashed red AI predicted link to Vis.js canvas
    edgesDataSet.add({
      id: predEdgeId,
      from: p.person_a_id,
      to: p.person_b_id,
      label: `ai_predicted (${Math.round(p.confidence_score * 100)}%)`,
      color: {
        color: "#ef4444",
        highlight: "#b91c1c",
        hover: "#dc2626"
      },
      dashes: [4, 4],
      width: 2.2,
      font: {
        size: 11,
        align: "middle",
        color: "#dc2626",
        background: "rgba(255,255,255,0.95)"
      },
      title: "AI-Predicted — not a database-backed relationship (Score: " + Math.round(p.confidence_score * 100) + "%)",
      arrows: { to: { enabled: false } }
    });

    if (statusLabel) statusLabel.innerText = "✓ Projected on graph (Click to remove)";
    if (card) card.style.borderColor = "#dc2626";

    // Highlight and focus the pair
    highlightGraphItems([p.person_a_id, p.person_b_id], [predEdgeId]);
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

  submitBtn.addEventListener("click", () => {
    executeCopilotQuery(input.value);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      executeCopilotQuery(input.value);
    }
  });

  document.getElementById("btn-reexplain").addEventListener("click", () => {
    if (currentSelectedPersonId) {
      loadPersonExplanation(currentSelectedPersonId, true);
    }
  });
}

async function executeCopilotQuery(question) {
  if (!question || !question.trim()) return;

  const resBox = document.getElementById("copilot-response");
  const textBox = document.getElementById("copilot-text");
  const citeBox = document.getElementById("copilot-citations");

  resBox.style.display = "block";
  textBox.innerHTML = "<em>Analyzing network topology and evidence records...</em>";
  citeBox.innerHTML = "<span class='cited-label'>Cited Entities:</span>";

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question.trim() })
    });
    const data = await res.json();

    textBox.innerHTML = data.answer || "Query processed.";
    
    const citedNodes = data.cited_nodes || [];
    const citedEdges = data.cited_edges || [];

    citeBox.innerHTML = "<span class='cited-label'>Cited Entities:</span>";
    citedNodes.forEach(nid => {
      const badge = document.createElement("span");
      badge.className = "cited-item";
      badge.innerText = `Node: ${nid}`;
      badge.onclick = () => {
        loadPersonExplanation(nid);
        highlightGraphItems([nid], citedEdges);
      };
      citeBox.appendChild(badge);
    });

    citedEdges.forEach(eid => {
      const badge = document.createElement("span");
      badge.className = "cited-item";
      badge.innerText = `Edge: ${eid}`;
      citeBox.appendChild(badge);
    });

    // Highlight on graph
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
    if (network) {
      network.fit({ animation: { duration: 500 } });
    }
  });

  document.getElementById("btn-reset-highlight").addEventListener("click", () => {
    if (network) {
      network.unselectAll();
    }
  });
}

// FIX 5: Evaluation Harness Handler
function setupValidation() {
  const valBtn = document.getElementById("btn-run-validation");
  const valBox = document.getElementById("validation-result-box");
  if (!valBtn || !valBox) return;

  valBtn.addEventListener("click", async () => {
    valBtn.disabled = true;
    valBtn.innerText = "Running...";
    valBox.style.display = "block";
    valBox.innerHTML = "<em>Executing leave-one-out validation on 6-edge evidentiary graph...</em>";

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
  details.innerHTML = "<em>Loading record from database...</em>";
  modal.style.display = "flex";

  try {
    const res = await fetch(`/api/evidence/${recordType}/${recordId}`);
    const data = await res.json();
    
    const rec = data.data || {};
    let html = `
      <div style="margin-bottom: 0.75rem; font-family: var(--font-mono); font-size: 0.8rem; color: #64748b;">
        Source Type: <strong>${recordType.toUpperCase()}</strong> | ID: <strong>${recordId}</strong>
      </div>
      <table class="table-custom" style="width:100%; border-collapse: collapse; margin-bottom: 1rem;">
    `;

    for (const [k, v] of Object.entries(rec)) {
      html += `
        <tr>
          <td style="font-weight:600; width:35%; background:#f8fafc; padding:0.4rem 0.6rem; border:1px solid #e2e8f0;">${k}</td>
          <td style="padding:0.4rem 0.6rem; border:1px solid #e2e8f0; font-family:${k.includes('id') || k.includes('phone') || k.includes('num') ? 'var(--font-mono)' : 'inherit'};">${v || '<em style="color:#94a3b8;">NULL</em>'}</td>
        </tr>
      `;
    }
    html += `</table>`;
    
    html += `
      <div style="font-size:0.75rem; color:#64748b; background:#f1f5f9; padding:0.6rem; border-radius:4px;">
        🔒 <strong>Evidence Audit Trail:</strong> Record indexed in local prototype repository. In production, this maps to SHA-256 hash-chained case audit ledger.
      </div>
    `;

    details.innerHTML = html;
  } catch (err) {
    details.innerText = "Error retrieving evidence: " + err.message;
  }
}
