import os
import pandas as pd
from core import etl_engine

RAW_DATA_DIR = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")
GOLD_DATA_DIR = os.path.join("data", "gold") # NOVA PASTA PARA O MODELO ESTRELA

os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(GOLD_DATA_DIR, exist_ok=True) # Cria a pasta fisicamente se não existir


ESTRUTURA_DADOS = {
    "Mercado Livre": { "Vendas (Geral)": {"skiprows": 5}, "Repasse Financeiro (Mercado Pago)": {"skiprows": 0} },
    "Renner": { "Vendas (Geral)": {"skiprows": 0} },
    "Loja Oficial": { "Vendas (Geral)": {"skiprows": 0} },
    "Data System": { "Vendas (Geral)": {"skiprows": 0} }
}
MARKETPLACES = list(ESTRUTURA_DADOS.keys())

def obter_tipos_relatorio(marketplace): return list(ESTRUTURA_DADOS[marketplace].keys())

def gerar_nome_banco(marketplace, tipo_relatorio):
    mk_limpo = marketplace.replace(' ', '_').lower()
    tp_limpo = tipo_relatorio.replace(' ', '_').replace('(', '').replace(')', '').lower()
    return os.path.join(PROCESSED_DATA_DIR, f"db_{mk_limpo}_{tp_limpo}.parquet")

def obter_abas(uploaded_file) -> list:
    if uploaded_file.name.endswith('.csv'): return ["Dados CSV"]
    excel_file = pd.ExcelFile(uploaded_file, engine='calamine')
    return excel_file.sheet_names

def auto_detectar_tipo_e_pulo(marketplace, filename):
    nome_min = filename.lower()
    if marketplace == "Mercado Livre":
        if "collection" in nome_min or "repasse" in nome_min: return "Repasse Financeiro (Mercado Pago)", 0
        else: return "Vendas (Geral)", 5 
    return "Vendas (Geral)", 0

def ler_amostra(uploaded_file, marketplace, sheet_name, nrows=10) -> pd.DataFrame:
    tipo, pular = auto_detectar_tipo_e_pulo(marketplace, uploaded_file.name)
    if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file, skiprows=pular, nrows=nrows)
    else: df = pd.read_excel(uploaded_file, sheet_name=sheet_name, skiprows=pular, nrows=nrows, engine='calamine')
    for col in df.columns: df[col] = df[col].astype(str)
    return df

def processar_carga_incremental(uploaded_file, marketplace, sheet_name, usuario, privilegio) -> tuple[int, int]:
    tipo_relatorio, pular = auto_detectar_tipo_e_pulo(marketplace, uploaded_file.name)
    
    nome_raw = f"{marketplace.replace(' ', '_')}_{tipo_relatorio.replace(' ', '')}_{uploaded_file.name}"
    caminho_raw = os.path.join(RAW_DATA_DIR, nome_raw)
    with open(caminho_raw, "wb") as f: f.write(uploaded_file.getbuffer())

    if uploaded_file.name.endswith('.csv'): df_novo = pd.read_csv(caminho_raw, skiprows=pular)
    else: df_novo = pd.read_excel(caminho_raw, sheet_name=sheet_name, skiprows=pular, engine='calamine')
    
    df_novo.dropna(how='all', axis=1, inplace=True)
    df_novo.dropna(how='all', axis=0, inplace=True)
    for col in df_novo.columns:
        if df_novo[col].dtype == 'object': df_novo[col] = df_novo[col].astype(str)

    df_novo['Origem_Marketplace'] = marketplace 
    df_novo['Tipo_Relatorio'] = tipo_relatorio
    df_novo['Arquivo_Origem'] = uploaded_file.name
    df_novo['Aba_Origem'] = sheet_name
    df_novo['Data_Ingestao'] = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
    df_novo['Usuario_Carga'] = usuario
    df_novo['Privilegio'] = privilegio
    
    linhas_novas = len(df_novo)
    banco_alvo = gerar_nome_banco(marketplace, tipo_relatorio)

    if os.path.exists(banco_alvo):
        df_historico = pd.read_parquet(banco_alvo)
        
        # SOBRESCRITA INTELIGENTE: Se o arquivo já existe no banco, apagamos a versão velha antes de colar a nova.
        df_historico = df_historico[df_historico['Arquivo_Origem'] != uploaded_file.name]
        
        df_completo = pd.concat([df_historico, df_novo], ignore_index=True)
    else:
        df_completo = df_novo

    colunas_auditoria = ['Origem_Marketplace', 'Tipo_Relatorio', 'Arquivo_Origem', 'Aba_Origem', 'Data_Ingestao', 'Usuario_Carga', 'Privilegio']
    colunas_dados = [col for col in df_completo.columns if col not in colunas_auditoria]
    
    df_completo = df_completo.drop_duplicates(subset=colunas_dados, keep='last')
    
    df_completo.to_parquet(banco_alvo, index=False)
    return linhas_novas, len(df_completo)

# --- NOVAS FUNÇÕES PARA GESTÃO DE SESSÃO ---
def verificar_arquivo_existe(marketplace, nome_arquivo):
    tipo, _ = auto_detectar_tipo_e_pulo(marketplace, nome_arquivo)
    banco_alvo = gerar_nome_banco(marketplace, tipo)
    if os.path.exists(banco_alvo):
        df = pd.read_parquet(banco_alvo)
        if 'Arquivo_Origem' in df.columns:
            return nome_arquivo in df['Arquivo_Origem'].values
    return False

def deletar_arquivo_do_banco(marketplace, tipo_relatorio, nome_arquivo) -> bool:
    banco_alvo = gerar_nome_banco(marketplace, tipo_relatorio)
    if os.path.exists(banco_alvo):
        df = pd.read_parquet(banco_alvo)
        df_filtrado = df[df['Arquivo_Origem'] != nome_arquivo]
        if len(df_filtrado) == 0:
            os.remove(banco_alvo) # Deleta o banco inteiro se ficar vazio
        else:
            df_filtrado.to_parquet(banco_alvo, index=False)
        return True
    return False

def listar_bancos_disponiveis():
    bancos = []
    if os.path.exists(PROCESSED_DATA_DIR):
        for file in os.listdir(PROCESSED_DATA_DIR):
            if file.endswith('.parquet'):
                caminho = os.path.join(PROCESSED_DATA_DIR, file)
                df = pd.read_parquet(caminho)
                marketplace = df['Origem_Marketplace'].iloc[0] if not df.empty and 'Origem_Marketplace' in df.columns else "Desconhecido"
                tipo = df['Tipo_Relatorio'].iloc[0] if not df.empty and 'Tipo_Relatorio' in df.columns else "Desconhecido"
                bancos.append({
                    "arquivo": file, "marketplace": marketplace, "tipo": tipo, "caminho": caminho, "dataframe": df
                })
    return bancos

def executar_pipeline_ouro(marketplace, df_bruto):
    """
    Passa o dataframe bruto pelo motor de ETL e guarda o Modelo Estrela na pasta Gold.
    """
    # 0. Separação: Vendas vs Repasse Mercado Pago
    df_vendas_bruto = df_bruto[df_bruto['Tipo_Relatorio'] == 'Vendas (Geral)'].copy()
    df_mp_bruto = df_bruto[df_bruto['Tipo_Relatorio'] == 'Repasse Financeiro (Mercado Pago)'].copy()
    
    if df_vendas_bruto.empty:
        raise ValueError("Nenhum dado de 'Vendas (Geral)' foi encontrado para este Marketplace.")

    # 1. Camada Prata (Limpeza Base)
    df_vendas_prata = etl_engine.limpar_base_vendas_ml(df_vendas_bruto)
    df_mp_prata = etl_engine.limpar_data_liberacao_mp(df_mp_bruto)
    
    # 1.5. A UNIFICAÇÃO (Busca Inteligente)
    df_prata_unificada = etl_engine.unificar_vendas_repasse(df_vendas_prata, df_mp_prata)
    
    # 2. Extração das Dimensões e Tabela Fato
    d_clientes = etl_engine.extrair_dclientes(df_prata_unificada)
    d_produtos = etl_engine.extrair_dprodutos(df_prata_unificada)
    d_logistica = etl_engine.extrair_dlogistica(df_prata_unificada)
    f_vendas = etl_engine.extrair_fvendas(df_prata_unificada)
    
    # 3. Guardar no banco de dados Ouro (Gold)
    mk_limpo = marketplace.replace(' ', '_').lower()
    
    d_clientes.to_parquet(os.path.join(GOLD_DATA_DIR, f"dim_clientes_{mk_limpo}.parquet"), index=False)
    d_produtos.to_parquet(os.path.join(GOLD_DATA_DIR, f"dim_produtos_{mk_limpo}.parquet"), index=False)
    d_logistica.to_parquet(os.path.join(GOLD_DATA_DIR, f"dim_logistica_{mk_limpo}.parquet"), index=False)
    f_vendas.to_parquet(os.path.join(GOLD_DATA_DIR, f"fato_vendas_{mk_limpo}.parquet"), index=False)
    
    resumo = {
        "Clientes Únicos (dClientes)": len(d_clientes),
        "Produtos Únicos (dProdutos)": len(d_produtos),
        "Registos de Envios (dLogistica)": len(d_logistica),
        "Total de Transações (fVendas)": len(f_vendas)
    }
    
    return resumo, df_prata_unificada