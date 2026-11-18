import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "cold_storage.db"

st.set_page_config(page_title="FrostGuard | Cold Storage", page_icon="❄️", layout="wide", initial_sidebar_state="expanded")

# ---------- Theme ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #F3F7FC; color: #172B45; }
section[data-testid="stSidebar"] { background: #101D30; border-right: 1px solid #22344D; }
section[data-testid="stSidebar"] * { color: #EAF2FC !important; }
section[data-testid="stSidebar"] .stRadio label { padding: 9px 12px; border-radius: 9px; }
section[data-testid="stSidebar"] .stRadio label:hover { background: #1C304B; }
.block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; max-width: 1500px; }
h1, h2, h3 { color: #172B45; letter-spacing: -0.035em; }
.eyebrow { color: #64809F; font-size: .76rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.metric-card { background: white; border: 1px solid #E1EAF3; border-radius: 16px; padding: 18px 20px; min-height: 132px; box-shadow: 0 5px 18px rgba(24,54,88,.035); }
.metric-label { color: #71859D; font-size: .9rem; }
.metric-value { color: #172B45; font-size: 2rem; font-weight: 800; margin-top: 8px; letter-spacing: -.04em; }
.metric-foot { color: #8294A9; font-size: .8rem; margin-top: 4px; }
.panel { background: white; border: 1px solid #E1EAF3; border-radius: 16px; padding: 20px; }
.status-safe { background:#E9F6EF; color:#287B50; padding:6px 11px; border-radius:20px; font-weight:700; font-size:.82rem; }
.status-warn { background:#FFF4DE; color:#A96A0B; padding:6px 11px; border-radius:20px; font-weight:700; font-size:.82rem; }
.status-critical { background:#FDEBEC; color:#B93842; padding:6px 11px; border-radius:20px; font-weight:700; font-size:.82rem; }
div[data-testid="stButton"] button[kind="primary"] { background:#2369B5; border:0; border-radius:10px; font-weight:700; }
div[data-testid="stButton"] button { border-radius:10px; }
[data-testid="stDataFrame"] { border:1px solid #E1EAF3; border-radius:12px; }
</style>
""", unsafe_allow_html=True)

# ---------- Database ----------
def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, temperature REAL, humidity REAL, status TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, severity TEXT, metric TEXT, value REAL, message TEXT
    )""")
    conn.commit()
    return conn

conn = db()

def get_limits():
    return float(st.session_state.get("temp_limit", 8.0)), float(st.session_state.get("humidity_limit", 80.0))

def classify(temp, hum):
    tlim, hlim = get_limits()
    if temp > tlim + 2 or hum > hlim + 10:
        return "CRITICAL"
    if temp > tlim or hum > hlim:
        return "WARNING"
    return "SAFE"

def add_reading(temp=None, hum=None):
    if temp is None:
        prev = conn.execute("SELECT temperature, humidity FROM readings ORDER BY id DESC LIMIT 1").fetchone()
        old_t, old_h = prev if prev else (4.5, 60.0)
        temp = float(np.clip(old_t + random.uniform(-0.65, 0.75), -1.0, 12.5))
        hum = float(np.clip(old_h + random.uniform(-2.8, 3.0), 35, 95))
    status = classify(temp, hum)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("INSERT INTO readings(timestamp,temperature,humidity,status) VALUES(?,?,?,?)",
                 (stamp, round(temp, 2), round(hum, 2), status))
    if status != "SAFE":
        tlim, hlim = get_limits()
        if temp > tlim:
            severity = "CRITICAL" if temp > tlim + 2 else "WARNING"
            conn.execute("INSERT INTO alerts(timestamp,severity,metric,value,message) VALUES(?,?,?,?,?)",
                         (stamp, severity, "Temperature", round(temp,2), f"Temperature exceeded limit of {tlim:.1f} °C"))
        if hum > hlim:
            severity = "CRITICAL" if hum > hlim + 10 else "WARNING"
            conn.execute("INSERT INTO alerts(timestamp,severity,metric,value,message) VALUES(?,?,?,?,?)",
                         (stamp, severity, "Humidity", round(hum,2), f"Humidity exceeded limit of {hlim:.1f} %"))
    conn.commit()

def load_readings(limit=5000):
    return pd.read_sql_query("SELECT * FROM readings ORDER BY id DESC LIMIT ?", conn, params=(limit,)).sort_values("id")

def load_alerts():
    return pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC", conn)

def metric_card(label, value, foot, icon):
    st.markdown(f"""<div class="metric-card"><div style="display:flex;justify-content:space-between;align-items:center">
      <span class="metric-label">{label}</span><span style="background:#EDF4FB;padding:9px 11px;border-radius:11px;color:#286CB3">{icon}</span>
      </div><div class="metric-value">{value}</div><div class="metric-foot">{foot}</div></div>""", unsafe_allow_html=True)

def make_pdf(readings, alerts):
    path = APP_DIR / "monitoring_report.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
    styles = getSampleStyleSheet()
    story = [Paragraph("FrostGuard — Cold Storage Monitoring Report", styles["Title"]),
             Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}", styles["Normal"]), Spacer(1, 14)]
    if not readings.empty:
        summary = [["Metric", "Minimum", "Average", "Maximum"],
                   ["Temperature (°C)", f"{readings.temperature.min():.2f}", f"{readings.temperature.mean():.2f}", f"{readings.temperature.max():.2f}"],
                   ["Humidity (%)", f"{readings.humidity.min():.2f}", f"{readings.humidity.mean():.2f}", f"{readings.humidity.max():.2f}"]]
        t = Table(summary, colWidths=[190,120,120,120])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#173454")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                               ("GRID",(0,0),(-1,-1),.5,colors.HexColor("#D8E2ED")),("PADDING",(0,0),(-1,-1),8)]))
        story += [Paragraph("Environmental summary", styles["Heading2"]), t, Spacer(1,14)]
        rows = [["Time", "Temperature °C", "Humidity %", "Status"]]
        for _, r in readings.tail(30).iloc[::-1].iterrows():
            rows.append([str(r.timestamp), f"{r.temperature:.2f}", f"{r.humidity:.2f}", str(r.status)])
        t2 = Table(rows, repeatRows=1, colWidths=[190,130,120,110])
        t2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2369B5")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                                ("GRID",(0,0),(-1,-1),.4,colors.HexColor("#D8E2ED")),("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),6)]))
        story += [Paragraph("Recent readings (latest 30)", styles["Heading2"]), t2]
    story += [Spacer(1,14), Paragraph(f"Recorded alerts: {len(alerts)}", styles["Heading2"])]
    doc.build(story)
    return path

# ---------- Login ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "running" not in st.session_state:
    st.session_state.running = False
if "temp_limit" not in st.session_state:
    st.session_state.temp_limit = 8.0
if "humidity_limit" not in st.session_state:
    st.session_state.humidity_limit = 80.0

if not st.session_state.authenticated:
    left, right = st.columns([1.05, 1])
    with left:
        st.markdown("""<div style="background:#101D30;border-radius:20px;padding:48px 42px;min-height:560px;color:#F5F8FC">
        <div style="font-size:1.2rem;font-weight:800;letter-spacing:.1em">❄ FROST<span style="color:#8FC5F5">GUARD</span></div>
        <div style="margin-top:90px;color:#8FC5F5;font-size:.75rem;font-weight:800;letter-spacing:.18em">SMART COLD STORAGE PLATFORM</div>
        <div style="font-size:3.7rem;line-height:1.04;font-weight:800;margin-top:20px">Protect what<br><span style="color:#8FC5F5">matters most.</span></div>
        <div style="font-size:1.05rem;line-height:1.8;color:#C0D0E2;margin-top:22px;max-width:430px">Monitor storage conditions, identify unsafe ranges and keep a reliable digital record.</div>
        <div style="display:flex;gap:36px;margin-top:90px;font-weight:700"><span>24/7<br><small style="color:#9DB0C6;font-weight:400">Monitoring</small></span><span>LIVE<br><small style="color:#9DB0C6;font-weight:400">Simulation</small></span><span>SECURE<br><small style="color:#9DB0C6;font-weight:400">Records</small></span></div></div>""", unsafe_allow_html=True)
    with right:
        st.markdown("<div style='padding:42px 7% 20px'>", unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">WELCOME BACK</div><h1 style="font-size:2.4rem;margin-bottom:4px">Sign in to your account</h1><p style="color:#71859D">Enter your demo credentials to continue.</p>', unsafe_allow_html=True)
        role = st.radio("Account type", ["Admin", "User"], horizontal=True)
        username = st.text_input("Username", value="admin" if role == "Admin" else "user")
        password = st.text_input("Password", type="password")
        if st.button("Sign in  ↗", type="primary", use_container_width=True):
            valid = (role == "Admin" and username == "admin" and password == "admin123") or (role == "User" and username == "user" and password == "user123")
            if valid:
                st.session_state.authenticated = True
                st.session_state.role = role
                st.rerun()
            else:
                st.error("Incorrect demo credentials. Check the credentials below.")
        st.info("Demo access — Admin: admin / admin123   ·   User: user / user123")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("<div style='font-size:1.35rem;font-weight:800;letter-spacing:.08em;padding:10px 4px 28px'>❄ FROST<span style='color:#8FC5F5'>GUARD</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:.7rem;letter-spacing:.16em;color:#8299B5!important;font-weight:800;margin:8px 0'>WORKSPACE</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='background:#1A2D45;border:1px solid #2B405B;padding:12px;border-radius:12px;margin-bottom:22px'>◉ &nbsp; {st.session_state.get('role','User')} account<br><small style='color:#91A6BF!important'>Cold storage monitoring</small></div>", unsafe_allow_html=True)
    page = st.radio("MENU", ["Overview", "Live Simulator", "Analytics", "Alerts", "Reports", "Settings"], label_visibility="visible")
    st.markdown("<div style='margin-top:38px;background:#1A2D45;border:1px solid #2B405B;padding:15px;border-radius:12px'><b>Cold chain, simplified.</b><br><small style='color:#A9BBD0!important'>Your storage conditions at a glance.</small></div>", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("Sign out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.running = False
        st.rerun()

readings = load_readings()
alerts = load_alerts()
latest = readings.iloc[-1] if not readings.empty else None
tlim, hlim = get_limits()
st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center'><div><div class='eyebrow'>WORKSPACE / {page.upper()}</div><h1 style='margin:5px 0 0'>"+({"Overview":"Good to see you","Live Simulator":"Live simulator","Analytics":"Environmental analytics","Alerts":"Alert center","Reports":"Monitoring reports","Settings":"System settings"}[page])+"</h1></div><div style='color:#71859D;font-size:.85rem'>● &nbsp; Software simulation active</div></div>", unsafe_allow_html=True)
st.markdown("<hr style='border:0;border-top:1px solid #DFE8F1;margin:20px 0 26px'>", unsafe_allow_html=True)

# ---------- Pages ----------
if page == "Overview":
    st.markdown('<div class="eyebrow">YOUR STORAGE, AT A GLANCE</div><p style="color:#71859D;margin-top:5px">Monitor environmental conditions and keep your inventory within safe limits.</p>', unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns(4)
    with c1: metric_card("Temperature", f"{latest.temperature:.1f} °C" if latest is not None else "—", f"Limit {tlim:.1f} °C", "🌡")
    with c2: metric_card("Humidity", f"{latest.humidity:.1f} %" if latest is not None else "—", f"Limit {hlim:.1f} %", "💧")
    with c3: metric_card("Storage status", latest.status if latest is not None else "NO DATA", "Latest simulated reading", "◉")
    with c4: metric_card("Total alerts", str(len(alerts)), "Recorded warnings and critical events", "⚑")
    st.write("")
    a,b = st.columns([1.65,1])
    with a:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Environmental trend")
        if not readings.empty:
            df = readings.tail(40)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.timestamp,y=df.temperature,name="Temperature °C",line=dict(color="#2878C7",width=3),mode="lines+markers"))
            fig.add_hline(y=tlim,line_dash="dash",line_color="#D79B3D",annotation_text="Temperature limit")
            fig.update_layout(height=300,margin=dict(l=10,r=10,t=20,b=10),paper_bgcolor="white",plot_bgcolor="white",legend=dict(orientation="h",y=1.12),font=dict(color="#637A94"))
            st.plotly_chart(fig,use_container_width=True)
        else:
            st.info("No readings yet. Open Live Simulator and generate the first reading.")
        st.markdown('</div>', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Quick overview")
        safe = int((readings.status=="SAFE").sum()) if not readings.empty else 0
        total = len(readings)
        pct = (safe/total*100) if total else 0
        st.metric("Safe readings", f"{safe} / {total}")
        st.progress(pct/100 if total else 0)
        st.caption(f"{pct:.0f}% of recorded readings are within configured limits.")
        st.markdown("---")
        st.markdown("**Safety thresholds**")
        st.write(f"🌡 Temperature: ≤ {tlim:.1f} °C")
        st.write(f"💧 Humidity: ≤ {hlim:.1f} %")
        st.markdown('</div>', unsafe_allow_html=True)
    st.subheader("Recent readings")
    st.dataframe(readings.tail(8).iloc[::-1][["timestamp","temperature","humidity","status"]] if not readings.empty else pd.DataFrame(columns=["timestamp","temperature","humidity","status"]), use_container_width=True, hide_index=True)

elif page == "Live Simulator":
    st.markdown('<div class="eyebrow">SIMULATED SENSOR FEED</div><p style="color:#71859D">Generate readings manually or run the automatic simulator. No physical sensors are connected.</p>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns([1,1,2])
    with c1:
        if st.button("▶ Start live simulation", type="primary", use_container_width=True):
            st.session_state.running = True
    with c2:
        if st.button("Ⅱ Pause simulation", use_container_width=True):
            st.session_state.running = False
    with c3:
        if st.button("＋ Generate one reading", use_container_width=True):
            add_reading()
            st.rerun()
    if st.session_state.running:
        st.success("Simulator is running — a new reading is generated every 3 seconds.")
        @st.fragment(run_every="3s")
        def live_feed():
            add_reading()
            data = load_readings(1)
            r = data.iloc[-1]
            x,y,z = st.columns(3)
            with x: metric_card("Temperature", f"{r.temperature:.1f} °C", f"Limit {tlim:.1f} °C", "🌡")
            with y: metric_card("Humidity", f"{r.humidity:.1f} %", f"Limit {hlim:.1f} %", "💧")
            with z: metric_card("Storage status", r.status, r.timestamp, "◉")
            st.caption("This panel refreshes automatically while the simulator is running.")
        live_feed()
    else:
        st.info("Simulator paused. Start the simulation to generate a reading every 3 seconds.")
        if latest is not None:
            x,y,z = st.columns(3)
            with x: metric_card("Temperature", f"{latest.temperature:.1f} °C", f"Limit {tlim:.1f} °C", "🌡")
            with y: metric_card("Humidity", f"{latest.humidity:.1f} %", f"Limit {hlim:.1f} %", "💧")
            with z: metric_card("Storage status", latest.status, latest.timestamp, "◉")
    st.subheader("Recent simulated readings")
    st.dataframe(readings.tail(15).iloc[::-1][["timestamp","temperature","humidity","status"]] if not readings.empty else pd.DataFrame(),use_container_width=True,hide_index=True)

elif page == "Analytics":
    st.markdown('<div class="eyebrow">HISTORICAL PERFORMANCE</div><p style="color:#71859D">Explore recorded environmental readings and identify trends.</p>', unsafe_allow_html=True)
    if readings.empty:
        st.info("Analytics will appear after you generate sensor readings.")
    else:
        d1,d2 = st.columns(2)
        with d1:
            st.metric("Average temperature", f"{readings.temperature.mean():.2f} °C")
            st.metric("Minimum / maximum", f"{readings.temperature.min():.2f} / {readings.temperature.max():.2f} °C")
        with d2:
            st.metric("Average humidity", f"{readings.humidity.mean():.2f} %")
            st.metric("Minimum / maximum", f"{readings.humidity.min():.2f} / {readings.humidity.max():.2f} %")
        tab1,tab2 = st.tabs(["Temperature","Humidity"])
        with tab1:
            fig=px.line(readings,x="timestamp",y="temperature",markers=True,labels={"timestamp":"Time","temperature":"Temperature (°C)"})
            fig.add_hline(y=tlim,line_dash="dash",line_color="#D79B3D",annotation_text="Limit")
            fig.update_traces(line_color="#2878C7")
            fig.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig,use_container_width=True)
        with tab2:
            fig=px.line(readings,x="timestamp",y="humidity",markers=True,labels={"timestamp":"Time","humidity":"Humidity (%)"})
            fig.add_hline(y=hlim,line_dash="dash",line_color="#D79B3D",annotation_text="Limit")
            fig.update_traces(line_color="#31A6A0")
            fig.update_layout(height=380,plot_bgcolor="white",paper_bgcolor="white")
            st.plotly_chart(fig,use_container_width=True)
        st.subheader("Reading distribution")
        counts=readings.status.value_counts().reindex(["SAFE","WARNING","CRITICAL"],fill_value=0).reset_index()
        counts.columns=["Status","Count"]
        st.bar_chart(counts.set_index("Status"))

elif page == "Alerts":
    st.markdown('<div class="eyebrow">SAFETY EVENT LOG</div><p style="color:#71859D">Unsafe readings are automatically recorded here.</p>', unsafe_allow_html=True)
    if alerts.empty:
        st.success("No alerts recorded. All generated readings are within configured limits.")
    else:
        q1,q2,q3=st.columns(3)
        with q1: st.metric("Total alerts",len(alerts))
        with q2: st.metric("Warnings",int((alerts.severity=="WARNING").sum()))
        with q3: st.metric("Critical",int((alerts.severity=="CRITICAL").sum()))
        st.dataframe(alerts[["timestamp","severity","metric","value","message"]],use_container_width=True,hide_index=True)
        if st.session_state.get("role")=="Admin" and st.button("Clear alert history"):
            conn.execute("DELETE FROM alerts"); conn.commit(); st.rerun()

elif page == "Reports":
    st.markdown('<div class="eyebrow">EXPORT & RECORD KEEPING</div><p style="color:#71859D">Download a digital record of simulated readings and safety events.</p>', unsafe_allow_html=True)
    r1,r2=st.columns(2)
    with r1: metric_card("Recorded readings",str(len(readings)),"All saved simulator readings","▤")
    with r2: metric_card("Recorded alerts",str(len(alerts)),"Warnings and critical events","⚑")
    if not readings.empty:
        csv=readings.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download readings CSV",csv,file_name="cold_storage_readings.csv",mime="text/csv",type="primary")
        st.download_button("⬇ Download alerts CSV",alerts.to_csv(index=False).encode("utf-8"),file_name="cold_storage_alerts.csv",mime="text/csv")
        pdf_path=make_pdf(readings,alerts)
        st.download_button("⬇ Download PDF monitoring report",pdf_path.read_bytes(),file_name="cold_storage_report.pdf",mime="application/pdf")
    else:
        st.info("Generate at least one reading before downloading a report.")

elif page == "Settings":
    st.markdown('<div class="eyebrow">CONFIGURATION</div><p style="color:#71859D">Set the thresholds used by the simulator to classify safe and unsafe conditions.</p>', unsafe_allow_html=True)
    if st.session_state.get("role") != "Admin":
        st.warning("Settings can only be changed by the Admin demo account.")
    else:
        with st.form("limits_form"):
            st.number_input("Maximum safe temperature (°C)",min_value=-10.0,max_value=30.0,step=0.5,key="temp_limit")
            st.number_input("Maximum safe humidity (%)",min_value=10.0,max_value=100.0,step=1.0,key="humidity_limit")
            st.form_submit_button("Save monitoring limits",type="primary")
        st.markdown("---")
        st.subheader("Data management")
        st.caption("This prototype stores readings and alerts in a local SQLite database.")
        if st.button("Delete all readings and alerts",type="secondary"):
            conn.execute("DELETE FROM readings"); conn.execute("DELETE FROM alerts"); conn.commit(); st.rerun()

st.markdown("<div style='text-align:center;color:#91A2B6;font-size:.75rem;margin-top:44px'>FrostGuard Academic Prototype · Simulated sensor values · No physical sensors connected</div>",unsafe_allow_html=True)
