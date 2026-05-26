import streamlit as st
import pandas as pd
from datetime import datetime

from core import auth
from core import file_manager

def render_login():
    st.markdown("""
        <style>
        .login-box { background-color: #1e293b; padding: 40px; border-radius: 12px; border: 1px solid #334155; max-width: 450px; margin: 80px auto; }
        .header-logo { text-align: center; font-size: 50px; margin-bottom: 0px; }
        h2 { color: #deff9a; text-align: center; margin-top: 0px; }
        /* CSS do Hover Consertado */
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

    # Nova estrutura de Abas: Adicionada a aba de Inspeção
    if st.session_state.role == "root":
        tab_ingestao, tab_inspecao, tab_admin = st.tabs(["📥 Ingestão Incremental", "🔍 Inspecionar Banco", "⚙️ Painel Root"])
    else:
        tab_ingestao = st.container()
        tab_inspecao = None
        tab_admin = None

    # ABA 1: INGESTÃO
    with tab_ingestao:
        st.subheader("Módulo de Carga em Lote (.xlsx ou .csv)")
        
        origem_selecionada = st.selectbox("📍 Origem destes dados:", file_manager.MARKETPLACES)
        
        # Agora o upload aceita múltiplos arquivos e CSVs
        uploaded_files = st.file_uploader(
            f"Arraste os arquivos recentes ({origem_selecionada})", 
            type=["xlsx", "csv"], 
            accept_multiple_files=True
        )

        if uploaded_files:
            st.markdown(f"**{len(uploaded_files)} arquivo(s) detectado(s).**")
            
            # Loop por cada arquivo para organizar a UI
            for idx, file in enumerate(uploaded_files):
                with st.expander(f"📄 Arquivo {idx+1}: {file.name}", expanded=True):
                    # 4 Colunas incluindo Data e Hora
                    col1, col2, col3, col4 = st.columns(4)
                    with col1: st.metric("Arquivo", file.name)
                    with col2: st.metric("Tamanho", f"{file.size / 1024:.2f} KB")
                    with col3: st.metric("Marketplace", origem_selecionada)
                    with col4: st.metric("Data Local", datetime.now().strftime("%d/%m/%Y %H:%M"))

                    try:
                        abas = file_manager.obter_abas(file)
                        selected_sheet = st.selectbox(f"Aba para carga ({file.name}):", abas, key=f"sheet_{file.name}")
                        
                        df_vis = file_manager.ler_amostra(file, selected_sheet)
                        st.dataframe(df_vis, width='stretch')
                        
                        # Botão individual para cada arquivo
                        if st.button(f"Processar {file.name}", key=f"btn_{file.name}"):
                            with st.spinner("Integrando ao banco histórico..."):
                                l_novas, l_totais = file_manager.processar_carga_incremental(file, origem_selecionada, selected_sheet)
                            st.success(f"🎉 Carga de '{file.name}' concluída!")
                            st.info(f"📊 Adicionadas **{l_novas} linhas**. Total no banco: **{l_totais} registros**.")
                    except Exception as e:
                        st.error(f"Erro ao ler arquivo: {e}")

    # ABA 2: INSPECIONAR BANCO (Só aparece para o root)
    if tab_inspecao is not None:
        with tab_inspecao:
            st.subheader("Visualização Raw do Banco Parquet")
            st.write("Aqui você audita os dados processados antes que eles vão para o dashboard final.")
            
            df_banco = file_manager.ler_banco_completo()
            
            if not df_banco.empty:
                st.metric("Total de Registros Oficiais", len(df_banco))
                st.dataframe(df_banco, width='stretch', height=400)
                
                # Permite baixar o banco em CSV para auditoria externa
                st.download_button(
                    label="⬇️ Baixar Banco Completo (CSV)",
                    data=df_banco.to_csv(index=False).encode('utf-8'),
                    file_name="banco_vendas_auditoria.csv",
                    mime="text/csv"
                )
            else:
                st.warning("O banco histórico está vazio. Faça uma ingestão primeiro.")

    # ABA 3: PAINEL ROOT
    if tab_admin is not None:
        with tab_admin:
            st.subheader("Gestão de Acessos")
            db_usuarios = auth.carregar_usuarios()
            df_users = pd.DataFrame.from_dict(db_usuarios, orient='index').reset_index()
            df_users.rename(columns={'index': 'Username'}, inplace=True)
            st.dataframe(df_users[['Username', 'nome', 'email', 'role', 'status', 'data_criacao']], width='stretch')
            
            st.markdown("---")
            with st.form("form_novo_usuario"):
                col1, col2 = st.columns(2)
                with col1:
                    novo_nome = st.text_input("Nome Completo *")
                    novo_username = st.text_input("Username (Login) *")
                    novo_email = st.text_input("E-mail (Opcional)")
                with col2:
                    nova_senha = st.text_input("Senha Temporária *", type="password")
                    novo_role = st.selectbox("Nível de Acesso", ["analista", "root"])
                    st.write(""); st.write("")
                    submit_novo = st.form_submit_button("Cadastrar Usuário", use_container_width=True)
                
                if submit_novo:
                    sucesso, msg = auth.registrar_usuario(novo_nome, novo_username, novo_email, nova_senha, novo_role)
                    if sucesso:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

def render_app():
    st.set_page_config(page_title="Portal de Analytics", page_icon="⚡", layout="wide")

    if "logado" not in st.session_state:
        st.session_state.logado = False
        st.session_state.role = None
        st.session_state.nome_usuario = None

    if not st.session_state.logado:
        render_login()
    else:
        render_dashboard()