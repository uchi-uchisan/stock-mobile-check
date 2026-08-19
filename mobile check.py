"""
軽量版 株価チェッカー
--------------------------------
Yahoo!ファイナンスから直近の株価を自動取得し、
「株式分析ダッシュボード」と同じ計算式でボラティリティ・レンジ幅（短期/中期/長期）を表示する。
DB（analysis_data.db）には一切依存しない、単体で動くスタンドアロン版。
GitHub + Streamlit Community Cloud での公開を想定している。
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="株価チェッカー", layout="centered")

# ----------------------------------------------------------------------
# デザイントークン（ダーク基調・クオンツ端末風。数値は等幅フォントで揃える）
# ----------------------------------------------------------------------
BG = "#0B0E14"
SURFACE = "#11151F"
BORDER = "#232838"
TEXT = "#E6E9EF"
TEXT_MUTED = "#7C8494"
ACCENT = "#6E8BFF"   # ブランド・見出し
POSITIVE = "#3DDC84"  # 収縮・改善（良いサイン）
NEGATIVE = "#FF6B6B"  # 拡大・悪化

st.markdown(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  html, body, [class*="css"] {{
      font-family: 'Zen Kaku Gothic New', sans-serif;
  }}
  .stApp {{
      background-color: {BG};
      color: {TEXT};
  }}
  .app-header {{
      margin-bottom: 0.2rem;
  }}
  .app-header .eyebrow {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      letter-spacing: 0.18em;
      color: {ACCENT};
      text-transform: uppercase;
  }}
  .app-header h1 {{
      font-weight: 700;
      font-size: 1.7rem;
      letter-spacing: 0.02em;
      margin: 0.15rem 0 0.3rem 0;
      color: {TEXT};
  }}
  .app-header p {{
      color: {TEXT_MUTED};
      font-size: 0.86rem;
      line-height: 1.6;
      margin: 0 0 1.1rem 0;
  }}
  hr.divider {{
      border: none;
      border-top: 1px solid {BORDER};
      margin: 1.3rem 0;
  }}
  /* 入力欄・セレクトボックス */
  div[data-testid="stTextInput"] input, div[data-baseweb="select"] > div {{
      background-color: {SURFACE} !important;
      border: 1px solid {BORDER} !important;
      color: {TEXT} !important;
      border-radius: 8px !important;
  }}
  label, .stSelectbox label, .stTextInput label {{
      color: {TEXT_MUTED} !important;
      font-size: 0.82rem !important;
  }}
  /* 送信ボタン */
  div[data-testid="stFormSubmitButton"] button {{
      background-color: {ACCENT} !important;
      color: #0B0E14 !important;
      border: none !important;
      border-radius: 8px !important;
      font-weight: 700 !important;
      letter-spacing: 0.05em;
  }}
  /* 見出し用ティッカー行 */
  .quote-row {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      padding: 0.9rem 0 0.5rem 0;
  }}
  .quote-row .ticker {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1rem;
      color: {TEXT_MUTED};
      letter-spacing: 0.05em;
  }}
  .quote-row .price {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.9rem;
      font-weight: 700;
      color: {TEXT};
  }}
  .quote-row .asof {{
      font-size: 0.72rem;
      color: {TEXT_MUTED};
  }}
  /* 統計カード */
  .stat-grid {{
      display: grid;
      grid-template-columns: repeat(var(--cols, 2), 1fr);
      gap: 0.6rem;
      margin: 0.6rem 0 1.1rem 0;
  }}
  .stat-card {{
      background-color: {SURFACE};
      border: 1px solid {BORDER};
      border-radius: 10px;
      padding: 0.85rem 0.9rem;
  }}
  .stat-card .label {{
      font-size: 0.72rem;
      color: {TEXT_MUTED};
      letter-spacing: 0.04em;
      margin-bottom: 0.3rem;
  }}
  .stat-card .value {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.35rem;
      font-weight: 700;
  }}
  .stat-card .sub {{
      font-size: 0.68rem;
      color: {TEXT_MUTED};
      margin-top: 0.2rem;
  }}
  /* レンジ幅の収縮バー（このツールの核＝収縮度を視覚化） */
  .range-item {{
      margin-bottom: 0.65rem;
  }}
  .range-item .range-top {{
      display: flex;
      justify-content: space-between;
      font-size: 0.78rem;
      color: {TEXT_MUTED};
      margin-bottom: 0.25rem;
  }}
  .range-item .range-top .val {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      color: {TEXT};
  }}
  .range-bar-bg {{
      background-color: {BORDER};
      border-radius: 4px;
      height: 6px;
      width: 100%;
      overflow: hidden;
  }}
  .range-bar-fill {{
      height: 100%;
      border-radius: 4px;
  }}
  .section-title {{
      font-size: 0.78rem;
      color: {TEXT_MUTED};
      letter-spacing: 0.05em;
      margin: 0.2rem 0 0.7rem 0;
  }}
</style>
""", unsafe_allow_html=True)


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

def normalize_ticker(raw: str) -> str:
    """入力補正：日本株の証券コード（数字4桁など）だけが入力された場合、
    「.T」を付け忘れているケースが多いため、自動で補完する。
    すでに「.」や「^」を含む場合（.T付き・米国指数など）はそのまま使う。"""
    t = raw.strip().upper()
    if t and t.replace(".", "").isdigit() and "." not in t:
        return f"{t}.T"
    return t


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
# 表示用ヘルパー
# ----------------------------------------------------------------------

def stat_card_html(label: str, value: str, sub: str = "", color: str = TEXT) -> str:
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (f'<div class="stat-card"><div class="label">{label}</div>'
            f'<div class="value" style="color:{color}">{value}</div>{sub_html}</div>')


def range_bar_html(label: str, days: int, pct, max_scale: float = 60.0) -> str:
    if pct is None:
        return (f'<div class="range-item"><div class="range-top">'
                f'<span>{label}（{days}日）</span><span class="val">―</span></div>'
                f'<div class="range-bar-bg"></div></div>')
    width = max(2, min(100, pct / max_scale * 100))
    color = POSITIVE if pct <= 25 else (ACCENT if pct <= 45 else NEGATIVE)
    return (f'<div class="range-item"><div class="range-top">'
            f'<span>{label}（{days}日）</span><span class="val">{pct}%</span></div>'
            f'<div class="range-bar-bg"><div class="range-bar-fill" '
            f'style="width:{width}%;background-color:{color}"></div></div></div>')


# ----------------------------------------------------------------------
# 画面
# ----------------------------------------------------------------------

st.markdown(f"""
<div class="app-header">
  <div class="eyebrow">Quant Utility</div>
  <h1>株価チェッカー</h1>
  <p>Yahoo!ファイナンスから直近データを自動取得し、ボラティリティとレンジ幅（短期/中期/長期）を
  確認できます。日本株は証券コードのみでOK（自動で「.T」を補完。例：3964）、
  米国株はティッカーそのまま（例：AAPL）で入力してください。</p>
</div>
""", unsafe_allow_html=True)

with st.form("ticker_form"):
    ticker_input = st.text_input("ティッカーまたは証券コード", placeholder="例：3964　または　AAPL")
    base_window = st.selectbox("基準期間（中期の日数。短期はその半分、長期は3倍）",
                               [10, 20, 30, 60], index=1,
                               help="「長期」は基準期間の3倍の日数が必要です（60日を選ぶと長期=180日分）。"
                                    "取得する日数は、これに応じて自動的に増やしています。")
    submitted = st.form_submit_button("取得", type="primary", use_container_width=True)

if submitted:
    if not ticker_input.strip():
        st.warning("ティッカーまたは証券コードを入力してください。")
    else:
        ticker = normalize_ticker(ticker_input)
        # 長期ウィンドウ（base_window×3）を計算するのに必要な日数＋αを、常に確保する。
        fetch_days = max(120, base_window * 3 + 40)
        with st.spinner(f"「{ticker}」を取得中...（直近{fetch_days}日分）"):
            try:
                df = fetch_prices(ticker, days=fetch_days)
            except Exception as e:
                st.error(f"取得に失敗しました：{e}")
                df = pd.DataFrame()

        if df.empty:
            st.warning(f"「{ticker}」のデータが取得できませんでした。\n\n"
                      "よくある原因：\n"
                      "・ティッカーが間違っている（例：存在しない銘柄コード）\n"
                      "・日本株なのに「.T」が付いていない（例：3964→3964.T。これは自動補完しています）\n"
                      "・上場廃止・非上場の銘柄\n\n"
                      "証券コードやティッカーをもう一度確認してみてください。")
        else:
            latest_close = df["close"].iloc[-1]
            latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d")

            st.markdown(f"""
            <div class="quote-row">
              <div><div class="ticker">{ticker}</div></div>
              <div style="text-align:right">
                <div class="price">{latest_close:,.2f}</div>
                <div class="asof">{latest_date} 時点</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            vola_df = compute_volatility_table(df, window=base_window)
            latest_vola = vola_df["ボラティリティ(%)"].dropna()
            latest_improve = vola_df["ボラティリティ改善率(%)"].dropna()

            vola_val = f"{latest_vola.iloc[-1]:.2f}%" if len(latest_vola) else "―"
            improve_val = latest_improve.iloc[-1] if len(latest_improve) else None
            improve_str = f"{improve_val:+.1f}%" if improve_val is not None else "―"
            improve_color = POSITIVE if (improve_val is not None and improve_val < 0) else (
                NEGATIVE if (improve_val is not None and improve_val > 0) else TEXT)

            st.markdown(
                '<div class="stat-grid" style="--cols:2">'
                + stat_card_html(f"ボラティリティ（{base_window}日平均）", vola_val)
                + stat_card_html("改善率（マイナス＝収縮）", improve_str, color=improve_color)
                + '</div>', unsafe_allow_html=True)

            range_result = compute_range_contraction_series(df, base_window=base_window)
            if range_result:
                latest_range, windows = range_result
                st.markdown('<div class="section-title">レンジ幅　(1−安値÷高値)×100・小さいほど収縮</div>',
                           unsafe_allow_html=True)
                bars = "".join(
                    range_bar_html(label, windows[label], latest_range[label])
                    for label in ["短期", "中期", "長期"]
                )
                st.markdown(bars, unsafe_allow_html=True)
            else:
                st.caption("レンジ幅の計算には、選んだ基準期間の3倍以上のデータが必要です"
                          "（データ不足のため計算できませんでした）。")

            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            with st.expander(f"株価データ（直近{fetch_days}日・新しい順）"):
                st.dataframe(df.sort_values("date", ascending=False), use_container_width=True, height=300)


