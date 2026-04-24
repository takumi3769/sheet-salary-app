import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import jpholiday
import gspread
from google.oauth2.service_account import Credentials
import math

# --- 1. スプレッドシート接続設定 ---
@st.cache_resource
def init_spreadsheet_service():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open("給料管理")
        return sh
    except Exception as e:
        st.error(f"接続エラー: {e}")
        return None

@st.cache_data(ttl=60)
def get_all_data(month_str):
    sh = init_spreadsheet_service()
    if sh:
        try:
            ws = sh.worksheet(month_str)
            return ws.get_all_records()
        except:
            return []
    return []

def get_worksheet(sh, month_str):
    try:
        return sh.worksheet(month_str)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=month_str, rows="100", cols="12")
        header = ["日付", "出勤", "退勤", "休憩時間", "労働(h)", "深夜(h)", "基本給(10円切上)", "深夜割増", "手当分", "給料合計", "手当適用"]
        worksheet.append_row(header)
        return worksheet

# --- 2. 補助関数 ---
def format_hours(hours_float):
    if pd.isna(hours_float) or hours_float <= 0: return "0:00"
    # 0.0001分以下のゴミを排除してから時間に直す
    total_minutes = int(round(round(hours_float, 8) * 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"

def ceil_10(x):
    """10円単位切り上げ（超微細な誤差をroundで消してから計算）"""
    return math.ceil(round(x, 5) / 10) * 10

def ceil_1(x):
    """1円単位切り上げ（超微細な誤差をroundで消してから計算）"""
    return math.ceil(round(x, 5))

def floor_delta(x, decimals=3):
    """小数点第4位を切り捨て"""
    multiplier = 10 ** decimals
    return math.floor(round(x, 8) * multiplier) / multiplier

# --- 3. 画面設定 & CSS ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="wide")

# CSS: 表の上のツールバー（虫眼鏡、ダウンロード等）を非表示にする
st.markdown("""
    <style>
    [data-testid="stElementToolbar"] {
        display: none;
    }

    /* メインエリア内の2つ目以降の divider よりも後にあるメトリクスだけを小さくする */
    /* あるいは、もっと確実に「履歴詳細」のセクションだけを狙う場合 */
    [data-testid="stVerticalBlock"] > div:nth-last-child(-n+5) [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
    }
    
     /* --- 1. アプリ全体の基本設定 --- */
    .stApp { background-color: #E0F2F7 !important; }

    /* 文字全般 */
    h1, h2, h3, p, label, .stMarkdown { color: #000000 !important; }
    
    /* --- 2. サイドバーの設定（枠なし・黄色背景） --- */
    [data-testid="stSidebar"] {
        background-color: #FFEB3B !important;
        background-image: none !important;
    }

    /* サイドバーの入力ボックス（枠を完全に消去） */
    [data-testid="stSidebar"] div[data-baseweb="input"],
    [data-testid="stSidebar"] div[data-baseweb="base-input"],
    [data-testid="stSidebar"] div[data-baseweb="input"] > div {
        background-color: #FFFFFF !important;
        border: none !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebar"] input {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: none !important;
    }

    /* ＋ーボタンの色分け */
    [data-testid="stSidebar"] button[data-testid^="stNumberInputStep"] {
        border: none !important;
        margin: 0 !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] button[data-testid="stNumberInputStepDown"] { background-color: #007BFF !important; }
    [data-testid="stSidebar"] button[data-testid="stNumberInputStepUp"] { background-color: #FF4B4B !important; }
    [data-testid="stSidebar"] button[data-testid^="stNumberInputStep"] svg { fill: #FFFFFF !important; }

    /* --- 3. メインエリアの設定（枠なし・白床・黒文字） --- */
    /* 全文字を黒に固定 */
    [data-testid="stMain"] * {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* 全ての入力ボックス・セレクトボックスの枠線を消す */
    [data-testid="stMain"] div[data-baseweb="input"],
    [data-testid="stMain"] div[data-baseweb="base-input"],
    [data-testid="stMain"] div[data-baseweb="input"] > div,
    [data-testid="stMain"] div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        border: none !important; /* メインの外枠も削除 */
        box-shadow: none !important; /* 影も削除 */
        border-radius: 4px !important;
    }

    /* 入力欄そのものの枠も消す */
    [data-testid="stMain"] input {
        border: none !important;
        background-color: transparent !important;
    }

    /* セレクトボックスの矢印アイコンを黒に */
    [data-testid="stMain"] svg {
        fill: #000000 !important;
    }

    /* --- 4. ボタン設定 --- */
    /* 「保存」ボタン（枠ありでボタンらしく見せる場合） */
    [data-testid="stMain"] div.stButton > button {
        background-color: #D3D3D3 !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

if 'hourly_wage' not in st.session_state:
    st.session_state.hourly_wage = 1200

with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state.hourly_wage = st.number_input("基本時給(円)", value=st.session_state.hourly_wage, step=10)

st.title("💰 給料管理システム")
sh_main = init_spreadsheet_service()

# --- 4. 勤務入力 ---
st.subheader("📅 勤務情報の入力")
d = st.date_input("日付を選択", datetime.now())
target_month = d.strftime('%Y-%m')

special_adjustment = st.checkbox("特定日手当を適用する (+50円)")
apply_premium = (jpholiday.is_holiday(d) or d.weekday() >= 5) or special_adjustment

col_s1, col_s2, col_e1, col_e2 = st.columns(4)
with col_s1: sh_val = st.selectbox("出勤（時）", list(range(24)), index=17)
with col_s2: sm_val = st.selectbox("出勤（分）", list(range(60)), index=55)
with col_e1: eh_val = st.selectbox("退勤（時）", list(range(30)), index=23)
with col_e2: em_val = st.selectbox("退勤（分）", list(range(60)), index=30)

break_status = st.radio("休憩", ["なし", "あり"], horizontal=True)
br_h, br_m = 0, 0
if break_status == "あり":
    col_br1, col_br2 = st.columns(2)
    br_h = col_br1.selectbox("休憩（h）", list(range(11)), index=0)
    br_m = col_br2.selectbox("休憩（m）", list(range(60)), index=25)

# --- 5. 計算ロジック ---
def calculate_salary(d, sh, sm, eh, em, bh, bm, base_wage, has_premium):
    start_dt = datetime.combine(d, time(sh, sm))
    if eh >= 24:
        end_dt = datetime.combine(d + timedelta(days=1), time(eh - 24, em))
    else:
        end_dt = datetime.combine(d, time(eh, em))
        if end_dt <= start_dt: end_dt += timedelta(days=1)
    
    actual_work_min = max(0, (end_dt - start_dt).total_seconds() / 60 - (bh * 60 + bm))
    
    night_minutes = 0
    curr = start_dt
    while curr < end_dt:
        if 22 <= curr.hour or curr.hour < 5: night_minutes += 1
        curr += timedelta(minutes=1)
    
    # 時間を小数に変換（第4位切捨）
    h_work = floor_delta(actual_work_min / 60.0)
    h_night = floor_delta(night_minutes / 60.0)
    
    b_pay = ceil_10(base_wage * h_work)
    n_prem = ceil_1(base_wage * 0.25 * h_night)
    e_allow = ceil_1(50 * h_work) if has_premium else 0
    
    return h_work, h_night, b_pay, n_prem, e_allow, (b_pay + n_prem + e_allow)

actual_h, night_h, b_pay, n_prem, e_allow, total_s = calculate_salary(
    d, sh_val, sm_val, eh_val, em_val, br_h, br_m, st.session_state.hourly_wage, apply_premium
)

st.divider()
st.subheader("💰 今回の計算結果")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("合計支給額", f"{total_s:,} 円")
c2.metric("基本給分", f"{b_pay:,} 円")
c3.metric("深夜割増分", f"{n_prem:,} 円")
c4.metric("手当分", f"{e_allow:,} 円")
c5.metric("労働時間", format_hours(actual_h))

if st.button("💾 スプレッドシートに保存"):
    if sh_main:
        sheet = get_worksheet(sh_main, target_month)
        break_str = f"{br_h}h {br_m}m" if break_status == "あり" else "なし"
        sheet.append_row([
            d.strftime('%Y-%m-%d'), f"{sh_val:02d}:{sm_val:02d}", f"{eh_val:02d}:{em_val:02d}", 
            break_str, actual_h, night_h, b_pay, n_prem, e_allow, total_s, "Yes" if apply_premium else "No"
        ])
        st.cache_data.clear()
        st.success("保存しました！")
        st.rerun()

# --- 7. 履歴詳細 ---
st.divider()
st.subheader(f"📊 {target_month} の履歴詳細")
if sh_main:
    data = get_all_data(target_month)
    if data:
        df = pd.DataFrame(data)
        df.columns = [c.strip() for c in df.columns]
        for col in ['労働(h)', '深夜(h)']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 【超・厳格化】
        # 合計した直後に round(x, 5) をして 0.00001 以下の浮動小数点ゴミを完全に削除
        # これにより、13.00000000001 のような値が 13.0 に修正されます
        total_work_h = round(df['労働(h)'].sum(), 5)
        total_night_h = round(df['深夜(h)'].sum(), 5)
        
        if '手当適用' in df.columns:
            total_prem_h = round(df[df['手当適用'] == 'Yes']['労働(h)'].sum(), 5)
        else:
            total_prem_h = 0.0

        # 月間一括計算
        final_base_pay = ceil_10(st.session_state.hourly_wage * total_work_h)
        # 時給×0.25の単価計算でもroundを挟み、時間にゴミが混ざるのを防ぐ
        final_night_pay = ceil_1(round(st.session_state.hourly_wage * 0.25, 5) * total_night_h)
        final_allowance_pay = ceil_1(50 * total_prem_h)
        
        # 支給額合計
        final_total_pay = final_base_pay + final_night_pay + final_allowance_pay

        # メトリクス表示
        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("支給額合計", f"{final_total_pay:,}円")
        m2.metric("基本給計", f"{final_base_pay:,}円")
        m3.metric("深夜割増計", f"{final_night_pay:,}円")
        m4.metric("手当合計", f"{final_allowance_pay:,}円")
        m5.metric("労働合計", format_hours(total_work_h))
        m6.metric("深夜合計", format_hours(total_night_h))
        m7.metric("土日祝合計", format_hours(total_prem_h))

        # テーブル表示
        df_disp = df.copy()
        df_disp['row_idx'] = [i + 2 for i in range(len(df))]
        df_disp.insert(0, "選択", False)
        df_disp['労働'] = df_disp['労働(h)'].apply(format_hours)
        df_disp['深夜'] = df_disp['深夜(h)'].apply(format_hours)
        cols_to_show = [c for c in df_disp.columns if c not in ['労働(h)', '深夜(h)', 'row_idx']]
        edited_df = st.data_editor(df_disp[cols_to_show], hide_index=True, key="cur_edt")
        
        if st.button("🗑️ 選択した行を削除", type="primary"):
            selected_indices = edited_df[edited_df["選択"]].index
            if not selected_indices.empty:
                ws = get_worksheet(sh_main, target_month)
                for r in sorted(df_disp.loc[selected_indices, 'row_idx'].tolist(), reverse=True):
                    ws.delete_rows(r)
                st.cache_data.clear()
                st.rerun()
    else: st.info("データがありません。")

# --- 8. 月別収入一覧 ---
st.divider()
st.subheader("📅 月別収入一覧")
if sh_main:
    summary = []
    for s in sh_main.worksheets():
        if "-" in s.title:
            content = s.get_all_records()
            if content:
                tdf = pd.DataFrame(content)
                tdf.columns = [c.strip() for c in tdf.columns]
                for c in ['労働(h)', '深夜(h)']:
                    if c in tdf.columns: tdf[c] = pd.to_numeric(tdf[c], errors='coerce').fillna(0)
                
                # 月別一覧でも一括計算ロジック
                s_work = round(tdf['労働(h)'].sum(), 5)
                s_night = round(tdf['深夜(h)'].sum(), 5)
                s_prem = round(tdf[tdf['手当適用'] == 'Yes']['労働(h)'].sum(), 5) if '手当適用' in tdf.columns else 0.0
                
                m_total = ceil_10(st.session_state.hourly_wage * s_work) + \
                          ceil_1(round(st.session_state.hourly_wage * 0.25, 5) * s_night) + \
                          ceil_1(50 * s_prem)
                summary.append({"月": s.title, "支給額": f"{int(m_total):,}円"})
    if summary:
        st.dataframe(pd.DataFrame(summary).sort_values("月", ascending=False), hide_index=True, use_container_width=True)
