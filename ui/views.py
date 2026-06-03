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
        
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            height: 50px; white-space: pre-wrap; background-color: #1e293b;
            border-radius: 8px 8px 0px 0px; gap: 1px; padding-top: 10px;
            padding-bottom: 10px; border: 1px solid #334155; border-bottom: none;
        }
        .stTabs [aria-selected="true"] { background-color: #0f172a; color: #deff9a; border-bottom: 2px solid #deff9a; }
        </style>
    """, unsafe_allow_html=True)

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

    if st.session_state.role == "root":
        tab_ingestao, tab_etl, tab_modelagem, tab_dash, tab_admin = st.tabs([
            "📥 1. Ingestão", "🛠️ 2. Transformação (ETL)", "🕸️ 3. Modelagem", "📊 4. Dashboards", "⚙️ Painel Root"
        ])
    else:
        tab_dash, tab_ingestao = st.tabs(["📊 Dashboards", "📥 Ingestão"])
        tab_etl = tab_modelagem = tab_admin = None

    # ==========================================
    # GUIA 1: INGESTÃO (Com Alerta Prévio no Expander)
    # ==========================================
    with tab_ingestao:
        st.subheader("Módulo de Carga")
        origem_selecionada = st.selectbox("📍 Marketplace:", file_manager.MARKETPLACES, key="ing_mk")
        uploaded_files = st.file_uploader(f"Arraste as planilhas ({origem_selecionada})", type=["xlsx", "csv"], accept_multiple_files=True)
        
        if uploaded_files:
            for idx, file in enumerate(uploaded_files):
                
                # 1. VERIFICAÇÃO ANTECIPADA (Antes de desenhar a interface)
                try:
                    ja_existe = file_manager.verificar_arquivo_existe(origem_selecionada, file.name)
                except Exception:
                    ja_existe = False # Prevenção caso seja o primeiro upload do sistema
                
                # 2. TITULO DINÂMICO DA CAIXA (Notificação visual para o usuário)
                if ja_existe:
                    titulo_expander = f"⚠️ ALERTA: '{file.name}' já existe no banco!"
                else:
                    titulo_expander = f"📄 Arquivo {idx+1}: {file.name}"

                # 3. CRIAÇÃO DA CAIXA
                with st.expander(titulo_expander, expanded=False):
                    try:
                        if ja_existe:
                            st.error("🚨 **ATENÇÃO: PLANILHA DUPLICADA DETECTADA!**\n\nEste arquivo já consta no banco de dados. Se você prosseguir, os dados antigos serão apagados e **SUBSTITUÍDOS** pela versão que você está subindo agora.")
                            texto_botao = f"🔄 Confirmar Substituição"
                        else:
                            texto_botao = f"▶️ Processar {file.name}"

                        abas = file_manager.obter_abas(file)
                        selected_sheet = st.selectbox("Aba:", abas, key=f"sheet_{file.name}")
                        df_vis = file_manager.ler_amostra(file, origem_selecionada, selected_sheet)
                        
                        st.dataframe(df_vis, height=150, use_container_width=True)
                        
                        if st.button(texto_botao, key=f"btn_{file.name}"):
                            with st.spinner("Integrando..."):
                                l_novas, l_totais = file_manager.processar_carga_incremental(
                                    file, origem_selecionada, selected_sheet, st.session_state.nome_usuario, st.session_state.role
                                )
                            st.success(f"Carga concluída! Processadas {l_novas} linhas. Total consolidado no banco: {l_totais}.")
                    except Exception as e: 
                        st.error(f"Erro ao ler arquivo: {e}")

    # ==========================================
    # GUIA 2: TRANSFORMAÇÃO (Power Query Local)
    # ==========================================
    if tab_etl is not None:
        with tab_etl:
            st.subheader("🛠️ Motor de Transformação (Exibição de Dados)")
            st.write("Visualize os dados brutos, aplique regras e gerencie as planilhas do banco.")
            
            bancos = file_manager.listar_bancos_disponiveis()
            if bancos:
                mk_escolhido = st.selectbox("1️⃣ Selecione o Marketplace para explorar:", list(set([b['marketplace'] for b in bancos])), key="etl_mk")
                df_mk = pd.concat([b["dataframe"] for b in bancos if b["marketplace"] == mk_escolhido], ignore_index=True)
                
                arquivos_no_banco = df_mk['Arquivo_Origem'].unique()
                
                col_sel_arq, col_btn_del = st.columns([0.8, 0.2])
                with col_sel_arq:
                    arq_escolhido = st.selectbox("2️⃣ Selecione a Planilha (Sessão):", arquivos_no_banco, key="etl_arq")
                with col_btn_del:
                    st.write("") 
                    st.write("")
                    # CORREÇÃO 3: Popover atua como um botão que abre uma janela de confirmação de exclusão
                    with st.popover("🗑️ Excluir do Banco", use_container_width=True):
                        st.markdown(f"**Deletar permanentemente?**")
                        st.write(f"Você está prestes a apagar os dados de `{arq_escolhido}`.")
                        # Botão com type="primary" para ficar destacado (vermelho na maioria dos temas)
                        if st.button("Sim, apagar dados", type="primary", use_container_width=True):
                            tipo_rel = df_mk[df_mk['Arquivo_Origem'] == arq_escolhido]['Tipo_Relatorio'].iloc[0]
                            file_manager.deletar_arquivo_do_banco(mk_escolhido, tipo_rel, arq_escolhido)
                            st.success("Planilha excluída com sucesso!")
                            st.rerun()
                
                df_arq = df_mk[df_mk['Arquivo_Origem'] == arq_escolhido]
                
                modo_vis = st.radio("3️⃣ Visualizar:", ["Planilha Inteira", "Por Aba"], horizontal=True, key="etl_modo")
                if modo_vis == "Por Aba":
                    abas_disp = df_arq['Aba_Origem'].unique()
                    df_final = df_arq[df_arq['Aba_Origem'] == st.selectbox("Aba:", abas_disp, key="etl_aba")]
                else:
                    df_final = df_arq
                
                st.markdown("---")
                
                col_tabela, col_regras = st.columns([0.75, 0.25])
                
                with col_tabela:
                    st.metric("Linhas Visíveis", len(df_final))
                    st.dataframe(df_final, width='stretch', height=500)
                    
                    c_csv, c_xls, c_pdf = st.columns(3)
                    c_csv.download_button("Exportar CSV", data=df_final.to_csv(index=False, sep=',').encode('utf-8'), file_name="dados.csv", mime="text/csv", use_container_width=True)
                    import io
                    excel_buffer = io.BytesIO()
                    df_final.to_excel(excel_buffer, index=False, engine='openpyxl')
                    c_xls.download_button("Exportar XLSX", data=excel_buffer.getvalue(), file_name="dados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
                    html_data = f"<html><body><h2>Tabela - {arq_escolhido}</h2>{df_final.to_html(index=False)}</body></html>".encode('utf-8')
                    c_pdf.download_button("Exportar PDF", data=html_data, file_name="dados.html", mime="text/html", help="Imprima como PDF", use_container_width=True)

                with col_regras:
                    st.markdown("### ⚙️ Etapas Aplicadas")
                    st.info("Modelo Estrela (Star Schema) pronto para execução via ETL Engine.")
                    
                    st.write("**Tabelas que serão geradas:**")
                    st.markdown("- 🧊 dClientes\n- 🧊 dProdutos\n- 🧊 dLogistica\n- 🔥 fVendas")
                    st.write("")
                    
                    # O botão mágico!
                    if st.button("🚀 Executar Limpeza", use_container_width=True, type="primary"):
                        with st.spinner("A modelar dados..."):
                            try:
                                # df_mk é o dataframe do marketplace inteiro que já está na memória do Streamlit
                                resumo = file_manager.executar_pipeline_ouro(mk_escolhido, df_mk)
                                st.success("Pipeline Ouro finalizado com sucesso!")
                                st.write("Resumo da Modelagem:")
                                st.json(resumo)
                            except Exception as e:
                                st.error(f"Erro no processamento: {e}")
            else:
                st.warning("Não há bancos disponíveis para transformação. Vá na aba de Ingestão primeiro.")

    # ==========================================
    # GUIA 3: MODELAGEM E RELACIONAMENTOS
    # ==========================================
    if tab_modelagem is not None:
        with tab_modelagem:
            st.subheader("🕸️ Modelagem de Dados")
            st.write("Crie ligações (Joins) entre os diferentes bancos de dados para cruzar informações.")
            st.info("🚧 Área em construção.")

    # ==========================================
    # GUIA 4: DASHBOARDS (Exibição de Relatório)
    # ==========================================
    with tab_dash:
        st.subheader("📊 Construtor de Relatórios")
        st.write("Selecione os dados transformados para compor os painéis visuais.")
        
        bancos = file_manager.listar_bancos_disponiveis()
        if bancos:
            col_controles, col_canvas = st.columns([0.25, 0.75])
            with col_controles:
                st.markdown("### 🎨 Visualização")
                mk_graf = st.selectbox("Fonte de Dados:", list(set([b['marketplace'] for b in bancos])), key="graf_mk")
                st.selectbox("Tipo de Gráfico:", ["Gráfico de Barras", "Gráfico de Linhas", "Gráfico de Pizza", "Tabela Resumo"])
                st.selectbox("Eixo X (Categoria):", ["Data_Ingestao", "Arquivo_Origem"])
                st.selectbox("Eixo Y (Valores):", ["Contagem de Linhas", "Faturamento Total (BETA)"])
                st.button("Gerar Gráfico", use_container_width=True, disabled=True)
            with col_canvas:
                st.markdown("<div style='height: 500px; border: 2px dashed #334155; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 20px;'>Área de Renderização dos Gráficos (Plotly)</div>", unsafe_allow_html=True)
        else:
            st.warning("Faça a ingestão de dados para criar Dashboards.")

    # ==========================================
    # GUIA 5: PAINEL ROOT
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