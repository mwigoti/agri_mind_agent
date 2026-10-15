# Maize Health, Yield Estimation and Agronomic Advisory

## 1. Purpose

This document defines the maize health and yield domain for the AgriVision platform. It describes the agronomic logic used to estimate maize crop health, forecast yield potential, and generate actionable recommendations using field data, satellite imagery, soil conditions, and weather information.

The maize workflow is designed for practical decision support in both smallholder and commercial systems, where growers and advisors need timely guidance on crop vigor, water stress, nutrient risk, irrigation timing, pest exposure, and expected output.

This is the canonical logic reference for the maize health and yield stack. It defines what the system evaluates, why those signals matter, and how the resulting recommendations are interpreted in agronomic terms. It also establishes the domain vocabulary used by the Phase 1 MCP integration layer and the Phase 2 LangGraph orchestration layer described in the companion documents.

The stack should be read in this order:
1. maize health and yield logic in this document
2. MCP exposure and tool contracts in [MAIZE_HEALTH_YIELD_MCP_SETUP.md](MAIZE_HEALTH_YIELD_MCP_SETUP.md)
3. LangGraph orchestration and human approval flow in [MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md](MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md)

Across all three documents, the same terminology is used: maize health, maize yield, agronomic advisory, evidence-backed decision-making, and operator approval before operational action.

---

## 2. Why maize is a primary focus

Maize is a high-value staple crop that is highly sensitive to:

- water stress during vegetative and flowering stages
- heat stress during pollination and grain filling
- nutrient imbalance and poor soil structure
- pest and disease escalation under warm, humid conditions
- delayed or poorly timed operations during critical phenological windows

The AgriVision workflow specifically accounts for these risk points by combining remote sensing, soil data, weather forecast data, and crop stage awareness to make agronomic decisions.

---

## 3. The maize analytical pipeline

The platform evaluates maize fields through a multi-layer pipeline:

1. Field and crop definition
   - field geometry is stored in the database
   - crop type is mapped to maize-specific growth requirements
   - crop stage is tracked from planting date or configured growth windows

2. Soil assessment
   - soil characteristics are retrieved from FieldSoilData or SoilGrids-based fallback logic
   - key features include organic carbon, pH, clay percentage, sand percentage, CEC, and water holding capacity

3. Weather analysis
   - current and forecast conditions are collected from weather services
   - relevant variables include rainfall, temperature, humidity, wind, and stress conditions

4. Remote sensing health analysis
   - NDVI, EVI, NDMI, SAVI values are used to estimate vegetation vigor and moisture condition
   - stress metrics and anomaly indicators are combined to assess crop condition

5. Yield potential estimation
   - historical and current health signals are fused with soil and weather conditions
   - the model estimates maize yield in tonnes per hectare and identifies limiting factors

6. Agronomic recommendations
   - field anomalies generate recommendations for irrigation, pest management, planting, harvest, and managing crop stress

---

## 4. Core maize health indicators

The health assessment is built around several agronomic indicators:

### 4.1 Vegetation health

Vegetation is monitored using optical indices such as:

- NDVI: indicates vegetation density and greenness
- EVI: improves sensitivity in high biomass conditions
- NDMI: captures moisture stress and canopy water status
- SAVI: helps when soil brightness confounds vegetation signal

Maize stress is inferred when vegetation indices drop below stage-specific expected values, especially during flowering and grain-filling periods.

### 4.2 Water stress index

Water stress is a major determinant of maize performance. The system evaluates moisture deficit, rainfall anomalies, and field water status against crop growth stage needs. A maize field under water stress may show:

- lower NDMI values
- reduced canopy vigor
- delayed crop progression
- increased risk of silking stress and poor ear formation

### 4.3 Soil health and suitability

The platform considers soil properties that strongly influence maize productivity:

- soil pH and nutrient buffering
- organic carbon content
- clay and sand fractions
- bulk density
- field capacity and wilting point
- CEC and water retention capacity

Low soil quality or poor water retention tends to magnify stress during warm periods and can reduce yield even when canopy greenness looks acceptable.

### 4.4 Weather-related stress

Maize is highly affected by: 

- extreme heat above preferred temperature ranges
- very low humidity combined with little rainfall
- intense rainfall or flooding
- strong winds damaging leaves or increasing evapotranspiration

The recommendation engine flags these conditions and translates them into field actions.

---

## 5. Yield estimation approach

Maize yield estimation in AgriVision combines agronomic and remote-sensing signals with field and climate knowledge.

### 5.1 Yield-driving factors

The system considers:

- canopy vigor and greenness
- moisture stress during sensitive stages
- soil fertility and water holding capacity
- crop growth stage timing
- rainfall and temperature anomalies
- stress history and predicted risk conditions

### 5.2 Output format

The analysis produces outputs such as:

- predicted yield in tonnes per hectare
- yield category (for example, low, moderate, strong, or high potential)
- limiting factors affecting yield
- optimization potential if interventions are applied
- confidence and condition scoring

These results are designed to support agronomic planning rather than replace agronomist judgment.

### 5.3 Practical interpretation

A healthy maize field should typically show:

- strong vegetation vigor during vegetative development
- adequate moisture support through flowering
- stable canopy conditions through grain filling
- no major water stress or pest pressure

If plant health begins to decline before grain filling, the platform identifies likely yield limitation and recommends corrective actions such as irrigation, improved nutrient routing, or pest control.

---

## 6. Agronomic advisory logic for maize

The recommendation engine generates field-specific advice using weather, crop stage, and field conditions.

### 6.1 Irrigation advice

Irrigation recommendations are triggered when:

- humidity is low
- rainfall is minimal
- temperatures are high
- water stress risk is elevated

Example logic:

- low humidity + low precipitation = irrigation recommended within 24 hours
- moderate humidity and favorable wind = good irrigation window

This is especially important during tasseling, silking, and grain-filling.

### 6.2 Pest and disease risk advice

The platform flags elevated pest risk under warm, humid conditions. Maize is particularly vulnerable to disease and insect pressure when:

- humidity is high
- temperatures remain within a favorable range for pest activity
- crop canopy remains wet for extended periods

Recommendations include monitoring, treatment timing, and avoiding wind-sensitive spraying periods.

### 6.3 Weather risk warnings

The system raises alerts for:

- heat stress events
- heavy rainfall risk
- high wind conditions
- airborne damage conditions affecting crops

These warnings advise when not to schedule spraying, harvesting, or field operations.

### 6.4 Planting and harvest timing recommendations

The recommendation logic evaluates:

- temperature suitability
- rainfall amount
- wind conditions
- seasonal suitability

This helps determine whether conditions are good for planting or harvesting maize and whether the next few days are favorable for operational decisions.

---

## 7. Maize growth-stage logic

The crop-stage logic aligns field analysis with meaningful maize growth phases:

- vegetative stage: early vigor, leaf expansion, biomass formation
- flowering stage: tasseling and silking sensitivity
- grain-filling stage: moisture and nutrient demand peak
- maturity stage: nutrient remobilization and field preparation for harvest

Stress at flowering and grain-filling stages usually has a larger effect on final yield than stress during early growth. The platform therefore weights these stages more heavily in interpretation and recommendations.

---

## 8. Example advisory outcomes

Typical outputs for maize fields include:

- "Irrigation recommended within 24 hours"
- "High heat warning during midday field operations"
- "Increased pest activity expected under warm, humid weather"
- "Excellent planting conditions"
- "Crop health below expected trend during grain-filling period"
- "Yield potential is below optimum due to moisture stress and soil limitations"

Each message is paired with urgency, recommended date, and action timing to support decisions.

---

## 9. Data sources used for maize decision support

The system integrates data from several sources:

- field boundary and crop records from the application database
- weather station or API data for rainfall, temperature, and humidity
- soil characteristics from the field model or external soil datasets
- satellite vegetation indices from Earth Engine workflows
- locally derived crop stage logic

This combination creates a more reliable crop status picture than relying on one data source alone.

---

## 10. Recommended use in practice

The maize advisory system is best used as a decision-support layer. It is most valuable when used to:

- monitor field health regularly
- compare field status to expected maize performance
- identify water and nutrient stress early
- schedule inputs and interventions more precisely
- estimate whether a field is likely to meet expected production targets

Agronomic teams should validate recommendations with in-field inspection, tissue testing, and local agronomic knowledge.

---

## 11. Strengths of the maize feature set

This maize-specific workflow provides several advantages:

- integrated crop health, weather, and soil evaluation
- stage-aware understanding of maize stress sensitivity
- use of vegetation and moisture indices for early stress detection
- operational recommendations grounded in near real-time conditions
- yield estimation support for planning and farm management

---

## 12. What the system is not

AgriVision is not a fully autonomous agronomic replacement system. It is a decision-support platform that helps farmers and agronomic advisors interpret field stress, seasonal progress, and probable yield outcomes. Outputs should be interpreted with agronomic expertise and field validation.

---

## 13. Summary

The maize-focused workflow in AgriVision is designed to turn field, soil, weather, and satellite data into a clear, actionable picture of crop status. It estimates crop health, identifies water and environmental stress, predicts yield potential, and produces agronomic guidance that helps producers take the right action at the right time.

In effect, the system bridges remote sensing, agronomic logic, and farm operations to help maize growers improve resilience, optimize inputs, and make better production decisions.
