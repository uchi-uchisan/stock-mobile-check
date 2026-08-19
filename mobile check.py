"""
外出先用・軽量版 株価チェッカー
--------------------------------
Yahoo!ファイナンスから直近120日分の株価を自動取得し、
「株式分析ダッシュボード」と同じ計算式でボラティリティ・レンジ幅（短期/中期/長期）を表示する。
DB（analysis_data.db）には一切依存しない、単体で動くスタンドアロン版。
GitHub + Streamlit Community Cloud での公開を想定している。
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="株価チェッカー（外出先用）", page_icon="📱", layout="centered")


# ----------------------------------------------------------------------
# 計算ロジック（本体アプリのcore.pyと同じ式をそのまま使用）
# ----------------------------------------------------------------------

def compute_volatility_table(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """陽線・陰線別4ルート振動幅ロジック。本体アプリと同じ計算式。"""
    df = df.dropna(subset=["open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        return df
    df["前日終値"] = df["close"].shift(1)

    def swing(row):
        o, h, l, c, pc = row["open"], row["high"], row["low"], row["close"], row["前日終値"]
        if pd.isna(pc):
            return np.nan
        if c >= o:
            return abs(pc - o) + abs(o - l) + abs(l - h) + abs(h - c)
        else:
            return abs(pc - o) + abs(o - h) + abs(h - l) + abs(l - c)

    df["1日の振動幅"] = df.apply(swing, axis=1)
    roll_swing = df["1日の振動幅"].rolling(window).mean()
    roll_close = df["close"].rolling(window).mean()
    vola = roll_swing / roll_close * 100
    vola[df["1日の振動幅"].rolling(window).count() < window] = np.nan
    df["ボラティリティ(%)"] = vola.round(2)

    vola_ago = df["ボラティリティ(%)"].shift(window)
    df["ボラティリティ改善率(%)"] = ((df["ボラティリティ(%)"] - vola_ago) / vola_ago * 100).round(1)
    return df


def compute_range_contraction_series(price_df: pd.DataFrame, base_window: int = 20):
    """レンジ幅（(1−安値÷高値)×100）を短期(0.5×base)・中期(base)・長期(3×base)の
    3つの時間軸で計算する。本体アプリと同じ計算式。"""
    df = price_df.dropna(subset=["high", "low"]).sort_values("date").reset_index(drop=True)
    windows = {"短期": max(3, round(base_window * 0.5)), "中期": base_window, "長期": base_window * 3}
    if len(df) < windows["長期"] + 5:
        return None
    latest = {}
    for label, w in windows.items():
        roll_high = df["high"].rolling(w).max()
        roll_low = df["low"].rolling(w).min()
        series = ((1 - roll_low / roll_high) * 100).dropna()
        latest[label] = round(series.iloc[-1], 1) if len(series) >= 1 else None
    return latest, windows


# ----------------------------------------------------------------------
# データ取得
# ----------------------------------------------------------------------

@st.cache_data(ttl=900)  # 15分キャッシュ（同じ銘柄を連打しても再取得しないように）
def fetch_prices(ticker: str, days: int = 120) -> pd.DataFrame:
    data = yf.download(ticker, period=f"{days + 30}d", progress=False, auto_adjust=False)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.reset_index()
    data.columns = [str(c).lower() for c in data.columns]
    data = data.rename(columns={"date": "date"})
    data["date"] = pd.to_datetime(data["date"])
    return data[["date", "open", "high", "low", "close", "volume"]].tail(days).reset_index(drop=True)


# ----------------------------------------------------------------------
# 画面
# ----------------------------------------------------------------------

st.title("📱 株価チェッカー（外出先用）")
st.caption("Yahoo!ファイナンスから直近120日分を自動取得し、ボラティリティとレンジ幅（短期/中期/長期）"
           "だけをサッと確認できる軽量版です。日本株は証券コード＋「.T」（例：3964.T）、"
           "米国株はティッカーそのまま（例：AAPL）で入力してください。")

ticker = st.text_input("ティッカー", placeholder="例：3964.T　または　AAPL")
base_window = st.selectbox("基準期間（中期の日数。短期はその半分、長期は3倍）", [10, 20, 30], index=1)

if st.button("取得", type="primary", disabled=not ticker.strip()):
    with st.spinner("取得中..."):
        try:
            df = fetch_prices(ticker.strip().upper(), days=120)
        except Exception as e:
            st.error(f"取得に失敗しました：{e}")
            df = pd.DataFrame()

    if df.empty:
        st.warning("データが取得できませんでした。ティッカーが正しいか確認してください。")
    else:
        latest_close = df["close"].iloc[-1]
        latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")
        st.subheader(f"{ticker.upper()}　{latest_close:.2f}　（{latest_date}時点）")

        vola_df = compute_volatility_table(df, window=base_window)
        latest_vola = vola_df["ボラティリティ(%)"].dropna()
        latest_improve = vola_df["ボラティリティ改善率(%)"].dropna()

        c1, c2 = st.columns(2)
        c1.metric(f"ボラティリティ（{base_window}日平均）",
                  f"{latest_vola.iloc[-1]:.2f}%" if len(latest_vola) else "―")
        c2.metric("ボラティリティ改善率",
                  f"{latest_improve.iloc[-1]:+.1f}%" if len(latest_improve) else "―",
                  help="マイナス＝値動きが縮小（保ち合い形成の兆し）")

        range_result = compute_range_contraction_series(df, base_window=base_window)
        if range_result:
            latest_range, windows = range_result
            st.write("**レンジ幅（(1−安値÷高値)×100。小さいほど収縮）**")
            r1, r2, r3 = st.columns(3)
            r1.metric(f"短期（{windows['短期']}日）",
                      f"{latest_range['短期']}%" if latest_range["短期"] is not None else "―")
            r2.metric(f"中期（{windows['中期']}日）",
                      f"{latest_range['中期']}%" if latest_range["中期"] is not None else "―")
            r3.metric(f"長期（{windows['長期']}日）",
                      f"{latest_range['長期']}%" if latest_range["長期"] is not None else "―")
        else:
            st.caption("レンジ幅の計算には、選んだ基準期間の3倍以上のデータが必要です"
                      "（データ不足のため計算できませんでした）。")

        with st.expander("株価データ（直近120日・新しい順）"):
            st.dataframe(df.sort_values("date", ascending=False), use_container_width=True, height=300)
