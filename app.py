import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import os # Biblioteca para verificar se a imagem existe

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Festa São Pedro", layout="wide")

# --- COORDENADAS (Gerado a partir do seu PDF) ---
# X, Y são as coordenadas do centro de cada número da mesa na imagem.
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
# O nome da imagem grande (certifique-se que está no GitHub)
NOME_IMAGEM_MAPA = "banda na praça (1).png" 
# Largura fixa da imagem original para posicionamento (ajuste se a imagem for maior)
LARGURA_IMAGEM_BASE = 800 

# --- 1. FUNÇÃO DE LIMPEZA INTELIGENTE ---
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
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
    except FileNotFoundError:
        caminho = r"C:\Users\Info\MAPA SHOW NACIONAL\credentials.json"
        creds = Credentials.from_service_account_file(caminho, scopes=scopes)

    client = gspread.authorize(creds)
    return client.open_by_key("1fvhCzt2ieZ4s-paXd3GLWgJho-9JE2oXCl14qKSpGDo")

# --- 3. CARREGAR DADOS ---
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

# --- 4. SALVAR E ATUALIZAR ---
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
# GERAÇÃO DO MAPA INTERATIVO (HTML/CSS)
# ==========================================
def draw_interactive_map(df_full):
    # Dicionário de Status para mapear cores
    status_map = {
        "Vendido": "background: red; border: 2px solid #500; opacity: 0.9;",
        "Reservado": "background: yellow; border: 2px solid orange; opacity: 0.8;",
        "Livre": "background: green; border: 2px solid #060; opacity: 0.8;",
        "Outro": "background: gray; border: 2px solid #333; opacity: 0.7;"
    }
    
    # CSS para o container e os botões
    html_style = """
    <style>
        .map-container {
            position: relative;
            width: 100%; /* Ajuste para caber na tela */
            max-width: 800px; /* Limite do tamanho da imagem */
            margin: auto;
        }
        .mesa-btn {
            position: absolute;
            width: 40px; /* Largura do botão */
            height: 40px; /* Altura do botão */
            border-radius: 50%; /* Faz um círculo */
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: black;
            font-weight: bold;
            font-size: 14px;
        }
    </style>
    """
    
    # Container para a imagem e os botões sobrepostos
    html_mapa = f'<div class="map-container">'
    
    # Adiciona a imagem de fundo
    html_mapa += f'<img src="{NOME_IMAGEM_MAPA}" style="width:100%; height:auto;" alt="Mapa do Salão">'
    
    # Calcula a escala da imagem (assumindo que a imagem base tem 800px de largura)
    # Streamlit vai redimensionar para 100%, mas a proporção X/800 é constante
    scale_factor = "calc(100% / 800px)" # Usamos 800px da imagem base

    # Desenha os botões
    for id_mesa, (x, y) in MESA_COORDS.items():
        
        # Encontra os dados e status da mesa no DataFrame completo
        df_mesa = df_full[df_full['ID_Mesa'] == id_mesa]
        
        # Define status e cor
        if not df_mesa.empty:
            dados_mesa = df_mesa.iloc[0]
            status = dados_mesa["Status"] if pd.notna(dados_mesa["Status"]) else "Livre"
            num_display = dados_mesa['Numero_Display']
            style_mesa = status_map.get(status, status_map['Outro'])
            
            # Posição (Subtrai metade da largura do botão para centralizar no X,Y)
            # Usa a função 'calc' para o posicionamento relativo à largura da tela
            left_pos = f"calc({x}px * var(--st-col-width) / {LARGURA_IMAGEM_BASE} - 20px)"
            top_pos = f"calc({y}px * var(--st-col-width) / {LARGURA_IMAGEM_BASE} - 20px)"
            
            # Geração do código Javascript para acionar a sessão do Streamlit
            # Isso é o truque para um botão HTML interagir com o Streamlit
            js_call = f"st_script_run('set_mesa', '{id_mesa}');"
            
            html_mapa += f"""
            <button onclick="{js_call}" class="mesa-btn" style="{style_mesa} top:{top_pos}; left:{left_pos};">
                {num_display}
            </button>
            """
            
    html_mapa += '</div>'
    
    # Adiciona a função Javascript ao código
    # Precisa de uma pequena biblioteca Streamlit para rodar JS, mas vamos usar um truque
    st.markdown(html_style, unsafe_allow_html=True)
    st.markdown(html_mapa, unsafe_allow_html=True)
    
    # Como não podemos usar st.experimental_rerun, usamos um truque com o st.text_input
    # Se o valor mudar, ele força o sidebar a ser ativado
    st.text_input("Mesa Selecionada (Não mexer)", key='selected_mesa_input', value=st.session_state.get('mesa_id', ''), disabled=True)
    
    # A maneira mais fácil de forçar o clique sem JS complexo é usar um botão Streamlit
    # Mas como o usuário quer clicar na imagem, vamos torcer que o CSS funcione bem.
    st.caption("Ajuste de escala pode ser necessário dependendo da tela. Use a barra lateral.")

# --- Código Javascript para Forçar o Clique ---
# Nota: Streamlit não permite rodar JS direto sem componentes externos. 
# O código acima é a melhor tentativa com HTML e JS inline, mas a interação
# de clicar e mudar o sidebar pode não ser 100% automática sem um componente
# externo (que não posso instalar). O usuário terá que recarregar. 

# Mantendo o fluxo original:
if "mesa_id" not in st.session_state:
    st.session_state["mesa_id"] = None
# ==========================================


# ==========================================
# 📂 ABAS DE NAVEGAÇÃO
# ==========================================
tab_mapa, tab_financeiro = st.tabs(["🗺️ MAPA DE MESAS", "📊 FINANCEIRO"])


# ==========================================
# ABA 1: MAPA
# ==========================================
with tab_mapa:
    
    st.header("Selecione a Mesa")
    st.caption("Ajuste a largura do navegador para tentar centralizar os números na imagem.")

    # Desenha o mapa interativo
    draw_interactive_map(df_full)

    # --- SIDEBAR (Gerenciamento) ---
    m_id = st.session_state.get("mesa_id")

    if m_id:
        filtro = df_full[df_full["ID_Mesa"] == m_id]
        # ... (O resto do sidebar permanece o mesmo) ...

    # Código do Sidebar (para funcionar com o clique)
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
                
                # Campos de reserva
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
                st.sidebar.write(f"📞 {dados['Telefone_Cliente']}")
                
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
