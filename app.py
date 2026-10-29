
import ipaddress
import platform
import re
import sqlite3
import subprocess
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ---------------- PAGE CONFIGURATION ----------------

st.set_page_config(
    page_title="Smart Network Fault Predictor",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------- PROFESSIONAL DARK THEME ----------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #07111f 0%, #0b1730 55%, #101d36 100%);
    color: #e7eefb;
}
[data-testid="stSidebar"] {
    background: #0b1425;
    border-right: 1px solid #263854;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

h1, h2, h3 {
    color: #edf4ff !important;
}
p, label, span {
    color: #d3def0;
}
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #142541, #101c32);
    border: 1px solid #2b4263;
    padding: 18px;
    border-radius: 16px;
    box-shadow: 0 5px 18px rgba(0,0,0,0.15);
}
div[data-testid="stMetricLabel"] {
    color: #a9bddb;
}
div[data-testid="stMetricValue"] {
    color: #f4f8ff;
}
.stButton > button, .stDownloadButton > button {
    background: linear-gradient(90deg, #2563eb, #0ea5e9);
    color: white;
    border: none;
    border-radius: 10px;
    min-height: 43px;
    font-weight: 600;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border: 1px solid #7dd3fc;
    color: white;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #293c59;
    border-radius: 12px;
}
hr {
    border-color: #293c59;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------

DB_NAME = "network_history.db"


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS network_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL
            )
        """)


def save_result(ip, status, latency):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            INSERT INTO network_checks
            (checked_at, ip_address, status, latency_ms)
            VALUES (?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ip,
            status,
            latency,
        ))


def load_history():
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query("""
            SELECT id, checked_at, ip_address, status, latency_ms
            FROM network_checks
            ORDER BY id DESC
        """, conn)


init_db()

st_autorefresh(
    interval=60_000,
    limit=None,
    key="network_auto_refresh"
)


# ---------------- NETWORK CHECK ----------------

def valid_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def check_device(ip):
    if not valid_ip(ip):
        return "Invalid IP", None

    if platform.system().lower() == "windows":
        command = ["ping", "-n", "1", "-w", "1500", ip]
    else:
        command = ["ping", "-c", "1", "-W", "2", ip]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=4,
        )

        output = result.stdout + result.stderr

        if result.returncode == 0:
            match = re.search(
                r"time[=<]\s*([\d.]+)\s*ms",
                output,
                re.IGNORECASE,
            )
            latency = float(match.group(1)) if match else None
            return "Online", latency

        return "No Response", None

    except (subprocess.TimeoutExpired, OSError):
        return "No Response", None


# ---------------- FAULT RISK ANALYSIS ----------------

def calculate_risk(history):
    if history.empty:
        return pd.DataFrame(columns=[
            "IP Address", "Checks Analysed",
            "Failures", "Failure Rate",
            "Average Latency (ms)", "Risk Level"
        ])

    rows = []

    for ip, group in history.groupby("ip_address", sort=False):
        recent = group.head(10)
        valid_checks = recent[recent["status"] != "Invalid IP"]

        if valid_checks.empty:
            continue

        failures = int((valid_checks["status"] != "Online").sum())
        total_checks = len(valid_checks)
        failure_rate = failures / total_checks * 100

        latencies = pd.to_numeric(
            valid_checks["latency_ms"], errors="coerce"
        ).dropna()

        avg_latency = (
            round(float(latencies.mean()), 2)
            if not latencies.empty else None
        )

        if failure_rate >= 50:
            risk = "High"
        elif failures > 0 or (
            avg_latency is not None and avg_latency >= 150
        ):
            risk = "Medium"
        else:
            risk = "Low"

        rows.append({
            "IP Address": ip,
            "Checks Analysed": total_checks,
            "Failures": failures,
            "Failure Rate": f"{failure_rate:.1f}%",
            "Average Latency (ms)": avg_latency,
            "Risk Level": risk,
        })

    return pd.DataFrame(rows)


# ---------------- HEADER ----------------

st.markdown("## 🌐 SMART NETWORK FAULT PREDICTOR")
st.markdown(
    "### Network monitoring · Health analytics · Fault-risk estimation"
)
st.caption(
    "Monitor IP connectivity, review response times, "
    "and identify devices that may need attention."
)

st.divider()


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown("## ⚙️ Control Panel")
    st.caption("Enter one IP address per line.")

    ip_input = st.text_area(
        "IP addresses",
        value="127.0.0.1\n8.8.8.8",
        height=130,
        help="Example: 127.0.0.1",
    )

    run_check = st.button(
        "🔍 Check Network",
        width="stretch",
    )
    
    auto_monitoring = st.toggle(
        "🔄 Enable automatic checks",
        value=True,
    )


    st.divider()
    st.markdown("### 📌 How it works")
    st.write("1. Validate IP addresses")
    st.write("2. Send ping requests")
    st.write("3. Record response times")
    st.write("4. Save results in SQLite")
    st.write("5. Estimate fault risk")

    st.info(
        "Risk levels are estimates based on recent checks, "
        "not guaranteed predictions."
    )


# ---------------- RUN CHECKS ----------------

# Automatic network monitoring
if "last_auto_check" not in st.session_state:
    st.session_state.last_auto_check = 0.0

if auto_monitoring:
    now = datetime.now().timestamp()

    if now - st.session_state.last_auto_check >= 60:
        addresses = list(dict.fromkeys(
            line.strip()
            for line in ip_input.splitlines()
            if line.strip()
        ))

        for ip in addresses:
            status, latency = check_device(ip)
            save_result(ip, status, latency)

        st.session_state.last_auto_check = now


if run_check:
    addresses = list(dict.fromkeys(
        line.strip()
        for line in ip_input.splitlines()
        if line.strip()
    ))

    if not addresses:
        st.warning("Please enter at least one IP address.")
    else:
        progress = st.progress(0)
        message = st.empty()

        for index, ip in enumerate(addresses):
            message.write(f"Checking: {ip}")

            status, latency = check_device(ip)
            save_result(ip, status, latency)

            progress.progress((index + 1) / len(addresses))

        message.success("Network check completed!")
        progress.empty()


# ---------------- LOAD DATA ----------------

history = load_history()

if not history.empty:
    history["latency_ms"] = pd.to_numeric(
        history["latency_ms"], errors="coerce"
    )

current = (
    history.drop_duplicates(subset=["ip_address"], keep="first")
    if not history.empty
    else pd.DataFrame()
)

if not current.empty:
    current = current[current["status"] != "Invalid IP"]

total = len(current)
online = int((current["status"] == "Online").sum()) if total else 0
offline = int((current["status"] == "No Response").sum()) if total else 0

health_percentage = (online / total * 100) if total else 0


# ---------------- SUMMARY CARDS ----------------

st.markdown("## 📊 Network Overview")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("Devices Checked", total)

with c2:
    st.metric("🟢 Online", online)

with c3:
    st.metric("🔴 No Response", offline)

with c4:
    st.metric("💚 Availability", f"{health_percentage:.1f}%")


# ---------------- HEALTH OVERVIEW ----------------

st.divider()
st.markdown("## 💚 Network Health Overview")

if total > 0:
    h1, h2 = st.columns([2, 1])

    with h1:
        st.progress(int(health_percentage))
        st.caption(
            f"{online} of {total} responding devices "
            f"({health_percentage:.1f}% availability)"
        )

    with h2:
        if health_percentage >= 90:
            st.success("Network status: Healthy")
        elif health_percentage >= 50:
            st.warning("Network status: Needs Attention")
        else:
            st.error("Network status: Critical")
else:
    st.info("Click Check Network to view network health.")


# ---------------- CURRENT RESULTS ----------------

st.divider()
st.markdown("## 🖥️ Current Device Results")

if not current.empty:
    display_current = current[
        ["checked_at", "ip_address", "status", "latency_ms"]
    ].copy()

    display_current.columns = [
        "Last Checked", "IP Address", "Status", "Latency (ms)"
    ]

    st.dataframe(
        display_current,
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No network results yet. Run your first check.")


# ---------------- LATENCY CHART ----------------

st.divider()
st.markdown("## 📈 Response Time Analysis")

latency_data = current[
    (current["status"] == "Online") &
    current["latency_ms"].notna()
].copy() if not current.empty else pd.DataFrame()

if not latency_data.empty:
    fig = px.bar(
        latency_data,
        x="ip_address",
        y="latency_ms",
        color="latency_ms",
        color_continuous_scale=["#22c55e", "#facc15", "#ef4444"],
        labels={
            "ip_address": "IP Address",
            "latency_ms": "Latency (ms)",
        },
        template="plotly_dark",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.info("No successful ping latency measurements available yet.")


# ---------------- RISK TABLE ----------------

st.divider()
st.markdown("## 🚦 Fault Risk Analysis")

risk_data = calculate_risk(history)

if not risk_data.empty:
    st.dataframe(
        risk_data,
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Risk analysis will appear after network checks.")


# ---------------- HISTORY ----------------

st.divider()
st.markdown("## 🗂️ Network Check History")

if not history.empty:
    history_display = history[
        ["checked_at", "ip_address", "status", "latency_ms"]
    ].copy()

    history_display.columns = [
        "Checked At", "IP Address", "Status", "Latency (ms)"
    ]

    st.dataframe(
        history_display,
        width="stretch",
        hide_index=True,
    )

    csv_data = history_display.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Download History as CSV",
        data=csv_data,
        file_name="network_history.csv",
        mime="text/csv",
        width="stretch",
    )
else:
    st.info("History will appear after the first network check.")


# ---------------- FOOTER ----------------

st.divider()
st.caption(
    "Smart Network Fault Predictor | Python · Streamlit · "
    "SQLite · Pandas · Plotly"
)

