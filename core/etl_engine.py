import pandas as pd
import numpy as np
import warnings

# Silencia o aviso do Pandas sobre adivinhação de formato de data
warnings.filterwarnings("ignore", message="Could not infer format")

# =====================================================================
# ETL ENGINE - CAMADA PRATA (LIMPEZA ML)
# =====================================================================
def limpar_base_vendas_ml(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # BLINDAGEM 1: Remove espaços invisíveis no início e fim de todas as colunas
    df.columns = df.columns.astype(str).str.strip()

    col_mapping = {
        "N.º de venda": "ID_Venda", "Data da venda": "Data da Compra", "Estado": "Status",
        "Unidades": "Unidades Compradas", "Receita por produtos (BRL)": "Receita por Produto",
        "Tarifa de venda e impostos (BRL)": "Impostos", "Tarifas de envio (BRL)": "Tarifas Envio",
        "Descontos e bônus": "Descontos", "Cancelamentos e reembolsos (BRL)": "Taxa Cancelamento",
        "Total (BRL)": "Valor Total", "Loja oficial": "Loja Oficial", "Título do anúncio": "Nome Anuncio",
        "Preço unitário de venda do anúncio (BRL)": "Valor Venda", "Tipo de anúncio": "Tipo Anuncio",
        "NF-e em anexo": "NFE em Anexo", "Dados pessoais ou da empresa": "Nome Cliente",
        "Endereço": "Endereco Cliente", "Motorista": "Responsavel Envio", "Estado_2": "Estado Envio",
        "Cidade": "Cidade Envio", "País": "Pais", "Número de rastreamento": "Numero Rastreamento",
        "Variação": "Variação"
    }
    df.rename(columns=col_mapping, inplace=True, errors='ignore')

    chaves_upsert = ["ID_Venda", "Nome Anuncio", "Variação"]
    chaves_existentes = [c for c in chaves_upsert if c in df.columns]
    if chaves_existentes:
        df = df.drop_duplicates(subset=chaves_existentes, keep='last')

    if 'SKU' in df.columns:
        df['SKU'] = df['SKU'].astype(str).str.replace(r'\.0$', '', regex=True)
        df['SKU'] = df['SKU'].str.replace(r'(?i)^(nan|none|<na>|null)$', '', regex=True).str.strip()

    mask_valid = (
        df['ID_Venda'].notna() & 
        (df['ID_Venda'].astype(str).str.strip() != "") & 
        (~df['ID_Venda'].astype(str).str.lower().isin(['nan', 'none', '<na>', 'null', 'total']))
    )
    df = df[mask_valid]

    # CONVERSÃO DE DATA ABSOLUTA: Força UTC e remove o fuso horário
    if 'Data da Compra' in df.columns:
        s_data = df['Data da Compra'].astype(str).str.replace(r'(?i)\s*hs\.?', '', regex=True).str.strip()
        s_data = s_data.replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
        df['Data da Compra'] = pd.to_datetime(s_data, dayfirst=True, errors='coerce', utc=True).dt.tz_localize(None)

    def extrair_tamanho(row):
        tit_raw = str(row.get('Nome Anuncio', '')).lower().strip()
        var_raw = str(row.get('Variação', '')).lower().strip()
        tam_titulo = ""
        if tit_raw.endswith(" br"):
            parts = tit_raw.split(" br")
            if len(parts) > 1: tam_titulo = parts[-2].split()[-1]
        tam_var = ""
        try:
            tam_var = var_raw.split(" ")[6] if len(var_raw.split(" ")) > 6 else ""
        except: pass

        r1 = tam_titulo.replace(":", "").replace("-", "").strip().upper() if tam_titulo else None
        r2 = tam_var.replace(":", "").replace("-", "").strip().upper() if tam_var else None
        return r1 if r1 else r2

    df['Tamanho'] = df.apply(extrair_tamanho, axis=1)

    def extrair_cor(row):
        tit_min = str(row.get('Nome Anuncio', '')).lower().strip()
        var_min = str(row.get('Variação', '')).lower().strip()
        tam_str = str(row.get('Tamanho', '')).lower()

        if "stucco/melon" in tit_min or "stucco melon" in tit_min or "stucco/melon" in var_min or "stucco melon" in var_min: return "Stucco Melon"
        if "multicolorido" in tit_min or "multicolorido" in var_min: return "Multicolorido"
        if "branco / rosa" in tit_min or "branco/rosa" in tit_min or "branco / rosa" in var_min or "branco/rosa" in var_min: return "Branco / Rosa"
        if "rosa-claro" in tit_min or "rosa-claro" in var_min: return "Rosa-Claro"

        termos_lixo = [tam_str, "br", "-", ":", "cor:", "tamanho:", "cor", "tamanho", "|", "tipo", "de", "largura", "largura:", "regular", "padrão", "padrao"]
        palavras_var = var_min.split()
        palavras_limpas = [p for p in palavras_var if p not in termos_lixo and p]
        cor_var_original = " ".join(palavras_limpas).title()

        cor_fallback = None
        if "preto" in tit_min: cor_fallback = "Preto"
        elif tam_str and tam_str in tit_min:
            antes_do_tamanho = tit_min.rsplit(tam_str, 1)[0].strip()
            tokens = antes_do_tamanho.split()
            if tokens: cor_fallback = tokens[-1].title()

        cor_preliminar = cor_var_original if cor_var_original else cor_fallback
        cor_preliminar = cor_preliminar.strip() if cor_preliminar else None

        if cor_preliminar and cor_preliminar.title() == "Bege" and ("speckled" in tit_min or "infantil e feminino" in tit_min):
            return "Stucco Melon"
        return cor_preliminar.title() if cor_preliminar else ""

    df['Cor'] = df.apply(extrair_cor, axis=1)

    def formatar_cpf(cpf):
        cpf = str(cpf).split('.')[0].zfill(11)
        if len(cpf) == 11: return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf
    
    def formatar_cep(cep):
        cep = str(cep).split('.')[0].zfill(8)
        if len(cep) >= 8: return f"{cep[:5]}-{cep[5:8]}"
        return cep

    if 'CPF' in df.columns: df['CPF'] = df['CPF'].apply(formatar_cpf)
    if 'CEP' in df.columns: df['CEP'] = df['CEP'].apply(formatar_cep)

    if 'Nome Cliente' in df.columns: df['Nome Cliente'] = df['Nome Cliente'].astype(str).str.title().str.strip()
    if 'Endereco Cliente' in df.columns: df['Endereco Cliente'] = df['Endereco Cliente'].astype(str).str.title().str.strip()
    
    colunas_filldown = ["Nome Cliente", "CPF", "Endereco Cliente", "CEP", "Cidade Envio", "Estado Envio"]
    colunas_existentes_fill = [c for c in colunas_filldown if c in df.columns]
    
    if colunas_existentes_fill:
        df[colunas_existentes_fill] = df[colunas_existentes_fill].replace(r'^\s*$', np.nan, regex=True)
        df[colunas_existentes_fill] = df[colunas_existentes_fill].replace(r'(?i)^(nan|none|<na>|null)$', np.nan, regex=True)
        df[colunas_existentes_fill] = df.groupby('ID_Venda')[colunas_existentes_fill].ffill().bfill()

    if 'Endereco Cliente' in df.columns:
        df['Bairro'] = df['Endereco Cliente'].apply(lambda x: str(x).split(' - ')[-1].split(',')[0].strip() if ' - ' in str(x) else None)

    if 'Data da Compra' in df.columns:
        df['Hora da Compra'] = df['Data da Compra'].dt.hour
        bins = [-1, 5, 11, 17, 24]
        labels = ['Madrugada', 'Manhã', 'Tarde', 'Noite']
        df['Turno'] = pd.cut(df['Hora da Compra'], bins=bins, labels=labels, right=False)
        df['Data_Relacionamento'] = df['Data da Compra'].dt.date

    cols_monetarias = ['Receita por Produto', 'Impostos', 'Tarifas Envio', 'Descontos', 'Taxa Cancelamento', 'Valor Total', 'Valor Venda']
    for col in cols_monetarias:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.extract(r'([\d.]+)')[0], errors='coerce').fillna(0)

    return df


# =====================================================================
# MÓDULO DE REPASSE E UNIFICAÇÃO (MERCADO PAGO)
# =====================================================================
def limpar_data_liberacao_mp(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    
    # BLINDAGEM 2: Remove espaços e usa busca flexível pelos códigos internos
    df.columns = df.columns.astype(str).str.strip()
    
    col_created = next((c for c in df.columns if 'date_created' in c.lower()), None)
    col_released = next((c for c in df.columns if 'date_released' in c.lower()), None)
    
    if not col_created or not col_released: 
        return pd.DataFrame(columns=['Data da Compra', 'Data de Repasse'])
        
    df = df[[col_created, col_released]].rename(columns={
        col_created: 'Data da Compra', 
        col_released: 'Data de Repasse'
    })
    
    df = df[df['Data da Compra'].notna()]
    df = df[df['Data da Compra'].astype(str).str.lower() != "data da compra (date_created)"]
    
    if 'Data da Compra' in df.columns: 
        s_compra = df['Data da Compra'].astype(str).replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
        df['Data da Compra'] = pd.to_datetime(s_compra, errors='coerce', utc=True).dt.tz_localize(None)
        
    if 'Data de Repasse' in df.columns: 
        s_repasse = df['Data de Repasse'].astype(str).replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
        df['Data de Repasse'] = pd.to_datetime(s_repasse, errors='coerce', utc=True).dt.tz_localize(None)
        
    df = df.dropna(subset=['Data da Compra']).copy()
    df = df.drop_duplicates(subset=['Data da Compra'], keep='last')
    
    return df.reset_index(drop=True)

def unificar_vendas_repasse(df_vendas: pd.DataFrame, df_mp: pd.DataFrame) -> pd.DataFrame:
    if df_mp.empty or 'Data da Compra' not in df_mp.columns:
        df_vendas['Data de Repasse'] = pd.NaT
        return df_vendas
        
    df_m = df_mp.dropna(subset=['Data da Compra']).copy()
    if df_m.empty:
        df_vendas['Data de Repasse'] = pd.NaT
        return df_vendas

    mask_valid = df_vendas['Data da Compra'].notna()
    df_v_valid = df_vendas[mask_valid].copy()
    df_v_invalid = df_vendas[~mask_valid].copy()

    if df_v_valid.empty:
        df_vendas['Data de Repasse'] = pd.NaT
        return df_vendas

    df_v_valid['Data da Compra'] = pd.to_datetime(df_v_valid['Data da Compra'], errors='coerce').astype('datetime64[ns]')
    df_m['Data da Compra'] = pd.to_datetime(df_m['Data da Compra'], errors='coerce').astype('datetime64[ns]')

    df_v_valid = df_v_valid.sort_values('Data da Compra')
    df_m = df_m.sort_values('Data da Compra')
    
    df_merged = pd.merge_asof(
        left=df_v_valid, 
        right=df_m[['Data da Compra', 'Data de Repasse']], 
        on='Data da Compra', 
        direction='nearest',
        tolerance=pd.Timedelta(minutes=4320)
    )
    
    df_final = pd.concat([df_merged, df_v_invalid], ignore_index=True)
    if 'ID_Venda' in df_final.columns:
        df_final = df_final.sort_values('ID_Venda', ascending=False).reset_index(drop=True)
        
    return df_final


# =====================================================================
# CAMADA OURO (MODELAGEM STAR SCHEMA)
# =====================================================================
def limpar_chave(v):
    if pd.isna(v): return ""
    s = str(v).strip().upper() 
    if s in ['NAN', 'NONE', '<NA>', 'NULL', '']: return ""
    if s.endswith('.0'): return s[:-2]
    return s

def extrair_dclientes(df_base: pd.DataFrame, df_erp: pd.DataFrame = None) -> pd.DataFrame:
    df_ml = df_base.copy()

    colunas_erp_esperadas = [
        "CODIGO", "NOME", "SOBRENOME", "CPF_Formatado", "ENDERECO", "CEP", 
        "CIDADE", "BAIRRO", "ESTADO", "LOJA", "TELEFONE1", "NASCIMENTO", "SEXO"
    ]
    
    if df_erp is not None and not df_erp.empty:
        df_erp.columns = df_erp.columns.str.replace('ï»¿', '', regex=False).str.strip()
        cols_existentes = [c for c in colunas_erp_esperadas if c in df_erp.columns]
        df_erp_clean = df_erp[cols_existentes].copy()
        
        renomeios_erp = {
            "CODIGO": "ID_Cliente", "NOME": "Nome Cliente", "SOBRENOME": "Sobrenome",
            "CPF_Formatado": "CPF", "ENDERECO": "Endereco Cliente", "CIDADE": "Cidade Envio", 
            "BAIRRO": "Bairro", "ESTADO": "Estado Envio", "LOJA": "Loja Cadastrada"
        }
        df_erp_clean.rename(columns=renomeios_erp, inplace=True, errors='ignore')
        
        if 'ID_Cliente' in df_erp_clean.columns:
            df_erp_clean['ID_Cliente'] = df_erp_clean['ID_Cliente'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
        if 'CPF' in df_erp_clean.columns:
            df_erp_clean['CPF'] = df_erp_clean['CPF'].astype(str).str.strip()
            df_erp_clean['CPF'] = df_erp_clean['CPF'].replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
    else:
        df_erp_clean = pd.DataFrame(columns=["ID_Cliente", "Nome Cliente", "Sobrenome", "CPF", "Endereco Cliente", "CEP", "Cidade Envio", "Bairro", "Estado Envio", "Loja Cadastrada", "TELEFONE1", "NASCIMENTO", "SEXO"])

    if 'CPF' in df_ml.columns: 
        df_ml['CPF_Limpo_ML'] = df_ml['CPF'].astype(str).str.strip()
        df_ml['CPF_Limpo_ML'] = df_ml['CPF_Limpo_ML'].replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
    else: 
        df_ml['CPF_Limpo_ML'] = pd.NA

    if not df_erp_clean.empty and 'CPF' in df_erp_clean.columns and 'ID_Cliente' in df_erp_clean.columns:
        df_map = df_erp_clean.dropna(subset=['CPF'])[['CPF', 'ID_Cliente']].drop_duplicates(subset=['CPF'])
        df_ml = df_ml.merge(df_map, left_on='CPF_Limpo_ML', right_on='CPF', how='left', suffixes=('', '_erp'))
        df_ml['Codigo_ERP'] = df_ml['ID_Cliente_erp']
    else:
        df_ml['Codigo_ERP'] = pd.NA

    nome_col = 'Nome Cliente' if 'Nome Cliente' in df_ml.columns else 'Comprador'
    df_ml['ID_Cliente'] = df_ml['Codigo_ERP'].fillna(df_ml['CPF_Limpo_ML']).fillna(df_ml[nome_col])
    df_ml['ID_Cliente'] = df_ml['ID_Cliente'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()

    colunas_cadastrais_ml = ["ID_Cliente", "Nome Cliente", "CPF", "Endereco Cliente", "CEP", "Cidade Envio", "Bairro", "Estado Envio", "Pais"]
    
    df_ml_desc = df_ml.copy()
    for col in colunas_cadastrais_ml:
        if col not in df_ml_desc.columns:
            df_ml_desc[col] = pd.NA
    df_ml_desc = df_ml_desc[colunas_cadastrais_ml].drop_duplicates(subset=["ID_Cliente"], keep='first')

    if not df_erp_clean.empty and 'ID_Cliente' in df_erp_clean.columns:
        ids_compradores_ml = df_ml_desc['ID_Cliente'].dropna().unique()
        df_erp_filtrado = df_erp_clean[df_erp_clean['ID_Cliente'].isin(ids_compradores_ml)].copy()
        
        erp_ids = df_erp_clean['ID_Cliente'].dropna().unique()
        df_ml_exclusivos = df_ml_desc[~df_ml_desc['ID_Cliente'].isin(erp_ids)].copy()
    else:
        df_erp_filtrado = df_erp_clean.copy()
        df_ml_exclusivos = df_ml_desc.copy()

    df_ml_exclusivos['Sobrenome'] = ""
    df_ml_exclusivos['Loja Cadastrada'] = "Apenas Online (Não Cadastrado)"
    df_ml_exclusivos['TELEFONE1'] = pd.NA
    df_ml_exclusivos['NASCIMENTO'] = pd.NA
    df_ml_exclusivos['SEXO'] = pd.NA

    df_uniao = pd.concat([df_erp_filtrado, df_ml_exclusivos], ignore_index=True)
    
    if 'ID_Cliente' in df_uniao.columns:
        df_final = df_uniao.dropna(subset=['ID_Cliente']).drop_duplicates(subset=['ID_Cliente'], keep='first').copy()
        if 'CPF' in df_final.columns:
            df_final['is_erp'] = df_final['Loja Cadastrada'] != "Apenas Online (Não Cadastrado)"
            df_final = df_final.sort_values('is_erp', ascending=False)
            
            mask_cpf_valid = df_final['CPF'].notna() & (df_final['CPF'].astype(str).str.strip() != "")
            df_cpf_dups = df_final[mask_cpf_valid].drop_duplicates(subset=['CPF'], keep='first')
            df_cpf_nulls = df_final[~mask_cpf_valid]
            
            df_final = pd.concat([df_cpf_dups, df_cpf_nulls], ignore_index=True)
            df_final = df_final.drop(columns=['is_erp'], errors='ignore')
            
        df_final = df_final.reset_index(drop=True)
    else:
        df_final = df_uniao

    return df_final


def extrair_dprodutos(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()

    def gerar_id_produto(row):
        status = limpar_chave(row.get('Status', ''))
        if status.startswith("PACOTE"): return "PACOTE-MULTIPLO"
        sku = limpar_chave(row.get('SKU', ''))
        tamanho = limpar_chave(row.get('Tamanho', ''))
        cor = limpar_chave(row.get('Cor', ''))
        return f"{sku}-{tamanho}-{cor}"

    df['ID_Produto'] = df.apply(gerar_id_produto, axis=1)
    df['Nome Anuncio'] = np.where(df['ID_Produto'] == "PACOTE-MULTIPLO", "📦 Pacote (Carrinho com Vários Itens)", df['Nome Anuncio'])

    colunas_produto = ["ID_Produto", "SKU", "Nome Anuncio", "Tamanho", "Cor", "Loja Oficial", "Tipo Anuncio"]
    df_produtos = df.copy()
    for col in colunas_produto:
        if col not in df_produtos.columns:
            df_produtos[col] = pd.NA
            
    df_produtos = df_produtos[colunas_produto].drop_duplicates(subset=["ID_Produto"], keep='first').reset_index(drop=True)

    def definir_categoria(nome):
        nome = str(nome).lower()
        if any(c in nome for c in ["calça", "camisa", "regata", "blusa", "casaco", "meia"]): return "Confecção"
        if any(c in nome for c in ["óculos", "oculos", "cordão", "cordao", "corrente", "boné", "bone", "anel", "relógio", "relogio", "pulseira"]): return "Acessório"
        if any(c in nome for c in ["sandália", "sandalia", "babuche", "clog", "crocs", "tênis", "tenis", "tesla", "skate"]): return "Calçado"
        return "Outros"
    df_produtos['Categoria'] = df_produtos['Nome Anuncio'].apply(definir_categoria)

    def definir_tipo(nome):
        nome = str(nome).lower()
        if any(c in nome for c in ["sandália", "sandalia", "babuche", "crocs", "clog"]): return "Sandália / Babuche"
        if any(c in nome for c in ["tênis", "tenis", "tesla", "skate"]): return "Tênis"
        if "calça" in nome: return "Calça"
        if "camisa" in nome: return "Camisa"
        if "regata" in nome: return "Regata"
        if "blusa" in nome: return "Blusa"
        if "casaco" in nome: return "Casaco"
        if "meia" in nome: return "Meia"
        if any(c in nome for c in ["óculos", "oculos"]): return "Óculos"
        if any(c in nome for c in ["cordão", "cordao"]): return "Cordão"
        if "corrente" in nome: return "Corrente"
        if any(c in nome for c in ["boné", "bone"]): return "Boné"
        if "anel" in nome: return "Anel"
        if any(c in nome for c in ["relógio", "relogio"]): return "Relógio"
        if "pulseira" in nome: return "Pulseira"
        return "Outros"
    df_produtos['Tipo Produto'] = df_produtos['Nome Anuncio'].apply(definir_tipo)

    def definir_modelo(nome):
        nome = str(nome).lower()
        if "speckled band" in nome: return "Speckled Band"
        if "bistro" in nome: return "Bistro"
        if "literide" in nome: return "LiteRide"
        if "crocband" in nome: return "Crocband"
        if "platform" in nome: return "Platform"
        if "classic" in nome or "x10001" in nome: return "Classic"
        if "x207006" in nome: return "Classic Infantil"
        if "flow" in nome: return "Flow"
        if "flat core" in nome: return "Flat Core"
        if "puff" in nome: return "Puff"
        if "rakka" in nome: return "Rakka"
        if "old skool" in nome: return "Old Skool"
        if "slip on" in nome: return "Slip On"
        if "coil" in nome: return "Tesla Coil"
        if "hertz" in nome: return "Tesla Hertz"
        if "pacote" in nome: return "Pacote / Múltiplos Itens"
        if "clog" in nome: return "Clog Genérico"
        if "crocs" in nome: return "Crocs Genérico"
        return "Modelo Não Mapeado"
    df_produtos['Modelo Produto'] = df_produtos['Nome Anuncio'].apply(definir_modelo)

    return df_produtos

def extrair_dlogistica(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    colunas_logistica = ["ID_Venda", "NFE em Anexo", "Responsavel Envio", "Forma de entrega", "Numero Rastreamento"]
    
    for col in colunas_logistica:
        if col not in df.columns:
            df[col] = pd.NA
            
    df_logistica = df[colunas_logistica].drop_duplicates(subset=["ID_Venda"], keep='first')
    return df_logistica.reset_index(drop=True)

def extrair_fvendas(df_base: pd.DataFrame, df_erp: pd.DataFrame = None) -> pd.DataFrame:
    df = df_base.copy()

    if df_erp is not None and not df_erp.empty:
        df_erp.columns = df_erp.columns.str.replace('ï»¿', '', regex=False).str.strip()
        if 'CPF_Formatado' in df_erp.columns and 'CODIGO' in df_erp.columns:
            df_erp['CPF_Formatado'] = df_erp['CPF_Formatado'].astype(str).str.strip()
            df_erp['CPF_Formatado'] = df_erp['CPF_Formatado'].replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
            df_erp['CODIGO'] = df_erp['CODIGO'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()
            
            df['CPF_Limpo_ML'] = df['CPF'].astype(str).str.strip()
            df['CPF_Limpo_ML'] = df['CPF_Limpo_ML'].replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
            
            df_erp_clean = df_erp.dropna(subset=['CPF_Formatado'])[['CPF_Formatado', 'CODIGO']].drop_duplicates(subset=['CPF_Formatado'])
            df = df.merge(df_erp_clean, left_on='CPF_Limpo_ML', right_on='CPF_Formatado', how='left')
            df.rename(columns={'CODIGO': 'Codigo_ERP'}, inplace=True)
        else:
            df['Codigo_ERP'] = pd.NA
            df['CPF_Limpo_ML'] = df['CPF'].replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
    else:
        df['Codigo_ERP'] = pd.NA
        if 'CPF' in df.columns:
            df['CPF_Limpo_ML'] = df['CPF'].astype(str).str.strip().replace(r'(?i)^(nan|none|<na>|null|)$', pd.NA, regex=True)
        else:
            df['CPF_Limpo_ML'] = pd.NA

    nome_col = 'Nome Cliente' if 'Nome Cliente' in df.columns else 'Comprador'
    df['ID_Cliente'] = df['Codigo_ERP'].fillna(df['CPF_Limpo_ML']).fillna(df[nome_col])
    df['ID_Cliente'] = df['ID_Cliente'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.upper()

    def gerar_id_produto(row):
        status = limpar_chave(row.get('Status', ''))
        if status.startswith("PACOTE"): return "PACOTE-MULTIPLO"
        sku = limpar_chave(row.get('SKU', ''))
        tamanho = limpar_chave(row.get('Tamanho', ''))
        cor = limpar_chave(row.get('Cor', ''))
        return f"{sku}-{tamanho}-{cor}"
    
    df['ID_Produto'] = df.apply(gerar_id_produto, axis=1)

    colunas_fato = [
        "ID_Venda", "ID_Cliente", "ID_Produto", "Data da Compra", "Data de Repasse", 
        "Status", "Descrição do status", "Unidades Compradas", "Receita por Produto", 
        "Impostos", "Tarifas Envio", "Taxa Cancelamento", "Descontos", "Valor Total", 
        "Hora da Compra", "Turno", "Data_Relacionamento"
    ]
    
    for col in colunas_fato:
        if col not in df.columns:
            df[col] = pd.NA
            
    df_fato = df[colunas_fato].copy()

    renomeios = {"Receita por Produto": "Valor Venda", "Tarifas Envio": "Tarifa Envio"}
    df_fato.rename(columns=renomeios, inplace=True, errors='ignore')

    if 'Tarifa Envio' in df_fato.columns:
        df_fato['Tarifa Envio'] = pd.to_numeric(df_fato['Tarifa Envio'], errors='coerce').fillna(0)
        df_fato['Tarifa Envio'] = df_fato['Tarifa Envio'] * -1

    return df_fato

def extrair_dcalendario(df_vendas: pd.DataFrame) -> pd.DataFrame:
    if df_vendas.empty or 'Data da Compra' not in df_vendas.columns:
        return pd.DataFrame()

    min_date = df_vendas['Data da Compra'].min()
    max_date = df_vendas['Data da Compra'].max()

    if pd.isna(min_date) or pd.isna(max_date): return pd.DataFrame()

    start_date = pd.Timestamp(year=min_date.year, month=1, day=1)
    end_date = pd.Timestamp(year=max_date.year, month=12, day=31)

    df_cal = pd.DataFrame({'Data': pd.date_range(start=start_date, end=end_date, freq='D')})

    df_cal['Ano'] = df_cal['Data'].dt.year
    df_cal['Mês Num'] = df_cal['Data'].dt.month
    meses = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
             7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}
    df_cal['Mês'] = df_cal['Mês Num'].map(meses)

    df_cal['Trimestre'] = 'Q' + df_cal['Data'].dt.quarter.astype(str)
    df_cal['Dia da Semana Num'] = df_cal['Data'].dt.dayofweek
    dias = {0: 'Segunda-Feira', 1: 'Terça-Feira', 2: 'Quarta-Feira', 3: 'Quinta-Feira',
            4: 'Sexta-Feira', 5: 'Sábado', 6: 'Domingo'}
    df_cal['Dia da Semana'] = df_cal['Dia da Semana Num'].map(dias)
    df_cal['Data'] = df_cal['Data'].dt.date

    return df_cal