import os
import pandas as pd

RAW_DATA_DIR = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")

os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

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
    df_novo['Aba_Origem'] = sheet_name # NOVO: Rastreando a Aba
    df_novo['Data_Ingestao'] = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
    df_novo['Usuario_Carga'] = usuario
    df_novo['Privilegio'] = privilegio
    
    linhas_novas = len(df_novo)
    banco_alvo = gerar_nome_banco(marketplace, tipo_relatorio)

    if os.path.exists(banco_alvo):
        df_historico = pd.read_parquet(banco_alvo)
        df_completo = pd.concat([df_historico, df_novo], ignore_index=True)
        df_completo = df_completo.drop_duplicates()
    else:
        df_completo = df_novo

    df_completo.to_parquet(banco_alvo, index=False)
    return linhas_novas, len(df_completo)

def listar_bancos_disponiveis():
    bancos = []
    if os.path.exists(PROCESSED_DATA_DIR):
        for file in os.listdir(PROCESSED_DATA_DIR):
            if file.endswith('.parquet'):
                caminho = os.path.join(PROCESSED_DATA_DIR, file)
                df = pd.read_parquet(caminho)
                marketplace = df['Origem_Marketplace'].iloc[0] if not df.empty and 'Origem_Marketplace' in df.columns else "Desconhecido"
                bancos.append({
                    "marketplace": marketplace,
                    "dataframe": df
                })
    return bancos