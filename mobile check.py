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
AMBER = "#F5A623"    # 惜しい・もう一歩

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
  /* 入力欄・セレクトボックス・テキストエリア（複数行入力） */
  div[data-testid="stTextInput"] input,
  div[data-testid="stTextArea"] textarea,
  div[data-baseweb="select"] > div {{
      background-color: {SURFACE} !important;
      border: 1px solid {BORDER} !important;
      color: {TEXT} !important;
      border-radius: 8px !important;
      -webkit-text-fill-color: {TEXT} !important;
  }}
  div[data-testid="stTextArea"] textarea::placeholder,
  div[data-testid="stTextInput"] input::placeholder {{
      color: {TEXT_MUTED} !important;
      opacity: 1 !important;
  }}
  label, .stSelectbox label, .stTextInput label, .stTextArea label {{
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
# スクリーニング用ロジック（トレンドテンプレート・オーバーヘッドサプライ・VCP簡易判定）
# ----------------------------------------------------------------------

def zigzag_pivots(prices: list, threshold_pct: float = 8.0) -> list:
    """終値の時系列から、threshold_pct(%)以上の逆行があった点だけを「山」「谷」として抽出する
    簡易ZigZag。戻り値は [(インデックス, 価格, "peak"|"trough"), ...]（時系列順）。
    本体アプリのRCI/VCP判定で使っているものと同じ考え方。"""
    if len(prices) < 3:
        return []
    pivots = []
    last_idx, last_price = 0, prices[0]
    direction = None
    for i in range(1, len(prices)):
        p = prices[i]
        if pd.isna(p) or pd.isna(last_price) or last_price == 0:
            continue
        change_pct = (p - last_price) / last_price * 100
        if direction is None:
            if abs(change_pct) >= threshold_pct:
                direction = "up" if change_pct > 0 else "down"
                last_idx, last_price = i, p
        elif direction == "up":
            if p > last_price:
                last_idx, last_price = i, p
            elif (p - last_price) / last_price * 100 <= -threshold_pct:
                pivots.append((last_idx, last_price, "peak"))
                direction, last_idx, last_price = "down", i, p
        else:
            if p < last_price:
                last_idx, last_price = i, p
            elif (p - last_price) / last_price * 100 >= threshold_pct:
                pivots.append((last_idx, last_price, "trough"))
                direction, last_idx, last_price = "up", i, p
    if direction is not None:
        pivots.append((last_idx, last_price, "peak" if direction == "up" else "trough"))
    return pivots


def evaluate_chart_quality(df: pd.DataFrame) -> dict:
    """「美しいチャート」判定（厳しめ）。あくまで機械的な近似判定であり、
    ミネルヴィニの著書にあるような、人間の目による最終判断の代わりにはならない。
    以下をすべて判定する：
    1. トレンドテンプレート簡易版：終値が50日線・200日線の両方の上にあるか
    2. オーバーヘッドサプライ：直近で急落（短期間に20%以上の下落）があり、
       その下落前の高値をまだ回復できていない場合を「未解消の売り圧力あり」とする
    3. VCP簡易判定：直近の押し目（山→谷の下落率）を2回以上検出し、
       その下落率が徐々に小さくなっている（収縮している）ケースを「収縮あり」とする
    戻り値のkeys: above_50ma, above_200ma, has_overhead, overhead_gap_pct, has_vcp,
                  contractions, is_beautiful, is_close_to_beautiful, notes"""
    d = df.dropna(subset=["close", "high", "low"]).sort_values("date").reset_index(drop=True)
    result = {"above_50ma": None, "above_200ma": None, "has_overhead": None, "overhead_gap_pct": None,
              "has_vcp": None, "contractions": [], "is_beautiful": False,
              "is_close_to_beautiful": False, "notes": []}
    if len(d) < 210:
        result["notes"].append("データ不足（200日線の判定には210日以上必要）")
        return result

    close = d["close"]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    last_close = close.iloc[-1]
    result["above_50ma"] = bool(last_close > sma50)
    result["above_200ma"] = bool(last_close > sma200)

    # --- オーバーヘッドサプライ判定 ---
    # 直近約1年（250営業日）の中で、15営業日以内に20%以上下落した箇所（急落）を探す。
    # 急落の起点（下落前の高値）を、現在値がまだ回復できていなければ「未解消」とする。
    lookback = d.tail(250).reset_index(drop=True)
    worst_drop_pct, worst_peak = 0, None
    win = 15
    for i in range(len(lookback) - win):
        seg = lookback["close"].iloc[i:i + win + 1]
        peak = seg.iloc[0]
        trough = seg.min()
        if peak <= 0:
            continue
        drop_pct = (peak - trough) / peak * 100
        if drop_pct > worst_drop_pct:
            worst_drop_pct = drop_pct
            worst_peak = peak
    if worst_drop_pct >= 20 and worst_peak:
        gap_pct = (worst_peak - last_close) / worst_peak * 100
        result["has_overhead"] = bool(gap_pct > 0)
        result["overhead_gap_pct"] = round(gap_pct, 1)
        if gap_pct > 0:
            result["notes"].append(f"急落前高値まであと{gap_pct:.1f}%（未回復＝売り圧力が残っている可能性）")
    else:
        result["has_overhead"] = False
        result["overhead_gap_pct"] = 0.0

    # --- VCP簡易判定 ---
    # 直近約6ヶ月（130営業日）のピボットから、山→谷の下落率を新しい順に並べ、
    # 2回以上連続で下落率が縮小していれば「収縮あり」とする。
    recent = d.tail(130).reset_index(drop=True)
    pivots = zigzag_pivots(recent["close"].tolist(), threshold_pct=8.0)
    pullbacks = []
    for j in range(1, len(pivots)):
        prev_idx, prev_price, prev_kind = pivots[j - 1]
        idx, price, kind = pivots[j]
        if prev_kind == "peak" and kind == "trough" and prev_price > 0:
            pullbacks.append(round((prev_price - price) / prev_price * 100, 1))
    if len(pullbacks) >= 2:
        last_pullbacks = pullbacks[-3:] if len(pullbacks) >= 3 else pullbacks
        is_contracting = all(last_pullbacks[k] > last_pullbacks[k + 1] for k in range(len(last_pullbacks) - 1))
        result["has_vcp"] = bool(is_contracting)
        result["contractions"] = last_pullbacks
    else:
        result["has_vcp"] = False
        result["contractions"] = pullbacks

    result["is_beautiful"] = bool(result["above_50ma"] and result["above_200ma"]
                                  and not result["has_overhead"] and result["has_vcp"])
    # 「あと少しで綺麗になる」＝トレンドは合格・VCPも収縮傾向はあるが、
    # オーバーヘッドの解消まで10%以内、というケースを拾う（新高値更新で解消しうる候補）
    result["is_close_to_beautiful"] = bool(
        not result["is_beautiful"] and result["above_50ma"] and result["above_200ma"]
        and result["has_overhead"] and result["overhead_gap_pct"] is not None
        and 0 < result["overhead_gap_pct"] <= 10)
    return result


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


def render_mini_chart(df: pd.DataFrame, days: int = 260):
    """終値・50日線・200日線を重ねた小さな折れ線チャートを表示する。
    「なぜ合格/不合格なのか」をチャートの形そのもので確認できるようにするために使う。"""
    d = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True).copy()
    d["50日線"] = d["close"].rolling(50).mean()
    d["200日線"] = d["close"].rolling(200).mean()
    chart_df = d.tail(days).set_index("date")[["close", "50日線", "200日線"]]
    chart_df = chart_df.rename(columns={"close": "終値"})
    st.line_chart(chart_df, height=200, color=[TEXT, ACCENT, NEGATIVE])


RANK_INFO = {
    # (色, 説明文)。厳しさの序列（厳しい→緩い）＝オーバーヘッド解消 > VCP収縮 > 50日/200日線。
    "S": (POSITIVE, "トレンド◎・オーバーヘッドなし・VCP収縮あり（3条件すべて達成）"),
    "A": (ACCENT, "トレンド◎・オーバーヘッドなし・VCP収縮はまだ（一番厳しい条件はクリア済み）"),
    "B": (AMBER, "トレンド◎・VCP収縮あり・オーバーヘッド解消まであと10%以内"),
    "C": (TEXT_MUTED, "トレンドは良いが、オーバーヘッド・VCPともに条件を満たさない"),
    "F": (NEGATIVE, "トレンドそのものが崩れている（50日線または200日線を割れ）"),
}


def rank_chart_quality(ev: dict) -> str:
    """厳しさをS/A/B/C/Fの5段階で返す。
    S：3条件すべて達成（一番厳しい）
    A：オーバーヘッドは解消済みだがVCP収縮がまだ（2番目に厳しい条件までクリア）
    B：VCP収縮はあるが、オーバーヘッド解消まであと10%以内（惜しい）
    C：トレンドは良いが、オーバーヘッド・VCPともに未達成
    F：トレンドそのものが崩れている（一番緩い＝そもそも土俵に乗っていない）"""
    trend_ok = bool(ev["above_50ma"] and ev["above_200ma"])
    if not trend_ok:
        return "F"
    no_overhead = not ev["has_overhead"]
    has_vcp = bool(ev["has_vcp"])
    gap = ev.get("overhead_gap_pct")
    if no_overhead and has_vcp:
        return "S"
    if no_overhead and not has_vcp:
        return "A"
    if ev["has_overhead"] and has_vcp and gap is not None and gap <= 10:
        return "B"
    return "C"


def reasons_text(ev: dict) -> str:
    """判定結果（evaluate_chart_qualityの戻り値）から、人が読める理由の一覧を組み立てる。"""
    lines = []
    lines.append(("✅" if ev["above_50ma"] else "❌") + " 50日線："
                 + ("上" if ev["above_50ma"] else "下"))
    lines.append(("✅" if ev["above_200ma"] else "❌") + " 200日線："
                 + ("上" if ev["above_200ma"] else "下"))
    if ev["has_overhead"]:
        lines.append(f"❌ オーバーヘッドサプライ：あり（急落前の高値まであと{ev['overhead_gap_pct']}%・未回復）")
    else:
        lines.append("✅ オーバーヘッドサプライ：なし")
    if ev["has_vcp"]:
        contractions_str = "→".join(f"{c}%" for c in ev["contractions"])
        lines.append(f"✅ VCP収縮：あり（押し目の下落率が縮小　{contractions_str}）")
    elif ev["contractions"]:
        contractions_str = "→".join(f"{c}%" for c in ev["contractions"])
        lines.append(f"❌ VCP収縮：なし（押し目はあるが縮小していない　{contractions_str}）")
    else:
        lines.append("❌ VCP収縮：判定できる押し目が見つからず")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# 画面
# ----------------------------------------------------------------------

st.markdown(f"""
<div class="app-header">
  <div class="eyebrow">Quant Utility</div>
  <h1>株価チェッカー</h1>
  <p>Yahoo!ファイナンスから直近データを自動取得します。日本株は証券コードのみでOK
  （自動で「.T」を補完。例：3964）、米国株はティッカーそのまま（例：AAPL）で入力してください。</p>
</div>
""", unsafe_allow_html=True)

tab_single, tab_screen = st.tabs(["個別チェック", "米国株スクリーニング"])

with tab_single:
    with st.form("ticker_form"):
        ticker_input = st.text_input("ティッカーまたは証券コード", placeholder="例：3964　または　AAPL")
        submitted = st.form_submit_button("取得", type="primary", use_container_width=True)

    # 取得ボタンを押したときだけYahoo!ファイナンスへ実際にアクセスする。
    # 一度取得したデータはセッション内に保持し、下の「基準期間」スライダーを動かすだけで
    # 再取得せずにその場で再計算できるようにする（Yahoo!への負荷軽減＆操作の即時性のため）。
    FETCH_DAYS = 400  # スライダーで最大60日を選んでも(長期=180日)十分足りるよう、常に多めに確保しておく

    if submitted:
        if not ticker_input.strip():
            st.warning("ティッカーまたは証券コードを入力してください。")
            st.session_state.pop("price_df", None)
        else:
            ticker = normalize_ticker(ticker_input)
            with st.spinner(f"「{ticker}」を取得中..."):
                try:
                    df = fetch_prices(ticker, days=FETCH_DAYS)
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
                st.session_state.pop("price_df", None)
            else:
                st.session_state["price_df"] = df
                st.session_state["price_ticker"] = ticker

    # ここから先は、セッションに取得済みデータがあれば毎回（スライダーを動かした瞬間も含めて）
    # 再計算・再描画される。Yahoo!への再アクセスは発生しない。
    if "price_df" in st.session_state:
        df = st.session_state["price_df"]
        ticker = st.session_state["price_ticker"]

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

        base_window = st.slider("基準期間（ボラティリティ計算日数／レンジ幅の中期日数）",
                                min_value=5, max_value=90, value=20, step=1,
                                help="ここを動かすと、Yahoo!に再アクセスせず、取得済みのデータの中で"
                                     "その場で再計算します。レンジ幅の「短期」はこの半分、"
                                     "「長期」は3倍の日数を使います。")

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

        # ボラティリティの推移（「どのくらい変化しているか」を数字だけでなく折れ線でも見えるように）
        trend = vola_df.dropna(subset=["ボラティリティ(%)"]).tail(90)
        if len(trend) >= 2:
            st.markdown('<div class="section-title">ボラティリティの推移（直近分）</div>', unsafe_allow_html=True)
            st.line_chart(trend.set_index("date")["ボラティリティ(%)"], height=140)

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
                      "（データ不足のため計算できませんでした。基準期間を短くしてみてください）。")

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        with st.expander(f"株価データ（取得済み{len(df)}日分・新しい順）"):
            st.dataframe(df.sort_values("date", ascending=False), use_container_width=True, height=300)

with tab_screen:
    st.markdown('<div class="section-title">米国株スクリーニング（厳しさランク付き）</div>', unsafe_allow_html=True)
    st.caption("Finvizなどで事前に絞り込んだ候補ティッカーを貼り付けると、3つの条件（厳しい順に "
              "①オーバーヘッドサプライの解消 → ②VCP収縮 → ③50日線・200日線の上）の達成度合いで "
              "S/A/B/C/Fの5段階ランクを付けます。あくまで機械的な近似判定なので、"
              "最終判断はご自身の目で行ってください。")
    with st.expander("ランクの意味"):
        for rank, (color, desc) in RANK_INFO.items():
            st.markdown(f'<span style="color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace">'
                       f'{rank}</span>　{desc}', unsafe_allow_html=True)

    tickers_raw = st.text_area("ティッカーを貼り付け（改行・カンマ・スペース区切り、いくつでも可）",
                               height=100, placeholder="例：\nAAPL\nMSFT, NVDA\nAMZN")
    run_screen = st.button("スクリーニング実行", type="primary", use_container_width=True)

    if run_screen:
        raw_list = tickers_raw.replace(",", "\n").replace(" ", "\n").splitlines()
        tickers = sorted(set(t.strip().upper() for t in raw_list if t.strip()))
        if not tickers:
            st.warning("ティッカーを1つ以上入力してください。")
        else:
            ranked = {"S": [], "A": [], "B": [], "C": [], "F": []}
            error_list = []
            progress = st.progress(0.0, text="判定中...")
            for i, tk in enumerate(tickers):
                try:
                    d = fetch_prices(tk, days=400)
                    if d.empty:
                        error_list.append(tk)
                    else:
                        ev = evaluate_chart_quality(d)
                        rank = rank_chart_quality(ev)
                        ranked[rank].append((tk, ev, d))
                except Exception:
                    error_list.append(tk)
                progress.progress((i + 1) / len(tickers), text=f"判定中... {i+1}/{len(tickers)}")
            progress.empty()
            st.session_state["screen_results"] = (ranked, error_list)

    if "screen_results" in st.session_state:
        ranked, error_list = st.session_state["screen_results"]

        for rank in ["S", "A", "B"]:
            color, desc = RANK_INFO[rank]
            items = ranked[rank]
            st.markdown(f'<div class="section-title">'
                       f'<span style="color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace">'
                       f'{rank}ランク</span>　{desc}（{len(items)}銘柄）</div>', unsafe_allow_html=True)
            if items:
                for tk, ev, d in items:
                    contractions_str = "→".join(f"{c}%" for c in ev["contractions"]) if ev["contractions"] else "―"
                    sub = f"収縮：{contractions_str}"
                    if ev["has_overhead"]:
                        sub += f"　｜オーバーヘッドまであと{ev['overhead_gap_pct']}%"
                    st.markdown(stat_card_html(tk, f"{rank}ランク", sub=sub, color=color),
                               unsafe_allow_html=True)
                    render_mini_chart(d)
                    st.caption(reasons_text(ev).replace("\n", "　|　"))
                    st.markdown('<hr class="divider">', unsafe_allow_html=True)
            else:
                st.caption("該当銘柄はありませんでした。")

        c_items, f_items = ranked["C"], ranked["F"]
        with st.expander(f"C・Fランク・データ取得失敗（{len(c_items) + len(f_items) + len(error_list)}銘柄）"):
            for rank in ["C", "F"]:
                color, desc = RANK_INFO[rank]
                for tk, ev, d in ranked[rank]:
                    st.markdown(f'<span style="color:{color};font-weight:700;'
                               f'font-family:\'JetBrains Mono\',monospace">{rank}</span> **{tk}**',
                               unsafe_allow_html=True)
                    st.caption(reasons_text(ev).replace("\n", "　|　"))
                    if st.checkbox(f"{tk} のチャートを見る", key=f"cf_chart_{tk}"):
                        render_mini_chart(d)
                    st.markdown('<hr class="divider">', unsafe_allow_html=True)
            for tk in error_list:
                st.write(f"**{tk}**：データ取得失敗")


