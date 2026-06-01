# Present-Day Integration Guide

## Overview
You now have a complete integration for displaying 2007 and 2024 instability forecasts in your frontend.

## Backend Changes

### API Endpoint Added
**`GET /present-day`** — Fetches and scores present-day profiles for 2007 (from Jenny gapminder) and 2024 (hand-coded)

**Response format:**
```json
{
  "forecasts_2007": {
    "country_name": {
      "country_name": "...",
      "year": 2007,
      "regime_type": "...",
      "infant_mortality": 55.0,
      "neighboring_conflicts": 2,
      "state_discrimination": true,
      "probability": 0.45,
      "probability_pct": 45,
      "risk_band": "High",
      "contributions": [...],
      "interpretation": "..."
    },
    ...
  },
  "forecasts_2024": {
    "country_name": { ... },
    ...
  },
  "errors": ["list of any processing errors"],
  "summary": {
    "countries_2007": 142,
    "countries_2024": 50,
    "errors_count": 0
  }
}
```

### Files Modified
- **`API.py`**
  - Added import: `from present_day import fetch_present_day`
  - Added `/present-day` endpoint that fetches and scores both 2007 and 2024 data

## Frontend Changes

### New Tab: "Present-Day"
A new tab has been added to your React app showing:

1. **Summary Statistics**
   - Number of countries scored
   - Average risk in 2007 vs 2024
   - Overall trend (↑ worsening / ↓ improving)

2. **Two View Modes**
   - **Table View**: Full country-by-country comparison with:
     - 2007 and 2024 instability probabilities
     - Year-over-year change (Δ)
     - Current regime type and risk band
     - Sortable by: highest 2024 risk, largest change, alphabetical
   
   - **Chart View**: Bar chart comparison of top 20 countries (2007 vs 2024)

3. **Error Reporting**
   - Any countries that failed to score are displayed with error messages

### Files Modified
- **`src/App.jsx`**
  - Added `PresentDayTab()` component (full featured comparison UI)
  - Updated TABS array to include "Present-Day"
  - Updated tab routing logic

## How to Use

### Starting the API
```bash
cd "c:\Kaeshav\Python Codes\Goldstone Model"
uvicorn api:app --reload --port 8000
```

### Starting the Frontend
In a new terminal:
```bash
npm run dev
```

### Accessing the Results
1. Open http://localhost:5173 (or your configured frontend URL)
2. Click the **"Present-Day"** tab
3. Choose between **Table** or **Chart** view
4. Sort the table by:
   - **Highest risk 2024** — Countries with most current instability
   - **Largest change** — Countries with biggest 2007→2024 shift
   - **Alphabetical** — Sort by country name

## Key Metrics Explained

### Probability (%)
- **< 15%**: Low risk
- **15–35%**: Moderate risk
- **35–60%**: High risk
- **> 60%**: Very high risk

### Change (Δ)
- **Positive (↑)**: Risk has worsened since 2007
- **Negative (↓)**: Risk has improved since 2007
- Shows in percentage points (pp)

### Risk Band
- Categorical assessment: **Low** / **Moderate** / **High** / **Very High**

## Data Sources

### 2007 Data
- **Source**: Jenny Bryan's Gapminder TSV (life expectancy)
- **IMR Conversion**: Derived from life expectancy using exponential mapping
- **Regime/Conflict/Discrimination**: Nearest prior year from historical pipeline (2005)
- **Coverage**: ~142 countries

### 2024 Data  
- **IMR**: UNICEF 2022–2023 estimates (World Bank WDI)
- **Regime**: V-Dem v13 (2023) + Freedom House 2024
- **Neighboring Conflicts**: UCDP armed conflicts (≥25 deaths/year)
- **Discrimination**: US State Dept reports 2023–2024
- **Coverage**: Hand-coded ~50 key countries

## Example Interpretation

| Country | 2007 | 2024 | Δ | Interpretation |
|---------|------|------|-------|---|
| Nigeria | 32% | 70% | +38pp | **Severe deterioration**: governance crisis, factional elections, Boko Haram |
| Chile | 8% | 6.5% | -1.5pp | **Slight improvement**: stable democracy despite constitutional turbulence |
| Poland | 5% | 4% | -1pp | **Stable**: full democracy, rule of law recovery post-2023 |

## Troubleshooting

### "API offline" message
- Check the API server is running: `uvicorn api:app --reload --port 8000`
- Ensure CORS middleware is enabled in API.py

### No data displaying
- Check browser console for errors (F12 → Console tab)
- Verify both API and frontend are running on correct ports
- Check that `present_day.py` can import successfully: `python -c "from present_day import fetch_present_day"`

### Fetch errors
- Some countries may not have complete 2007 data (shown in errors list)
- 2024 hand-coded data only includes ~50 major countries
- Frontend gracefully handles partial data availability

## Next Steps

1. **Add drill-down**: Click a country to see detailed contributor breakdown
2. **Extend 2024 coverage**: Add more countries to `PRESENT_DAY_2024` dict in `present_day.py`
3. **Refresh cycle**: Automate 2024 data updates from World Bank / V-Dem APIs
4. **Export**: Add CSV/Excel export for analysis in external tools
