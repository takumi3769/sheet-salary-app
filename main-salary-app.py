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
    total_minutes = int(round(hours_float * 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}:{minutes:02d}"

def ceil_10(x):
    if x <= 0: return 0
    # 10円単位の切り上げ（誤差対策：微小値を引いてから切り上げ）
    return math.ceil((round(x, 5) - 0.001) / 10) * 10

# --- 3. 画面設定 ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="centered")

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
is_holiday = jpholiday.is_holiday(d)
is_weekend = d.weekday() >= 5 
apply_premium = (is_holiday or is_weekend) or special_adjustment

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

# --- 5. 時間計算（「分」で計算） ---
start_dt = datetime.combine(d, time(sh_val, sm_val))
if eh_val >= 24:
    end_dt = datetime.combine(d + timedelta(days=1), time(eh_val - 24, em_val))
else:
    end_dt = datetime.combine(d, time(eh_val, em_val))
    if end_dt <= start_dt: end_dt += timedelta(days=1)

actual_min = max(0, (end_dt - start_dt).total_seconds() / 60 - ((br_h * 60) + br_m))
night_min = 0
curr = start_dt
while curr < end_dt:
    if curr.hour >= 22 or curr.hour < 5: night_min += 1
    curr += timedelta(minutes=1)

# 保存用
actual_h = round(actual_min / 60, 4)
night_h = round(night_min / 60, 4)

# 本日の目安計算（すべて「分単価」で計算）
day_b_pay = ceil_10((actual_min * st.session_state.hourly_wage) / 60)
day_n_prem = math.ceil((night_min * (st.session_state.hourly_wage * 0.25)) / 60)
day_e_allow = math.ceil((actual_min * 50) / 60) if apply_premium else 0
day_total = day_b_pay + day_n_prem + day_e_allow

st.divider()
st.metric("計算結果 (合計支給額)", f"{int(day_total):,} 円", f"↑ {format_hours(actual_h)} 労働")

# --- 6. 保存処理 ---
if st.button("💾 スプレッドシートに保存"):
    if sh_main:
        sheet = get_worksheet(sh_main, target_month)
        break_str = f"{br_h}h {br_m}m" if break_status == "あり" else "なし"
        new_row = [
            d.strftime('%Y-%m-%d'), f"{sh_val:02d}:{sm_val:02d}", f"{eh_val:02d}:{em_val:02d}", 
            break_str, actual_h, night_h, day_b_pay, day_n_prem, day_e_allow, day_total,
            "Yes" if apply_premium else "No"
        ]
        sheet.append_row(new_row)
        st.cache_data.clear()
        st.success("保存しました！")
        st.rerun()

# --- 7. 履歴詳細 (全項目を「分」の合計から一括計算) ---
st.divider()
st.subheader(f"📊 {target_month} の履歴詳細")
if sh_main:
    data = get_all_data(target_month)
    if data:
        df = pd.DataFrame(data)
        df.columns = [c.strip() for c in df.columns]
        df['労働(h)'] = pd.to_numeric(df['労働(h)'], errors='coerce').fillna(0)
        df['深夜(h)'] = pd.to_numeric(df['深夜(h)'], errors='coerce').fillna(0)

        # 全ての合計を「分」に変換
        total_work_min = round(df['労働(h)'].sum() * 60)
        total_night_min = round(df['深夜(h)'].sum() * 60)
        premium_min = round(df[df['手当適用'] == 'Yes']['労働(h)'].sum() * 60) if '手当適用' in df.columns else 0

        # 月合計に対する一括計算
        # 基本給：(総分 × 時給) / 60 -> 10円単位切り上げ
        sum_base = ceil_10((total_work_min * st.session_state.hourly_wage) / 60)
        
        # 深夜給：(総深夜分 × (時給×0.25)) / 60 -> 1円単位切り上げ
        sum_night = math.ceil((total_night_min * (st.session_state.hourly_wage * 0.25)) / 60)
        
        # 土日祝手当：(総手当分 × 50) / 60 -> 1円単位切り上げ
        sum_allow = math.ceil((premium_min * 50) / 60)
        
        # 合計支給額
        final_total = sum_base + sum_night + sum_allow

        # メトリクス表示
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("支給額合計", f"{int(final_total):,}円")
        m2.metric("基本給計", f"{int(sum_base):,}円")
        m3.metric("労働合計", format_hours(total_work_min / 60))
        m4.metric("深夜合計", format_hours(total_night_min / 60))
        m5.metric("土日祝合計", format_hours(premium_min / 60))

        # テーブル表示
        df_disp = df.copy()
        df_disp['row_idx'] = [i + 2 for i in range(len(df))]
        df_disp.insert(0, "選択", False)
        df_disp['労働'] = df_disp['労働(h)'].apply(format_hours)
        df_disp['深夜'] = df_disp['深夜(h)'].apply(format_hours)
        
        cols_to_show = ["選択", "日付", "出勤", "退勤", "労働", "深夜", "手当適用"]
        actual_cols = [c for c in cols_to_show if c in df_disp.columns]
        st.data_editor(df_disp[actual_cols], hide_index=True, key="cur_edt")
        
        if st.button("🗑️ 選択した行を削除", type="primary"):
            selected_indices = st.session_state.cur_edt[st.session_state.cur_edt["選択"]].index
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
                w_m = round(pd.to_numeric(tdf['労働(h)'], errors='coerce').sum() * 60)
                n_m = round(pd.to_numeric(tdf['深夜(h)'], errors='coerce').sum() * 60)
                p_m = round(tdf[tdf['手当適用'] == 'Yes']['労働(h)'].astype(float).sum() * 60)
                
                m_t = ceil_10((w_m * st.session_state.hourly_wage) / 60) + \
                      math.ceil((n_m * (st.session_state.hourly_wage * 0.25)) / 60) + \
                      math.ceil((p_m * 50) / 60)
                summary.append({"月": s.title, "支給額": f"{int(m_t):,}円"})
    if summary:
        st.dataframe(pd.DataFrame(summary).sort_values("月", ascending=False), hide_index=True, use_container_width=True)
