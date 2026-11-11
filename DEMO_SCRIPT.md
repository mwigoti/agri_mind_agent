# 🎬 3-Minute AgriMind & VRA Demonstration Script
**Project**: AgriVision & AgriMind Agentic Layer  
**Setting**: Uasin Gishu County Grain Corridor (Moiben & Soy Sub-Counties, Kenya)  
**Target Duration**: 3 Minutes (180 Seconds)  
**Key Features Highlighted**: Autonomous Multi-Agent Advisory, VRA Resource Optimization Tool, Real Failure / Fail-Safe Demonstration, and USSD Last-Mile Delivery.

---

## ⏱️ Video Timeline Overview

| Time | Phase | On-Screen Action | Key Narration Focus |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:35** | **Act 1: The Problem & USSD Access** | Africa's Talking USSD Simulator / Feature Phone (`*384#`) | Smallholder reality, 2G connectivity, avoiding pesticide panic spraying. |
| **0:35 – 1:20** | **Act 2: VRA Tool & Resource Optimization** | VRA Analysis Page (`/vra_page/<id>/`) | Maize spatial vigor clustering, avoiding uniform fertilizer waste (23.4% CAN savings). |
| **1:20 – 2:05** | **Act 3: AgriMind Multi-Agent Reasoning** | Web Dashboard (`/health/`) & Crop Details Modal | Sentinel-2 NDVI + CHIRPS rainfall MCP ingestion, agronomist approval queue. |
| **2:05 – 2:45** | **Act 4: Showing Where It Fails** | Terminal / API / Invalid Hazard Trigger | **The Fail-Safe**: Missing rain data / rain hazard $\rightarrow$ Agent refuses to spray and fails closed. |
| **2:45 – 3:00** | **Act 5: Defensibility & Cost Wrap-Up** | Benchmark Table (`eval_results.json`) | $0.00014 cost/run ($2.79 for 1,000 farmers/season), closing impact statement. |

---

## 📝 Detailed Script & Storyboard

### ACT 1: The Smallholder Reality & Last-Mile USSD (0:00 – 0:35)

**Visual**: 
- Split screen or fullscreen view of the Africa's Talking USSD simulator (or terminal/browser dialer) dialing `*384#`.
- Select `1. Crop Health & Advisory` $\rightarrow$ Select `1. Moiben Plot A`.

**Voiceover (Spoken with energy and clarity)**:
> *"In Kenya's Uasin Gishu maize breadbasket, smallholders like Wanjiku Cherop cultivate 2.5 acres without smartphones or 4G data. During vegetative V6 growth, when Fall Armyworm strikes, farmers panic. They often spend thousands of shillings on pesticides and spray right before a downpour, washing the chemicals into rivers and losing 100% of their investment.*  
>  
> *With AgriMind, Wanjiku simply dials `*384#` on her basic Nokia phone. The agent checks real-time agro-ecological baselines and immediately advises: `Action: HOLD — heavy rain expected`. Let’s see what is powering this behind the scenes."*

---

### ACT 2: VRA Tool — Maize Fertilizer Resource Optimization (0:35 – 1:20)

**Visual**:
- Transition to browser at `http://127.0.0.1:8000/vra_page/<field_id>/`.
- Show the interactive spatial management zones map generated from Sentinel-2 multispectral imagery.
- Highlight the 3 distinct vigor clusters: Zone 1 (Green/High vigor), Zone 2 (Yellow/Moderate), and Zone 3 (Red/Stressed).
- Point to the Prescription Table and Resource Savings summary.

**Voiceover**:
> *"Before treating a field, uniform blanket broadcasting wastes massive amounts of resources. In Uasin Gishu, farmers traditionally dump 80 kg/ha of CAN nitrogen fertilizer uniformly across the whole field. Over-fertilizing high-vigor areas causes nitrate leaching and lodging, while under-fertilizing poor zones reduces yield.*  
>  
> *Here is our **Variable Rate Application (VRA) Tool**. Using Sentinel-2 multispectral indices, AgriVision clusters the maize field into three precise zones:*
> * *Zone 1 (High Vigor): Prescribed only 40 kg/ha — preventing lodging and chemical waste.*
> * *Zone 2 (Moderate): Maintenance rate of 65 kg/ha.*
> * *Zone 3 (Nutrient-Stressed): Targeted boost of 90 kg/ha to restore canopy potential.*  
>  
> *The result? **A 23.4% net reduction in fertilizer usage**, saving over KES 1,780 per hectare while protecting groundwater ecology."*

---

### ACT 3: AgriMind Multi-Agent Reasoning & Agronomist Sign-Off (1:20 – 2:05)

**Visual**:
- Navigate to `http://127.0.0.1:8000/health/`.
- Open the Field Card for `Moiben Plot A` and click **"⚡ Run AgriMind Advisory"**.
- Show the badge change to `PENDING_APPROVAL` with evidence tags:
  `[🔎 Sentinel-2 MSI NDVI: 0.42]` `[🔎 CHIRPS Rain Forecast: 18mm in 48h]` `[🔎 RULE-RAIN-WINDOW-01]`.
- Click **"✓ Approve Action"** as Sub-County Agricultural Officer Kiprono Biwott.

**Voiceover**:
> *"Now let's look at the autonomous decision agent. When an extension officer reviews flagged fields, AgriMind orchestrates a deterministic LangGraph state machine. It calls our custom FastMCP telemetry server to inspect 10-meter Sentinel-2 NDVI and CHIRPS rainfall anomaly data.*  
>  
> *Notice our core safety gate: AgriMind **strictly forbids** single-source hallucination. It requires at least two independent corroborating evidence citations before formulating a recommendation.*  
>  
> *The proposal enters an interrupt state: `PENDING_APPROVAL`. The extension officer verifies the evidence citations in seconds and clicks 'Approve Action'. Only then is the SMS dispatched to the farmer's feature phone."*

---

### ACT 4: WHERE THE AGENT FAILS (Critical Requirement) (2:05 – 2:45)

**Visual**:
- Switch to terminal or browser where a hazardous or degraded scenario is executed:
  - Run `python scripts/eval_benchmark.py` or trigger an invalid advisory call (e.g., Scenario `UG-MOI-01` where a spray is requested during a 22.5mm rainstorm, or `ADV-03` where soil moisture telemetry is missing).
- Show the terminal/UI output:
  `VALIDATION FAILED: Deterministic calendar does not confirm spraying is permitted (Rain > 15mm in 48h)`.
- Show that the agent **does not crash** and **refuses to issue a harmful spray**, failing closed to:
  `status: INSUFFICIENT_EVIDENCE` | `fallback_action: HOLD`.
- Briefly show `agentic_layer_2/audit.py` writing the audit log entry:
  `{"event": "evidence_validation", "valid": false, "errors": ["Deterministic calendar blocks spray"]}`.

**Voiceover**:
> *"Crucially, judging requires showing where the agent fails. Let's stress-test AgriMind with an adversarial edge case:*  
>  
> *Here, an external request attempts to force a chemical pesticide spray when a 22mm rainfall event is imminent. If this were a naive LLM in a loop, it might hallucinate compliance.*  
>  
> *Watch what happens: Our deterministic calendar gate catches the violation. The agent **fails closed**. It rejects the spray, outputs `INSUFFICIENT_EVIDENCE`, and defaults safely to `HOLD`. Furthermore, if cloud cover blinds Sentinel-2 or rainfall data is missing, AgriMind immediately halts tool execution and alerts the officer rather than guessing.*  
>  
> *This fail-closed resilience is proven across all 25 Uasin Gishu test scenarios with 100% safety adherence."*

---

### ACT 5: Defensibility & Cost Wrap-Up (2:45 – 3:00)

**Visual**:
- Display the terminal summary table from `eval_benchmark.py` or the `eval_results.json` summary.
- Highlight the bottom-line metrics:
  - Cost per run: **$0.000139 USD**
  - 1,000 Farmers for 20 Weeks: **$2.79 USD**

**Voiceover**:
> *"Finally, defensibility: AgriMind isn't an expensive black box. Running on open-weights Qwen 2.5, every advisory execution costs just **$0.00014 USD**.*  
>  
> *Monitoring 1,000 smallholders across an entire 20-week season costs the Uasin Gishu Department of Agriculture **under $3.00 total**.*  
>  
> *AgriVision and AgriMind: Verifiable multi-agent intelligence, resource-saving VRA optimization, and last-mile feature phone access for African agriculture. Thank you."*

---

## 🎥 Recording Checklist
1. **Screen Resolution**: 1080p (1920x1080) at 30 or 60 fps.
2. **Audio**: Clean microphone audio with zero background noise.
3. **Pacing**: Speak at a steady ~135 words per minute to finish comfortably inside the 180-second window.
4. **Tabs Ready Before Recording**:
   - Tab 1: Africa's Talking USSD Simulator or Local USSD view.
   - Tab 2: VRA Page (`http://127.0.0.1:8000/vra_page/1/`).
   - Tab 3: AgriVision Dashboard (`http://127.0.0.1:8000/health/`).
   - Tab 4: Terminal ready to run `python scripts/eval_benchmark.py`.

