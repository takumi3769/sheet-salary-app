import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import jpholiday
import gspread
from google.oauth2.service_account import Credentials

# --- 1. スプレッドシート接続設定 ---
def init_spreadsheet(month_str):
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    try:
        creds_info = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        gc = gspread.authorize(credentials)
        
        sh = gc.open("給料管理")
        
        try:
            worksheet = sh.worksheet(month_str)
        except gspread.exceptions.WorksheetNotFound:
            # なければ新規作成し、ヘッダーを追加
            worksheet = sh.add_worksheet(title=month_str, rows="100", cols="10")
            header = ["日付", "出勤", "退勤", "労働(h)", "深夜(h)", "給料"]
            worksheet.append_row(header)
            
        return worksheet
    except Exception as e:
        st.error(f"スプレッドシートへの接続に失敗しました: {e}")
        return None

# --- 2. 画面基本設定 ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="centered")

# --- 表の上のツールバーを非表示にするCSS (修正済み) ---
st.markdown("""
    <style>
    [data-testid="stElementToolbar"] {
        display: none;
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

break_choice = st.radio("☕ 休憩の有無", ["なし", "あり（1時間）"], horizontal=True)

# --- 5. 計算ロジック ---
def calculate_salary(d, sh, sm, eh, em, base_wage, has_break):
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
    
    if has_break == "あり（1時間）":
        work_minutes = max(0, work_minutes - 60)
        total_salary = max(0, total_salary - base_wage)
    return work_minutes/60.0, night_minutes/60.0, int(total_salary)

actual_h, night_h, salary = calculate_salary(d, sh, sm, eh, em, base_wage_today, break_choice)

st.divider()
st.metric("計算された給料", f"{salary:,} 円", f"{actual_h:.2f} 時間労働")

# --- 6. 保存処理 ---
if st.button("💾 スプレッドシートに保存"):
    sheet = init_spreadsheet(target_month)
    if sheet:
        new_row = [d.strftime('%Y-%m-%d'), f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}", round(actual_h, 2), round(night_h, 2), salary]
        sheet.append_row(new_row)
        st.success(f"シート「{target_month}」に保存しました！")
    else:
        st.error("保存に失敗しました。")

# --- 7. 履歴表示・削除 ---
st.divider()
st.subheader(f"📊 {target_month} の履歴管理")

sheet = init_spreadsheet(target_month)
if sheet:
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        df['row_idx'] = [i + 2 for i in range(len(df))]
        df.insert(0, "選択", False)
        
        edited_df = st.data_editor(
            df,
            column_config={
                "選択": st.column_config.CheckboxColumn(required=True),
                "row_idx": None
            },
            disabled=[col for col in df.columns if col != "選択"],
            hide_index=True,
        )

        if not edited_df[edited_df["選択"]].empty:
            if st.button("🗑️ 選択した行を削除", type="primary"):
                rows_to_delete = sorted(edited_df[edited_df["選択"]]["row_idx"].tolist(), reverse=True)
                for r in rows_to_delete:
                    sheet.delete_rows(r)
                st.rerun()

        st.write(f"### {target_month} 合計")
        m1, m2 = st.columns(2)
        m1.metric("支給額合計", f"{df['給料'].sum():,} 円")
        m2.metric("労働時間合計", f"{df['労働(h)'].sum():.1f} h")
    else:
        st.info("この月のデータはまだありません。")
