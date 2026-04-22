import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import jpholiday
import gspread
from google.oauth2.service_account import Credentials

# --- 1. スプレッドシート接続設定 ---
def init_spreadsheet():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        # Streamlit Secretsから読み込み
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

# --- 3. セッション状態の初期化 ---
if 'hourly_wage' not in st.session_state:
    st.session_state.hourly_wage = 1200

# --- 4. サイドバー：時給設定 ---
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

# 時間設定を横並びにする
col_start, col_end = st.columns(2)

with col_start:
    st.write("**出勤**")
    c1, c2 = st.columns(2)
    with c1:
        sh = st.selectbox("時", list(range(24)), index=18, key="sh")
    with c2:
        sm = st.selectbox("分", list(range(60)), index=0, key="sm")

with col_end:
    st.write("**退勤**")
    c3, c4 = st.columns(2)
    with c3:
        eh = st.selectbox("時", list(range(24)), index=22, key="eh")
    with c4:
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
    
    # 休憩（1時間=60分）
    if has_break == "あり（1時間）":
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
        # st.balloons() は削除しました
    else:
        st.error("シートに接続されていないため保存できません。")

# --- 8. 履歴表示・削除機能 ---
st.divider()
st.subheader("📊 履歴の管理")

if sheet:
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # スプレッドシートの実際の行番号（ヘッダーがあるため index + 2）
        df['row_idx'] = [i + 2 for i in range(len(df))]
        
        st.write("削除したいデータにチェックを入れてください：")
        # 削除用のチェックボックス列を追加
        df.insert(0, "選択", False)
        
        # データエディタを表示
        edited_df = st.data_editor(
            df,
            column_config={
                "選択": st.column_config.CheckboxColumn(required=True),
                "row_idx": None # 行番号は非表示
            },
            disabled=[col for col in df.columns if col != "選択"],
            hide_index=True,
        )

        # 削除実行
        selected_rows = edited_df[edited_df["選択"] == True]
        if not selected_rows.empty:
            if st.button("🗑️ 選択した行を削除する", type="primary"):
                # 下の行から消さないと行番号がズレるため逆順にソート
                rows_to_delete = sorted(selected_rows["row_idx"].tolist(), reverse=True)
                try:
                    for r in rows_to_delete:
                        sheet.delete_rows(r)
                    st.success(f"{len(rows_to_delete)}件削除しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"削除エラー: {e}")

        # 今月の集計
        st.divider()
        df['日付'] = pd.to_datetime(df['日付'])
        current_month = datetime.now().month
        this_month_df = df[df['日付'].dt.month == current_month]
        
        st.write(f"### {current_month}月の集計")
        m1, m2 = st.columns(2)
        m1.metric("今月の支給額", f"{this_month_df['給料'].sum():,} 円")
        m2.metric("今月の労働時間", f"{this_month_df['労働(h)'].sum():.1f} h")
    else:
        st.write("履歴はまだありません。")
