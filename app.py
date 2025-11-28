import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import os 

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Festa São Pedro", layout="wide")

# NOME DA IMAGEM
NOME_IMAGEM_LAYOUT = "banda na praça (1).png"

# --- 1. FUNÇÕES DE LIMPEZA ---
def limpar_numero_inteligente(valor):
    valor_str = str(valor).upper().strip()
    if not valor_str or valor_str == "NONE" or valor_str == "NAN": return 0.0
    if "R$" in valor_str or "," in valor_str or "." in valor_str:
        limpo = valor_str.replace("R$", "").replace(" ", "")
        if "." in limpo and "," in limpo: limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo: limpo = limpo.replace(",", ".")
        try: return float(limpo)
        except: return 0.0
    numeros = re.findall(r'\d+', valor_str)
    if numeros: return int(numeros[0])
    return 0.0

# --- 2. CONEXÃO ---
@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    else:
        try:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        except:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key("1fvhCzt2ieZ4s-paXd3GLWgJho-9JE2oXCl14qKSpGDo")

# --- 3. CARREGAR DADOS ---
def carregar_dados():
    sh = conectar_gsheets()
    ws_layout = sh.worksheet("Layout_Mesas")
    df = pd.DataFrame(ws_layout.get_all_records())
    
    # Converte colunas chave para numero
    df['Linha_Num'] = df['Linha'].apply(limpar_numero_inteligente)
    df['Coluna_Num'] = df['Coluna'].apply(limpar_numero_inteligente)
    df['Preco_Num'] = df['Preco_Mesa'].apply(limpar_numero_inteligente)
    
    # Garante que Tipo_Item seja texto limpo e maiúsculo para agrupar certo
    df['Tipo_Item'] = df['Tipo_Item'].astype(str).str.strip().str.upper()
    
    df = df[df['Linha_Num'] > 0] 

    try:
        ws_res = sh.worksheet("RESERVAS")
        df_res = pd.DataFrame(ws_res.get_all_records())
    except:
        df_res = pd.DataFrame()
    return df, df_res

# --- 4. FUNÇÕES DE AÇÃO ---
def salvar_reserva(dados):
    sh = conectar_gsheets()
    sh.worksheet("RESERVAS").append_row(dados)
    st.toast("Reserva Salva!", icon="✅")
    st.session_state["mesa_id"] = None
    st.rerun()

def atualizar_status(id_venda, status, valor=0):
    sh = conectar_gsheets()
    ws = sh.worksheet("RESERVAS")
    cell = ws.find(id_venda)
    if cell:
        ws.update_cell(cell.row, 3, status)
        if status == "Vendido":
            ws.update_cell(cell.row, 7, valor)
            ws.update_cell(cell.row, 9, str(datetime.now()))
    st.toast("Status Atualizado!", icon="💰")
    st.session_state["mesa_id"] = None
    st.rerun()

def cancelar(id_venda):
    sh = conectar_gsheets()
    ws = sh.worksheet("RESERVAS")
    cell = ws.find(id_venda)
    if cell:
        ws.delete_rows(cell.row)
        st.toast("Cancelado!", icon="🗑️")
        st.session_state["mesa_id"] = None
        st.rerun()

# --- 5. FUNÇÃO DE DESENHO DO GRID ---
def desenhar_grade_mesas(dataframe_setor, max_cols):
    linhas = dataframe_setor['Linha_Num'].unique()
    linhas.sort()
    for l in linhas:
        c_cols = st.columns(int(max_cols))
        for i, col_obj in enumerate(c_cols):
            item = dataframe_setor[(dataframe_setor["Linha_Num"] == l) & (dataframe_setor["Coluna_Num"] == (i + 1))]
            if not item.empty:
                d = item.iloc[0]
                st_mesa = d["Status"]
                
                if st_mesa == "Vendido": 
                    btn_label = f"🔴 {d['Numero_Display']}"
                elif st_mesa == "Reservado": 
                    btn_label = f"🟡 {d['Numero_Display']}"
                else: 
                    btn_label = f"🟢 {d['Numero_Display']}"
                
                if col_obj.button(btn_label, key=f"btn_{d['ID_Mesa']}", use_container_width=True):
                    st.session_state["mesa_id"] = d["ID_Mesa"]
                    st.rerun()
            else:
                col_obj.write("")

# --- INÍCIO DO APP ---
st.title("Reserva de Mesa Festa de São Pedro 2026")

try:
    df_layout, df_reservas = carregar_dados()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

if not df_reservas.empty:
    df_res_sorted = df_reservas.sort_values(by="Data_Reserva", ascending=False)
    df_res_limpo = df_res_sorted.drop_duplicates(subset=["Ref_Mesa"])
    df_full = pd.merge(df_layout, df_res_limpo, left_on="ID_Mesa", right_on="Ref_Mesa", how="left")
else:
    df_full = df_layout
    df_full["Status"] = None


# ==========================================
# ABAS
# ==========================================
tab_mapa, tab_visual, tab_financeiro = st.tabs(["🗺️ MAPA DE MESAS", "👁️ VISUALIZAR IMAGEM", "📊 RELATÓRIO"])

# ==========================================
# ABA 1: MAPA EM BLOCOS (FIXO)
# ==========================================
with tab_mapa:
    
    st.caption("Legenda: 🟢 Livre | 🟡 Reservado | 🔴 Vendido")
    
    # --- SIDEBAR LATERAL ---
    if "mesa_id" not in st.session_state:
        st.session_state["mesa_id"] = None
    m_id = st.session_state["mesa_id"]

    if m_id:
        filtro = df_full[df_full["ID_Mesa"] == m_id]
        if not filtro.empty:
            dados = filtro.iloc[0]
            status = dados["Status"] if pd.notna(dados["Status"]) else "Livre"
            
            st.sidebar.subheader(f"Mesa {dados['Numero_Display']}")
            st.sidebar.info(f"📍 {dados['Linha']}")
            st.sidebar.caption(f"Setor: {dados.get('Tipo_Item', '-')}")
            
            if status == "Livre":
                st.sidebar.write(f"Valor: **R$ {dados['Preco_Mesa']}**")
                st.sidebar.markdown("---")
                cli = st.sidebar.text_input("Nome Cliente", key=f"cli_{m_id}")
                fest = st.sidebar.text_input("Festeiro", key=f"fest_{m_id}")
                tel = st.sidebar.text_input("Telefone", key=f"tel_{m_id}")
                if st.sidebar.button("💾 SALVAR RESERVA", type="primary"):
                    if not cli: st.sidebar.error("Preencha o nome!")
                    else:
                        nid = f"RES-{int(datetime.now().timestamp())}"
                        lin = [nid, m_id, "Reservado", cli, fest, tel, "", str(datetime.now()), ""]
                        salvar_reserva(lin)
            
            elif status == "Reservado":
                st.sidebar.warning("RESERVADO")
                st.sidebar.write(f"👤 {dados['Nome_Cliente']}")
                col1, col2 = st.sidebar.columns(2)
                if col1.button("💲 PAGO"):
                    val_padrao = dados['Preco_Num']
                    atualizar_status(dados["ID_Venda"], "Vendido", val_padrao)
                if col2.button("❌ CANCELAR"):
                    cancelar(dados["ID_Venda"])
            
            elif status == "Vendido":
                st.sidebar.success("VENDIDO")
                st.sidebar.write(f"👤 {dados['Nome_Cliente']}")
                if st.sidebar.button("Desfazer Venda"):
                    atualizar_status(dados["ID_Venda"], "Reservado", "")


    # --- BLOCOS DE SETORES ---
    # Aqui definimos a ordem exata que você pediu.
    # O sistema vai procurar exatamente esses nomes na coluna Tipo_Item (convertido para maiúsculo)
    
    ORDEM_SETORES = ["PATROCINADOR", "SETOR A", "SETOR B", "SETOR C"]
    
    max_cols_geral = df_full['Coluna_Num'].max() if not df_full.empty else 10

    # 1. Desenha os setores na ordem da sua lista
    for setor_nome in ORDEM_SETORES:
        # Filtra o dataframe procurando esse nome
        df_subset = df_full[df_full["Tipo_Item"] == setor_nome]
        
        if not df_subset.empty:
            st.markdown(f"### 🏷️ {setor_nome}")
            desenhar_grade_mesas(df_subset, max_cols_geral)
            st.markdown("---")
    
    # 2. Desenha qualquer outro setor que esteja na planilha mas não na lista acima (Segurança)
    outros_setores = [x for x in df_full["Tipo_Item"].unique() if x not in ORDEM_SETORES and x != ""]
    for setor_extra in outros_setores:
        st.markdown(f"### 🏷️ {setor_extra}")
        df_subset = df_full[df_full["Tipo_Item"] == setor_extra]
        desenhar_grade_mesas(df_subset, max_cols_geral)
        st.markdown("---")


# ==========================================
# ABA 2: VISUALIZAR
# ==========================================
with tab_visual:
    st.header("Layout do Salão")
    if os.path.exists(NOME_IMAGEM_LAYOUT):
        st.image(NOME_IMAGEM_LAYOUT, caption="Mapa Geral", use_container_width=True)
    else:
        st.warning(f"Imagem '{NOME_IMAGEM_LAYOUT}' não encontrada.")

# ==========================================
# ABA 3: RELATORIO
# ==========================================
with tab_financeiro:
    st.header("Resumo Financeiro")
    total = len(df_full)
    vendidas = df_full[df_full["Status"] == "Vendido"]
    reservadas = df_full[df_full["Status"] == "Reservado"]
    livres = total - (len(vendidas) + len(reservadas))

    caixa = vendidas["Valor_Entrada_Cobrado"].apply(limpar_numero_inteligente).sum() if not vendidas.empty else 0
    receber = reservadas["Preco_Num"].sum() if not reservadas.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 CAIXA", f"R$ {caixa:,.2f}")
    c2.metric("🟡 A RECEBER", f"R$ {receber:,.2f}")
    c3.metric("🔴 VENDIDAS", f"{len(vendidas)}")
    c4.metric("🟢 LIVRES", f"{livres}")
    
    st.subheader("Extrato Detalhado")
    if not vendidas.empty:
        st.dataframe(vendidas[["Numero_Display", "Nome_Cliente", "Valor_Entrada_Cobrado"]], use_container_width=True)

