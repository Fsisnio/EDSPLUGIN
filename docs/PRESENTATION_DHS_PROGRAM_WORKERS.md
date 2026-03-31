# DHS Hybrid Plugin Platform  
**Presentation for The DHS Program staff**  
*Speaker notes & slide outline*

---

## 1. Title slide

**DHS Hybrid Plugin Platform**  
*Web analytics, microdata workflows, and GIS — aligned with DHS Program data and standards*

- Optional subtitle: *EDHS / DHS indicator exploration without replacing official tools*

---

## 2. Why this matters to DHS Program colleagues

- Researchers and partners routinely use **aggregated indicators** (STATcompiler / DHS API) and **survey microdata** (with proper agreements).
- Gaps this platform addresses:
  - **One place** to explore official API catalog data *and* run **reproducible** indicator logic on uploaded sessions (when authorized).
  - **Spatial views** (choropleths by admin level) when boundaries are available.
  - **Transparency**: DHS Program API access is proxied server-side; users may supply **their own API key** or rely on a host-configured key.

*Positioning:* This is a **research and analysis helper**, not a replacement for DHS data distribution, MEASURE DHS, or official citation requirements.

---

## 3. What the platform is (in one sentence)

A **FastAPI backend** plus a **Streamlit web dashboard** (and an optional **QGIS plugin**) that:

1. Connects to **The DHS Program API** (`api.dhsprogram.com`) for countries, surveys, indicators, and aggregated data.  
2. Supports **session-based** work with survey files (e.g. `.dta`, `.sav`) where policy allows — with **no persistent microdata storage by default**.  
3. Computes **registered indicators** (e.g. fertility, stunting, modern contraception, women’s autonomy) with **sampling weights** where applicable.

---

## 4. Audience & typical users

| User type | Typical use |
|-----------|-------------|
| Analysts | Browse indicators, pull API data, export CSV/JSON, charts |
| Methodologists | Compare microdata-based estimates vs. published logic (within session) |
| GIS users | QGIS plugin: choropleths linked to the same backend API |

---

## 5. Feature walkthrough (demo order)

**A. DHS Program API (aggregated)**  
- Catalog: indicators, countries, filters.  
- Data pull with year ranges; exports.  
- **Attribution:** Data source is **The DHS Program** / STATcompiler; methodology links in the app.

**B. Microdata path (session)**  
- Sample / upload / URL import (where deployed).  
- Session metadata: country, year, survey type.  
- Indicator selection + **weights** (e.g. `v005`-style).  
- Grouped breakdowns, maps (Folium), exports.

**C. Optional: QGIS**  
- Plugin connects to the same API: indicators + **spatial aggregation** to admin boundaries (local boundary datasets).

---

## 6. Data governance & compliance (talk track)

- **Default:** `DHS_ALLOW_PERSISTENT_MICRODATA` is **off** — processing is **session-oriented** with **TTL** and cleanup of temp storage.  
- Suitable for environments that require **no long-term copy** of microdata on the server.  
- **API keys:** Host can set `DHS_PROGRAM_API_KEY`; end users can override via **optional header** / UI field (their own key from `api.dhsprogram.com`).  
- **Citations:** UI encourages proper **DHS Program** attribution for API-sourced statistics.

*Invite feedback:* If DHS Program has additional **technical or policy** requirements, the architecture can be adjusted (e.g. stricter storage, audit logs, SSO).

---

## 7. Architecture (simple diagram for slide)

```
[ Browser ]  →  [ Streamlit dashboard ]
                    ↓ HTTPS
              [ FastAPI /api/v1 ]
                    ↓                    ↓
         [ Session engine + indicators ]   [ Proxy → api.dhsprogram.com ]
                    ↓
         [ Optional: QGIS plugin ]
```

- **Deployable** as a single container (e.g. Render) or split services.  
- **OpenAPI** docs at `/docs` for integration and review.

---

## 8. Indicator engine (high level)

- **Pluggable registry** — new indicators implement a shared `BaseIndicator` contract.  
- **Built-ins today** include themes such as:  
  - Total fertility / fertility-related  
  - Stunting (child anthropometry)  
  - Modern contraception  
  - Women’s autonomy (example dimensions)  
- **Extensible** for additional DHS-harmonized measures pending requirements and testing.

---

## 9. What we are *not* claiming

- Not an official DHS Program product unless explicitly adopted.  
- Does not replace **data user agreements**, **country authorization**, or **IHSN / MEASURE** distribution rules.  
- Aggregated tabulations from the API remain subject to **DHS Program API terms** and citation standards.

---

## 10. Discussion prompts (for Q&A)

1. Interest in a **formal collaboration** or **technical review** of indicator definitions vs. DHS documentation?  
2. Preferred **disclaimers** or **branding** when shown next to official DHS materials?  
3. Requirements for **audit trails**, **PII**, or **regional hosting** for partner deployments?  
4. Whether **training materials** or **sample workflows** should align with a specific DHS course (e.g. DHS Statistics).

---

## 11. Closing slide

**DHS Hybrid Plugin Platform**  
- Transparent use of **The DHS Program API**  
- **Session-safe** microdata workflows  
- **Open API** + web + optional GIS  

**Contact / repo:** *[your GitHub or contact]*  
**Live demo:** *[your Render URL if public]*

---

## Appendix — Timing (≈15–20 min)

| Minutes | Block |
|--------:|-------|
| 2 | Title + why DHS Program audience |
| 4 | What it is + positioning |
| 6 | Live or recorded demo (API + one microdata path) |
| 3 | Governance & API keys |
| 3 | Architecture + indicators |
| 2 | Q&A |

---

*Document version: aligned with repository structure (FastAPI `edhs_core`, Streamlit `web_dashboard`, QGIS `edhs_qgis_plugin`). Update URLs and contacts before presenting.*
