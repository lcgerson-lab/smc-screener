import streamlit as st
import pandas as pd
import ccxt
from smartmoneyconcepts import smc

# Configuración visual de la página
st.set_page_config(page_title="SMC Radar & Screener", layout="wide")

st.title("⚡ SMC Radar & Screener - 4H")
st.caption("Escáner de Liquidez (BSL/SSL) y Fair Value Gaps (FVG) en tiempo real")

# Configuración del panel lateral (Sidebar)
st.sidebar.header("Configuración del Escáner")
TIMEFRAME = st.sidebar.selectbox("Temporalidad", ["1h", "4h", "1d"], index=1)

DEFAULT_SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT',
    'XRP/USDT', 'DOGE/USDT', 'AVAX/USDT', 'LINK/USDT',
    'DOT/USDT', 'LTC/USDT'
]

symbols_input = st.sidebar.text_area(
    "Watchlist (separados por coma)", 
    value=", ".join(DEFAULT_SYMBOLS)
)
SYMBOL_LIST = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]

if st.button("🔄 Actualizar Escáner"):
    st.cache_data.clear()
    st.rerun()

# Kraken no aplica geobloqueos a las IPs de Streamlit Cloud
exchange = ccxt.kraken({'enableRateLimit': True})

@st.cache_data(ttl=60)
def fetch_data(symbol, timeframe):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=150)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        return None

def analyze_symbol(symbol, timeframe):
    df = fetch_data(symbol, timeframe)
    if df is None or df.empty:
        return None
    
    current_price = df['close'].iloc[-1]
    
    # 1. Fair Value Gaps (FVG)
    fvg_status = "Sin zona cercana"
    try:
        fvg_df = smc.fvg(df)
        if not fvg_df.empty and 'top' in fvg_df.columns:
            active_fvgs = fvg_df[fvg_df['mitigated_index'].isna()] if 'mitigated_index' in fvg_df.columns else fvg_df
            if not active_fvgs.empty:
                last_fvg = active_fvgs.iloc[-1]
                top_z, bot_z = last_fvg['top'], last_fvg['bottom']
                if (bot_z * 0.995) <= current_price <= (top_z * 1.005):
                    fvg_status = "🟢 FVG Demand (Alcista)" if last_fvg.get('fvg', 0) == 1 else "🔴 FVG Supply (Bajista)"
    except Exception:
        pass

    # 2. Liquidez BSL/SSL
    liq_status = "En rango"
    try:
        liq_df = smc.liquidity(df)
        if not liq_df.empty and 'level' in liq_df.columns:
            active_liq = liq_df.dropna(subset=['level'])
            if not active_liq.empty:
                level = active_liq.iloc[-1]['level']
                diff_pct = abs(current_price - level) / current_price * 100
                if diff_pct <= 1.0:
                    liq_status = "⚡ Cerca de BSL (Liquidez Superior)" if level > current_price else "⚡ Cerca de SSL (Liquidez Inferior)"
    except Exception:
        pass

    return {
        "Activo": symbol,
        "Precio Actual ($)": f"{current_price:,.2f}",
        "Estado FVG / POI": fvg_status,
        "Proximidad Liquidez": liq_status
    }

# --- EJECUCIÓN Y TABLA EN PANTALLA ---
with st.spinner("Conectando con Kraken y procesando SMC..."):
    results = []
    for sym in SYMBOL_LIST:
        res = analyze_symbol(sym, TIMEFRAME)
        if res:
            results.append(res)

if results:
    results_df = pd.DataFrame(results)
    st.dataframe(results_df, use_container_width=True)
else:
    st.error("No se pudieron cargar los datos del exchange.")
