import { useState, useEffect, useCallback } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts";

// ─── CONFIG ────────────────────────────────────────────────────────────────
const API = "http://localhost:8000";

const REGIME_OPTIONS = [
  { value: "full_autocracy",          label: "Full Autocracy" },
  { value: "partial_autocracy",       label: "Partial Autocracy" },
  { value: "factionalized_democracy", label: "Factionalized Democracy" },
  { value: "partial_democracy",       label: "Partial Democracy" },
  { value: "full_democracy",          label: "Full Democracy" },
];

const RISK_COLORS = {
  "Low":       "#4caf76",
  "Moderate":  "#e8a838",
  "High":      "#e06030",
  "Very High": "#c0392b",
};

const REGIME_SHORT = {
  full_autocracy:           "Autocracy",
  partial_autocracy:        "Part. Auto.",
  factionalized_democracy:  "Factional",
  partial_democracy:        "Part. Dem.",
  full_democracy:           "Democracy",
};

// ─── UTILITIES ─────────────────────────────────────────────────────────────
async function apiFetch(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || r.status);
  }
  return r.json();
}

function riskColor(band) { return RISK_COLORS[band] || "#888"; }
function probColor(p) {
  if (p < 15) return "#4caf76";
  if (p < 35) return "#e8a838";
  if (p < 60) return "#e06030";
  return "#c0392b";
}

// ─── SHARED COMPONENTS ──────────────────────────────────────────────────────
function Spinner() {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:8, color:"#888", fontSize:13 }}>
      <div style={{
        width:14, height:14, border:"2px solid #333", borderTopColor:"#a0b4c8",
        borderRadius:"50%", animation:"spin 0.8s linear infinite"
      }} />
      Loading…
    </div>
  );
}

function ErrorBox({ msg }) {
  return (
    <div style={{
      background:"#1a0c0c", border:"1px solid #5a1a1a", borderRadius:6,
      padding:"10px 14px", fontSize:13, color:"#e08080", marginTop:8
    }}>
      ⚠ {msg}. Make sure the API server is running: <code style={{color:"#f0a0a0"}}>uvicorn api:app --reload --port 8000</code>
    </div>
  );
}

function RiskBadge({ band, pct }) {
  return (
    <span style={{
      background: riskColor(band) + "22",
      border: `1px solid ${riskColor(band)}55`,
      color: riskColor(band),
      borderRadius: 4, padding:"2px 8px", fontSize:12, fontWeight:600,
      fontFamily:"'IBM Plex Mono', monospace"
    }}>
      {band} · {pct}%
    </span>
  );
}

function ProbBar({ pct, height=6 }) {
  return (
    <div style={{ background:"#1a1a2a", borderRadius:3, height, overflow:"hidden" }}>
      <div style={{
        height:"100%", width:`${Math.min(pct,100)}%`,
        background: probColor(pct),
        borderRadius:3, transition:"width 0.5s ease"
      }} />
    </div>
  );
}

// ─── TAB: FORECAST (manual scorer) ─────────────────────────────────────────
function ForecastTab() {
  const [form, setForm] = useState({
    regime_type: "partial_democracy",
    infant_mortality: 50,
    neighboring_conflicts: 1,
    state_discrimination: false,
    country_name: "",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async () => {
    setLoading(true); setError(null);
    try {
      const data = await apiPost("/forecast", form);
      setResult(data);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const set = (k, v) => setForm(f => ({...f, [k]: v}));

  return (
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:24, alignItems:"start" }}>

      {/* Left: inputs */}
      <div>
        <div style={{ marginBottom:20 }}>
          <label style={styles.label}>Country name (optional)</label>
          <input
            value={form.country_name}
            onChange={e => set("country_name", e.target.value)}
            placeholder="e.g. Country X"
            style={styles.input}
          />
        </div>

        <div style={{ marginBottom:20 }}>
          <label style={styles.label}>Regime type</label>
          <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
            {REGIME_OPTIONS.map(opt => (
              <label key={opt.value} style={{
                display:"flex", alignItems:"center", gap:10, cursor:"pointer",
                padding:"8px 12px", borderRadius:6,
                background: form.regime_type === opt.value ? "#1a2535" : "transparent",
                border: `1px solid ${form.regime_type === opt.value ? "#3a5a8a" : "#1e1e2e"}`,
                transition:"all 0.15s"
              }}>
                <input
                  type="radio" name="regime" value={opt.value}
                  checked={form.regime_type === opt.value}
                  onChange={() => set("regime_type", opt.value)}
                  style={{ accentColor:"#5a8fc0" }}
                />
                <span style={{ fontSize:13, color: form.regime_type === opt.value ? "#c8daf0" : "#888" }}>
                  {opt.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        <div style={{ marginBottom:20 }}>
          <label style={styles.label}>
            Infant mortality rate
            <span style={styles.badge}>{form.infant_mortality} / 1,000</span>
          </label>
          <input type="range" min={1} max={200} value={form.infant_mortality}
            onChange={e => set("infant_mortality", +e.target.value)}
            style={{ width:"100%", accentColor:"#5a8fc0" }}
          />
          <div style={{ display:"flex", justifyContent:"space-between", fontSize:11, color:"#555", marginTop:2 }}>
            <span>1 (OECD)</span><span>100 (sub-Saharan avg)</span><span>200 (critical)</span>
          </div>
        </div>

        <div style={{ marginBottom:20 }}>
          <label style={styles.label}>
            Neighboring conflicts
            <span style={styles.badge}>{form.neighboring_conflicts}</span>
          </label>
          <input type="range" min={0} max={6} step={1} value={form.neighboring_conflicts}
            onChange={e => set("neighboring_conflicts", +e.target.value)}
            style={{ width:"100%", accentColor:"#5a8fc0" }}
          />
        </div>

        <div style={{ marginBottom:24 }}>
          <label style={{
            display:"flex", alignItems:"center", gap:10, cursor:"pointer",
            padding:"10px 14px", borderRadius:6,
            background: form.state_discrimination ? "#1f1020" : "#0e0e1a",
            border:`1px solid ${form.state_discrimination ? "#7a3a8a" : "#1e1e2e"}`,
          }}>
            <input
              type="checkbox"
              checked={form.state_discrimination}
              onChange={e => set("state_discrimination", e.target.checked)}
              style={{ accentColor:"#9a5ac0", width:16, height:16 }}
            />
            <span style={{ fontSize:13, color: form.state_discrimination ? "#d0a0e8" : "#888" }}>
              State-led political discrimination active
            </span>
          </label>
        </div>

        <button onClick={submit} disabled={loading} style={styles.btn}>
          {loading ? "Scoring…" : "Run Forecast →"}
        </button>
        {error && <ErrorBox msg={error} />}
      </div>

      {/* Right: results */}
      <div>
        {!result && !loading && (
          <div style={{ color:"#444", fontSize:13, paddingTop:40, textAlign:"center" }}>
            Configure variables and run forecast
          </div>
        )}
        {loading && <div style={{ paddingTop:40, display:"flex", justifyContent:"center" }}><Spinner /></div>}
        {result && (
          <div style={{ animation:"fadeIn 0.3s ease" }}>
            <div style={{
              background:"#0c1220", border:"1px solid #1e2e40", borderRadius:10,
              padding:"20px 24px", marginBottom:16
            }}>
              {result.country_name && (
                <div style={{ fontSize:12, color:"#557", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:4 }}>
                  {result.country_name}
                </div>
              )}
              <div style={{
                fontSize:52, fontWeight:300, letterSpacing:"-2px",
                color: probColor(result.probability_pct),
                fontFamily:"'IBM Plex Mono', monospace",
                lineHeight:1, marginBottom:8
              }}>
                {result.probability_pct}%
              </div>
              <ProbBar pct={result.probability_pct} height={8} />
              <div style={{ marginTop:10, display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
                <RiskBadge band={result.risk_band} pct={result.probability_pct} />
                <span style={{ fontSize:12, color:"#556" }}>{result.odds_ratio_vs_stable}× vs. stable reference</span>
              </div>
            </div>

            <div style={{ fontSize:12, color:"#667", lineHeight:1.6, marginBottom:16, padding:"0 2px" }}>
              {result.interpretation}
            </div>

            <div style={{ background:"#0a0f18", borderRadius:8, padding:"14px 16px", border:"1px solid #181828" }}>
              <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:10 }}>
                Variable contributions
              </div>
              {result.contributions.map(c => (
                <div key={c.variable} style={{ marginBottom:8 }}>
                  <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, marginBottom:3 }}>
                    <span style={{ color:"#889" }}>{c.variable}</span>
                    <span style={{ color:"#aab", fontFamily:"'IBM Plex Mono', monospace" }}>
                      {Math.round(c.share_of_total * 100)}%
                    </span>
                  </div>
                  <div style={{ background:"#141420", borderRadius:2, height:4 }}>
                    <div style={{
                      height:"100%", width:`${c.share_of_total * 100}%`,
                      background: c.direction === "destabilising" ? "#e06030" : "#4caf76",
                      borderRadius:2, transition:"width 0.4s ease"
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── TAB: TIME SERIES ───────────────────────────────────────────────────────
function TimeSeriesTab({ countries }) {
  const [selected, setSelected] = useState("Colombia");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (country) => {
    setLoading(true); setError(null); setData(null);
    try {
      const d = await apiFetch(`/pipeline/series/${encodeURIComponent(country)}`);
      setData(d);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (selected) load(selected); }, [selected, load]);

  const chartData = data?.chart_data?.map(row => ({
    ...row,
    fill: probColor(row.probability_pct),
  })) || [];

  return (
    <div>
      <div style={{ marginBottom:20, display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
        <label style={styles.label}>Select country</label>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          style={styles.select}
        >
          {countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {data && (
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            <span style={{ fontSize:12, color:"#667" }}>
              Mean: <strong style={{ color:"#aab" }}>{data.mean_probability}%</strong>
            </span>
            <span style={{ fontSize:12, color:"#667" }}>
              Peak: <strong style={{ color: probColor(data.max_probability) }}>
                {data.max_probability}% ({data.peak_year})
              </strong>
            </span>
            <span style={{ fontSize:12, color:"#667" }}>
              Trend: <strong style={{
                color: data.trend_direction === "worsening" ? "#e06030"
                     : data.trend_direction === "improving" ? "#4caf76" : "#aab"
              }}>
                {data.trend_direction}
              </strong>
            </span>
          </div>
        )}
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          {/* Main probability chart */}
          <div style={{ background:"#080c14", borderRadius:8, padding:"16px 8px 8px", border:"1px solid #151525", marginBottom:16 }}>
            <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12, paddingLeft:12 }}>
              Instability probability 1955–2005
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ left:0, right:16, top:4, bottom:4 }}>
                <XAxis dataKey="year" tick={{ fontSize:11, fill:"#445" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0,100]} tick={{ fontSize:11, fill:"#445" }} axisLine={false} tickLine={false}
                  tickFormatter={v => `${v}%`} width={38} />
                <Tooltip
                  contentStyle={{ background:"#0a0f1e", border:"1px solid #1e2e40", borderRadius:6, fontSize:12 }}
                  formatter={(v, n) => [`${v}%`, "Probability"]}
                  labelStyle={{ color:"#aab" }}
                />
                <ReferenceLine y={15} stroke="#2a3a2a" strokeDasharray="3 3" />
                <ReferenceLine y={35} stroke="#3a3020" strokeDasharray="3 3" />
                <ReferenceLine y={60} stroke="#3a2010" strokeDasharray="3 3" />
                {/* Regime-change markers */}
                {data.regime_changes?.map(rc => (
                  <ReferenceLine key={rc.year} x={rc.year} stroke="#3a4a6a" strokeDasharray="2 4"
                    label={{ value: "⤿", position:"top", fill:"#3a5a8a", fontSize:14 }}
                  />
                ))}
                <Line
                  type="monotone" dataKey="probability_pct"
                  stroke="#5a8fc0" strokeWidth={2.5}
                  dot={({ cx, cy, payload }) => (
                    <circle key={`dot-${payload.year}`} cx={cx} cy={cy} r={4}
                      fill={probColor(payload.probability_pct)} stroke="#080c14" strokeWidth={1.5} />
                  )}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Regime timeline */}
          <div style={{ background:"#080c14", borderRadius:8, padding:"14px 16px", border:"1px solid #151525", marginBottom:16 }}>
            <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:10 }}>
              Regime type
            </div>
            <div style={{ display:"flex", gap:3, flexWrap:"wrap" }}>
              {data.chart_data?.map((row, i) => (
                <div key={row.year} style={{ textAlign:"center" }}>
                  <div style={{
                    width:48, padding:"4px 0", borderRadius:3, fontSize:10,
                    background: {
                      full_autocracy: "#2a1515",
                      partial_autocracy: "#2a2010",
                      factionalized_democracy: "#2a1020",
                      partial_democracy: "#10202a",
                      full_democracy: "#102a18",
                    }[row.regime_type] || "#1a1a2a",
                    color: {
                      full_autocracy: "#e06060",
                      partial_autocracy: "#d09040",
                      factionalized_democracy: "#c060c0",
                      partial_democracy: "#60a0d0",
                      full_democracy: "#60c080",
                    }[row.regime_type] || "#888",
                    fontFamily:"'IBM Plex Mono', monospace"
                  }}>
                    {REGIME_SHORT[row.regime_type] || row.regime_type}
                  </div>
                  <div style={{ fontSize:10, color:"#445", marginTop:2 }}>{row.year}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Events */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:16 }}>
            <div style={{ background:"#080c14", borderRadius:8, padding:"14px 16px", border:"1px solid #151525" }}>
              <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:8 }}>
                Regime changes ({data.regime_changes?.length || 0})
              </div>
              {data.regime_changes?.length === 0 && <div style={{ color:"#445", fontSize:12 }}>None in period</div>}
              {data.regime_changes?.map(rc => (
                <div key={rc.year} style={{ marginBottom:8, fontSize:12 }}>
                  <span style={{ color:"#5a8fc0", fontFamily:"'IBM Plex Mono', monospace" }}>{rc.year}</span>
                  <span style={{ color:"#667", marginLeft:8 }}>
                    {rc.from_regime.replace(/_/g," ")} → {rc.to_regime.replace(/_/g," ")}
                  </span>
                  <span style={{
                    marginLeft:6, color: rc.delta_probability > 0 ? "#e06030" : "#4caf76",
                    fontFamily:"'IBM Plex Mono', monospace"
                  }}>
                    {rc.delta_probability > 0 ? "+" : ""}{rc.delta_probability}pp
                  </span>
                </div>
              ))}
            </div>
            <div style={{ background:"#080c14", borderRadius:8, padding:"14px 16px", border:"1px solid #151525" }}>
              <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:8 }}>
                Risk spikes ≥ 10pp ({data.risk_spikes?.length || 0})
              </div>
              {data.risk_spikes?.length === 0 && <div style={{ color:"#445", fontSize:12 }}>None in period</div>}
              {data.risk_spikes?.map(s => (
                <div key={s.year} style={{ marginBottom:8, fontSize:12 }}>
                  <span style={{ color:"#e06030", fontFamily:"'IBM Plex Mono', monospace" }}>{s.year}</span>
                  <span style={{ color:"#e8a838", marginLeft:8, fontFamily:"'IBM Plex Mono', monospace" }}>
                    +{s.delta_from_prior}pp
                  </span>
                  <span style={{ color:"#667", marginLeft:6 }}>via {s.driver.toLowerCase()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Summary */}
          <div style={{
            background:"#0a0f18", borderRadius:8, padding:"14px 16px",
            border:"1px solid #1a2030", fontSize:13, color:"#778", lineHeight:1.7
          }}>
            {data.summary}
          </div>
        </>
      )}
    </div>
  );
}

// ─── TAB: COUNTRY COMPARISON ─────────────────────────────────────────────
const COMPARE_COLORS = ["#5a8fc0","#e8a838","#4caf76","#c060c0","#e06030"];

function CompareTab({ countries }) {
  const [selected, setSelected] = useState(["Colombia", "Chile", "Peru"]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [input, setInput] = useState("");

  const load = async () => {
    if (selected.length < 2) return;
    setLoading(true); setError(null);
    try {
      const d = await apiFetch(`/pipeline/compare?countries=${selected.join(",")}`);
      setData(d);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [selected.join(",")]);

  const toggle = (c) => {
    setSelected(s => s.includes(c)
      ? s.filter(x => x !== c)
      : s.length < 5 ? [...s, c] : s
    );
  };

  const chartData = data?.years?.map((yr, i) => {
    const row = { year: yr };
    data.countries.forEach(c => {
      row[c] = data.series[c]?.[i] ?? null;
    });
    return row;
  }) || [];

  return (
    <div>
      <div style={{ marginBottom:16 }}>
        <div style={{ fontSize:12, color:"#667", marginBottom:8 }}>
          Select up to 5 countries to compare (currently {selected.length})
        </div>
        <div style={{ display:"flex", flexWrap:"wrap", gap:6, maxHeight:140, overflowY:"auto" }}>
          {countries.map((c, i) => (
            <button key={c} onClick={() => toggle(c)} style={{
              padding:"4px 10px", borderRadius:4, fontSize:12, cursor:"pointer",
              border:`1px solid ${selected.includes(c) ? COMPARE_COLORS[selected.indexOf(c)] + "aa" : "#1e1e2e"}`,
              background: selected.includes(c) ? COMPARE_COLORS[selected.indexOf(c)] + "18" : "#0a0a14",
              color: selected.includes(c) ? COMPARE_COLORS[selected.indexOf(c)] : "#556",
              transition:"all 0.15s"
            }}>{c}</button>
          ))}
        </div>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          <div style={{ background:"#080c14", borderRadius:8, padding:"16px 8px 8px", border:"1px solid #151525", marginBottom:16 }}>
            <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12, paddingLeft:12 }}>
              Instability probability over time
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={chartData} margin={{ left:0, right:16, top:4, bottom:4 }}>
                <XAxis dataKey="year" tick={{ fontSize:11, fill:"#445" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0,100]} tick={{ fontSize:11, fill:"#445" }} axisLine={false} tickLine={false}
                  tickFormatter={v=>`${v}%`} width={38} />
                <Tooltip
                  contentStyle={{ background:"#0a0f1e", border:"1px solid #1e2e40", borderRadius:6, fontSize:12 }}
                  formatter={(v,n) => [`${v}%`, n]}
                  labelStyle={{ color:"#aab" }}
                />
                {data.countries.map((c, i) => (
                  <Line key={c} type="monotone" dataKey={c}
                    stroke={COMPARE_COLORS[i % COMPARE_COLORS.length]}
                    strokeWidth={2} dot={false} connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Summary table */}
          <div style={{ background:"#080c14", borderRadius:8, border:"1px solid #151525", overflow:"hidden" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead>
                <tr style={{ borderBottom:"1px solid #151525" }}>
                  {["Country","Mean","Peak","Year","Trend","Summary"].map(h => (
                    <th key={h} style={{ padding:"10px 14px", textAlign:"left", color:"#445",
                      fontSize:11, textTransform:"uppercase", letterSpacing:"0.06em", fontWeight:500 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.countries.map((c, i) => {
                  const a = data.analyses[c];
                  return (
                    <tr key={c} style={{ borderBottom:"1px solid #0e0e1a" }}>
                      <td style={{ padding:"10px 14px" }}>
                        <span style={{ color: COMPARE_COLORS[i % COMPARE_COLORS.length], fontWeight:600 }}>
                          {c}
                        </span>
                      </td>
                      <td style={{ padding:"10px 14px", fontFamily:"'IBM Plex Mono', monospace", color: probColor(a.mean_probability) }}>
                        {a.mean_probability}%
                      </td>
                      <td style={{ padding:"10px 14px", fontFamily:"'IBM Plex Mono', monospace", color: probColor(a.max_probability) }}>
                        {a.max_probability}%
                      </td>
                      <td style={{ padding:"10px 14px", color:"#667", fontFamily:"'IBM Plex Mono', monospace" }}>
                        {a.peak_year}
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        <span style={{
                          color: a.trend_direction === "worsening" ? "#e06030"
                               : a.trend_direction === "improving" ? "#4caf76" : "#889"
                        }}>
                          {a.trend_direction === "worsening" ? "↑" : a.trend_direction === "improving" ? "↓" : "→"} {a.trend_direction}
                        </span>
                      </td>
                      <td style={{ padding:"10px 14px", color:"#556", maxWidth:200,
                        whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                        {a.summary}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ─── TAB: GLOBAL RANKINGS ────────────────────────────────────────────────
function RankingsTab() {
  const YEARS = [1955,1960,1965,1970,1975,1980,1985,1990,1995,2000,2005];
  const [year, setYear] = useState(1990);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async (y) => {
    setLoading(true); setError(null);
    try {
      const d = await apiFetch(`/pipeline/rankings/${y}`);
      setData(d);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(year); }, [year, load]);

  const chartData = data?.rankings?.slice(0, 20).map(r => ({
    country: r.country.length > 12 ? r.country.slice(0,12)+"…" : r.country,
    fullName: r.country,
    pct: r.probability_pct,
    band: r.risk_band,
  })) || [];

  return (
    <div>
      <div style={{ display:"flex", gap:12, alignItems:"center", marginBottom:20, flexWrap:"wrap" }}>
        <label style={styles.label}>Year</label>
        <div style={{ display:"flex", gap:4, flexWrap:"wrap" }}>
          {YEARS.map(y => (
            <button key={y} onClick={() => setYear(y)} style={{
              padding:"5px 12px", borderRadius:4, fontSize:12, cursor:"pointer",
              border:`1px solid ${year === y ? "#3a5a8a" : "#1e1e2e"}`,
              background: year === y ? "#1a2535" : "#0a0a14",
              color: year === y ? "#c8daf0" : "#556",
              transition:"all 0.15s"
            }}>{y}</button>
          ))}
        </div>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          {/* Bar chart - top 20 */}
          <div style={{ background:"#080c14", borderRadius:8, padding:"16px 8px 8px", border:"1px solid #151525", marginBottom:16 }}>
            <div style={{ fontSize:11, color:"#445", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:12, paddingLeft:12 }}>
              Top 20 highest-risk countries — {year}
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical" margin={{ left:8, right:24, top:0, bottom:4 }}>
                <XAxis type="number" domain={[0,100]} tick={{ fontSize:10, fill:"#445" }}
                  axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`} />
                <YAxis type="category" dataKey="country" tick={{ fontSize:11, fill:"#778" }}
                  axisLine={false} tickLine={false} width={90} />
                <Tooltip
                  contentStyle={{ background:"#0a0f1e", border:"1px solid #1e2e40", borderRadius:6, fontSize:12 }}
                  formatter={(v, n, props) => [`${v}% — ${props.payload.band}`, props.payload.fullName]}
                />
                <Bar dataKey="pct" radius={[0,3,3,0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={riskColor(entry.band)} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Full table */}
          <div style={{ background:"#080c14", borderRadius:8, border:"1px solid #151525", overflow:"hidden" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
              <thead>
                <tr style={{ borderBottom:"1px solid #151525" }}>
                  {["#","Country","Probability","Band","Regime","IMR"].map(h => (
                    <th key={h} style={{ padding:"9px 14px", textAlign:"left", color:"#445",
                      fontSize:11, textTransform:"uppercase", letterSpacing:"0.06em", fontWeight:500 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rankings.map(r => (
                  <tr key={r.country} style={{ borderBottom:"1px solid #0e0e1a" }}>
                    <td style={{ padding:"8px 14px", color:"#445", fontFamily:"'IBM Plex Mono', monospace" }}>
                      {r.rank}
                    </td>
                    <td style={{ padding:"8px 14px", color:"#aab" }}>{r.country}</td>
                    <td style={{ padding:"8px 14px" }}>
                      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                        <span style={{
                          color: probColor(r.probability_pct),
                          fontFamily:"'IBM Plex Mono', monospace"
                        }}>
                          {r.probability_pct}%
                        </span>
                        <ProbBar pct={r.probability_pct} height={4} />
                      </div>
                    </td>
                    <td style={{ padding:"8px 14px" }}>
                      <span style={{
                        color: riskColor(r.risk_band), fontSize:11,
                        border:`1px solid ${riskColor(r.risk_band)}44`,
                        borderRadius:3, padding:"1px 6px"
                      }}>
                        {r.risk_band}
                      </span>
                    </td>
                    <td style={{ padding:"8px 14px", color:"#667", fontSize:11 }}>
                      {r.regime_type?.replace(/_/g," ")}
                    </td>
                    <td style={{ padding:"8px 14px", color:"#556", fontFamily:"'IBM Plex Mono', monospace" }}>
                      {r.infant_mortality}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ─── TAB: PRESENT-DAY (2007 vs 2024) ────────────────────────────────────────
function PresentDayTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState("table"); // "table" or "chart"
  const [sortBy, setSortBy] = useState("risk_2024"); // "risk_2024", "delta", "country"

  useEffect(() => {
    apiFetch("/present-day")
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox msg={error} />;
  if (!data) return null;

  // Combine 2007 and 2024 data
  const combined = [];
  Object.entries(data.forecasts_2024).forEach(([country, f2024]) => {
    const f2007 = data.forecasts_2007[country];
    if (f2024) {
      combined.push({
        country,
        f2007: f2007 || null,
        f2024,
        delta: f2007 ? (f2024.probability_pct - f2007.probability_pct) : null,
      });
    }
  });

  // Sort based on selection
  combined.sort((a, b) => {
    if (sortBy === "risk_2024") return (b.f2024.probability_pct || 0) - (a.f2024.probability_pct || 0);
    if (sortBy === "delta") return (b.delta || 0) - (a.delta || 0);
    if (sortBy === "country") return a.country.localeCompare(b.country);
    return 0;
  });

  // Prepare chart data for comparison
  const chartData = combined.slice(0, 20).map(item => ({
    country: item.country.length > 14 ? item.country.slice(0, 14) + "…" : item.country,
    fullName: item.country,
    "2007": item.f2007?.probability_pct || 0,
    "2024": item.f2024?.probability_pct || 0,
    delta: item.delta,
  }));

  // Stats
  const avg2007 = data.forecasts_2007 && Object.values(data.forecasts_2007).filter(f => f?.probability_pct).length > 0
    ? Math.round(Object.values(data.forecasts_2007).filter(f => f?.probability_pct).reduce((s, f) => s + f.probability_pct, 0) / 
        Object.values(data.forecasts_2007).filter(f => f?.probability_pct).length)
    : 0;
  const avg2024 = Object.values(data.forecasts_2024).filter(f => f?.probability_pct).length > 0
    ? Math.round(Object.values(data.forecasts_2024).filter(f => f?.probability_pct).reduce((s, f) => s + f.probability_pct, 0) / 
        Object.values(data.forecasts_2024).filter(f => f?.probability_pct).length)
    : 0;

  return (
    <div>
      {/* Summary stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 }}>
        <div style={{ background: "#0c1220", border: "1px solid #1e2e40", borderRadius: 8, padding: 16 }}>
          <div style={{ fontSize: 11, color: "#556", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
            Countries scored
          </div>
          <div style={{ fontSize: 24, fontWeight: 600, color: "#aab", fontFamily: "'IBM Plex Mono', monospace" }}>
            {combined.length}
          </div>
        </div>
        <div style={{ background: "#0c1220", border: "1px solid #1e2e40", borderRadius: 8, padding: 16 }}>
          <div style={{ fontSize: 11, color: "#556", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
            Average risk 2007
          </div>
          <div style={{ fontSize: 24, fontWeight: 600, color: probColor(avg2007), fontFamily: "'IBM Plex Mono', monospace" }}>
            {avg2007}%
          </div>
        </div>
        <div style={{ background: "#0c1220", border: "1px solid #1e2e40", borderRadius: 8, padding: 16 }}>
          <div style={{ fontSize: 11, color: "#556", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
            Average risk 2024
          </div>
          <div style={{ fontSize: 24, fontWeight: 600, color: probColor(avg2024), fontFamily: "'IBM Plex Mono', monospace" }}>
            {avg2024}%
          </div>
        </div>
        <div style={{ background: "#0c1220", border: "1px solid #1e2e40", borderRadius: 8, padding: 16 }}>
          <div style={{ fontSize: 11, color: "#556", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
            Trend
          </div>
          <div style={{ fontSize: 24, fontWeight: 600, color: avg2024 > avg2007 ? "#e06030" : "#4caf76", fontFamily: "'IBM Plex Mono', monospace" }}>
            {avg2024 > avg2007 ? `↑ +${avg2024 - avg2007}pp` : `↓ ${avg2024 - avg2007}pp`}
          </div>
        </div>
      </div>

      {/* View toggles */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 6 }}>
          {["table", "chart"].map(v => (
            <button key={v} onClick={() => setView(v)} style={{
              padding: "6px 14px", fontSize: 12, cursor: "pointer",
              border: `1px solid ${view === v ? "#3a5a8a" : "#1e1e2e"}`,
              background: view === v ? "#1a2535" : "#0a0a14",
              color: view === v ? "#c8daf0" : "#556",
              borderRadius: 4, transition: "all 0.15s", textTransform: "capitalize"
            }}>
              {v === "table" ? "📊 Table" : "📈 Chart"}
            </button>
          ))}
        </div>
        {view === "table" && (
          <div style={{ display: "flex", gap: 6 }}>
            {[["risk_2024", "Highest risk 2024"], ["delta", "Largest change"], ["country", "Alphabetical"]].map(([val, label]) => (
              <button key={val} onClick={() => setSortBy(val)} style={{
                padding: "5px 10px", fontSize: 11, cursor: "pointer",
                border: `1px solid ${sortBy === val ? "#3a5a8a" : "#1e1e2e"}`,
                background: sortBy === val ? "#1a2535" : "transparent",
                color: sortBy === val ? "#90bce0" : "#556",
                borderRadius: 3, transition: "all 0.15s"
              }}>
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Chart view */}
      {view === "chart" && (
        <div style={{ background: "#080c14", borderRadius: 8, padding: "16px 8px 8px", border: "1px solid #151525", marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: "#445", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12, paddingLeft: 12 }}>
            Top 20 countries: 2007 vs 2024
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 0, bottom: 4 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: "#445" }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
              <YAxis type="category" dataKey="country" tick={{ fontSize: 11, fill: "#778" }} axisLine={false} tickLine={false} width={90} />
              <Tooltip
                contentStyle={{ background: "#0a0f1e", border: "1px solid #1e2e40", borderRadius: 6, fontSize: 12 }}
                formatter={(v, name) => `${v}%`}
                labelFormatter={(label) => {
                  const item = chartData.find(d => d.country === label);
                  return item?.fullName || label;
                }}
              />
              <Bar dataKey="2007" fill="#5a8fc0" fillOpacity={0.6} />
              <Bar dataKey="2024" fill="#e8a838" fillOpacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table view */}
      {view === "table" && (
        <div style={{ background: "#080c14", borderRadius: 8, border: "1px solid #151525", overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #151525" }}>
                {["Country", "2007 Risk", "2024 Risk", "Change", "2024 Regime", "Status"].map(h => (
                  <th key={h} style={{
                    padding: "10px 14px", textAlign: "left", color: "#445",
                    fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {combined.map(item => (
                <tr key={item.country} style={{ borderBottom: "1px solid #0e0e1a" }}>
                  <td style={{ padding: "10px 14px", color: "#aab" }}>{item.country}</td>
                  <td style={{ padding: "10px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: probColor(item.f2007?.probability_pct || 0), fontFamily: "'IBM Plex Mono', monospace" }}>
                        {item.f2007?.probability_pct || "—"}%
                      </span>
                      {item.f2007 && <ProbBar pct={item.f2007.probability_pct} height={4} />}
                    </div>
                  </td>
                  <td style={{ padding: "10px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: probColor(item.f2024.probability_pct), fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>
                        {item.f2024.probability_pct}%
                      </span>
                      <ProbBar pct={item.f2024.probability_pct} height={4} />
                    </div>
                  </td>
                  <td style={{
                    padding: "10px 14px", fontFamily: "'IBM Plex Mono', monospace",
                    color: item.delta > 0 ? "#e06030" : item.delta < 0 ? "#4caf76" : "#667"
                  }}>
                    {item.delta !== null ? (item.delta > 0 ? "+" : "") + Math.round(item.delta * 10) / 10 : "—"}pp
                  </td>
                  <td style={{ padding: "10px 14px", fontSize: 11, color: "#889" }}>
                    {item.f2024.regime_type?.replace(/_/g, " ") || "—"}
                  </td>
                  <td style={{ padding: "10px 14px" }}>
                    <RiskBadge band={item.f2024.risk_band} pct={item.f2024.probability_pct} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Errors */}
      {data.errors && data.errors.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 11, color: "#e06030", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
            ⚠ {data.errors.length} errors during processing:
          </div>
          <div style={{ background: "#1a0c0c", border: "1px solid #5a1a1a", borderRadius: 6, padding: 12 }}>
            {data.errors.map((err, i) => (
              <div key={i} style={{ fontSize: 11, color: "#e08080", marginBottom: i < data.errors.length - 1 ? 6 : 0 }}>
                • {err}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── TAB: HEATMAP ───────────────────────────────────────────────────────
function HeatmapTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    apiFetch("/pipeline/heatmap")
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const rows = data?.rows?.filter(r =>
    !filter || r.country.toLowerCase().includes(filter.toLowerCase())
  ) || [];

  const cellBg = (v) => {
    if (!v) return "#080c14";
    if (v < 15) return `rgba(76,175,118,${0.15 + v/100})`;
    if (v < 35) return `rgba(232,168,56,${0.15 + v/100})`;
    if (v < 60) return `rgba(224,96,48,${0.15 + v/100})`;
    return `rgba(192,57,43,${0.2 + v/100})`;
  };

  return (
    <div>
      <div style={{ marginBottom:14, display:"flex", gap:12, alignItems:"center" }}>
        <input
          placeholder="Filter countries…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{ ...styles.input, width:200, marginBottom:0 }}
        />
        <div style={{ display:"flex", gap:8, fontSize:11, color:"#556" }}>
          {[["< 15%","#4caf76"],["15–35%","#e8a838"],["35–60%","#e06030"],["> 60%","#c0392b"]].map(([l,c]) => (
            <span key={l} style={{ display:"flex", alignItems:"center", gap:4 }}>
              <span style={{ width:10, height:10, borderRadius:2, background:c+"66", display:"inline-block" }} />
              {l}
            </span>
          ))}
        </div>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <div style={{ overflowX:"auto" }}>
          <table style={{ borderCollapse:"collapse", fontSize:11, minWidth:700 }}>
            <thead>
              <tr>
                <th style={{ padding:"8px 12px", textAlign:"left", color:"#445", fontWeight:500,
                  fontSize:11, borderBottom:"1px solid #151525", position:"sticky", left:0, background:"#080c14", zIndex:2 }}>
                  Country
                </th>
                {data.years?.map(y => (
                  <th key={y} style={{ padding:"8px 10px", color:"#445", fontWeight:500,
                    borderBottom:"1px solid #151525", minWidth:52 }}>
                    {y}
                  </th>
                ))}
                <th style={{ padding:"8px 10px", color:"#445", fontWeight:500, borderBottom:"1px solid #151525" }}>
                  Mean
                </th>
                <th style={{ padding:"8px 10px", color:"#445", fontWeight:500, borderBottom:"1px solid #151525" }}>
                  Peak
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.country}>
                  <td style={{
                    padding:"6px 12px", color:"#889", borderBottom:"1px solid #0e0e1a",
                    whiteSpace:"nowrap", position:"sticky", left:0,
                    background:"#080c14", zIndex:1
                  }}>
                    {row.country}
                  </td>
                  {data.years?.map(y => {
                    const v = row.values[String(y)] || 0;
                    return (
                      <td key={y} style={{
                        padding:"5px 8px", textAlign:"center",
                        background: cellBg(v),
                        borderBottom:"1px solid #0a0a12",
                        color: v > 15 ? "#ddd" : "#556",
                        fontFamily:"'IBM Plex Mono', monospace"
                      }}>
                        {v > 0 ? Math.round(v) : "—"}
                      </td>
                    );
                  })}
                  <td style={{
                    padding:"5px 10px", textAlign:"center",
                    color: probColor(row.mean_probability),
                    fontFamily:"'IBM Plex Mono', monospace", fontWeight:600,
                    borderBottom:"1px solid #0a0a12"
                  }}>
                    {row.mean_probability}
                  </td>
                  <td style={{
                    padding:"5px 10px", textAlign:"center",
                    color:"#667", fontSize:10,
                    borderBottom:"1px solid #0a0a12"
                  }}>
                    {row.peak_year}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── MAIN APP ──────────────────────────────────────────────────────────────
const TABS = ["Forecast", "Time Series", "Compare", "Rankings", "Present-Day", "Heatmap"];

const styles = {
  label: {
    display:"block", fontSize:11, color:"#556", textTransform:"uppercase",
    letterSpacing:"0.08em", marginBottom:6, fontWeight:500
  },
  input: {
    width:"100%", background:"#0a0a14", border:"1px solid #1e1e2e", borderRadius:5,
    padding:"8px 12px", color:"#aab", fontSize:13, outline:"none",
    fontFamily:"inherit", boxSizing:"border-box", marginBottom:0,
    transition:"border-color 0.15s"
  },
  select: {
    background:"#0a0a14", border:"1px solid #1e1e2e", borderRadius:5,
    padding:"7px 12px", color:"#aab", fontSize:13, outline:"none",
    fontFamily:"inherit", cursor:"pointer"
  },
  btn: {
    background:"#1a2a3a", border:"1px solid #2a4a6a", borderRadius:6,
    padding:"10px 20px", color:"#90bce0", fontSize:13, cursor:"pointer",
    fontFamily:"inherit", width:"100%", transition:"all 0.15s",
    fontWeight:500, letterSpacing:"0.02em"
  },
  badge: {
    marginLeft:8, background:"#1a1a2a", border:"1px solid #2a2a3a",
    borderRadius:3, padding:"1px 7px", fontSize:11, color:"#778",
    fontFamily:"'IBM Plex Mono', monospace", fontWeight:"normal"
  }
};

export default function App() {
  const [tab, setTab] = useState(0);
  const [countries, setCountries] = useState([]);
  const [apiOk, setApiOk] = useState(null);

  useEffect(() => {
    apiFetch("/health")
      .then(() => {
        setApiOk(true);
        return apiFetch("/pipeline/countries");
      })
      .then(d => setCountries(d.countries || []))
      .catch(() => setApiOk(false));
  }, []);

  return (
    <div style={{
      minHeight:"100vh", background:"#060810",
      fontFamily:"'IBM Plex Sans', 'DM Sans', system-ui, sans-serif",
      color:"#c0c8d8"
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
        input[type=range] { height:4px; cursor:pointer; }
        ::-webkit-scrollbar { width:6px; height:6px; }
        ::-webkit-scrollbar-track { background:#060810; }
        ::-webkit-scrollbar-thumb { background:#1e2838; border-radius:3px; }
        button:hover { filter: brightness(1.15); }
      `}</style>

      {/* Header */}
      <div style={{
        borderBottom:"1px solid #0e1420", padding:"20px 32px 0",
        background:"#060810"
      }}>
        <div style={{ display:"flex", alignItems:"flex-end", justifyContent:"space-between", marginBottom:20 }}>
          <div>
            <div style={{ fontSize:10, letterSpacing:"0.18em", textTransform:"uppercase", color:"#445", marginBottom:4 }}>
              PITF · Goldstone et al. (2010)
            </div>
            <h1 style={{
              margin:0, fontSize:22, fontWeight:400, letterSpacing:"-0.5px",
              color:"#c8daf0"
            }}>
              Political Instability Forecasting System
            </h1>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:6, paddingBottom:4 }}>
            <div style={{
              width:7, height:7, borderRadius:"50%",
              background: apiOk === null ? "#888" : apiOk ? "#4caf76" : "#e06030",
              boxShadow: apiOk ? "0 0 6px #4caf7688" : ""
            }} />
            <span style={{ fontSize:11, color:"#445" }}>
              {apiOk === null ? "Connecting…" : apiOk ? `API online · ${countries.length} countries` : "API offline"}
            </span>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display:"flex", gap:0 }}>
          {TABS.map((t, i) => (
            <button key={t} onClick={() => setTab(i)} style={{
              padding:"9px 18px", fontSize:13, cursor:"pointer",
              background:"transparent", border:"none",
              borderBottom:`2px solid ${tab === i ? "#5a8fc0" : "transparent"}`,
              color: tab === i ? "#90bce0" : "#556",
              transition:"all 0.15s", fontFamily:"inherit", fontWeight: tab === i ? 500 : 400
            }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ padding:"28px 32px", maxWidth:1100, margin:"0 auto" }}>
        {tab === 0 && <ForecastTab />}
        {tab === 1 && <TimeSeriesTab countries={countries} />}
        {tab === 2 && <CompareTab countries={countries} />}
        {tab === 3 && <RankingsTab />}
        {tab === 4 && <PresentDayTab />}
        {tab === 5 && <HeatmapTab />}
      </div>
    </div>
  );
}