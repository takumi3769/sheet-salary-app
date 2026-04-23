import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import jpholiday
import gspread
from google.oauth2.service_account import Credentials

# --- 1. スプレッドシート接続設定 ---
def init_spreadsheet_service():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open("給料管理")
        return sh
    except Exception as e:
        st.error(f"スプレッドシートへの接続に失敗しました: {e}")
        return None

def get_worksheet(sh, month_str):
    try:
        return sh.worksheet(month_str)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sh.add_worksheet(title=month_str, rows="100", cols="10")
        # ヘッダーを定義（7項目）
        header = ["日付", "出勤", "退勤", "休憩時間", "労働(h)", "深夜(h)", "給料"]
        worksheet.append_row(header)
        return worksheet

# --- 2. 画面基本設定 ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="centered")
# CSS: 表の上のツールバー（虫眼鏡、ダウンロード等）を非表示にする
st.markdown("""
    <style>
    [data-testid="stElementToolbar"] {
        display: none;
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

# --- 3. サイドバー ---
with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state.hourly_wage = st.number_input("基本時給(円)", value=st.session_state.hourly_wage, step=10)

st.title("💰 給料管理システム")
sh_main = init_spreadsheet_service()

# --- 4. 入力セクション ---
st.subheader("📅 勤務情報の入力")
d = st.date_input("日付を選択", datetime.now())
target_month = d.strftime('%Y-%m')

is_holiday = jpholiday.is_holiday(d)
is_weekend = d.weekday() >= 5 
base_wage_today = st.session_state.hourly_wage + 50 if (is_holiday or is_weekend) else st.session_state.hourly_wage

if is_holiday or is_weekend:
    st.warning(f"📅 手当適用日：ベース時給 {base_wage_today}円")

col_start, col_end = st.columns(2)
with col_start:
    st.write("**出勤**")
    c1, c2 = st.columns(2)
    with c1: sh = st.selectbox("時", list(range(24)), index=18, key="sh")
    with c2: sm = st.selectbox("分", list(range(60)), index=0, key="sm")
with col_end:
    st.write("**退勤**")
    c3, c4 = st.columns(2)
    with c3: eh = st.selectbox("時", list(range(24)), index=22, key="eh")
    with c4: em = st.selectbox("分", list(range(60)), index=0, key="em")

st.write("**休憩の有無**")
break_status = st.radio("休憩を選択", ["なし", "あり"], horizontal=True, label_visibility="collapsed")

br_h, br_m = 0, 0
if break_status == "あり":
    col_br1, col_br2 = st.columns(2)
    with col_br1: br_h = st.selectbox("休憩（時間）", list(range(10)), index=1, key="br_h")
    with col_br2: br_m = st.selectbox("休憩（分）", [0, 15, 30, 45], index=0, key="br_m")

# --- 5. 計算ロジック ---
def calculate_salary(d, sh, sm, eh, em, bh, bm, base_wage):
    start_dt = datetime.combine(d, time(sh, sm))
    end_dt = datetime.combine(d, time(eh, em))
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    
    total_salary, work_minutes, night_minutes = 0.0, 0, 0
    curr = start_dt
    while curr < end_dt:
        work_minutes += 1
        if curr.hour >= 22 or curr.hour < 5:
            night_minutes += 1
            total_salary += (base_wage / 60.0) * 1.25
        else:
            total_salary += (base_wage / 60.0)
        curr += timedelta(minutes=1)
    
    break_total_min = (bh * 60) + bm
    if break_total_min > 0:
        actual_work_min = max(0, work_minutes - break_total_min)
        ratio = actual_work_min / work_minutes if work_minutes > 0 else 0
        total_salary *= ratio
        work_minutes = actual_work_min
        night_minutes = int(night_minutes * ratio)

    return work_minutes/60.0, night_minutes/60.0, int(total_salary)

actual_h, night_h, salary = calculate_salary(d, sh, sm, eh, em, br_h, br_m, base_wage_today)

st.divider()
st.metric("計算された給料", f"{salary:,} 円", f"{actual_h:.2f} 時間労働")

# --- 6. 保存処理 ---
if st.button("💾 スプレッドシートに保存"):
    if sh_main:
        sheet = get_worksheet(sh_main, target_month)
        break_str = f"{br_h}h {br_m}m" if break_status == "あり" else "なし"
        # 確実にヘッダーと同じ7項目を順番通りに並べる
        new_row = [
            d.strftime('%Y-%m-%d'), 
            f"{sh:02d}:{sm:02d}", 
            f"{eh:02d}:{em:02d}", 
            break_str,            # D列: 休憩時間
            round(actual_h, 2),    # E列: 労働(h)
            round(night_h, 2),     # F列: 深夜(h)
            salary                 # G列: 給料
        ]
        sheet.append_row(new_row)
        st.success(f"保存しました！")
        st.rerun()

# --- 7. 履歴詳細 ---
st.divider()
st.subheader(f"📊 {target_month} の履歴詳細")
if sh_main:
    sheet = get_worksheet(sh_main, target_month)
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        
        # 読み込んだデータの列名を整理し、数値を強制変換
        if '給料' in df.columns:
            df['給料'] = pd.to_numeric(df['給料'], errors='coerce').fillna(0)
        if '労働(h)' in df.columns:
            df['労働(h)'] = pd.to_numeric(df['労働(h)'], errors='coerce').fillna(0)
        
        df['row_idx'] = [i + 2 for i in range(len(df))]
        df.insert(0, "選択", False)
        
        edited_df = st.data_editor(
            df, 
            column_config={"選択": st.column_config.CheckboxColumn(required=True), "row_idx": None}, 
            disabled=[col for col in df.columns if col != "選択"], 
            hide_index=True, 
            key="cur_edt"
        )
        
        if not edited_df[edited_df["選択"]].empty:
            if st.button("🗑️ 選択した行を削除", type="primary"):
                rows_to_delete = sorted(edited_df[edited_df["選択"]]["row_idx"].tolist(), reverse=True)
                for r in rows_to_delete: sheet.delete_rows(r)
                st.rerun()
        
        m1, m2 = st.columns(2)
        m1.metric("支給額合計", f"{int(df['給料'].sum()):,} 円")
        m2.metric("労働合計", f"{df['労働(h)'].sum():.1f} h")
    else:
        st.info("データがありません。")

# --- 8. 月別収入一覧 ---
st.divider()
st.subheader("📅 月別収入一覧")
if sh_main:
    summary_data = []
    for s in sh_main.worksheets():
        if len(s.title) == 7 and s.title[4] == '-':
            content = s.get_all_records()
            if content:
                temp_df = pd.DataFrame(content)
                temp_df['給料'] = pd.to_numeric(temp_df['給料'], errors='coerce').fillna(0)
                temp_df['労働(h)'] = pd.to_numeric(temp_df['労働(h)'], errors='coerce').fillna(0)
                
                summary_data.append({
                    "月": s.title, 
                    "支給額合計": temp_df['給料'].sum(), 
                    "労働時間合計": round(temp_df['労働(h)'].sum(), 1)
                })
    if summary_data:
        summary_df = pd.DataFrame(summary_data).sort_values("月", ascending=False)
        st.dataframe(
            summary_df, 
            column_config={
                "支給額合計": st.column_config.NumberColumn(format="%d 円"), 
                "労働時間合計": st.column_config.NumberColumn(format="%.1f h")
            }, 
            hide_index=True, 
            use_container_width=True
        )
