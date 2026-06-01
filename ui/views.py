import streamlit as st
import pandas as pd
import io
from datetime import datetime

from core import auth
from core import file_manager

def render_login():
    st.markdown("<h2>Acesso Restrito</h2>", unsafe_allow_html=True)
    
    usuario_sugerido = auth.carregar_lembrete()
    
    with st.form("form_login"):
        username_input = st.text_input("Usuário", value=usuario_sugerido, autocomplete="username")
        password = st.text_input("Senha", type="password", autocomplete="current-password")
        lembrar_me = st.checkbox("Lembrar meu usuário", value=bool(usuario_sugerido))
        
        if st.form_submit_button("Autenticar", use_container_width=True):
            sucesso, dados = auth.validar_login(username_input, password)
            if sucesso:
                st.session_state.logado = True
                st.session_state.username = username_input
                st.session_state.nome_usuario = dados["nome"]
                st.session_state.role = dados["role"]
                auth.salvar_lembrete(username_input, lembrar_me)
                st.rerun()
            else:
                st.error(dados.get("erro", "Falha no login."))
    st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard():
    st.markdown("""
        <style>
        .main { background-color: #0f172a; color: #f8fafc; }
        .stButton>button { background-color: #deff9a; color: #000000; font-weight: bold; border-radius: 8px; border: none; transition: all 0.3s ease; }
        .stButton>button:hover { background-color: #b5e550; color: #000000; box-shadow: 0px 0px 15px rgba(222, 255, 154, 0.6); }
        div[data-testid="stExpander"] { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }
        
        /* Estilização para as Abas do Streamlit parecerem menus de navegação modernos */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: #1e293b;
            border-radius: 8px 8px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
            border: 1px solid #334155;
            border-bottom: none;
        }
        .stTabs [aria-selected="true"] {
            background-color: #0f172a;
            color: #deff9a;
            border-bottom: 2px solid #deff9a;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- HEADER ---
    col_title, col_user, col_logout = st.columns([0.6, 0.3, 0.1])
    with col_title: st.title("⚡ Portal Interno de Analytics")
    with col_user:
        badge = "#deff9a" if st.session_state.role == "root" else "#94a3b8"
        st.markdown(f"""
            <div style="text-align: right; padding-top: 20px;">
                Logado como: <strong>{st.session_state.nome_usuario}</strong> <br>
                <span style="background-color: {badge}; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold;">
                    {str(st.session_state.role).upper()}
                </span>
            </div>
        """, unsafe_allow_html=True)
    with col_logout:
        st.write(""); 
        if st.button("Sair"): st.session_state.logado = False; st.rerun()
            
    st.markdown("---")

    # --- CONTROLE DE ACESSO AS ABAS ---
    if st.session_state.role == "root":
        # A Jornada Completa
        tab_ingestao, tab_etl, tab_modelagem, tab_dash, tab_admin = st.tabs([
            "📥 1. Ingestão", 
            "🛠️ 2. Transformação (ETL)", 
            "🕸️ 3. Modelagem", 
            "📊 4. Dashboards", 
            "⚙️ Painel Root"
        ])
    else:
        # Analistas veem apenas Dashboards (e talvez Ingestão, dependendo da sua regra)
        tab_dash, tab_ingestao = st.tabs(["📊 Dashboards", "📥 Ingestão"])
        tab_etl = tab_modelagem = tab_admin = None

    # ==========================================
    # GUIA 1: INGESTÃO (O código que já fizemos)
    # ==========================================
    with tab_ingestao:
        st.subheader("Módulo de Carga")
        origem_selecionada = st.selectbox("📍 Marketplace:", file_manager.MARKETPLACES, key="ing_mk")
        uploaded_files = st.file_uploader(f"Arraste as planilhas ({origem_selecionada})", type=["xlsx", "csv"], accept_multiple_files=True)
        
        if uploaded_files:
            for idx, file in enumerate(uploaded_files):
                with st.expander(f"Arquivo {idx+1}: {file.name}", expanded=True):
                    try:
                        abas = file_manager.obter_abas(file)
                        selected_sheet = st.selectbox("Aba:", abas, key=f"sheet_{file.name}")
                        df_vis = file_manager.ler_amostra(file, origem_selecionada, selected_sheet)
                        st.dataframe(df_vis, width='stretch')
                        if st.button(f"Processar {file.name}", key=f"btn_{file.name}"):
                            with st.spinner("Integrando..."):
                                l_novas, l_totais = file_manager.processar_carga_incremental(
                                    file, origem_selecionada, selected_sheet, st.session_state.nome_usuario, st.session_state.role
                                )
                            st.success(f"Carga concluída! Adicionadas {l_novas} linhas. Total do banco: {l_totais}.")
                    except Exception as e: st.error(f"Erro: {e}")

    # ==========================================
    # GUIA 2: TRANSFORMAÇÃO (Power Query Local)
    # ==========================================
    if tab_etl is not None:
        with tab_etl:
            st.subheader("🛠️ Motor de Transformação (ETL)")
            st.write("Selecione um banco de dados bruto para aplicar regras de limpeza, formatação e criação de colunas.")
            
            bancos = file_manager.listar_bancos_disponiveis()
            if bancos:
                # Cria uma lista bonita para o usuário ler, ex: "[Mercado Livre] db_mercado_livre_vendas_geral.parquet"
                opcoes_banco = {f"[{b['marketplace']}] {b['tipo']}": b for b in bancos}
                
                banco_alvo = st.selectbox("Selecione o contexto para transformar:", list(opcoes_banco.keys()))
                
                st.info("🚧 Área em construção. Aqui aplicaremos as regras customizadas (Remover Nulos, Formatar Texto, Injetar Regras).")
                
                # Mockup do que construiremos
                col_regra, col_aplicar = st.columns([0.8, 0.2])
                with col_regra:
                    st.selectbox("Adicionar Etapa Aplicada:", ["Nenhuma", "Remover Duplicatas", "Limpar Caracteres Especiais", "Criar Coluna Calculada"])
                with col_aplicar:
                    st.write("")
                    st.write("")
                    st.button("Aplicar Regra", disabled=True)
            else:
                st.warning("Não há bancos disponíveis para transformação. Vá na aba de Ingestão primeiro.")

    # ==========================================
    # GUIA 3: MODELAGEM E RELACIONAMENTOS
    # ==========================================
    if tab_modelagem is not None:
        with tab_modelagem:
            st.subheader("🕸️ Modelagem de Dados")
            st.write("Crie ligações (Joins) entre os diferentes bancos de dados para cruzar informações.")
            st.info("🚧 Área em construção. Aqui exibiremos o diagrama de rede (Node Graph) das tabelas.")

    # ==========================================
    # GUIA 4: DASHBOARDS (Visualização)
    # ==========================================
    with tab_dash:
        # Mesclamos o Explorador de Dados que fizemos antes para dentro desta aba,
        # pois analisar a tabela já é o primeiro passo da visualização.
        st.subheader("📊 Visualização e Exportação")
        bancos = file_manager.listar_bancos_disponiveis()
        
        if bancos:
            marketplaces_unicos = list(set([b['marketplace'] for b in bancos]))
            mk_escolhido = st.selectbox("1️⃣ Selecione o Marketplace:", marketplaces_unicos, key="dash_mk")
            df_mk = pd.concat([b["dataframe"] for b in bancos if b["marketplace"] == mk_escolhido], ignore_index=True)
            
            # (Mantido o código de visualização e exportação que já validamos)
            arquivos_no_banco = df_mk['Arquivo_Origem'].unique()
            arq_escolhido = st.selectbox("2️⃣ Planilha Fonte:", arquivos_no_banco, key="dash_arq")
            df_arq = df_mk[df_mk['Arquivo_Origem'] == arq_escolhido]
            
            modo_vis = st.radio("3️⃣ Visualizar:", ["Planilha Inteira", "Por Aba"], horizontal=True, key="dash_modo")
            if modo_vis == "Por Aba":
                abas_disp = df_arq['Aba_Origem'].unique()
                df_final = df_arq[df_arq['Aba_Origem'] == st.selectbox("Aba:", abas_disp, key="dash_aba")]
            else:
                df_final = df_arq
            
            st.dataframe(df_final, width='stretch', height=300)
            
            # Exportação
            col_csv, col_xls, col_pdf = st.columns(3)
            col_csv.download_button("Exportar CSV", data=df_final.to_csv(index=False, sep=',').encode('utf-8'), file_name="relatorio.csv", mime="text/csv", use_container_width=True)
            import io
            excel_buffer = io.BytesIO()
            df_final.to_excel(excel_buffer, index=False, engine='openpyxl')
            col_xls.download_button("Exportar XLSX", data=excel_buffer.getvalue(), file_name="relatorio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            html_data = f"<html><body><h2>Relatório - {arq_escolhido}</h2>{df_final.to_html(index=False)}</body></html>".encode('utf-8')
            col_pdf.download_button("Exportar PDF", data=html_data, file_name="relatorio.html", mime="text/html", help="Imprima como PDF", use_container_width=True)
            
            st.markdown("---")
            st.info("🚧 Em breve: Gráficos dinâmicos (Barras, Linhas, Pizza) aparecerão aqui.")

        else:
            st.warning("Faça a ingestão de dados para visualizar o Dashboard.")

    # ==========================================
    # GUIA 5: PAINEL ROOT (Segurança)
    # ==========================================
    if tab_admin is not None:
        with tab_admin:
            st.subheader("Gestão de Acessos")
            db_usuarios = auth.carregar_usuarios()
            df_users = pd.DataFrame.from_dict(db_usuarios, orient='index').reset_index()
            df_users.rename(columns={'index': 'Username'}, inplace=True)
            st.dataframe(df_users[['Username', 'nome', 'email', 'role', 'status', 'data_criacao']], width='stretch')
            
            st.markdown("---")
            col_novo, col_gerenciar = st.columns(2)
            with col_novo:
                st.markdown("### ➕ Novo Usuário")
                with st.form("form_novo"):
                    n_nome, n_user = st.text_input("Nome *"), st.text_input("Username *")
                    n_senha, n_role = st.text_input("Senha *", type="password"), st.selectbox("Acesso", ["analista", "root"])
                    if st.form_submit_button("Criar", use_container_width=True):
                        sucesso, msg = auth.registrar_usuario(n_nome, n_user, "", n_senha, n_role)
                        if sucesso: st.success(msg); st.rerun()
                        else: st.error(msg)
            with col_gerenciar:
                st.markdown("### ⚙️ Gerenciar")
                with st.form("form_gerenciar"):
                    usr = st.selectbox("Usuário", list(db_usuarios.keys()))
                    nvl = st.selectbox("Privilégio", ["analista", "root"], index=0 if db_usuarios[usr]['role'] == 'analista' else 1)
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Salvar Nível", use_container_width=True):
                        s, m = auth.alterar_privilegio(usr, nvl)
                        if s: st.success(m); st.rerun()
                        else: st.error(m)
                    if c2.form_submit_button("🚨 Excluir", use_container_width=True):
                        s, m = auth.excluir_usuario(usr)
                        if s: st.success(m); st.rerun()
                        else: st.error(m)

def render_app():
    st.set_page_config(page_title="Portal de Analytics", page_icon="⚡", layout="wide")
    if "logado" not in st.session_state:
        st.session_state.logado = False
        st.session_state.role = None
        st.session_state.nome_usuario = None
    if not st.session_state.logado: render_login()
    else: render_dashboard()