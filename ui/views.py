import streamlit as st
import pandas as pd
import io
from datetime import datetime

from core import auth
from core import file_manager

def render_login():
    st.markdown("""
        <style>
        .login-box { background-color: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; max-width: 450px; margin: 80px auto; }
        .header-logo { text-align: center; font-size: 50px; margin-bottom: 0px; }
        h2 { color: #deff9a; text-align: center; margin-top: 0px; }
        .stButton>button { background-color: #deff9a; color: #000000; font-weight: bold; border-radius: 8px; border: none; transition: all 0.3s ease; }
        .stButton>button:hover { background-color: #b5e550; color: #000000; box-shadow: 0px 0px 15px rgba(222, 255, 154, 0.6); border-color: #deff9a; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="header-logo">⚡</div>', unsafe_allow_html=True)
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
        </style>
    """, unsafe_allow_html=True)

    col_title, col_user, col_logout = st.columns([0.6, 0.3, 0.1])
    with col_title:
        st.title("⚡ Portal Interno de Analytics")
    with col_user:
        badge_color = "#deff9a" if st.session_state.role == "root" else "#94a3b8"
        st.markdown(f"""
            <div style="text-align: right; padding-top: 20px;">
                Logado como: <strong>{st.session_state.nome_usuario}</strong> <br>
                <span style="background-color: {badge_color}; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: bold;">
                    {str(st.session_state.role).upper()}
                </span>
            </div>
        """, unsafe_allow_html=True)
    with col_logout:
        st.write("") 
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
            
    st.markdown("---")

    if st.session_state.role == "root":
        tab_ingestao, tab_inspecao, tab_admin = st.tabs(["📥 Ingestão", "🔍 Explorador de Dados", "⚙️ Painel Root"])
    else:
        tab_ingestao, tab_inspecao = st.tabs(["📥 Ingestão", "🔍 Explorador de Dados"])
        tab_admin = None

    # ==========================================
    # ABA 1: INGESTÃO (Mais Limpa - Sem Tipo de Relatório)
    # ==========================================
    with tab_ingestao:
        st.subheader("Módulo de Carga")
        origem_selecionada = st.selectbox("📍 Marketplace:", file_manager.MARKETPLACES)
        
        uploaded_files = st.file_uploader(
            f"Arraste as planilhas ({origem_selecionada})", 
            type=["xlsx", "csv"], 
            accept_multiple_files=True
        )

        if uploaded_files:
            for idx, file in enumerate(uploaded_files):
                with st.expander(f"Arquivo {idx+1}: {file.name}", expanded=True):
                    try:
                        abas = file_manager.obter_abas(file)
                        selected_sheet = st.selectbox(f"Aba:", abas, key=f"sheet_{file.name}")
                        
                        df_vis = file_manager.ler_amostra(file, origem_selecionada, selected_sheet)
                        st.dataframe(df_vis, width='stretch')
                        
                        if st.button(f"Processar {file.name}", key=f"btn_{file.name}"):
                            with st.spinner("Integrando..."):
                                l_novas, l_totais = file_manager.processar_carga_incremental(
                                    file, origem_selecionada, selected_sheet,
                                    st.session_state.nome_usuario, st.session_state.role
                                )
                            st.success(f"Carga concluída! Adicionadas {l_novas} linhas. Total do banco: {l_totais}.")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    # ==========================================
    # ABA 2: EXPLORADOR DE DADOS (Um Arquivo por Vez)
    # ==========================================
    with tab_inspecao:
        st.subheader("🔍 Explorador de Bancos e Arquivos")
        
        bancos = file_manager.listar_bancos_disponiveis()
        
        if bancos:
            # 1. Filtra Marketplace
            marketplaces_unicos = list(set([b['marketplace'] for b in bancos]))
            mk_escolhido = st.selectbox("1️⃣ Selecione o Marketplace:", marketplaces_unicos)
            
            # Combina todos os dados daquele marketplace de forma isolada
            df_mk = pd.concat([b["dataframe"] for b in bancos if b["marketplace"] == mk_escolhido], ignore_index=True)
            
            # 2. Mostra Auditoria do Marketplace
            st.markdown(f"### 🗂️ Histórico de Uploads - {mk_escolhido}")
            rastreabilidade = df_mk.groupby(['Arquivo_Origem', 'Tipo_Relatorio', 'Data_Ingestao', 'Usuario_Carga', 'Privilegio']).size().reset_index(name='Linhas Salvas')
            st.dataframe(rastreabilidade, hide_index=True, width='stretch')
            st.markdown("---")
            
            # 3. Seleção de APENAS UM arquivo
            arquivos_no_banco = df_mk['Arquivo_Origem'].unique()
            arq_escolhido = st.selectbox("2️⃣ Selecione a Planilha que deseja visualizar:", arquivos_no_banco)
            
            df_arq = df_mk[df_mk['Arquivo_Origem'] == arq_escolhido]
            
            # 4. Modo de Visualização (Planilha Inteira vs Por Aba)
            modo_vis = st.radio("3️⃣ Modo de Visualização:", ["Planilha Inteira", "Por Aba"], horizontal=True)
            
            if modo_vis == "Por Aba":
                abas_disp = df_arq['Aba_Origem'].unique()
                aba_escolhida = st.selectbox("Selecione a Aba:", abas_disp)
                df_final = df_arq[df_arq['Aba_Origem'] == aba_escolhida]
            else:
                df_final = df_arq
            
            st.markdown("### 📊 Dados Brutos")
            st.metric("Linhas Visíveis", len(df_final))
            st.dataframe(df_final, width='stretch', height=400)
            
            # --- EXPORTAÇÃO CORRIGIDA ---
            st.markdown("### ⬇️ Exportar Relatório")
            col_csv, col_xls, col_pdf = st.columns(3)
            
            # A. CSV Padrão (Vírgula)
            csv_data = df_final.to_csv(index=False, sep=',').encode('utf-8')
            col_csv.download_button("Exportar CSV", data=csv_data, file_name="relatorio.csv", mime="text/csv", use_container_width=True)
            
            # B. XLSX Nativo
            excel_buffer = io.BytesIO()
            df_final.to_excel(excel_buffer, index=False, engine='openpyxl')
            col_xls.download_button("Exportar XLSX", data=excel_buffer.getvalue(), file_name="relatorio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            # C. Relatório Web/PDF (O usuário imprime como PDF pelo navegador)
            html_data = f"""
            <html><head><title>Relatório PDF</title><style>table {{border-collapse: collapse; width: 100%; font-family: sans-serif; font-size: 10px;}} th, td {{border: 1px solid #ddd; padding: 8px; text-align: left;}} th {{background-color: #f2f2f2;}}</style></head>
            <body><h2>Relatório de Dados - {arq_escolhido}</h2>{df_final.to_html(index=False)}</body></html>
            """.encode('utf-8')
            col_pdf.download_button("Exportar PDF (HTML Web)", data=html_data, file_name="relatorio.html", mime="text/html", help="Abre no navegador. Pressione Ctrl+P e escolha 'Salvar como PDF'.", use_container_width=True)

        else:
            st.info("Nenhum banco de dados foi processado ainda.")

    # ==========================================
    # ABA 3: PAINEL ROOT (COM EDIÇÃO/EXCLUSÃO)
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
            
            # Criar Novo
            with col_novo:
                st.markdown("### ➕ Criar Novo Usuário")
                with st.form("form_novo_usuario"):
                    novo_nome = st.text_input("Nome Completo *")
                    novo_username = st.text_input("Username (Login) *")
                    nova_senha = st.text_input("Senha Temporária *", type="password")
                    novo_role = st.selectbox("Nível de Acesso", ["analista", "root"])
                    if st.form_submit_button("Cadastrar", use_container_width=True):
                        if not novo_nome or not novo_username or not nova_senha: st.warning("Preencha campos obrigatórios.")
                        else:
                            sucesso, msg = auth.registrar_usuario(novo_nome, novo_username, "", nova_senha, novo_role)
                            if sucesso: st.success(msg); st.rerun()
                            else: st.error(msg)
            
            # Gerenciar Existente
            with col_gerenciar:
                st.markdown("### ⚙️ Gerenciar Usuário")
                with st.form("form_gerenciar_usuario"):
                    usr_selecionado = st.selectbox("Selecione o Usuário", list(db_usuarios.keys()))
                    novo_nivel = st.selectbox("Alterar Privilégio para:", ["analista", "root"], index=0 if db_usuarios[usr_selecionado]['role'] == 'analista' else 1)
                    
                    c1, c2 = st.columns(2)
                    if c1.form_submit_button("Salvar Nível", use_container_width=True):
                        sucesso, msg = auth.alterar_privilegio(usr_selecionado, novo_nivel)
                        if sucesso: st.success(msg); st.rerun()
                        else: st.error(msg)
                    
                    if c2.form_submit_button("🚨 Excluir Usuário", use_container_width=True):
                        sucesso, msg = auth.excluir_usuario(usr_selecionado)
                        if sucesso: st.success(msg); st.rerun()
                        else: st.error(msg)

def render_app():
    st.set_page_config(page_title="Portal de Analytics", page_icon="⚡", layout="wide")
    if "logado" not in st.session_state:
        st.session_state.logado = False
        st.session_state.role = None
        st.session_state.nome_usuario = None
    if not st.session_state.logado: render_login()
    else: render_dashboard()