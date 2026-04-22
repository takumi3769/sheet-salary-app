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
        # Streamlit Secretsから認証情報を取得
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
        # シートが存在しない場合は新規作成しヘッダーを挿入
        worksheet = sh.add_worksheet(title=month_str, rows="100", cols="10")
        header = ["日付", "出勤", "退勤", "休憩時間", "労働(h)", "深夜(h)", "給料"]
        worksheet.append_row(header)
        return worksheet

# --- 2. 画面基本設定 ---
st.set_page_config(page_title="給料管理", page_icon="💰", layout="centered")

# CSS: 表のツールバー（虫眼鏡・ダウンロード等）を非表示にする
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
sh_main = init_spreadsheet_service()

# --- 4. 入力セクション ---
st.subheader("📅 勤務情報の入力")
d = st.date_input("日付を選択", datetime.now())
target_month = d.strftime('%Y-%m')

# 祝日・週末の時給アップ判定
is_holiday = jpholiday.is_holiday(d)
is_weekend = d.weekday() >= 5 
base_wage_today = st.session_state.hourly_wage + 50 if (is_holiday or is_weekend) else st.session_state.hourly_wage

if is_holiday or is_weekend:
    st.warning(f"📅 手当適用日：ベース時給 {base_wage_today}円")

# 出退勤時間の横並び入力
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

# 休憩設定：ありを選んだ時だけ時間選択を表示
st.write("**休憩の有無**")
break_status = st.radio("休憩を選択", ["なし", "あり"], horizontal=True, label_visibility="collapsed")

br_h, br_m = 0, 0
if break_status == "あり":
    col_br1, col_br2 = st.columns(2)
    with col_br1:
        br_h = st.selectbox("休憩（時間）", list(range(10)), index=1, key="br_h")
    with col_br2:
        br_m = st.selectbox("休憩（分）", [0, 15, 30, 45], index=0, key="br_m")

# --- 5. 計算ロジック ---
def calculate_salary(d, sh, sm, eh, em, bh, bm, base_wage):
    start_dt = datetime.combine(d, time(sh, sm))
    end_dt = datetime.combine(d, time(eh, em))
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    
    total_salary, work_minutes, night_minutes = 0.0, 0, 0
    curr = start_dt
    while curr < end_dt:
        work_minutes += 1
        # 22時〜5時は深夜手当(25%UP)
        if curr.hour >= 22 or curr.hour < 5:
            night_minutes += 1
            total_salary += (base_wage / 60.0) * 1.25
        else:
            total_salary += (base_wage / 60.0)
        curr += timedelta(minutes=1)
    
    # 休憩時間を差し引く
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
        new_row = [
            d.strftime('%Y-%m-%d'), 
            f"{sh:02d}:{sm:02d}", 
            f"{eh:02d}:{em:02d}", 
            break_str, 
            round(actual_h, 2), 
            round(night_h, 2), 
            salary
        ]
        sheet.append_row(new_row)
        st.success(f"シート「{target_month}」に保存しました！")
        st.rerun()

# --- 7. 履歴詳細・削除 ---
st.divider()
st.subheader(f"📊 {target_month} の履歴詳細")
if sh_main:
    sheet = get_worksheet(sh_main, target_month)
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
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
        m1.metric(f"{target_month} 支給額合計", f"{df['給料'].sum():,} 円")
        m2.metric(f"{target_month} 労働合計", f"{df['労働(h)'].sum():.1f} h")
    else:
        st.info(f"{target_month} のデータはまだありません。")

# --- 8. 月別収入一覧 ---
st.divider()
st.subheader("📅 月別収入一覧")
if sh_main:
    summary_data = []
    for s in sh_main.worksheets():
        # YYYY-MM 形式のシート名のみ集計
        if len(s.title) == 7 and s.title[4] == '-':
            content = s.get_all_records()
            if content:
                temp_df = pd.DataFrame(content)
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
