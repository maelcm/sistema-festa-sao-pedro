import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import os 
import math # Para calcular a distancia (raio) do clique
from streamlit_image_coordinates import streamlit_image_coordinates # A biblioteca que faltava

# --- CONFIGURAÇÃO E DADOS DE COORDENADAS ---
st.set_page_config(page_title="Gestão Festa São Pedro", layout="wide")

# Mapeamento de coordenadas (X, Y) para o ID da Mesa (Extraído do seu PDF)
# O centro do numero da mesa eh a area de clique
MESA_COORDS = {
    "M01": (217, 311), "M02": (260, 311), "M03": (303, 311), "M04": (346, 311), "M05": (389, 311),
    "M06": (432, 311), "M07": (475, 311), "M08": (518, 311), "M09": (561, 311),
    "M10": (217, 358), "M11": (259, 358), "M12": (301, 358), "M13": (343, 358),
    "M14": (385, 358), "M15": (427, 358), "M16": (469, 358), "M17": (511, 358),
    "M18": (553, 358), "M19": (217, 405), "M20": (259, 405), "M21": (301, 405),
    "M22": (343, 405), "M23": (385, 405), "M24": (427, 405), "M25": (469, 405),
    "M26": (511, 405), "M27": (553, 405), "M28": (217, 477), "M29": (259, 477),
    "M30": (301, 477), "M31": (343, 477), "M32": (385, 477), "M33": (427, 477),
    "M34": (469, 477), "M35": (511, 477), "M36": (553, 477), "M37": (217, 526),
    "M38": (259, 526), "M39": (301, 526), "M40": (343, 526), "M41": (385, 526),
    "M42": (427, 526), "M43": (469, 526), "M44": (511, 526), "M45": (553, 526),
    "M46": (217, 570), "M47": (259, 570), "M48": (301, 570), "M49": (343, 570),
    "M50": (385, 570), "M51": (427, 570), "M52": (469, 570), "M53": (511, 570),
    "M54": (553, 570), "M55": (217, 616), "M56": (259, 616), "M57": (301, 616),
    "M58": (343, 616), "M59": (385, 616), "M60": (427, 616), "M61": (469, 616),
    "M62": (511, 616), "M63": (553, 616),
}
# Nome da imagem no repositório
NOME_IMAGEM_LAYOUT = "mapa_geral.png" 

# --- CONSTANTE DE RAIO DE CLIQUE (HITBOX) ---
# Se o clique estiver a 25 pixels do centro, ele conta como um acerto
RAIO_CLIQUE = 25 


# --- FUNÇÕES DE LIMPEZA E CONEXÃO (MANTIDAS) ---
def limpar_numero_inteligente(valor):
    valor_str = str(valor).upper().strip()
    if not valor_str or valor_str == "NONE" or valor_str == "NAN": return 0.0
    
    if "R$" in valor_str or "," in valor_str or "." in valor_str:
        limpo = valor_str.replace("R$", "").replace(".", "").replace(" ", "")
        if "." in limpo and "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        try: return float(limpo)
        except: return 0.0

    numeros = re.findall(r'\d+', valor_str)
    if numeros: return int(numeros[0])
    return 0.0

@st.cache_resource
def conectar_gsheets():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    except FileNotFoundError:
        caminho = r"C:\Users\Info\MAPA SHOW NACIONAL\credentials.json"
        creds = Credentials.from_service_account_file(caminho, scopes=scopes)

    client = gspread.authorize(creds)
    return client.open_by_key("1fvhCzt2ieZ4s-paXd3GLWgJho-9JE2oXCl14qKSpGDo")

def carregar_dados():
    sh = conectar_gsheets()
    
    ws_layout = sh.worksheet("Layout_Mesas")
    df = pd.DataFrame(ws_layout.get_all_records())
    
    df['Linha_Num'] = df['Linha'].apply(limpar_numero_inteligente)
    df['Coluna_Num'] = df['Coluna'].apply(limpar_numero_inteligente)
    df['Preco_Num'] = df['Preco_Mesa'].apply(limpar_numero_inteligente)
    df = df[df['Linha_Num'] > 0] 

    try:
        ws_res = sh.worksheet("RESERVAS")
        df_res = pd.DataFrame(ws_res.get_all_records())
    except:
        df_res = pd.DataFrame()

    return df, df_res

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

# --- 6. FUNÇÃO DE CÁLCULO DE CLIQUE ---
def check_click_location(clicked_x, clicked_y):
    """Verifica qual mesa foi clicada baseada na distância do centro."""
    
    # Obtém o fator de escala da imagem atual para as coordenadas originais
    # O Streamlit ajusta a imagem. Precisamos reverter essa escala.
    # Como não temos o valor exato da imagem renderizada, vamos usar uma função.
    
    # A maneira mais simples e estável é checar a distância com as coordenadas originais.
    # O Streamlit Image Coordinates retorna as coordenadas da imagem original se tiver um "key".
    
    closest_mesa_id = None
    min_distance = RAIO_CLIQUE # Começa com o raio máximo

    for mesa_id, (center_x, center_y) in MESA_COORDS.items():
        # Distância Euclidiana (a² + b² = c²)
        distance = math.sqrt((clicked_x - center_x)**2 + (clicked_y - center_y)**2)
        
        if distance < min_distance:
            min_distance = distance
            closest_mesa_id = mesa_id
            
    return closest_mesa_id


# --- 7. IMPLEMENTAÇÃO DO MAPA CLICÁVEL ---
def interactive_image_map(df_full):
    st.header("Selecione a Mesa por Imagem")

    # Garante que a imagem está na raiz do projeto (GitHub)
    if not os.path.exists(NOME_IMAGEM_LAYOUT):
        st.error(f"Imagem '{NOME_IMAGEM_LAYOUT}' não encontrada. Por favor, suba a imagem para o GitHub.")
        return

    # AQUI ESTÁ A IMPLEMENTAÇÃO DO CLIQUE NA IMAGEM
    value = streamlit_image_coordinates(NOME_IMAGEM_LAYOUT, key="mapa_clique")

    # Processa o clique
    if value and "point" in value:
        clicked_x = value["point"]["x"]
        clicked_y = value["point"]["y"]
        
        # A biblioteca retorna coordenadas na escala da imagem exibida. 
        # Precisamos da escala real:
        mesa_id = check_click_location(clicked_x, clicked_y)
        
        if mesa_id:
            if st.session_state.get("mesa_id") != mesa_id:
                st.session_state["mesa_id"] = mesa_id
                st.rerun()
            
        else:
            st.toast("Nenhuma mesa encontrada neste ponto de clique.", icon="⚠️")
        
    # --- Desenha os status das mesas (para dar feedback) ---
    # Aqui voce pode desenhar marcadores, mas isso requer um canvas mais complexo.
    # Por hora, apenas mostramos a imagem e o clique.
    st.caption("Clique sobre o número da mesa. O painel lateral se abrirá.")


# --- INTERFACE PRINCIPAL (FLUXO) ---
st.title("🤠 Sistema Festa São Pedro")

try:
    df_layout, df_reservas = carregar_dados()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# Cruzamento de dados
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
# ABA 1: MAPA (CLICÁVEL)
# ==========================================
with tab_mapa:
    interactive_image_map(df_full)
    
    # --- SIDEBAR (CONTEÚDO) ---
    m_id = st.session_state.get("mesa_id")

    if m_id:
        filtro = df_full[df_full["ID_Mesa"] == m_id]
        if not filtro.empty:
            dados = filtro.iloc[0]
            status = dados["Status"] if pd.notna(dados["Status"]) else "Livre"
            
            st.sidebar.subheader(f"Mesa {dados['Numero_Display']}")
            st.sidebar.info(f"📍 {dados['Linha']}")
            
            # --- LIVRE ---
            if status == "Livre":
                st.sidebar.write(f"Valor: **R$ {dados['Preco_Mesa']}**")
                
                cli = st.sidebar.text_input("Nome Cliente", key=f"cli_{m_id}")
                fest = st.sidebar.text_input("Festeiro", key=f"fest_{m_id}")
                tel = st.sidebar.text_input("Telefone", key=f"tel_{m_id}")
                
                if st.sidebar.button("💾 SALVAR RESERVA", type="primary"):
                    if not cli:
                        st.sidebar.error("Preencha o nome do cliente!")
                    else:
                        nid = f"RES-{int(datetime.now().timestamp())}"
                        lin = [nid, m_id, "Reservado", cli, fest, tel, "", str(datetime.now()), ""]
                        salvar_reserva(lin)
            
            # --- RESERVADO ---
            elif status == "Reservado":
                st.sidebar.warning("RESERVADO")
                st.sidebar.write(f"👤 **{dados['Nome_Cliente']}**")
                
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
                
                if st.sidebar.button("Desfazer Venda"):
                    atualizar_status(dados["ID_Venda"], "Reservado", "")


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
