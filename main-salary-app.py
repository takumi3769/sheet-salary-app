import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import jpholiday
import gspread
from google.oauth2.service_account import Credentials

# --- 1. スプレッドシート接続設定 ---
def init_spreadsheet():
    # 権限のスコープを設定
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # StreamlitのSecrets（設定画面）から認証情報を読み込む
    # ローカルでテストする場合は st.secrets の代わりに jsonファイルを読み込む処理に変えてください
    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        
        # スプレッドシート名で開く
        sh = gc.open("給料管理").sheet1 
        return sh
    except Exception as e:
        st.error(f"スプレッドシートへの接続に失敗しました: {e}")
        return None

sheet = init_spreadsheet()

# --- 2. 画面基本設定 ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="centered")

# --- 3. カスタムCSS（サイドバー・メイン共に枠線を完全消去） ---
st.markdown("""
    <style>
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
# --- 4. サイドバー：時給設定 ---
if 'hourly_wage' not in st.session_state:
    st.session_state.hourly_wage = 1200

with st.sidebar:
    st.header("⚙️ 設定")
    st.session_state.hourly_wage = st.number_input("基本時給(円)", value=st.session_state.hourly_wage, step=10)
    st.info("※この時給は保存ボタンを押した時に計算に使用されます。")

st.title("💰 給料管理システム")

# --- 5. 入力セクション ---
st.subheader("📅 勤務情報の入力")
d = st.date_input("日付を選択", datetime.now())

# 祝日・週末判定
is_holiday = jpholiday.is_holiday(d)
is_weekend = d.weekday() >= 5 
base_wage_today = st.session_state.hourly_wage + 50 if (is_holiday or is_weekend) else st.session_state.hourly_wage

if is_holiday or is_weekend:
    st.warning(f"📅 手当適用日：ベース時給 {base_wage_today}円")

col_start, col_end = st.columns(2)
with col_start:
    st.write("**出勤**")
    sh = st.selectbox("時", list(range(24)), index=18, key="sh")
    sm = st.selectbox("分", list(range(60)), index=0, key="sm")
with col_end:
    st.write("**退勤**")
    eh = st.selectbox("時", list(range(24)), index=22, key="eh")
    em = st.selectbox("分", list(range(60)), index=0, key="em")

# 休憩設定
break_choice = st.radio("☕ 休憩の有無", ["なし", "あり（1時間）"], horizontal=True)

# --- 6. 計算ロジック ---
def calculate_salary(d, sh, sm, eh, em, base_wage, has_break):
    start_dt = datetime.combine(d, time(sh, sm))
    end_dt = datetime.combine(d, time(eh, em))
    
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    
    total_salary = 0.0
    work_minutes = 0
    night_minutes = 0
    
    curr = start_dt
    while curr < end_dt:
        work_minutes += 1
        # 深夜時間帯（22:00〜05:00）
        if curr.hour >= 22 or curr.hour < 5:
            night_minutes += 1
            total_salary += (base_wage / 60.0) * 1.25
        else:
            total_salary += (base_wage / 60.0)
        curr += timedelta(minutes=1)
    
    # 休憩（1時間=60分）を引く
    if has_break == "あり（1時間）":
        # 休憩分を単純に基本給からマイナス（深夜休憩などは考慮しない簡易版）
        work_minutes = max(0, work_minutes - 60)
        total_salary = max(0, total_salary - base_wage)
        
    return work_minutes/60.0, night_minutes/60.0, int(total_salary)

actual_h, night_h, salary = calculate_salary(d, sh, sm, eh, em, base_wage_today, break_choice)

st.divider()
st.metric("計算された給料", f"{salary:,} 円", f"{actual_h:.2f} 時間労働")

# --- 7. スプレッドシートへの保存 ---
if st.button("💾 スプレッドシートに保存"):
    if sheet:
        new_row = [
            d.strftime('%Y-%m-%d'),
            f"{sh:02d}:{sm:02d}",
            f"{eh:02d}:{em:02d}",
            round(actual_h, 2),
            round(night_h, 2),
            salary
        ]
        sheet.append_row(new_row)
        st.success("スプレッドシートに追記しました！")
        st.balloons()
    else:
        st.error("シートに接続されていないため保存できません。")

# --- 8. 履歴表示 ---
st.divider()
st.subheader("📊 最近の履歴")
if sheet:
    # 全データを取得してDataFrameにする
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # 最新の5件を表示
        st.table(df.tail(5))
        
        # 今月の合計などを表示
        df['日付'] = pd.to_datetime(df['日付'])
        current_month = datetime.now().month
        this_month_df = df[df['日付'].dt.month == current_month]
        
        st.write(f"### {current_month}月の集計")
        m1, m2 = st.columns(2)
        m1.metric("今月の支給額", f"{this_month_df['給料'].sum():,} 円")
        m2.metric("今月の労働時間", f"{this_month_df['労働(h)'].sum():.1f} h")
    else:
        st.write("履歴はまだありません。")
