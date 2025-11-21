import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Festa São Pedro", layout="wide")

# --- 1. FUNÇÃO DE LIMPEZA ---
def limpar_numero_inteligente(valor):
    valor_str = str(valor).upper().strip()
    if not valor_str or valor_str == "NONE" or valor_str == "NAN": return 0.0
    
    if "R$" in valor_str or "," in valor_str or "." in valor_str:
        limpo = valor_str.replace("R$", "").replace(" ", "")
        if "." in limpo and "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        try: return float(limpo)
        except: return 0.0

    numeros = re.findall(r'\d+', valor_str)
    if numeros: return int(numeros[0])
    return 0.0

# --- 2. CONEXÃO ---
@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    except FileNotFoundError:
        caminho = r"C:\Users\Info\MAPA SHOW NACIONAL\credentials.json"
        creds = Credentials.from_service_account_file(caminho, scopes=scopes)

    client = gspread.authorize(creds)
    return client.open_by_key("1fvhCzt2ieZ4s-paXd3GLWgJho-9JE2oXCl14qKSpGDo")

# --- 3. CARREGAR DADOS ---
def carregar_dados():
    sh = conectar_gsheets()
    
    # Layout
    ws_layout = sh.worksheet("Layout_Mesas")
    df = pd.DataFrame(ws_layout.get_all_records())
    
    df['Linha_Num'] = df['Linha'].apply(limpar_numero_inteligente)
    df['Coluna_Num'] = df['Coluna'].apply(limpar_numero_inteligente)
    df['Preco_Num'] = df['Preco_Mesa'].apply(limpar_numero_inteligente)
    df = df[df['Linha_Num'] > 0] 

    # Reservas
    try:
        ws_res = sh.worksheet("RESERVAS")
        df_res = pd.DataFrame(ws_res.get_all_records())
    except:
        df_res = pd.DataFrame()

    return df, df_res

# --- 4. SALVAR E ATUALIZAR ---
def salvar_reserva(dados):
    sh = conectar_gsheets()
    sh.worksheet("RESERVAS").append_row(dados)
    st.toast("Reserva Salva!", icon="✅")
    st.session_state["mesa_id"] = None # Fecha a mesa após salvar
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

# --- 5. INTERFACE PRINCIPAL ---
st.title("🤠 Sistema Festa São Pedro")

try:
    df_layout, df_reservas = carregar_dados()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# Cruzamento
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
tab_mapa, tab_financeiro = st.tabs(["🗺️ MAPA DE MESAS", "📊 FINANCEIRO"])


# ==========================================
# ABA 1: MAPA
# ==========================================
with tab_mapa:
    
    if "Tipo_Item" in df_full.columns:
        setores = ["Todos"] + list(df_full["Tipo_Item"].unique())
        col_filtro, _ = st.columns([1, 3])
        with col_filtro:
            escolha_setor = st.selectbox("Filtrar por Setor:", setores)
        
        if escolha_setor != "Todos":
            df_mapa = df_full[df_full["Tipo_Item"] == escolha_setor]
        else:
            df_mapa = df_full
    else:
        df_mapa = df_full

    st.caption("Clique na mesa para Reservar ou Vender")

    # --- SIDEBAR (SEM FORMULÁRIO AGORA) ---
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
            
            # --- LIVRE ---
            if status == "Livre":
                st.sidebar.write(f"Valor: **R$ {dados['Preco_Mesa']}**")
                st.sidebar.markdown("---")
                
                # AQUI ESTÁ A MUDANÇA: CAMPOS SOLTOS SEM 'st.form'
                # Usamos key=f"nome_{m_id}" para limpar quando troca de mesa
                cli = st.sidebar.text_input("Nome Cliente", key=f"cli_{m_id}")
                fest = st.sidebar.text_input("Festeiro", key=f"fest_{m_id}")
                tel = st.sidebar.text_input("Telefone", key=f"tel_{m_id}")
                
                # O botão agora é um botão normal, só salva se clicar nele
                if st.sidebar.button("💾 SALVAR RESERVA", type="primary"):
                    if not cli:
                        st.sidebar.error("Preencha o nome do cliente!")
                    else:
                        nid = f"RES-{int(datetime.now().timestamp())}"
                        # A:ID, B:Ref, C:Status, D:Cli, E:Fest, F:Tel, G:Val, H:DatR, I:DatC
                        lin = [nid, m_id, "Reservado", cli, fest, tel, "", str(datetime.now()), ""]
                        salvar_reserva(lin)
            
            # --- RESERVADO ---
            elif status == "Reservado":
                st.sidebar.warning("RESERVADO")
                st.sidebar.write(f"👤 **{dados['Nome_Cliente']}**")
                st.sidebar.write(f"📞 {dados['Telefone_Cliente']}")
                st.sidebar.write(f"🎉 Indicação: {dados['Nome_Festeiro']}")
                
                st.sidebar.markdown("---")
                col1, col2 = st.sidebar.columns(2)
                if col1.button("💲 PAGO"):
                    val_padrao = dados['Preco_Num']
                    atualizar_status(dados["ID_Venda"], "Vendido", val_padrao)
                
                if col2.button("❌ CANCELAR"):
                    cancelar(dados["ID_Venda"])
            
            # --- VENDIDO ---
            elif status == "Vendido":
                st.sidebar.success("VENDIDO")
                st.sidebar.write(f"👤 **{dados['Nome_Cliente']}**")
                try:
                    val_pago = limpar_numero_inteligente(dados["Valor_Entrada_Cobrado"])
                    st.sidebar.metric("Valor Pago", f"R$ {val_pago:,.2f}")
                except: pass
                
                if st.sidebar.button("Desfazer Venda"):
                    atualizar_status(dados["ID_Venda"], "Reservado", "")

    # --- DESENHO DO MAPA ---
    linhas_visiveis = df_mapa['Linha_Num'].unique()
    linhas_visiveis.sort()
    cols = df_mapa['Coluna_Num'].max()

    if len(linhas_visiveis) > 0:
        for l in linhas_visiveis:
            c_cols = st.columns(int(cols))
            for i, col_obj in enumerate(c_cols):
                item = df_mapa[(df_mapa["Linha_Num"] == l) & (df_mapa["Coluna_Num"] == (i + 1))]
                if not item.empty:
                    d = item.iloc[0]
                    st_mesa = d["Status"]
                    
                    if st_mesa == "Vendido": 
                        btn_label = f"🔴 {d['Numero_Display']}"
                        tipo = "primary"
                    elif st_mesa == "Reservado": 
                        btn_label = f"🟡 {d['Numero_Display']}"
                    else: 
                        btn_label = f"🟢 {d['Numero_Display']}"
                    
                    if col_obj.button(btn_label, key=d["ID_Mesa"], use_container_width=True):
                        st.session_state["mesa_id"] = d["ID_Mesa"]
                        st.rerun()
                else:
                    col_obj.write("")
    else:
        st.warning("Nenhuma mesa encontrada neste filtro.")


# ==========================================
# ABA 2: FINANCEIRO
# ==========================================
with tab_financeiro:
    st.header("Visão Geral do Evento")
    
    total_mesas = len(df_full)
    vendidas = df_full[df_full["Status"] == "Vendido"]
    reservadas = df_full[df_full["Status"] == "Reservado"]
    livres = total_mesas - (len(vendidas) + len(reservadas))

    if not vendidas.empty and "Valor_Entrada_Cobrado" in vendidas.columns:
        caixa_atual = vendidas["Valor_Entrada_Cobrado"].apply(limpar_numero_inteligente).sum()
    else:
        caixa_atual = 0.0

    if not reservadas.empty:
        a_receber = reservadas["Preco_Num"].sum()
    else:
        a_receber = 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("💰 CAIXA (RECEBIDO)", f"R$ {caixa_atual:,.2f}", delta="Confirmado")
    kpi2.metric("🟡 A RECEBER", f"R$ {a_receber:,.2f}", delta="Pendente", delta_color="off")
    kpi3.metric("🔴 VENDIDAS", f"{len(vendidas)} / {total_mesas}")
    kpi4.metric("🟢 LIVRES", f"{livres}")

    ocupacao = (len(vendidas) + len(reservadas)) / total_mesas if total_mesas > 0 else 0
    st.progress(ocupacao, text=f"Ocupação do Salão: {int(ocupacao*100)}%")
    
    st.markdown("---")
    st.subheader("Extrato de Vendas")
    if not vendidas.empty:
        tabela_vendas = vendidas[["Numero_Display", "Nome_Cliente", "Nome_Festeiro", "Valor_Entrada_Cobrado", "Data_Confirmacao"]]
        st.dataframe(tabela_vendas, use_container_width=True)
    else:
        st.info("Nenhuma venda confirmada ainda.")
