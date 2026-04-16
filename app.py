import streamlit as st
import pandas as pd
import time

# --- APP CONFIGURATION ---
st.set_page_config(
    page_title="Performance Automator", 
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM STYLING ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        width: 100%;
        border-radius: 5px;
        height: 3em;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/1157/1157053.png", width=100)
    st.title("Control Panel")
    st.info("""
    **Instructions:**
    1. Upload the 3 required CSV files.
    2. Wait for the AI to merge the datasets.
    3. Preview the metrics in the dashboard.
    4. Download your consolidated report.
    """)
    st.divider()
    st.caption("v2.0.1 - Performance Automator")

# --- HELPER FUNCTIONS (UNCHANGED) ---
def hms_to_sec(t):
    if pd.isna(t) or t == '0' or t == 0: return 0
    try:
        t_clean = str(t).split('.')[0] 
        parts = t_clean.split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except:
        return 0

def sec_to_hms(seconds):
    if pd.isna(seconds) or seconds <= 0: return "00:00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# --- MAIN UI ---
st.title("📊 AI-Powered Report Automator")
st.subheader("Transform raw CSV exports into performance insights.")

# --- FILE UPLOADS IN AN EXPANDER ---
with st.expander("📤 Step 1: Upload Source Files", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        prod_file = st.file_uploader("Productivity Summary", type="csv", help="Upload the core productivity export")
    with col2:
        sess_file = st.file_uploader("Session Details", type="csv", help="Upload the session/break log")
    with col3:
        sales_file = st.file_uploader("Custom Sales Report", type="csv", help="Upload the outbound sales/call log")

if prod_file and sess_file and sales_file:
    # Use a status container for better UX
    with st.status("🚀 Processing Data...", expanded=True) as status:
        st.write("Reading files...")
        prod = pd.read_csv(prod_file)
        sess = pd.read_csv(sess_file)
        sales = pd.read_csv(sales_file)

        st.write("Cleaning and normalizing IDs...")
        for df in [prod, sess, sales]:
            df.dropna(subset=['User ID'], inplace=True)
            df['User ID'] = df['User ID'].str.lower().str.strip()

        # Process Dates
        prod['Date'] = pd.to_datetime(prod['Interval Start'], dayfirst=True).dt.date
        sess['Date'] = pd.to_datetime(sess['Login Time'], dayfirst=True).dt.date
        sales['Date'] = pd.to_datetime(sales['Start Time'], dayfirst=True).dt.date

        st.write("Calculating break distributions...")
        sess['Break_Sec'] = sess['Break Duration'].apply(hms_to_sec)
        break_pivot = sess.pivot_table(
            index=['Date', 'User ID'], 
            columns='Break Reason', 
            values='Break_Sec', 
            aggfunc='sum', 
            fill_value=0
        ).reset_index()

        st.write("Aggregating call metrics...")
        sales['Talk_Sec'] = sales['Talk Time'].apply(hms_to_sec)
        sales['Is_Connected'] = sales['Talk_Sec'] >= 1
        
        sales_agg = sales.groupby(['Date', 'User ID']).agg(
            Total_OB_Calls=('call Id', 'count'),
            Unq_OB_Calls=('dstPhone', 'nunique')
        ).reset_index()

        conn_agg = sales[sales['Is_Connected']].groupby(['Date', 'User ID']).agg(
            Connected_OB_Calls=('call Id', 'count'),
            Unq_CC_Calls=('dstPhone', 'nunique')
        ).reset_index()
        sales_final = pd.merge(sales_agg, conn_agg, on=['Date', 'User ID'], how='left').fillna(0)

        st.write("Merging productivity data...")
        prod_time_cols = ['Total Staffed Duration', 'Total Ready Duration', 'Total Break Duration', 
                          'Total Idle Time', 'Total Talk Time in Interval', 'Total ACW Duration in Interval']
        for col in prod_time_cols:
            prod[col + '_sec'] = prod[col].apply(hms_to_sec)

        prod_final = prod.groupby(['Date', 'User ID', 'User Name']).agg({
            'Total Staffed Duration_sec': 'sum',
            'Total Ready Duration_sec': 'sum',
            'Total Break Duration_sec': 'sum',
            'Total Idle Time_sec': 'sum',
            'Total Talk Time in Interval_sec': 'sum',
            'Total ACW Duration in Interval_sec': 'sum'
        }).reset_index()

        # 7. Convert Sec to HMS with specific naming
        dynamic_breaks = [c for c in break_pivot.columns if c not in ['Date', 'User ID']]
        
        # Explicitly map the system names to your desired report names
        rename_map = {
            'Total Staffed Duration_sec': 'Staffed Duration',
            'Total Ready Duration_sec': 'Ready Duration',
            'Total Break Duration_sec': 'Break Duration',
            'Total Idle Time_sec': 'Idle Time',
            'Total Talk Time in Interval_sec': 'Talk Time',
            'Total ACW Duration in Interval_sec': 'ACW Duration'
        }

        for original, clean in rename_map.items():
            if original in final_df.columns:
                final_df[clean] = final_df[original].apply(sec_to_hms)

        # Convert dynamic breaks
        clean_break_cols = []
        for col in dynamic_breaks:
            clean_name = col.replace('Total ', '')
            final_df[clean_name] = final_df[col].apply(sec_to_hms)
            clean_break_cols.append(clean_name)

        # Final Column Selection using the new clean names
        perf_metrics = ['Idle Time', 'Talk Time', 'ACW Duration', 'Total_OB_Calls', 'Connected_OB_Calls', 'Unq_OB_Calls', 'Unq_CC_Calls']
        final_order = ['Date', 'User Name', 'User ID', 'Staffed Duration', 'Ready Duration', 'Break Duration'] + clean_break_cols + perf_metrics
        
        # Use a list comprehension to ensure only existing columns are selected
        result = final_df[[c for c in final_order if c in final_df.columns]].copy()
        final_order = ['Date', 'User Name', 'User ID', 'Staffed Duration', 'Ready Duration', 'Break Duration'] + \
                      [b.replace('Total ', '') for b in dynamic_breaks] + perf_cols
        
        result = final_df[final_order].copy()
        status.update(label="✅ Transformation Complete!", state="complete", expanded=False)

    # --- TABS FOR RESULTS ---
    tab1, tab2 = st.tabs(["📊 Performance Dashboard", "📂 Detailed Database"])

    with tab1:
        # KPI Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Agents", result['User ID'].nunique())
        m2.metric("Total OB Calls", int(result['Total_OB_Calls'].sum()))
        m3.metric("Connected Calls", int(result['Connected_OB_Calls'].sum()))
        m4.metric("Unique Connections", int(result['Unq_CC_Calls'].sum()))

        st.divider()
        
        # Download at the top for convenience
        csv = result.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Consolidated CSV Report",
            data=csv,
            file_name=f"Agent_Performance_{time.strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    with tab2:
        st.dataframe(result, use_container_width=True, hide_index=True)

else:
    st.info("👋 Please upload the required CSV files above to begin the automated analysis.")
