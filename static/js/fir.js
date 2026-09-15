// FIR Ingestion Demo Logic

const SAMPLES = {
  "1": `First Information Report (FIR-2026-0417) filed at Anna Nagar Police Station. 
Complainant reported an organized financial fraud syndicate operating across Chennai. 
Preliminary investigation names Karthik Selvam (also known as Karthi or K. Selvam, Mobile: 9840055566, Vehicle: TN01GH8765) and Rajesh Elumalai (alias Raja, Mobile: 9840022233) as principal co-accused in the case. 
Suresh Babu (Mobile: 9840033344) was named as a known associate of Karthik Selvam in witness statements, having transferred funds into account ACC10017.`,

  "2": `Special Task Force FIR-2026-0298 registered at Tambaram PS. 
Confidential informant reported a narcotics trafficking ring and hawala routing network. 
Vignesh Raja (alias Vicky, Mobile: 9840044455, Vehicle: TN07EF4321) and Bharath Venkatesan (alias B. Venkat, Mobile: 9840088899) are named as primary co-accused. 
Transactions totaling INR 25,000 were logged between bank account ACC10009 and account ACC10041 prior to courier interception.`,

  "3": `Crime Branch FIR-2026-0512. Investigation into interstate luxury vehicle theft and forged registration syndicates. 
Dinesh Prabhakaran (alias D. Prabhakaran, Mobile: 9840066677, Account: ACC10022) was observed meeting Manoj Iyappan (alias Manu, Mobile: 9840077788, Vehicle: TN04IJ2468) near Porur junction. 
Manoj Iyappan coordinated subsequent disposal with Arun Kumar S. (alias Arun K, Vehicle: TN22AB1234).`
};

document.addEventListener("DOMContentLoaded", () => {
  const firInput = document.getElementById("fir-input");
  const extractBtn = document.getElementById("btn-extract");
  const sampleBtns = document.querySelectorAll(".sample-btn");

  // Load sample 1 by default
  firInput.value = SAMPLES["1"];

  sampleBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const sId = btn.getAttribute("data-sample");
      if (SAMPLES[sId]) {
        firInput.value = SAMPLES[sId];
      }
    });
  });

  extractBtn.addEventListener("click", async () => {
    const text = firInput.value.trim();
    if (!text) {
      alert("Please paste an FIR narrative first.");
      return;
    }

    const statusEl = document.getElementById("extraction-status");
    const resultsContainer = document.getElementById("extraction-results");

    statusEl.innerText = "Extracting entities with NLP / Gemini LLM...";
    extractBtn.disabled = true;

    try {
      const res = await fetch("/api/extract-fir", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fir_text: text })
      });
      const data = await res.json();

      statusEl.innerText = "Extraction completed successfully!";
      resultsContainer.style.display = "block";

      // Render Persons
      const pContainer = document.getElementById("res-persons");
      pContainer.innerHTML = "";
      if (data.persons && data.persons.length > 0) {
        data.persons.forEach(p => {
          const div = document.createElement("div");
          div.style.marginBottom = "0.4rem";
          div.innerHTML = `<strong>${p.name}</strong> <span style="color:#64748b;">(${p.aliases || 'no alias'})</span> — <span class="badge-role" style="font-size:0.7rem; padding:0.1rem 0.4rem;">${p.role || 'Person'}</span>`;
          pContainer.appendChild(div);
        });
      } else {
        pContainer.innerHTML = "<span style='color:#94a3b8;'>No persons recognized.</span>";
      }

      // Render Phones
      renderTags("res-phones", data.phone_numbers);
      // Render Vehicles
      renderTags("res-vehicles", data.vehicle_numbers);
      // Render Accounts
      renderTags("res-accounts", data.account_numbers);

      // Render Relationships
      const rBody = document.getElementById("res-relationships-tbody");
      rBody.innerHTML = "";
      if (data.relationships && data.relationships.length > 0) {
        data.relationships.forEach(r => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td style="font-weight:600; font-family:var(--font-mono);">${r.source}</td>
            <td style="font-weight:600; font-family:var(--font-mono);">${r.target}</td>
            <td><span class="tag-item" style="background:#e0f2fe; color:#0369a1;">${r.type}</span></td>
            <td style="color:#475569;">${r.evidence_quote}</td>
          `;
          rBody.appendChild(tr);
        });
      } else {
        rBody.innerHTML = "<tr><td colspan='4' style='text-align:center; color:#94a3b8;'>No direct relationships extracted.</td></tr>";
      }

    } catch (err) {
      statusEl.innerText = "Error extracting FIR: " + err.message;
    } finally {
      extractBtn.disabled = false;
    }
  });
});

function renderTags(elementId, items) {
  const el = document.getElementById(elementId);
  el.innerHTML = "";
  if (items && items.length > 0) {
    items.forEach(it => {
      const span = document.createElement("span");
      span.className = "tag-item";
      span.innerText = it;
      el.appendChild(span);
    });
  } else {
    el.innerHTML = "<span style='color:#94a3b8; font-size:0.75rem;'>None detected</span>";
  }
}
