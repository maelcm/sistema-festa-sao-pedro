"""
Gestão Festa São Pedro — Sistema de Reserva de Mesas
Layout profissional, otimizado e com aparência de sistema.
"""
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import os

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================
st.set_page_config(
    page_title="Gestão Festa São Pedro",
    page_icon="🎪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Imagem do mapa: prioriza PNG na pasta, depois JPG
IMAGEM_MAPA_PNG = "mapa.png"
IMAGEM_MAPA_JPG = "banda na praça (1).jpg"
CACHE_TTL_SEGUNDOS = 90

# CSS: aparência de sistema (header, cards, botões, métricas)
st.markdown("""
<style>
    /* Tema geral */
    .stApp { background: linear-gradient(180deg, #0e1117 0%, #1a1d24 100%); }
    
    /* Header do sistema */
    .main-header {
        background: linear-gradient(90deg, #1e3a5f 0%, #2d5a87 50%, #1e3a5f 100%);
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.08);
    }
    .main-header h1 {
        color: #fff;
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .main-header p { color: rgba(255,255,255,0.85); margin: 0.25rem 0 0 0; font-size: 0.9rem; }
    
    /* Cards de métricas */
    .metric-card {
        background: linear-gradient(145deg, #262a33 0%, #1e2128 100%);
        padding: 1rem 1.25rem;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 2px 12px rgba(0,0,0,0.2);
        text-align: center;
    }
    .metric-card .label { color: #8892a0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-card .value { color: #fff; font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }
    .metric-card.caixa .value { color: #4ade80; }
    .metric-card.receber .value { color: #fbbf24; }
    
    /* Card do formulário / painel */
    .panel-card {
        background: linear-gradient(145deg, #1c1f26 0%, #16191e 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 4px 24px rgba(0,0,0,0.25);
        margin-bottom: 1rem;
    }
    .panel-card h3 { color: #e2e8f0; font-size: 1.1rem; margin-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 0.5rem; }
    
    /* Botões principais */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #fff !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.5rem 1.25rem !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.4) !important;
    }
    .stButton > button[kind="primary"]:hover { box-shadow: 0 4px 14px rgba(37,99,235,0.5) !important; }
    
    /* Tabs mais visíveis */
    .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255,255,255,0.04);
        border-radius: 8px 8px 0 0;
        padding: 0.6rem 1.25rem;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] { background: rgba(37,99,235,0.25); color: #93c5fd; }
    
    /* Esconder elementos desnecessários */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    
    /* Celular: 9 mesas em UMA fileira — só nas fileiras do mapa (blocos com 9 colunas) */
    @media (max-width: 768px) {
        /* Apenas blocos com exatamente 9 colunas (fileiras de mesas) */
        [data-testid="stHorizontalBlock"]:has(> div:nth-child(9):nth-last-child(1)) {
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
        }
        [data-testid="stHorizontalBlock"]:has(> div:nth-child(9):nth-last-child(1)) > div {
            flex: 0 0 11.11% !important;
            min-width: 0 !important;
            max-width: 11.11% !important;
        }
        /* Botões menores em todo o app no celular (principalmente mesas) */
        .stButton > button {
            padding: 0.2rem 0.2rem !important;
            font-size: 0.65rem !important;
            min-height: 1.7rem !important;
        }
    }
    @media (max-width: 480px) {
        [data-testid="stHorizontalBlock"]:has(> div:nth-child(9):nth-last-child(1)) > div {
            flex: 0 0 11.11% !important;
            min-width: 0 !important;
            max-width: 11.11% !important;
        }
        .stButton > button {
            padding: 0.15rem 0.12rem !important;
            font-size: 0.6rem !important;
            min-height: 1.55rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# FUNÇÕES AUXILIARES E DADOS
# =============================================================================
def limpar_numero(valor):
    s = str(valor).upper().strip()
    if not s or s in ("NONE", "NAN"): return 0.0
    if "R$" in s or "," in s or "." in s:
        limpo = s.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try: return float(limpo)
        except: return 0.0
    nums = re.findall(r"\d+", s)
    return int(nums[0]) if nums else 0


@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    return gspread.authorize(creds).open_by_key("1fvhCzt2ieZ4s-paXd3GLWgJho-9JE2oXCl14qKSpGDo")


@st.cache_data(ttl=CACHE_TTL_SEGUNDOS)
def carregar_dados():
    sh = conectar_gsheets()
    df = pd.DataFrame(sh.worksheet("Layout_Mesas").get_all_records())
    df["Linha_Num"] = df["Linha"].apply(limpar_numero)
    df["Coluna_Num"] = df["Coluna"].apply(limpar_numero)
    df["Preco_Num"] = df["Preco_Mesa"].apply(limpar_numero)
    df["Tipo_Item"] = df["Tipo_Item"].astype(str).str.strip().str.upper()
    df = df[df["Linha_Num"] > 0]
    try:
        df_res = pd.DataFrame(sh.worksheet("RESERVAS").get_all_records())
    except Exception:
        df_res = pd.DataFrame()
    return df, df_res


def salvar_reserva(dados):
    conectar_gsheets().worksheet("RESERVAS").append_row(dados)
    carregar_dados.clear()
    st.toast("Reserva salva com sucesso!", icon="✅")
    st.session_state["mesa_id"] = None
    st.rerun()


def atualizar_status(id_venda: str, status: str, valor: int | float = 0) -> None:
    sh = conectar_gsheets()
    ws = sh.worksheet("RESERVAS")
    cell = ws.find(id_venda)
    if cell:
        ws.update_cell(cell.row, 3, status)
        if status == "Vendido":
            ws.update_cell(cell.row, 7, valor)
            ws.update_cell(cell.row, 9, str(datetime.now()))
    carregar_dados.clear()
    st.toast("Status atualizado!", icon="💰")
    st.session_state["mesa_id"] = None
    st.rerun()


def cancelar_reserva(id_venda):
    sh = conectar_gsheets()
    ws = sh.worksheet("RESERVAS")
    cell = ws.find(id_venda)
    if cell:
        ws.delete_rows(cell.row)
    carregar_dados.clear()
    st.toast("Reserva cancelada.", icon="🗑️")
    st.session_state["mesa_id"] = None
    st.rerun()


def desenhar_grade(setor_df, max_cols):
    for linha in sorted(setor_df["Linha_Num"].unique()):
        cols = st.columns(int(max_cols))
        for i, col in enumerate(cols):
            row_df = setor_df[(setor_df["Linha_Num"] == linha) & (setor_df["Coluna_Num"] == i + 1)]
            if row_df.empty:
                col.write("")
                continue
            d = row_df.iloc[0]
            st_mesa = d.get("Status")
            if st_mesa == "Vendido": lbl = f"🔴 {d['Numero_Display']}"
            elif st_mesa == "Reservado": lbl = f"🟡 {d['Numero_Display']}"
            else: lbl = f"🟢 {d['Numero_Display']}"
            if col.button(lbl, key=f"btn_{d['ID_Mesa']}", use_container_width=True):
                st.session_state["mesa_id"] = d["ID_Mesa"]
                st.rerun()


# =============================================================================
# CARREGAR DADOS E PREPARAR DF
# =============================================================================
df_layout: pd.DataFrame = pd.DataFrame()
df_reservas: pd.DataFrame = pd.DataFrame()
try:
    df_layout, df_reservas = carregar_dados()
except Exception as e:
    err = str(e)
    if "429" in err or "Quota exceeded" in err or "RESOURCE_EXHAUSTED" in err:
        st.error("Limite de leituras do Google Sheets atingido (60/min). Aguarde ~1 minuto e clique em **Atualizar dados**.")
        if st.button("🔄 Atualizar dados"):
            carregar_dados.clear()
            st.rerun()
    else:
        st.error(f"Erro de conexão: {e}")
    st.stop()

if not df_reservas.empty:
    df_res_limpo = df_reservas.sort_values("Data_Reserva", ascending=False).drop_duplicates(subset=["Ref_Mesa"])
    df_full = pd.merge(df_layout, df_res_limpo, left_on="ID_Mesa", right_on="Ref_Mesa", how="left")
else:
    df_full = df_layout.copy()
    df_full["Status"] = None

# Lookup rápido: número da mesa (01, 02, … 99) -> ID_Mesa
lookup_numero_para_id = {}
for _, row in df_full.iterrows():
    nd = str(row.get("Numero_Display", "")).strip()
    if not nd: continue
    id_mesa = row["ID_Mesa"]
    lookup_numero_para_id[nd.zfill(2)] = id_mesa
    lookup_numero_para_id[nd] = id_mesa

# Clique no mapa (link ?mesa=N): abrir essa mesa
if "mesa_id" not in st.session_state:
    st.session_state["mesa_id"] = None
try:
    q = st.query_params.get("mesa")
    if q is not None:
        num = int(q) if isinstance(q, str) else (int(q[0]) if q else 0)
        if 1 <= num <= 99:
            id_mesa = lookup_numero_para_id.get(f"{num:02d}") or lookup_numero_para_id.get(str(num))
            if id_mesa:
                st.session_state["mesa_id"] = id_mesa
except (TypeError, ValueError, Exception):
    pass

# Métricas globais (para header)
total = len(df_full)
vendidas = df_full[df_full["Status"] == "Vendido"]
reservadas = df_full[df_full["Status"] == "Reservado"]
livres = total - len(vendidas) - len(reservadas)
caixa = vendidas["Valor_Entrada_Cobrado"].apply(limpar_numero).sum() if not vendidas.empty else 0
receber = reservadas["Preco_Num"].sum() if not reservadas.empty else 0


# =============================================================================
# UI — HEADER
# =============================================================================
col_logo, col_stats = st.columns([2, 3])
with col_logo:
    st.markdown("""
    <div class="main-header">
        <h1>🎪 Gestão Festa São Pedro 2026</h1>
        <p>Sistema de Reserva de Mesas</p>
    </div>
    """, unsafe_allow_html=True)
with col_stats:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🟢 Livres", livres)
    c2.metric("🟡 Reservadas", len(reservadas))
    c3.metric("🔴 Vendidas", len(vendidas))
    c4.metric("💰 Caixa", f"R$ {caixa:,.0f}")
    c5.metric("💸 A receber", f"R$ {receber:,.0f}")


# =============================================================================
# ABAS
# =============================================================================
tab_mapa, tab_visual, tab_financeiro = st.tabs(["🗺️ Mapa de Mesas", "🖼️ Imagem do Mapa", "📊 Relatório"])

# ---------- ABA MAPA ----------
with tab_mapa:
    m_id = st.session_state.get("mesa_id")

    st.subheader("Clique no botão da mesa")
    st.caption("🟢 Livre · 🟡 Reservado · 🔴 Vendido")
    ORDEM_SETORES = ["PATROCINADOR", "SETOR A", "SETOR B", "SETOR C"]
    max_cols = int(df_full["Coluna_Num"].max()) if not df_full.empty else 9
    for setor in ORDEM_SETORES:
        sub = df_full[df_full["Tipo_Item"] == setor]
        if not sub.empty:
            st.markdown(f"**{setor}**")
            desenhar_grade(sub, max_cols)
    for setor in df_full["Tipo_Item"].unique():
        if setor and setor not in ORDEM_SETORES:
            st.markdown(f"**{setor}**")
            desenhar_grade(df_full[df_full["Tipo_Item"] == setor], max_cols)
    st.divider()

    st.subheader("Ou digite o número da mesa")
    col_num, col_btn, _ = st.columns([1, 1, 3])
    with col_num:
        numero_mesa = st.number_input("Número da mesa (1 a 99)", min_value=1, max_value=99, value=1, step=1, key="numero_mesa_rapida")
    with col_btn:
        st.write("")
        if st.button("Abrir mesa", type="primary", use_container_width=True):
            id_mesa = lookup_numero_para_id.get(f"{numero_mesa:02d}") or lookup_numero_para_id.get(str(numero_mesa))
            if id_mesa:
                st.session_state["mesa_id"] = id_mesa
                st.rerun()
            else:
                st.warning(f"Mesa {numero_mesa:02d} não encontrada.")
    st.divider()

    # Formulário da mesa selecionada (rola até aqui ao abrir uma mesa)
    if m_id:
        st.markdown(
            '<div id="formulario-mesa"></div><script>(function(){var el=document.getElementById("formulario-mesa");if(el){setTimeout(function(){el.scrollIntoView({behavior:"smooth",block:"start"});},400);}})();</script>',
            unsafe_allow_html=True,
        )
        row = df_full[df_full["ID_Mesa"] == m_id]
        if not row.empty:
            d = row.iloc[0]
            status = d["Status"] if pd.notna(d["Status"]) else "Livre"
            with st.container():
                st.markdown(f"### 📝 Mesa {d['Numero_Display']} — {status}")
                st.caption(f"Setor: {d.get('Tipo_Item', '-')} · Linha {d['Linha']}")
                if status == "Livre":
                    st.write(f"**Valor:** R$ {d['Preco_Mesa']}")
                    cli = st.text_input("Nome do cliente", key=f"cli_{m_id}")
                    tel = st.text_input("Telefone", key=f"tel_{m_id}")
                    fest = st.text_input("Festeiro (indicação)", key=f"fest_{m_id}")
                    b1, b2 = st.columns(2)
                    if b1.button("💾 Salvar reserva", type="primary", use_container_width=True):
                        if not cli:
                            st.error("Nome obrigatório.")
                        else:
                            salvar_reserva([f"RES-{int(datetime.now().timestamp())}", m_id, "Reservado", cli, fest, tel, "", str(datetime.now()), ""])
                    if b2.button("Fechar", use_container_width=True):
                        st.session_state["mesa_id"] = None
                        st.rerun()
                elif status == "Reservado":
                    st.warning(f"Reservado para **{d['Nome_Cliente']}** · 📞 {d.get('Telefone_Cliente', '-')}")
                    b1, b2, b3 = st.columns(3)
                    if b1.button("💲 Marcar pago", type="primary", use_container_width=True):
                        atualizar_status(d["ID_Venda"], "Vendido", d["Preco_Num"])
                    if b2.button("❌ Cancelar reserva", use_container_width=True):
                        cancelar_reserva(d["ID_Venda"])
                    if b3.button("Fechar", use_container_width=True):
                        st.session_state["mesa_id"] = None
                        st.rerun()
                elif status == "Vendido":
                    st.success(f"Vendido para **{d['Nome_Cliente']}**")
                    b1, b2 = st.columns(2)
                    if b1.button("Desfazer venda", use_container_width=True):
                        atualizar_status(d["ID_Venda"], "Reservado", 0)
                    if b2.button("Fechar", use_container_width=True):
                        st.session_state["mesa_id"] = None
                        st.rerun()
            st.divider()

# ---------- ABA IMAGEM ----------
with tab_visual:
    # Usa o PNG da pasta se existir, senão o JPG
    if os.path.exists(IMAGEM_MAPA_PNG):
        st.image(IMAGEM_MAPA_PNG, caption="Layout do salão (mapa.png)", use_container_width=True)
    elif os.path.exists(IMAGEM_MAPA_JPG):
        st.image(IMAGEM_MAPA_JPG, caption="Layout do salão", use_container_width=True)
    else:
        st.warning(f"Coloque a imagem do mapa na pasta: **{IMAGEM_MAPA_PNG}** ou **{IMAGEM_MAPA_JPG}**.")

# ---------- ABA RELATÓRIO ----------
with tab_financeiro:
    st.subheader("Resumo financeiro e ocupação")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("💰 Caixa", f"R$ {caixa:,.2f}")
    col2.metric("💸 A receber", f"R$ {receber:,.2f}")
    col3.metric("🔴 Vendidas", len(vendidas))
    col4.metric("🟡 Reservadas", len(reservadas))
    col5.metric("🟢 Livres", livres)
    st.divider()
    st.subheader("Extrato (vendas e reservas)")
    ocupadas = df_full[df_full["Status"].isin(["Vendido", "Reservado"])]
    if not ocupadas.empty:
        st.dataframe(ocupadas[["Numero_Display", "Status", "Nome_Cliente", "Telefone_Cliente", "Preco_Mesa", "Valor_Entrada_Cobrado"]], use_container_width=True)
    else:
        st.info("Nenhuma venda ou reserva ainda.")
