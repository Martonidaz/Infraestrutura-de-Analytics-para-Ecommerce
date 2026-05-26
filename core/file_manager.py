import os
import pandas as pd

RAW_DATA_DIR = os.path.join("data", "raw")
PROCESSED_DATA_DIR = os.path.join("data", "processed")
HISTORICO_DB = os.path.join(PROCESSED_DATA_DIR, "banco_historico_vendas.parquet")

os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

MARKETPLACES = ["Mercado Livre", "Renner", "Loja Oficial", "Data System"]

def obter_abas(uploaded_file) -> list:
    """Se for CSV retorna uma aba fictícia, se for Excel lê as abas reais."""
    if uploaded_file.name.endswith('.csv'):
        return ["Dados CSV"]
    excel_file = pd.ExcelFile(uploaded_file, engine='calamine')
    return excel_file.sheet_names

def ler_amostra(uploaded_file, sheet_name, nrows=10) -> pd.DataFrame:
    """Lê as primeiras linhas de CSV ou Excel."""
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, nrows=nrows)
    else:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name, nrows=nrows, engine='calamine')
    
    for col in df.columns: df[col] = df[col].astype(str)
    return df

def ler_banco_completo() -> pd.DataFrame:
    """Retorna o banco de dados Parquet inteiro para inspeção do Gestor/Root."""
    if os.path.exists(HISTORICO_DB):
        return pd.read_parquet(HISTORICO_DB)
    return pd.DataFrame() # Retorna vazio se não existir

def processar_carga_incremental(uploaded_file, marketplace_selecionado, sheet_name) -> tuple[int, int]:
    """Processa um único arquivo e anexa ao banco (funciona para CSV e XLSX)."""
    nome_arquivo_seguro = f"{marketplace_selecionado.replace(' ', '_')}_{uploaded_file.name}"
    caminho_raw = os.path.join(RAW_DATA_DIR, nome_arquivo_seguro)
    with open(caminho_raw, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # Lógica de Leitura Condicional (CSV vs Excel)
    if uploaded_file.name.endswith('.csv'):
        df_novo = pd.read_csv(caminho_raw)
    else:
        df_novo = pd.read_excel(caminho_raw, sheet_name=sheet_name, engine='calamine')
    
    # Limpeza ETL
    df_novo.dropna(how='all', axis=1, inplace=True)
    df_novo.dropna(how='all', axis=0, inplace=True)
    
    for col in df_novo.columns:
        if df_novo[col].dtype == 'object':
            df_novo[col] = df_novo[col].astype(str)

    df_novo['Origem_Marketplace'] = marketplace_selecionado 
    linhas_novas = len(df_novo)

    # Anexo (Incremental)
    if os.path.exists(HISTORICO_DB):
        df_historico = pd.read_parquet(HISTORICO_DB)
        df_completo = pd.concat([df_historico, df_novo], ignore_index=True)
        df_completo = df_completo.drop_duplicates()
    else:
        df_completo = df_novo

    df_completo.to_parquet(HISTORICO_DB, index=False)
    linhas_totais = len(df_completo)
    
    return linhas_novas, linhas_totais