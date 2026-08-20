"""
軽量版 株価チェッカー
--------------------------------
Yahoo!ファイナンスから直近の株価を自動取得し、
「株式分析ダッシュボード」と同じ計算式でボラティリティ・レンジ幅（短期/中期/長期）を表示する。
DB（analysis_data.db）には一切依存しない、単体で動くスタンドアロン版。
GitHub + Streamlit Community Cloud での公開を想定している。
"""

import re

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
  /* 送信ボタン・通常ボタン（st.form_submit_buttonとst.button、両方に同じ配色を適用） */
  div[data-testid="stFormSubmitButton"] button, div[data-testid="stButton"] button {{
      background-color: {SURFACE} !important;
      color: {TEXT} !important;
      border: 1px solid {BORDER} !important;
      border-radius: 8px !important;
      font-weight: 700 !important;
      letter-spacing: 0.05em;
  }}
  div[data-testid="stFormSubmitButton"] button[kind="primary"],
  div[data-testid="stButton"] button[kind="primary"] {{
      background-color: {ACCENT} !important;
      color: #0B0E14 !important;
      border: none !important;
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
  /* エラー・例外表示（st.error、実行時エラー画面など）が、ダーク背景と重なって
     読みにくくなっていたため、はっきりした配色に上書きする */
  div[data-testid="stException"], div[data-testid="stAlert"] {{
      background-color: #2A1418 !important;
      border: 1px solid {NEGATIVE} !important;
      border-radius: 8px !important;
  }}
  div[data-testid="stException"] *, div[data-testid="stAlert"] * {{
      color: #FFD9D9 !important;
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
    result = {"above_50ma": None, "above_200ma": None, "sma200_rising": None,
              "has_overhead": None, "overhead_gap_pct": None,
              "has_vcp": None, "contractions": [], "volume_contracting": None, "volume_dryup_ratio": None,
              "is_beautiful": False, "is_close_to_beautiful": False, "notes": []}
    if len(d) < 231:
        result["notes"].append("データ不足（200日線が1ヶ月前上向きだったかの判定には231日以上必要）")
        return result

    close = d["close"]
    sma200_series = close.rolling(200).mean()
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = sma200_series.iloc[-1]
    sma200_1mo_ago = sma200_series.iloc[-22]  # 約1ヶ月（21営業日）前の200日線
    last_close = close.iloc[-1]
    result["above_50ma"] = bool(last_close > sma50)
    result["above_200ma"] = bool(last_close > sma200)
    result["sma200_rising"] = bool(sma200 > sma200_1mo_ago) if pd.notna(sma200_1mo_ago) else None

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

    # --- VCP簡易判定（値幅の収縮＋出来高の収縮の両方を見る） ---
    # 直近約6ヶ月（130営業日）のピボットから、山→谷の下落率を新しい順に並べ、
    # 2回以上連続で下落率が縮小していれば「値幅の収縮あり」とする。
    # 本来のVCPは、値幅だけでなく「押し目のたびに出来高も減っている」ことが重要な条件なので、
    # 各押し目区間の平均出来高も合わせて確認する。
    recent = d.tail(130).reset_index(drop=True)
    pivots = zigzag_pivots(recent["close"].tolist(), threshold_pct=8.0)
    pullbacks = []
    pullback_volumes = []
    has_volume = "volume" in recent.columns and recent["volume"].notna().any()
    for j in range(1, len(pivots)):
        prev_idx, prev_price, prev_kind = pivots[j - 1]
        idx, price, kind = pivots[j]
        if prev_kind == "peak" and kind == "trough" and prev_price > 0:
            pullbacks.append(round((prev_price - price) / prev_price * 100, 1))
            if has_volume:
                seg_vol = recent["volume"].iloc[prev_idx:idx + 1]
                pullback_volumes.append(seg_vol.mean() if len(seg_vol) else np.nan)
    if len(pullbacks) >= 2:
        last_pullbacks = pullbacks[-3:] if len(pullbacks) >= 3 else pullbacks
        is_contracting = all(last_pullbacks[k] > last_pullbacks[k + 1] for k in range(len(last_pullbacks) - 1))
        result["has_vcp"] = bool(is_contracting)
        result["contractions"] = last_pullbacks
        # 出来高の収縮：値幅と同じ本数だけ末尾を揃えて比較し、押し目のたびに減っていればTrue
        if has_volume and len(pullback_volumes) >= 2:
            last_vols = pullback_volumes[-3:] if len(pullback_volumes) >= 3 else pullback_volumes
            valid = [v for v in last_vols if pd.notna(v)]
            if len(valid) == len(last_vols) and len(valid) >= 2:
                result["volume_contracting"] = bool(
                    all(last_vols[k] > last_vols[k + 1] for k in range(len(last_vols) - 1)))
            else:
                result["volume_contracting"] = None
        else:
            result["volume_contracting"] = None
    else:
        result["has_vcp"] = False
        result["contractions"] = pullbacks
        result["volume_contracting"] = None

    # 直近の出来高が、平常時（50日平均）と比べて枯れているかどうか（基盤形成中の目安）
    if has_volume and len(recent) >= 50:
        vol_ma50 = recent["volume"].rolling(50).mean().iloc[-1]
        vol_recent10 = recent["volume"].tail(10).mean()
        result["volume_dryup_ratio"] = round(vol_recent10 / vol_ma50, 2) if vol_ma50 else None
    else:
        result["volume_dryup_ratio"] = None

    result["is_beautiful"] = bool(result["above_50ma"] and result["above_200ma"] and result["sma200_rising"]
                                  and not result["has_overhead"] and result["has_vcp"])
    # 「あと少しで綺麗になる」＝トレンドは合格・VCPも収縮傾向はあるが、
    # オーバーヘッドの解消まで10%以内、というケースを拾う（新高値更新で解消しうる候補）
    result["is_close_to_beautiful"] = bool(
        not result["is_beautiful"] and result["above_50ma"] and result["above_200ma"] and result["sma200_rising"]
        and result["has_overhead"] and result["overhead_gap_pct"] is not None
        and 0 < result["overhead_gap_pct"] <= 10)
    return result


# ----------------------------------------------------------------------
# データ取得
# ----------------------------------------------------------------------

def normalize_ticker(raw: str) -> str:
    """入力補正：日本株の証券コードだけが入力された場合、「.T」を付け忘れているケースが多いため、
    自動で補完する。すでに「.」「^」「=」を含む場合（.T付き・米国指数・先物など）はそのまま使う。
    対応パターン：
    - 従来の4桁数字コード（例：3964）
    - 東証が2024年以降、新規上場銘柄に割り当て始めた「数字3桁＋英字1桁」の新形式コード
      （例：212A＝フィットイージー）。数字を含まない純アルファベットは米国株ティッカーと
      区別がつかないため対象外（AAPLなどを誤って.T化しないように）。"""
    t = raw.strip().upper()
    if not t or "." in t or "^" in t or "=" in t:
        return t
    if re.fullmatch(r"\d{3,4}", t):
        return f"{t}.T"
    if re.fullmatch(r"\d{3}[A-Z]", t):
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


@st.cache_data(ttl=3600 * 12)  # 会社名は滅多に変わらないので長めにキャッシュ
def fetch_company_name(ticker: str) -> str:
    """Yahoo!ファイナンスから会社名を取得する。取得できない場合は空文字を返す
    （ティッカー表示だけになるが、処理は止めない）。"""
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ""
    except Exception:
        return ""


def is_jp_ticker(ticker: str) -> bool:
    """「.T」で終わる日本株ティッカーかどうかを判定する。"""
    return ticker.strip().upper().endswith(".T")


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
    「なぜ合格/不合格なのか」をチャートの形そのもので確認できるようにするために使う。
    st.line_chartは白背景で描画されるため、アプリ全体のダーク配色（薄いグレー）をそのまま
    「終値」の線色に使うと、白背景にほぼ溶け込んで見えなくなってしまう。そのため、
    チャート内だけは白背景でも視認できる、はっきりした濃い色を別途使う。"""
    d = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True).copy()
    d["50日線"] = d["close"].rolling(50).mean()
    d["200日線"] = d["close"].rolling(200).mean()
    chart_df = d.tail(days).set_index("date")[["close", "50日線", "200日線"]]
    chart_df = chart_df.rename(columns={"close": "終値"})
    CHART_LINE_DARK = "#2B2F3A"  # 白背景のチャート内でも視認できる、はっきりした濃色（TEXTとは別）
    st.line_chart(chart_df, height=200, color=[CHART_LINE_DARK, ACCENT, NEGATIVE])


RANK_INFO = {
    # (色, 説明文)。厳しさの序列（厳しい→緩い）＝オーバーヘッド解消 > VCP収縮 > 50日/200日線。
    "S": (POSITIVE, "トレンド◎・オーバーヘッドなし・VCP収縮あり（3条件すべて達成）"),
    "A": (ACCENT, "トレンド◎・オーバーヘッドなし・VCP収縮はまだ（一番厳しい条件はクリア済み）"),
    "B": (AMBER, "トレンド◎・VCP収縮あり・オーバーヘッド解消まであと10%以内"),
    "C": (TEXT_MUTED, "トレンドは良いが、オーバーヘッド・VCPともに条件を満たさない"),
    "F": (NEGATIVE, "トレンドそのものが崩れている（50日線・200日線割れ、または200日線が下向き）"),
}


def evaluate_relative_strength(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame, lookback: int = 60,
                               benchmark_name: str = "S&P500") -> dict:
    """対ベンチマークの相対力（RS）を判定する。直近lookback営業日の騰落率を、
    銘柄とベンチマークで比較する。指数が下げている局面で銘柄が踏みとどまっている・
    上がっている場合は、その旨を説明文として生成する（リーダー株の典型的な値動き）。
    benchmark_nameは説明文に使う表示名（例："S&P500"／"TOPIX"）。
    戻り値：stock_return_pct, bench_return_pct, rs_status(強い/普通/弱い), explanation"""
    s = stock_df.dropna(subset=["close"]).sort_values("date").tail(lookback + 1)
    b = benchmark_df.dropna(subset=["close"]).sort_values("date").tail(lookback + 1)
    if len(s) < 2 or len(b) < 2:
        return {"stock_return_pct": None, "bench_return_pct": None, "rs_status": "判定不可", "explanation": ""}

    stock_return = (s["close"].iloc[-1] / s["close"].iloc[0] - 1) * 100
    bench_return = (b["close"].iloc[-1] / b["close"].iloc[0] - 1) * 100
    diff = stock_return - bench_return

    if diff >= 5:
        rs_status = "強い"
    elif diff <= -5:
        rs_status = "弱い"
    else:
        rs_status = "普通"

    explanation = ""
    if bench_return < 0:
        if stock_return > 0:
            explanation = (f"直近{lookback}営業日で{benchmark_name}が{bench_return:.1f}%下落する中、"
                          f"この銘柄は+{stock_return:.1f}%と上昇しています。指数の逆風下で買われている、"
                          "相対的にかなり強い値動きです。")
        elif stock_return > bench_return:
            explanation = (f"直近{lookback}営業日で{benchmark_name}が{bench_return:.1f}%下落する中、"
                          f"この銘柄は{stock_return:.1f}%と下げ幅を抑えています。指数ほど売られておらず、"
                          "底堅い動きです。")
        else:
            explanation = (f"直近{lookback}営業日で{benchmark_name}が{bench_return:.1f}%下落する中、"
                          f"この銘柄は{stock_return:.1f}%とそれ以上に下げています。指数より弱い動きです。")
    else:
        if stock_return > bench_return:
            explanation = (f"直近{lookback}営業日で{benchmark_name}が+{bench_return:.1f}%の中、"
                          f"この銘柄は+{stock_return:.1f}%とそれを上回っています。")
        else:
            explanation = (f"直近{lookback}営業日で{benchmark_name}が+{bench_return:.1f}%の中、"
                          f"この銘柄は{stock_return:+.1f}%と指数ほど伸びていません。")

    return {"stock_return_pct": round(stock_return, 1), "bench_return_pct": round(bench_return, 1),
            "rs_status": rs_status, "explanation": explanation, "benchmark_name": benchmark_name}


def rank_chart_quality(ev: dict) -> str:
    """厳しさをS/A/B/C/Fの5段階で返す。
    S：3条件すべて達成（一番厳しい）
    A：オーバーヘッドは解消済みだがVCP収縮がまだ（2番目に厳しい条件までクリア）
    B：VCP収縮はあるが、オーバーヘッド解消まであと10%以内（惜しい）
    C：トレンドは良いが、オーバーヘッド・VCPともに未達成
    F：トレンドそのものが崩れている（一番緩い＝そもそも土俵に乗っていない）"""
    trend_ok = bool(ev["above_50ma"] and ev["above_200ma"] and ev.get("sma200_rising"))
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
    """判定結果（evaluate_chart_qualityの戻り値）から、人が読める理由の一覧を組み立てる。
    値がNone（データ不足などで判定そのものができない）の場合は、False（未達）と混同しないよう
    「❓判定不可」として表示する。"""
    def mark(v):
        if v is None:
            return "❓"
        return "✅" if v else "❌"

    lines = []
    if ev.get("above_50ma") is None:
        lines.append("❓ データ不足のため、50日線・200日線などの判定ができません"
                     "（この銘柄は上場・設定からまだ日が浅い可能性があります）。")
        return "\n".join(lines)
    lines.append(mark(ev["above_50ma"]) + " 50日線：" + ("上" if ev["above_50ma"] else "下"))
    lines.append(mark(ev["above_200ma"]) + " 200日線：" + ("上" if ev["above_200ma"] else "下"))
    if ev.get("sma200_rising") is not None:
        lines.append(mark(ev["sma200_rising"]) + " 200日線の向き："
                     + ("上向き（1ヶ月前比）" if ev["sma200_rising"] else "下向き・横ばい（1ヶ月前比）"))
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
    if ev.get("volume_contracting") is True:
        lines.append("✅ 出来高：押し目のたびに減少（枯れてきている＝良いサイン）")
    elif ev.get("volume_contracting") is False:
        lines.append("❌ 出来高：押し目でも減っていない")
    if ev.get("volume_dryup_ratio") is not None:
        ratio = ev["volume_dryup_ratio"]
        lines.append(f"　直近10日間の出来高は50日平均の{ratio:.2f}倍"
                     + ("（枯れている）" if ratio < 0.8 else ("（多い）" if ratio > 1.3 else "")))
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

tab_single, tab_screen = "個別チェック", "スクリーニング"
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = tab_single
if "pending_tab" in st.session_state:
    # ラジオボタン（key="active_tab"）がこの下で描画される前に反映させる。
    # ウィジェットが一度描画された後に同じキーを直接書き換えるとエラーになるため、
    # ボタン側では「pending_tab」という別のキーに希望のタブ名を入れておき、
    # 次の再描画の最初（ウィジェットが描画されるより前）にここで正式に反映する。
    st.session_state["active_tab"] = st.session_state.pop("pending_tab")
active_tab = st.radio("表示切り替え", [tab_single, tab_screen], key="active_tab",
                      horizontal=True, label_visibility="collapsed")

if active_tab == tab_single:
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

        if st.button(f"「{ticker}」をスクリーニングのリストに追加", key="add_to_screening_btn"):
            existing = st.session_state.get("screening_tickers_input", "") or ""
            names = [n.strip() for n in existing.replace(",", "\n").splitlines() if n.strip()]
            if ticker not in names:
                names.append(ticker)
            st.session_state["screening_tickers_input"] = "\n".join(names)
            st.session_state["pending_tab"] = tab_screen
            st.toast(f"「{ticker}」をスクリーニングのリストに追加しました。")
            st.rerun()

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
            with st.expander("日付ごとの数値を見る（過去の特定の日を確認したい場合）"):
                st.caption("グラフだと正確な数値が読み取りにくいため、表でも確認できるようにしています。"
                          "「基準期間」を変えると、この表の計算日数も連動して変わります。")
                display_tbl = trend[["date", "ボラティリティ(%)", "ボラティリティ改善率(%)"]].copy()
                display_tbl["date"] = display_tbl["date"].dt.strftime("%Y-%m-%d")
                st.dataframe(display_tbl.sort_values("date", ascending=False),
                           use_container_width=True, height=250, hide_index=True)

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

elif active_tab == tab_screen:
    st.markdown('<div class="section-title">スクリーニング（厳しさランク付き）</div>', unsafe_allow_html=True)
    st.caption("Finvizなどで事前に絞り込んだ候補ティッカーを貼り付けると、3つの条件（厳しい順に "
              "①オーバーヘッドサプライの解消 → ②VCP収縮 → ③50日線・200日線の上）の達成度合いで "
              "S/A/B/C/Fの5段階ランクを付けます。日本株・米国株どちらも使えます"
              "（日本株は証券コードのみでOK。自動で「.T」を補完し、ベンチマークもTOPIXに切り替えます）。"
              "あくまで機械的な近似判定なので、最終判断はご自身の目で行ってください。")
    with st.expander("ランクの意味"):
        for rank, (color, desc) in RANK_INFO.items():
            st.markdown(f'<span style="color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace">'
                       f'{rank}</span>　{desc}', unsafe_allow_html=True)

    tickers_raw = st.text_area("ティッカー・証券コードを貼り付け（改行・カンマ・スペース区切り、いくつでも可）",
                               height=100, placeholder="例：\nAAPL\nMSFT, NVDA\n3964\n7203",
                               key="screening_tickers_input")
    run_screen = st.button("スクリーニング実行", type="primary", use_container_width=True)

    if run_screen:
        raw_list = tickers_raw.replace(",", "\n").replace(" ", "\n").splitlines()
        tickers = sorted(set(normalize_ticker(t) for t in raw_list if t.strip()))
        if not tickers:
            st.warning("ティッカー・証券コードを1つ以上入力してください。")
        else:
            with st.spinner("ベンチマーク（S&P500・TOPIX）を取得中..."):
                try:
                    benchmark_us = fetch_prices("^GSPC", days=400)
                except Exception:
                    benchmark_us = pd.DataFrame()
                try:
                    benchmark_jp = fetch_prices("1306.T", days=400)  # TOPIX連動ETF
                except Exception:
                    benchmark_jp = pd.DataFrame()

            ranked = {"S": [], "A": [], "B": [], "C": [], "F": [], "データ不足": []}
            error_list = []
            progress = st.progress(0.0, text="判定中...")
            for i, tk in enumerate(tickers):
                try:
                    d = fetch_prices(tk, days=400)
                    if d.empty:
                        error_list.append(tk)
                    else:
                        ev = evaluate_chart_quality(d)
                        ev["company_name"] = fetch_company_name(tk)
                        if is_jp_ticker(tk) and not benchmark_jp.empty:
                            ev["rs"] = evaluate_relative_strength(d, benchmark_jp, lookback=60,
                                                                  benchmark_name="TOPIX")
                        elif not is_jp_ticker(tk) and not benchmark_us.empty:
                            ev["rs"] = evaluate_relative_strength(d, benchmark_us, lookback=60,
                                                                  benchmark_name="S&P500")
                        else:
                            ev["rs"] = {"stock_return_pct": None, "bench_return_pct": None,
                                       "rs_status": "判定不可", "explanation": ""}
                        if ev.get("above_50ma") is None:
                            # 200日分のデータが無い（上場・設定から日が浅いなど）＝判定不可。
                            # Fランク（トレンド崩れ）と混同しないよう、別枠にする。
                            ranked["データ不足"].append((tk, ev, d))
                        else:
                            rank = rank_chart_quality(ev)
                            ranked[rank].append((tk, ev, d))
                except Exception:
                    error_list.append(tk)
                progress.progress((i + 1) / len(tickers), text=f"判定中... {i+1}/{len(tickers)}")
            progress.empty()
            st.session_state["screen_results"] = (ranked, error_list)

    if "screen_results" in st.session_state:
        ranked, error_list = st.session_state["screen_results"]

        # ①「どのランクに何件あるか」を一番上に一覧で出し、探し回らなくても分かるようにする
        summary_bits = []
        for rank in ["S", "A", "B", "C", "F"]:
            color, _ = RANK_INFO[rank]
            n = len(ranked[rank])
            weight = "700" if n > 0 else "400"
            op = "1" if n > 0 else "0.4"
            summary_bits.append(f'<span style="color:{color};font-weight:{weight};opacity:{op};'
                               f'font-family:\'JetBrains Mono\',monospace;margin-right:14px">'
                               f'{rank} {n}</span>')
        n_insufficient = len(ranked["データ不足"]) + len(error_list)
        summary_bits.append(f'<span style="color:{TEXT_MUTED};margin-right:14px">'
                           f'データ不足/失敗 {n_insufficient}</span>')
        st.markdown(f'<div class="stat-card" style="margin-bottom:1rem">{"".join(summary_bits)}</div>',
                   unsafe_allow_html=True)

        for rank in ["S", "A", "B"]:
            color, desc = RANK_INFO[rank]
            items = ranked[rank]
            if not items:
                # 該当0件のランクは、大きな見出し＋説明文を出さず、1行だけの表示に留めて
                # 目立たなくする（内山さんが「探さないといけない」と感じた原因はここだったため）。
                st.markdown(f'<div style="opacity:0.4;font-size:0.8rem;margin-bottom:0.4rem">'
                           f'<span style="color:{color};font-weight:700;'
                           f'font-family:\'JetBrains Mono\',monospace">{rank}</span> 該当銘柄なし</div>',
                           unsafe_allow_html=True)
                continue
            st.markdown(f'<div class="section-title">'
                       f'<span style="color:{color};font-weight:700;font-family:\'JetBrains Mono\',monospace">'
                       f'{rank}ランク</span>　{desc}（{len(items)}銘柄）</div>', unsafe_allow_html=True)
            for tk, ev, d in items:
                contractions_str = "→".join(f"{c}%" for c in ev["contractions"]) if ev["contractions"] else "―"
                sub = f"収縮：{contractions_str}"
                if ev["has_overhead"]:
                    sub += f"　｜オーバーヘッドまであと{ev['overhead_gap_pct']}%"
                company_name = ev.get("company_name", "")
                title = f"{tk}　{company_name}" if company_name else tk
                st.markdown(stat_card_html(title, f"{rank}ランク", sub=sub, color=color),
                           unsafe_allow_html=True)
                rs = ev.get("rs", {})
                if rs.get("rs_status") and rs["rs_status"] != "判定不可":
                    rs_color = {"強い": POSITIVE, "普通": TEXT_MUTED, "弱い": NEGATIVE}.get(rs["rs_status"], TEXT)
                    bench_label = rs.get("benchmark_name", "指数")
                    st.markdown(stat_card_html(
                        f"対{bench_label} 相対力（60営業日）", f"RS {rs['rs_status']}",
                        sub=f"銘柄 {rs['stock_return_pct']:+.1f}%　vs　{bench_label} {rs['bench_return_pct']:+.1f}%",
                        color=rs_color), unsafe_allow_html=True)
                    if rs.get("explanation"):
                        st.caption(f"💬 {rs['explanation']}")
                render_mini_chart(d)
                st.caption(reasons_text(ev).replace("\n", "　|　"))
                if st.button(f"「{tk}」を個別チェックで詳しく見る", key=f"goto_single_{rank}_{tk}",
                            use_container_width=True):
                    st.session_state["price_df"] = d
                    st.session_state["price_ticker"] = tk
                    st.session_state["pending_tab"] = tab_single
                    st.rerun()
                st.markdown('<hr class="divider">', unsafe_allow_html=True)

        c_items, f_items, insuff_items = ranked["C"], ranked["F"], ranked["データ不足"]
        cf_tickers = [tk for tk, ev, d in c_items + f_items]
        # 「チャートを見る」チェックボックスを押すと画面が再描画され、st.expanderは
        # 何も指定しないと毎回「閉じた状態」に戻ってしまう（せっかく開いたのにチェックした
        # 瞬間に閉じて見えなくなる、という不具合の原因）。チェック済みのものが1つでもあれば
        # 開いたままにする。
        any_chart_checked = any(st.session_state.get(f"cf_chart_{tk}", False) for tk in cf_tickers)
        with st.expander(f"C・Fランク・データ不足・取得失敗（"
                        f"{len(c_items) + len(f_items) + len(insuff_items) + len(error_list)}銘柄）",
                        expanded=any_chart_checked):
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
            for tk, ev, d in insuff_items:
                st.markdown(f'<span style="color:{TEXT_MUTED};font-weight:700">❓</span> **{tk}**',
                           unsafe_allow_html=True)
                st.caption(reasons_text(ev))
                st.markdown('<hr class="divider">', unsafe_allow_html=True)
            for tk in error_list:
                st.write(f"**{tk}**：データ取得失敗")


