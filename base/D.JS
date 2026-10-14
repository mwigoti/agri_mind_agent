const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, TableOfContents,
  HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber, PageBreak
} = require("docx");
const fs = require("fs");

// ---------- helpers ----------
const FONT = "Arial";

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, italics: !!opts.italic, bold: !!opts.bold })],
  });
}
// paragraph with a bold lead-in phrase followed by normal text
function lead(leadText, rest) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [
      new TextRun({ text: leadText, bold: true }),
      new TextRun({ text: rest }),
    ],
  });
}
function bullets(items) {
  return items.map(
    (t) =>
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 80 },
        children: Array.isArray(t)
          ? t.map((seg) => new TextRun(seg))
          : [new TextRun(t)],
      })
  );
}
function numbered(items, ref = "numbers") {
  return items.map(
    (t) =>
      new Paragraph({
        numbering: { reference: ref, level: 0 },
        spacing: { after: 80 },
        children: [new TextRun(t)],
      })
  );
}
function quoteLine(text) {
  return new Paragraph({
    spacing: { after: 100 },
    indent: { left: 360 },
    children: [new TextRun({ text: `\u201C${text}\u201D`, italics: true })],
  });
}
const cellBorder = { style: BorderStyle.SINGLE, size: 2, color: "CBD5E0" };
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };

function headerCell(text, width) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill: "1F4E5F", type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 20 })] })],
  });
}
function bodyCell(text, width, opts = {}) {
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.shade ? { fill: opts.shade, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, size: 20, bold: !!opts.bold })] })],
  });
}
function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((hd, i) => headerCell(hd, widths[i])) }),
      ...rows.map(
        (r, ri) =>
          new TableRow({
            children: r.map((c, i) => bodyCell(c, widths[i], { shade: ri % 2 === 1 ? "F2F6F8" : undefined })),
          })
      ),
    ],
  });
}
function spacer() {
  return new Paragraph({ spacing: { after: 120 }, children: [] });
}
function hr() {
  return new Paragraph({
    spacing: { before: 100, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F4E5F", space: 1 } },
    children: [],
  });
}

// ---------- content ----------
const content = [];

// TITLE PAGE
content.push(
  new Paragraph({ spacing: { before: 2000, after: 200 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "AgriVision", bold: true, size: 64, color: "1F4E5F" })] }),
  new Paragraph({ spacing: { after: 100 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Strategic Founder, Investor, Agronomist & Customer Analysis", size: 30, color: "44546A" })] }),
  new Paragraph({ spacing: { after: 600 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "A brutally honest build, sell, and validate roadmap for a Kenyan farm productivity intelligence platform", italics: true, size: 22, color: "666666" })] }),
  new Paragraph({ spacing: { after: 40 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Prepared for: AgriVision Founder", size: 22 })] }),
  new Paragraph({ spacing: { after: 40 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "Pilot geography: Taita Taveta County, Kenya", size: 22 })] }),
  new Paragraph({ spacing: { after: 40 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: "June 2026", size: 22 })] }),
  new Paragraph({ children: [new PageBreak()] }),
);

// CORE INSIGHT BANNER
content.push(
  h1("Core Insight, Stated Up Front"),
  p("Before the thirteen-part breakdown: the single highest-leverage finding in this analysis is that AgriVision is currently designed to solve an information problem (\u201Cfarmers lack data\u201D), but the sharpest, most monetizable pain in the target segment is a trust and accountability problem (\u201Cowners cannot verify what happens on their land when they are not physically present\u201D). Kenyan commercial farms in the 5\u2013100 acre range are disproportionately owned by professionals, civil servants, diaspora, and absentee investors who hired the farm rather than work it themselves. That principal-agent gap \u2014 not crop science \u2014 is the wedge. Every recommendation below is built around that reframe.", { bold: false }),
  spacer(),
);

// TOC
content.push(
  h1("Table of Contents"),
  new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
);

content.push(
  h1("Part 1 \u2014 Brutally Honest Assessment"),
  h2("Is this a good business?"),
  p("Conditionally \u2014 but not as currently scoped. The underlying market (commercial horticulture in Kenya, labor-intensive, cash-flow volatile, poorly digitized) is real and underserved. But the six-module vision described \u2014 farm setup, crop calendar engine, workforce management, satellite monitoring, farm intelligence, and executive reporting \u2014 is roughly five separate products bundled into one pitch. That is not a go-to-market plan, it is a five-year roadmap wearing a 90-day costume. A good business here is very plausible. This specific plan, executed in this order, is not yet one."),
  h2("Dangerous assumptions"),
  bullets([
    "That farmers have a \u2018productivity\u2019 problem they will pay to solve, rather than a cash, price, and trust problem they are already living with. Farmers rarely say \u2018I need better data\u2019; they say \u2018my foreman is stealing from me\u2019 or \u2018tomato prices crashed and I lost everything.\u2019",
    "That digital records can replace, rather than threaten, the existing relationship-based trust system between owner, foreman, and workers. Introducing surveillance-feeling tools into a labor relationship is a social intervention, not just a software rollout.",
    "That a 12-acre or 20-acre farm block is best understood through 10-meter resolution Sentinel-2 NDVI. It is usable, but coarse \u2014 a single pixel can straddle two different crop conditions on a small block, so the signal-to-noise ratio for genuinely small parcels is worse than the pitch implies.",
    "That a monthly executive report is the right cadence. Owners worried about theft or disease want to know today, not in four weeks \u2014 by the time a monthly report flags an underperforming block, the loss has already happened.",
    "That one product can serve a 12-acre family-run tomato farm and a 150-acre estate with a compliance department. Their buyers, budgets, sales cycles, and definitions of \u2018done\u2019 are not the same business.",
    "That satellite monitoring is a sellable headline. The founder has already learned this lesson once with the original AgriVision concept \u2014 the same trap is being walked back into here, just with three more modules attached to it.",
  ]),
  h2("The biggest risks"),
  bullets([
    [{ text: "Scope risk. ", bold: true }, "Six modules means six things that can each fail to find product-market fit, and a solo-to-small founding team cannot run six discovery loops in parallel. Every module not yet validated is a place the runway can quietly leak away."],
    [{ text: "Distribution risk. ", bold: true }, "Kenyan agri-SaaS has a thin track record of self-serve adoption. This will be a relationship-driven, boots-on-ground sales motion in Taita Taveta \u2014 which means cost-to-acquire looks more like a field sales business than a SaaS business, and the financial model has to reflect that honestly."],
    [{ text: "Adoption risk inside the farm. ", bold: true }, "The people asked to enter attendance and task data day to day (foremen, workers) are often the same people whose performance the data exposes. Without a real incentive for them, data entry quality will degrade within weeks \u2014 this is the single most common reason farm-ops tools die quietly."],
    [{ text: "Connectivity and literacy risk. ", bold: true }, "Parts of Taita Taveta have inconsistent network coverage, and not every supervisor is comfortable with a data-entry-heavy Android app. Offline-first is not a nice-to-have feature here; it is a precondition for the product working at all."],
    [{ text: "Willingness-to-pay risk. ", bold: true }, "KES 30,000\u2013200,000 per season is being proposed before a single farmer has confirmed what they would actually pay. Horticulture income is seasonal and volatile (tomato price crashes are common), so a fixed software bill due regardless of harvest outcome is a hard sell unless tied directly and visibly to money saved or earned."],
    [{ text: "Founder bandwidth risk. ", bold: true }, "Crop calendar automation grounded in real agronomic best practice, a defensible NDVI alerting pipeline, and a trustworthy workforce module are each a serious build. Attempting all three before revenue exists is the most common way capital-constrained agri-tech founders run out of time."],
  ]),
  h2("Why this could fail"),
  p("The most likely failure mode is not \u2018no one wants this.\u2019 It is \u2018we built five things reasonably well, none of them got pushed hard enough to find the one farmers will actually pay for, and we ran out of runway evaluating all six modules at once.\u2019 The second most likely failure mode is dismissing the labor/trust angle as a smaller idea than \u2018the operating system for farms\u2019 and chasing the bigger vision before earning the right to it with one working wedge."),
  spacer(),
content.push(
  h1("Part 2 \u2014 Customer Validation Strategy"),
  h2("What to test first"),
  p("Before writing more code, test which job the farmer is actually hiring software to do. Run the 30-question interview framework (Part 12) against three distinct buyer types in Taita Taveta: an on-farm owner-operator, an absentee owner with a hired manager, and a hired farm manager who is not the owner. The hypothesis to test is the trust/oversight reframe from the Core Insight: that the sharpest pain is verifying what happens on the land when the owner is not there, not a general lack of agronomic information."),
  h2("What to sell first"),
  p("Sell a narrow, tamper-resistant attendance and task-completion log with a labor cost per acre view. This is the easiest value proposition to demonstrate in a single season, it attacks the largest controllable cost line (labor), and it directly answers the fear that shows up hardest in the customer POV work in Part 9: \u2018am I being cheated by people I cannot watch all day.\u2019 Satellite-based stress alerts can be sold second, framed explicitly as an independent cross-check on what the workforce log claims happened (\u2018the log says block 3 was irrigated Tuesday \u2014 here is what the satellite saw\u2019), which is a far stronger pitch than satellite monitoring sold on its own."),
  h2("What to avoid building"),
  bullets([
    "A full agronomic rules engine for the crop calendar. This is high domain complexity, carries real liability if a generated schedule is wrong, and is not what early adopters are asking for.",
    "Automated monthly executive reports. Build this only after there is a paying base that has expressed a need for it \u2014 reporting cadence should follow validated usage, not precede it.",
    "A broad \u2018farm intelligence\u2019 dashboard that tries to fuse labor, weather, and satellite data into general insight. Fusion features are usually the last thing customers value and the first thing they ignore.",
    "Building for Segment C (100+ acre estates) at all in year one. Their sales cycle, integration requirements, and support expectations will absorb founder time disproportionate to the revenue and learning gained.",
  ]),
  spacer(),
content.push(
  h1("Part 3 \u2014 Product Roadmap"),
  p("Each phase is deliberately narrow. The roadmap adds modules only after the previous phase has proven retention, not just a sale."),
  h2("Phase 1 \u2014 First paying customer (Month 1\u20132)"),
  table(
    ["Dimension", "Detail"],
    [
      ["Features", "Mobile-first, offline-capable attendance log (GPS- and time-stamped check-in/out); task assignment and completion log; auto-calculated labor cost per acre. Nothing else."],
      ["Team", "Founder + one developer (existing Django/Android base can be repurposed); informal agronomist advisor on call, not on payroll."],
      ["Budget", "KES 50,000\u2013150,000: devices for pilot foremen, data bundles, basic hosting. No paid ads, no hires."],
      ["KPIs", "One farm paying KES 20,000\u201330,000 for a pilot season; weekly active data entry by the foreman; one documented, attributable saving (e.g., a discrepancy caught between claimed and actual labor)."],
    ],
    [2400, 6960]
  ),
  h2("Phase 2 \u2014 First 5 farms (Month 3\u20135)"),
  table(
    ["Dimension", "Detail"],
    [
      ["Features", "Refine attendance/task module from pilot feedback; add a simple, manually-editable crop calendar (reminders, not an automated agronomic engine); add a basic NDVI overlay as a visual companion to the workforce log, not as a standalone sell."],
      ["Team", "Add a part-time local field agent in Taita Taveta for onboarding and trust-building visits."],
      ["Budget", "KES 300,000\u2013500,000 covering field agent stipend, travel, and continued hosting/imagery costs."],
      ["KPIs", "5 paying farms; full-season retention through at least one harvest cycle; at least one farmer reference willing to be quoted to prospects."],
    ],
    [2400, 6960]
  ),
  h2("Phase 3 \u2014 First 20 farms (Month 6\u20139)"),
  table(
    ["Dimension", "Detail"],
    [
      ["Features", "Introduce satellite stress/disease alerts as a paid upsell tier, explicitly framed as cross-checking the workforce log; lightweight, opt-in weekly or monthly report for absentee owners."],
      ["Team", "Hire one field sales / customer success person; founder shifts toward product and partnerships."],
      ["Budget", "KES 1.5M\u20132.5M, primarily salary, field travel, and device subsidies for new farms."],
      ["KPIs", "20 paying farms; CAC payback within one season; churn tracked and below an explicit threshold the founder sets after Phase 2 data exists."],
    ],
    [2400, 6960]
  ),
  h2("Phase 4 \u2014 First 100 farms (Month 10\u201318)"),
  table(
    ["Dimension", "Detail"],
    [
      ["Features", "Full module set reintroduced deliberately: tiered pricing, fuller crop calendar, executive dashboards for Segment B/C buyers; explore an M-Pesa-integrated payroll disbursement feature as a daily-use anchor."],
      ["Team", "2\u20133 field agents/CSMs, one additional developer, formal agronomist partnership (university or county extension)."],
      ["Budget", "KES 6M\u20139M, funded substantially by Phase 3 revenue plus modest external capital if needed."],
      ["KPIs", "100 paying farms; distribution partnerships with at least one agrovet, SACCO, or county extension program; early signal on whether farm records can unlock credit or insurance partnerships."],
    ],
    [2400, 6960]
  ),
  spacer(),
content.push(
  h1("Part 4 \u2014 Competitive Analysis"),
  table(
    ["Competitor", "What they do", "Weakness for this market", "Opportunity for AgriVision"],
    [
      ["EOSDA Crop Monitoring", "Global satellite-only crop monitoring SaaS, subscription-based, USD pricing.", "No labor/workforce layer; not offline-first; UI and pricing not localized to smallholder/mid-commercial Kenyan buyers; no field presence in Kenya.", "Win on hyperlocal trust and a workforce-first wedge satellite monitoring cannot offer alone."],
      ["Farmonaut", "Satellite-based monitoring with some freemium and marketplace features.", "Same localization gap as EOSDA; weak on-the-ground support; no payroll/labor trust angle.", "Differentiate on M-Pesa-native payments and in-person onboarding, which a remote SaaS cannot replicate."],
      ["Climate FieldView (Bayer)", "Precision-ag platform built around large-scale row-crop machinery integration (US/Brazil corn and soy).", "Irrelevant hardware assumptions (combine/planter integration) for 12\u2013100 acre Kenyan horticulture; not a real competitor here.", "Useful only as an aspirational long-term analog for the \u2018farm operating system\u2019 vision \u2014 not a near-term threat."],
      ["Local Kenyan agri-tech (e.g., input financing and market-linkage platforms)", "Many pivoted from crop monitoring toward financing and market access, because that is where farmer willingness-to-pay is actually highest.", "Generally do not address the on-farm labor accountability problem directly.", "Validates that the information problem alone underpays \u2014 and signals that bundling farm records with future credit or insurance access (Phase 4) is a stronger long-term differentiator than monitoring alone."],
    ],
    [1900, 2400, 2700, 2360]
  ),
  h2("Defensible advantages worth building toward"),
  bullets([
    "Hyperlocal field presence and trust relationships in Taita Taveta \u2014 something no international platform will replicate cheaply.",
    "M-Pesa-native payroll and recordkeeping, turning the app from a reporting tool into a daily operational utility workers and owners must actually open.",
    "Offline-first architecture suited to inconsistent rural connectivity, rather than a cloud-only assumption.",
    "A trust/verification value proposition (independent satellite cross-check of claimed farm activity) that none of the listed competitors are positioned to sell, because none of them have a workforce layer to verify against.",
  ]),
  spacer(),
content.push(
  h1("Part 5 \u2014 Economics"),
  p("These figures are illustrative planning assumptions, not measured data \u2014 no farmer has paid yet. Treat every number here as a hypothesis to replace with real CAC, churn, and cost-to-serve figures the moment Phase 1 produces them. The biggest unknown is cost-to-serve, because this will function more like a field sales business than a self-serve SaaS business in year one.", { italic: true }),
  h2("Working assumptions"),
  bullets([
    "Pilot price: KES 30,000 per season. Standard price once value is proven: KES 80,000\u2013100,000 per season.",
    "Two sellable seasons per year for most horticulture crops in this region, so a retained farm can plausibly be billed twice annually.",
    "Marginal cloud and Sentinel imagery cost is low (Google Earth Engine access is free for this kind of use), so the dominant cost driver is human: field agent time, device subsidies, and support \u2014 not infrastructure.",
  ]),
  h2("Illustrative model"),
  table(
    ["Stage", "Paying farms", "Revenue per season (KES)", "Approx. annual revenue (KES)", "Dominant cost driver", "Realistic gross margin"],
    [
      ["Phase 1\u20132", "5", "30,000\u201380,000", "300,000\u2013800,000", "Founder time, field travel (uncosted)", "High on a cash basis; effectively break-even once founder time is valued"],
      ["Phase 3", "20", "80,000", "~3.2M", "One field agent salary + travel", "50\u201360% after field costs"],
      ["Phase 4", "100", "80,000\u2013120,000", "16M\u201324M", "2\u20133 field agents/CSMs, support, device subsidy", "65\u201375%, improving as fixed dev cost amortizes"],
    ],
    [1300, 1100, 1900, 1900, 1860, 1300]
  ),
  p("The honest takeaway: at 5 and even 20 farms, this is not yet a venture-scale business \u2014 it is a lean, field-intensive operation that should be run to prove unit economics, not to impress investors. The investable story only becomes credible once cost-to-serve per farm is shown to drop as the field team's territory density increases (more farms per agent visit-route in the same county), which is exactly why Phase 3\u20134 stay concentrated in Taita Taveta rather than expanding counties prematurely."),
  spacer(),
content.push(
  h1("Part 6 \u2014 Product-Market Fit"),
  h2("The exact problem to solve first"),
  p("Help a farm owner who cannot be on the land every hour of every day know, with evidence they can trust, what their workforce actually did and what it actually cost \u2014 per block, per acre, per week. Not \u2018monitor crops.\u2019 Not \u2018improve productivity.\u2019 Specifically: close the trust gap between the owner and whoever is supervising the land in their absence."),
  h2("The one feature for the next 90 days"),
  p("A tamper-resistant attendance and task-completion log (GPS- and time-stamped, ideally with a lightweight photo check-in) that rolls up automatically into a labor cost per acre view. If only one thing can be built and sold in 90 days, it is this \u2014 because it is the feature most directly tied to the fear that shows up across every customer segment in Part 9, and it requires no agronomic modeling, no satellite pipeline, and no liability around giving wrong farming advice."),
  spacer(),

  h1("Part 7 \u2014 Strategic Recommendation"),
  p("If the constraints are limited money, no investors, and revenue required within six months, here is the founder's plan."),
  h2("What to build"),
  p("Only the attendance, task, and labor-cost module described in Part 6. Resist every temptation to add satellite imagery, an automated crop calendar, or a report generator until that one module has paying, retained customers."),
  h2("What to sell"),
  p("A trust and oversight tool, sold first to absentee or partially-absentee owners \u2014 people who already feel anxious about not being on their land every day. That anxiety is the strongest, most pre-existing motivation available, and it does not need to be created through education; it already exists."),
  h2("What to ignore"),
  bullets([
    "Satellite crop monitoring as a standalone sell.",
    "Automated agronomic recommendations and crop calendars.",
    "Monthly executive reports and dashboards.",
    "Large estates (Segment C) and anything requiring enterprise procurement or integration work.",
  ]),
  h2("The 90-day plan"),
  table(
    ["Window", "Focus"],
    [
      ["Days 1\u201330", "Run the 30-question interview framework (Part 12) across all three buyer types. Narrow to 3\u20135 farms willing to pilot at low or no cost. Build the minimum attendance/task/labor-cost MVP \u2014 offline-capable Android or mobile web."],
      ["Days 31\u201360", "Run the pilot live across one planting-to-mid-season window. Iterate weekly based on what foremen and owners actually do (and avoid doing) in the app. Push for one concrete, attributable result \u2014 a caught discrepancy, a documented saving \u2014 that can become a reference story."],
      ["Days 61\u201390", "Convert pilot farms to a paying \u2018founding customer\u2019 rate (e.g., KES 20,000\u201330,000). Ask each for a direct referral to one other farm owner. Begin charging new farms at the standard pilot price, and start logging real CAC and retention numbers to replace the assumptions in Part 5."],
    ],
    [2200, 7160]
  ),
  spacer(),
content.push(
  h1("Part 8 \u2014 Customer Analysis"),
  p("Three segments are analyzed in depth: small commercial farms (5\u201320 acres, 5\u201320 workers), medium commercial farms (20\u2013100 acres, 20\u2013100 workers), and large/estate operations (100+ acres). The figures below are grounded estimates for Kenyan horticulture economics, not audited data, and should be sharpened with real numbers as pilots progress."),

  h2("Segment A \u2014 Small Commercial Farms (5\u201320 acres, 5\u201320 workers)"),
  h3("Economics"),
  bullets([
    "Revenue is highly volatile and crop-price-dependent \u2014 horticulture crops like tomato are notorious for boom-bust pricing, where a glut can crash farmgate prices to near zero within weeks.",
    "Labor typically represents 30\u201340% of total production cost, paid largely as casual daily wages for planting, weeding, and harvesting.",
    "Input costs (seed, fertilizer, agrochemicals) are significant and rising, especially on disease-prone crops, and are frequently financed through agrovet credit.",
    "Net margins are thin and can turn negative in a bad price or disease season \u2014 there is rarely a comfortable buffer for discretionary software spend.",
  ]),
  h3("Current workflow"),
  p("The owner or a family member is usually the direct supervisor, with a foreman managing day labor informally. Attendance is tracked by verbal headcount or a paper notebook. Decisions are made on experience and gut feel, reinforced by advice from neighboring farmers. WhatsApp is used for input-supplier contact and sometimes for SMS-based county or NGO extension advisories. M-Pesa handles most payments, including wages."),
  h3("Top operational frustrations"),
  bullets([
    "Unreliable turnout of casual day laborers, especially during peak planting and harvest windows.",
    "Supervision gaps whenever the owner is away from the farm.",
    "Irrigation timing decided by guesswork rather than soil or crop-stage data.",
    "Pest and disease detected only once visible damage has already spread.",
    "Post-harvest losses from delayed or mishandled transport to market.",
    "Theft of produce or inputs, sometimes involving the very workers hired to protect them.",
    "No clear visibility into which block or crop variety is underperforming and why.",
    "Difficulty coordinating labor and input timing across multiple small blocks at once.",
  ]),
  h3("Top financial frustrations"),
  bullets([
    "Cash flow gaps between paying for inputs and receiving harvest income.",
    "Unpredictable market prices that can erase a season's margin overnight.",
    "Mounting agrovet credit and informal debt carried between seasons.",
    "No reliable record of true cost per acre, so profitability is felt rather than known.",
    "Payroll disputes and suspected ghost workers with no independent way to verify claims.",
    "Inability to use farm performance as evidence when seeking credit from a SACCO or bank.",
  ]),
  h3("Buying behavior"),
  bullets([
    "Trigger: usually a bad season or a loss event (a theft incident, a missed disease outbreak), or a direct recommendation from a trusted neighboring farmer.",
    "Decision maker: the owner, who is frequently also the on-site supervisor.",
    "Influencers: a trusted agronomist, county extension officer, or SACCO official.",
    "Sales cycle: long relative to deal size \u2014 trust has to be built over weeks, and the pitch lands best right after a harvest payout, not during the cash-tight planting window.",
  ]),
  lead("Budget reality: ", "realistically KES 5,000\u201315,000 per month if billed monthly, or KES 20,000\u201340,000 if billed once per season \u2014 and billing should follow the harvest cash cycle, not a flat monthly SaaS calendar."),
  lead("Churn risk: ", "high if the app does not show a clear, attributable saving within one season, if data entry burden falls unfairly on a resentful foreman, if connectivity issues create daily friction, or if a bad season triggers a blanket cut of anything seen as non-essential spend."),
  spacer(),
content.push(
  h2("Segment B \u2014 Medium Commercial Farms (20\u2013100 acres, 20\u2013100 workers)"),
  h3("Economics"),
  bullets([
    "More diversified crop mix and some economies of scale in input purchasing, but labor exposure grows with farm size \u2014 more workers means a bigger payroll fraud surface, not a smaller one.",
    "Often has some formal bookkeeping (an Excel sheet or a part-time bookkeeper), but rarely a true cost-per-block accounting system.",
    "A meaningful share of farms this size in Kenya are owned by professionals, civil servants, or diaspora investors who are not physically present \u2014 the farm is a managed asset, not a daily occupation.",
  ]),
  h3("Current workflow"),
  p("A dedicated farm manager runs day-to-day operations, frequently reporting to an absentee owner by phone call or occasional visit. Recordkeeping is more formal than Segment A but still largely manual or spreadsheet-based. Where the owner has banking or SACCO relationships, there is some pressure toward better financial documentation, but it is rarely systematic."),
  h3("Top operational frustrations"),
  bullets([
    "Supervising a workforce spread across multiple blocks with only one or two managers on site.",
    "Verifying the farm manager's own accountability when the owner is absent \u2014 the classic principal-agent gap.",
    "Payroll complexity at scale, including statutory deductions for any formally registered workers.",
    "Input pilferage or misuse that is hard to catch without an independent record.",
    "No benchmarking across blocks or seasons to know which parts of the farm are actually worth the input spend.",
    "Difficulty reconciling the manager's verbal or written reports with what is actually happening on the ground.",
  ]),
  h3("Top financial frustrations"),
  bullets([
    "Suspected embezzlement or under-the-table side deals by farm staff, with no independent data source to confirm or rule it out.",
    "Manager-reported numbers that cannot be verified, which undermines trust in every report received.",
    "Difficulty using farm performance data to negotiate better financing terms.",
    "Cost overruns on inputs or labor that are only discovered well after the fact.",
  ]),
  h3("Buying behavior"),
  bullets([
    "Trigger: a discovered discrepancy, a disappointing season relative to expectations, or a desire to professionalize the operation ahead of expansion.",
    "Decision maker: the owner \u2014 especially when absentee, since they are the one losing sleep over what they cannot see.",
    "Important dynamic: the farm manager may be a reluctant adopter or even a quiet blocker, since the tool increases their own visibility and accountability. The sale must be made to, and the trial driven by, the owner.",
    "Sales cycle: moderate, shortened considerably if the owner has already had a bad experience with a manager.",
  ]),
  lead("Budget reality: ", "higher willingness to pay than Segment A, plausibly KES 60,000\u2013150,000 per season, justified by a larger revenue base and a much clearer return from preventing fraud or inefficiency at scale."),
  lead("Churn risk: ", "high if the manager actively or passively sabotages adoption, if reports do not translate into owner action, or if data entry discipline collapses without an on-site champion."),
  spacer(),
content.push(
  h2("Segment C \u2014 Large Commercial Farms / Estate Operations (100+ acres)"),
  h3("Economics"),
  bullets([
    "Larger capital base, often formal payroll with NSSF/NHIF compliance and sometimes unionized labor.",
    "May already run accounting or even basic ERP systems, and may need to meet export certification standards such as GlobalGAP.",
    "Single large losses (a certification failure, a major disease outbreak across a big block) carry outsized financial and reputational consequences.",
  ]),
  h3("Current workflow"),
  p("Professional management structure with separate functions for HR, agronomy, and operations. Purchasing and software adoption typically run through a more formal procurement process involving multiple stakeholders rather than a single owner decision."),
  h3("Top pain points"),
  bullets([
    "Compliance and certification reporting overhead (GlobalGAP, FairTrade, buyer audits).",
    "Integrating any new tool with existing HR or accounting systems rather than running in a silo.",
    "Block-level yield optimization at a scale where small percentage gains are worth a great deal in absolute terms.",
    "Coordinating large-scale labor across export deadlines and buyer contract obligations.",
  ]),
  h3("Buying behavior and recommendation"),
  p("Decision-making sits with an operations director or general manager, shaped by agronomy and compliance staff, and the sales cycle runs months rather than weeks. Budgets can be substantial \u2014 potentially KES 200,000 or more per season \u2014 but so is the cost of winning the deal, and expectations around uptime, support, and integration will be enterprise-grade from day one."),
  lead("Recommendation: ", "Segment C is not the right early target. The sales cycle is too long, the competitive bar too high, and the support expectations too demanding for a resource-constrained founder. Win Segments A and B first, build a track record, and move upmarket once there is a team and a product mature enough to earn an estate's trust."),
  spacer(),
content.push(
  h1("Part 9 \u2014 Customer POV (Point of View Analysis)"),
  p("Written from inside each segment's head, not the founder's."),

  h2("Segment A owner"),
  quoteLine("Will my foreman cheat me again this season? Did the rains or the price collapse before I even get to harvest? Can I cover wages and my agrovet loan this week?"),
  bullets([
    [{ text: "Biggest fears: ", bold: true }, "crop failure, a debt spiral from input credit, labor theft, a market price collapse right before harvest."],
    [{ text: "Biggest goals: ", bold: true }, "a stable profit, not being cheated, eventually expanding to more acres if this season works out."],
    [{ text: "Believes the cause is: ", bold: true }, "bad luck with weather or price, untrustworthy workers or a dishonest foreman, sometimes fake seed or fertilizer from an agrovet."],
    [{ text: "Already tried: ", bold: true }, "putting a relative in as supervisor, asking neighbors for advice, switching agrovet suppliers, informal insurance through table-banking or a SACCO."],
    [{ text: "Why it failed: ", bold: true }, "relatives also get tired or compromised, neighbor advice is anecdotal, and there is still no real data trail to prove who is cheating whom."],
  ]),
  h3("Why this owner would distrust AgriVision"),
  quoteLine("Another app that takes my data and gives nothing back. I don't have time to type into a phone after a full day in the field. This is townspeople software, not for us shamba people."),
  h3("Objections"),
  bullets([
    "\u201CI already know my farm.\u201D",
    "\u201CI'm not even sure I'll profit this season \u2014 why would I add another bill?\u201D",
    "\u201CSatellite data isn't useful. I can see my plants are stressed just by walking there.\u201D",
  ]),
  h3("What would build trust"),
  bullets([
    "A neighboring farmer's testimonial showing a real KES amount saved.",
    "A free trial that runs through to harvest, so the risk is on AgriVision, not the farmer.",
    "Endorsement from a known local agronomist or county extension officer.",
    "A partnership with county government or a credible NGO.",
    "An app that works entirely in Kiswahili with a simple, low-literacy-friendly interface.",
  ]),
  spacer(),

  h2("Segment B owner / manager"),
  quoteLine("Is my manager actually managing well when I'm not there? Are my numbers what they should be compared to similar farms? Am I being cheated by my own staff?"),
  bullets([
    [{ text: "Biggest fears: ", bold: true }, "embezzlement, a manager's incompetence staying hidden, a disease outbreak no one catches early enough."],
    [{ text: "Biggest goals: ", bold: true }, "peace of mind while absent, professionalizing the operation, eventually using farm records to access better financing."],
    [{ text: "Believes the cause is: ", bold: true }, "a lack of visibility and accountability systems, and a manager who holds too much unchecked authority."],
    [{ text: "Already tried: ", bold: true }, "spot-check visits, putting a \u2018trusted\u2019 relative in as an extra supervisor, requesting Excel reports from the manager."],
    [{ text: "Why it failed: ", bold: true }, "visits are infrequent, and manual reports can simply be shaped to look good \u2014 there is no independent source to check them against."],
  ]),
  h3("Why this owner would distrust AgriVision"),
  quoteLine("Won't my manager just enter fake data anyway? Is this just another report I have to read but still can't verify?"),
  p("This is the sharpest and most legitimate objection in the entire analysis \u2014 it means the product has to include genuine anti-gaming features (GPS- and time-stamped check-ins, photo verification) and, eventually, an independent satellite cross-check, or this entire segment will correctly conclude the tool solves nothing."),
  h3("What would build trust"),
  bullets([
    "Tamper-resistant, GPS- and photo-verified attendance that the manager cannot simply type around.",
    "An independent satellite cross-check that catches mismatches \u2014 for example, a manager reporting that a block was irrigated while the imagery shows no corresponding change.",
    "Real-time visibility from a phone while traveling, rather than a delayed monthly summary.",
  ]),
  spacer(),

  h2("Segment C estate general manager"),
  quoteLine("Will we pass the next compliance audit? Can a small startup actually deliver the uptime and support a deal this size requires?"),
  bullets([
    [{ text: "Biggest fears: ", bold: true }, "certification or contract loss, a major crop failure across a large block, reputational damage with export buyers."],
    [{ text: "Biggest goals: ", bold: true }, "operational efficiency at scale, reliable compliance documentation, predictable yields for buyer contracts."],
  ]),
  h3("Why this manager would distrust AgriVision"),
  quoteLine("We already have systems. Why would we add an unproven one without a track record at our scale?"),
  h3("What would build trust"),
  bullets([
    "Case studies from comparable-scale clients.",
    "A demonstrated support SLA and clear data security practices.",
    "Proof of successful integration with existing accounting or HR tools.",
  ]),
  spacer(),
content.push(
  h1("Part 10 \u2014 Customer Jobs-To-Be-Done"),
  p("The wrong framing is \u201Cmonitor crops.\u201D The real jobs being hired for are about certainty and control over money and trust, not data for its own sake."),
  h2("Segment A"),
  bullets([
    [{ text: "Functional: ", bold: true }, "know that workers showed up and did the work, even when I can't be there all day; catch a problem before it costs me real money."],
    [{ text: "Emotional: ", bold: true }, "feel in control, not foolish, not cheated."],
    [{ text: "Social: ", bold: true }, "be seen by family and community as a capable, modern farmer \u2014 not someone who lost their farm to theft or mismanagement."],
  ]),
  h2("Segment B"),
  bullets([
    [{ text: "Functional: ", bold: true }, "supervise the farm remotely with confidence; get independent proof of what is actually happening on the land."],
    [{ text: "Emotional: ", bold: true }, "feel secure rather than anxious while away; feel in command despite the physical distance."],
    [{ text: "Social: ", bold: true }, "be seen among peers as a savvy investor-owner, not a naive absentee landlord being quietly fleeced."],
  ]),
  h2("Segment C"),
  bullets([
    [{ text: "Functional: ", bold: true }, "maintain compliance and optimize large-scale operations with auditable records."],
    [{ text: "Emotional: ", bold: true }, "reduce the stress of audits and large-scale exposure."],
    [{ text: "Social: ", bold: true }, "be seen as running an internationally credible, professionally managed operation."],
  ]),
  spacer(),
content.push(
  h1("Part 11 \u2014 Customer Value Proposition Testing"),
  p("Ranked from the customer's perspective, most to least valuable, based on the trust/accountability reframe established in the Core Insight."),
  table(
    ["Rank", "Feature", "Why"],
    [
      ["1", "Attendance tracking (tamper-resistant)", "Directly answers the number one fear across every segment \u2014 theft and ghost workers \u2014 and the value is understood instantly, with no education needed."],
      ["2", "Workforce / task management", "A natural extension of attendance \u2014 proves not just that someone showed up, but that the work was actually done."],
      ["3", "Productivity analytics (labor cost per acre, output per worker)", "Turns raw attendance into the answer to \u2018is this worth it, and is someone cheating me,\u2019 but only delivers value once 1 and 2 are trusted."],
      ["4", "Disease / stress alerts", "High emotional value because crop failure is a core fear, but farmers will not trust an alert over their own eyes until the tool has a track record."],
      ["5", "Payroll", "High utility if it works flawlessly (saves manual M-Pesa effort), but high risk \u2014 a bug here means unpaid workers and a trust crisis, not just an inconvenience."],
      ["6", "Agronomic recommendations", "Valuable in principle but runs straight into \u2018I already know my farm\u2019 unless advice is hyper-localized and has a proven track record."],
      ["7", "Yield forecasting", "Interesting, but hard to trust without season-over-season proof; more useful to a future lender or buyer than to the farmer in year one."],
      ["8", "Farm reports", "Useful for an absentee Segment B owner, far less useful for a present Segment A owner who already sees the farm daily."],
      ["9", "Satellite monitoring (standalone)", "The founder has already learned this lesson once \u2014 weak as a standalone sell; far stronger repositioned as a verification layer behind the workforce data."],
      ["10", "Executive dashboards", "Nice-to-have, largely redundant with simple reports for Segment A; mainly relevant to Segment C."],
      ["11", "Weather intelligence", "Already available for free via SMS from county or meteorological services in most cases, so it differentiates and monetizes least on its own."],
    ],
    [900, 3000, 5460]
  ),
  spacer(),
content.push(
  h1("Part 12 \u2014 Customer Interview Framework"),
  p("Thirty open, non-leading questions, organized into six categories of five. None of these pitch AgriVision \u2014 the goal is to surface real workflows, pain, and willingness to pay without suggesting the answer."),
  h2("Operations"),
  numbered([
    "Walk me through what happened on your farm yesterday, from morning to evening.",
    "How do you currently know whether the work you assigned actually got done?",
    "What is the last thing that went wrong on the farm that you only found out about later?",
    "How do you decide what needs to happen on the farm each week?",
    "Tell me about a time the farm did not run the way you expected while you were away.",
  ], "operations"),
  h2("Labor"),
  numbered([
    "How do you currently keep track of who worked, and for how long?",
    "Tell me about the last disagreement you had with a worker or foreman over pay or hours.",
    "How do you decide how many workers to hire for a given task?",
    "What happens when a worker does not show up as expected?",
    "How confident are you that the hours you pay for match the hours actually worked?",
  ], "labor"),
  h2("Crop Management"),
  numbered([
    "How do you currently decide when to irrigate, fertilize, or spray?",
    "Tell me about the last time you noticed a problem with your crop \u2014 how did you find out, and how long had it likely been there?",
    "Where do you currently get advice when something looks wrong with your crop?",
    "What is the biggest crop loss you have experienced in the last two years, and what caused it?",
    "How do you currently compare how one block or field is performing against another?",
  ], "crop"),
  h2("Decision Making"),
  numbered([
    "Walk me through the last big decision you made about the farm \u2014 what information did you use?",
    "Tell me about a decision you made that you later wished you had had better information for.",
    "Who do you talk to before making a major decision about the farm?",
    "What records, if any, do you keep from one season to compare with the next?",
    "How do you know, at the end of a season, whether it was a good one or not?",
  ], "decision"),
  h2("Financial Management"),
  numbered([
    "How do you currently track what it costs you to run the farm, block by block?",
    "Tell me about a time the farm's finances surprised you, for better or worse.",
    "How do you currently decide whether a particular crop or block was worth the investment?",
    "What is your process for getting credit or financing when you need it?",
    "What financial record, if you had had it, would have changed a decision you made recently?",
  ], "financial"),
  h2("Technology Adoption"),
  numbered([
    "What apps or tools, if any, do you currently use to manage the farm?",
    "Tell me about a time you tried a new tool or app for the farm \u2014 what happened?",
    "What would have to be true for you to trust a new app with information about your farm?",
    "How comfortable are the people working with you on the farm with using a smartphone?",
    "In your experience, what is the biggest reason a farm tool has failed to stick?",
  ], "techadopt"),
  spacer(),
content.push(
  h1("Part 13 \u2014 The Customer's Day"),
  h2("A day in the life of a farm owner"),
  bullets([
    [{ text: "Early morning: ", bold: true }, "wakes up, often already thinking about whether yesterday's irrigation or spraying instruction was actually carried out \u2014 there is no way to know until physically checking or calling the foreman."],
    [{ text: "Mid-morning: ", bold: true }, "calls or visits the farm to check on workers. If absent, relies entirely on a phone call to the foreman, whose account cannot be independently verified."],
    [{ text: "Midday: ", bold: true }, "inspects crops if present, looking for visible stress or disease \u2014 by the time anything is visible to the eye, the underlying problem may already be days old."],
    [{ text: "Afternoon: ", bold: true }, "makes decisions about labor allocation, input purchases, or harvest timing, almost always based on incomplete information and recent memory rather than a written record."],
    [{ text: "Evening: ", bold: true }, "handles a problem \u2014 a payment dispute, a missing input, a worker complaint \u2014 reactively, after it has already become a conflict rather than catching it early."],
  ]),
  h3("Friction, delays, and information gaps"),
  bullets([
    "A full day or more between something going wrong on the farm and the owner finding out about it.",
    "No independent record to settle a labor or payment dispute \u2014 it becomes one person's word against another's.",
    "Decisions made from memory and verbal reports rather than any written, comparable record.",
    "Anxiety that persists throughout the day specifically during the hours the owner is away from the land.",
  ]),
  h3("Where AgriVision fits"),
  p("The highest-leverage entry point is the early morning and mid-morning friction: the owner's very first need each day is reassurance about what happened since they last checked. A tamper-resistant attendance and task log that can be checked from a phone in thirty seconds removes the single biggest recurring anxiety in this day \u2014 before any satellite data, crop calendar, or executive report would ever be opened."),
  spacer(),

  h1("Final Strategic Question"),
  h2("Would I buy AgriVision today, as the farm owner?"),
  p("As currently scoped \u2014 six bundled modules, unproven pricing, a monitoring-first pitch \u2014 the honest answer is no. The price feels disconnected from proven value, the satellite-and-reports framing does not address the fear that is actually keeping the owner up at night, and \u2018I already know my farm\u2019 remains a live, unanswered objection."),
  p("Narrowed to a tamper-resistant attendance and labor-cost tool, offered as a free or low-cost trial through a full season, sold explicitly as a way to know what is happening on the land when the owner cannot be there \u2014 yes. That is a specific, believable, low-risk-to-try answer to a fear the owner already has every single day."),
  h2("Redesigning the business around that insight"),
  p("AgriVision should reposition from a \u201CFarm Productivity Intelligence Platform\u201D to a \u201CFarm Trust and Accountability\u201D tool in its early go-to-market language, even while the longer-term \u2018operating system for farms\u2019 vision stays intact as the multi-year destination. Concretely:"),
  bullets([
    "Lead every pitch, every demo, and every piece of marketing with the attendance, task, and labor-cost-per-acre module \u2014 nothing else, until it has paying, retained customers.",
    "Introduce satellite imagery later, explicitly as an independent verification layer behind workforce claims, never as a standalone headline feature.",
    "Hold the agronomic recommendation engine and automated executive reporting until there is a paying base actively asking for them.",
    "Target Segments A and B first, with a deliberate emphasis on partially-absentee owners, since their existing anxiety is the strongest and most pre-existing motivation available \u2014 and explicitly deprioritize Segment C until the product and team have matured.",
    "Treat the 90-day plan in Part 7 as the literal next step, not a hypothetical one.",
  ]),
// ===== PART_MARKER: insert further .push() calls above this line =====

// ---------- assemble & write ----------
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: FONT, color: "1F4E5F" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, font: FONT, color: "2E75B6" },
        paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: FONT, color: "44546A" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      ...["operations", "labor", "crop", "decision", "financial", "techadopt"].map((ref) => ({
        reference: ref,
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
      })),
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: "AgriVision Strategic Analysis", size: 16, color: "888888" })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Page ", size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "888888" })],
      })] }),
    },
    children: content,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("/home/claude/agrivision_report/AgriVision_Strategic_Analysis.docx", buffer);
  console.log("done");
});