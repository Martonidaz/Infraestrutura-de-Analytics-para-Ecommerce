import pandas as pd
import numpy as np
import warnings

# Silencia o aviso do Pandas sobre adivinhação de formato de data
warnings.filterwarnings("ignore", message="Could not infer format")

# =====================================================================
# ETL ENGINE - CAMADA PRATA E OURO (MODELAGEM)
# =====================================================================

def limpar_base_vendas_ml(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()

    # 1. RENOMEAR COLUNAS
    col_mapping = {
        "N.º de venda": "ID_Venda", "Data da venda": "Data da Compra", "Estado": "Status",
        "Unidades": "Unidades Compradas", "Receita por produtos (BRL)": "Receita por Produto",
        "Tarifa de venda e impostos (BRL)": "Impostos", "Tarifas de envio (BRL)": "Tarifas Envio",
        "Descontos e bônus": "Descontos", "Cancelamentos e reembolsos (BRL)": "Taxa Cancelamento",
        "Total (BRL)": "Valor Total", "Loja oficial": "Loja Oficial", "Título do anúncio": "Nome Anuncio",
        "Preço unitário de venda do anúncio (BRL)": "Valor Venda", "Tipo de anúncio": "Tipo Anuncio",
        "NF-e em anexo": "NFE em Anexo", "Dados pessoais ou da empresa": "Nome Cliente",
        "Endereço": "Endereco Cliente", "Motorista": "Responsavel Envio", "Estado_2": "Estado Envio",
        "Cidade": "Cidade Envio", "País": "Pais", "Número de rastreamento": "Numero Rastreamento"
    }
    df.rename(columns=col_mapping, inplace=True, errors='ignore')

    # Limpeza Global de SKU
    if 'SKU' in df.columns:
        df['SKU'] = df['SKU'].astype(str).str.replace(r'\.0$', '', regex=True)
        df['SKU'] = df['SKU'].str.replace(r'^(?i)(nan|none|<na>|null)$', '', regex=True).str.strip()

    # Filtro de Segurança
    mask_valid = (
        df['ID_Venda'].notna() & 
        (df['ID_Venda'].astype(str).str.strip() != "") & 
        (~df['ID_Venda'].astype(str).str.lower().isin(['nan', 'none', '<na>', 'null', 'total']))
    )
    df = df[mask_valid]

    # 2. CONVERSÃO DE DATA (Padrão Brasileiro Seguro)
    if 'Data da Compra' in df.columns:
        df['Data da Compra'] = df['Data da Compra'].astype(str).str.replace(" hs.", "", regex=False)
        df['Data da Compra'] = pd.to_datetime(df['Data da Compra'], format='mixed', dayfirst=True, errors='coerce')

    # 3. EXTRAÇÃO DE TAMANHO
    def extrair_tamanho(row):
        tit_raw = str(row.get('Nome Anuncio', '')).lower().strip()
        var_raw = str(row.get('Variação', '')).lower().strip()
        
        tam_titulo = ""
        if tit_raw.endswith(" br"):
            parts = tit_raw.split(" br")
            if len(parts) > 1: tam_titulo = parts[-2].split()[-1]
        
        tam_var = ""
        try:
            # Correção de índice M para Python
            tam_var = var_raw.split(" ")[6] if len(var_raw.split(" ")) > 6 else ""
        except: pass

        r1 = tam_titulo.replace(":", "").replace("-", "").strip().upper() if tam_titulo else None
        r2 = tam_var.replace(":", "").replace("-", "").strip().upper() if tam_var else None
        return r1 if r1 else r2

    df['Tamanho'] = df.apply(extrair_tamanho, axis=1)

    # 4. EXTRAÇÃO DE COR
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

    # 5. FORMATAÇÃO DE CPF E CEP
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

    # 6. LIMPEZA DE TEXTO
    if 'Nome Cliente' in df.columns: df['Nome Cliente'] = df['Nome Cliente'].astype(str).str.title().str.strip()
    if 'Endereco Cliente' in df.columns: df['Endereco Cliente'] = df['Endereco Cliente'].astype(str).str.title().str.strip()
    if 'Endereco Cliente' in df.columns:
        df['Bairro'] = df['Endereco Cliente'].apply(lambda x: str(x).split(' - ')[-1].split(',')[0].strip() if ' - ' in str(x) else None)

    # 7. VARIÁVEIS DE TEMPO
    if 'Data da Compra' in df.columns:
        df['Hora da Compra'] = df['Data da Compra'].dt.hour
        bins = [-1, 5, 11, 17, 24]
        labels = ['Madrugada', 'Manhã', 'Tarde', 'Noite']
        df['Turno'] = pd.cut(df['Hora da Compra'], bins=bins, labels=labels, right=False)
        df['Data_Relacionamento'] = df['Data da Compra'].dt.date

    # 8. TIPAGEM MONETÁRIA FINAL (Corrigido o erro \d)
    cols_monetarias = ['Receita por Produto', 'Impostos', 'Tarifas Envio', 'Descontos', 'Taxa Cancelamento', 'Valor Total', 'Valor Venda']
    for col in cols_monetarias:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.extract(r'([\d.]+)')[0], errors='coerce').fillna(0)

    return df

# =====================================================================
# FUNÇÃO BLINDADA COM FORCE UPPERCASE (IGUAL POWER BI)
# =====================================================================
def limpar_chave(v):
    if pd.isna(v): return ""
    s = str(v).strip().upper() # Força Maiúscula absoluta
    if s in ['NAN', 'NONE', '<NA>', 'NULL', '']: return ""
    if s.endswith('.0'): return s[:-2]
    return s

def extrair_dclientes(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    if 'CPF' in df.columns: df['CPF_Limpo'] = df['CPF'].replace(r'^\s*$', pd.NA, regex=True)
    else: df['CPF_Limpo'] = pd.NA
    
    nome_col = 'Nome Cliente' if 'Nome Cliente' in df.columns else 'Comprador'
    df['ID_Cliente'] = df['CPF_Limpo'].fillna(df[nome_col])

    colunas_cadastrais = ["ID_Cliente", "Nome Cliente", "CPF", "Endereco Cliente", "CEP", "Cidade Envio", "Bairro", "Estado Envio", "Pais"]
    df_clientes = df[[col for col in colunas_cadastrais if col in df.columns]]
    return df_clientes.drop_duplicates(subset=["ID_Cliente"], keep='first').reset_index(drop=True)

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
    df_produtos = df[[col for col in colunas_produto if col in df.columns]].copy()
    
    # Agora a remoção de duplicatas é 100% igual ao Power BI
    df_produtos = df_produtos.drop_duplicates(subset=["ID_Produto"], keep='first').reset_index(drop=True)

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

    colunas_finais = ["ID_Produto", "SKU", "Nome Anuncio", "Categoria", "Tipo Produto", "Modelo Produto", "Tamanho", "Cor", "Loja Oficial", "Tipo Anuncio"]
    return df_produtos[[col for col in colunas_finais if col in df_produtos.columns]]

def extrair_dlogistica(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()
    colunas_logistica = ["ID_Venda", "NFE em Anexo", "Responsavel Envio", "Forma de entrega", "Numero Rastreamento"]
    df_logistica = df[[col for col in colunas_logistica if col in df.columns]]
    if "ID_Venda" in df_logistica.columns: df_logistica = df_logistica.drop_duplicates(subset=["ID_Venda"], keep='first')
    return df_logistica.reset_index(drop=True)

def extrair_fvendas(df_base: pd.DataFrame) -> pd.DataFrame:
    df = df_base.copy()

    if 'CPF' in df.columns: df['CPF_Limpo'] = df['CPF'].replace(r'^\s*$', pd.NA, regex=True)
    else: df['CPF_Limpo'] = pd.NA
    nome_col = 'Nome Cliente' if 'Nome Cliente' in df.columns else 'Comprador'
    df['ID_Cliente'] = df['CPF_Limpo'].fillna(df[nome_col])

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
    df_fato = df[[col for col in colunas_fato if col in df.columns]].copy()

    renomeios = {"Receita por Produto": "Valor Venda", "Tarifas Envio": "Tarifa Envio"}
    df_fato.rename(columns=renomeios, inplace=True, errors='ignore')

    if 'Tarifa Envio' in df_fato.columns:
        df_fato['Tarifa Envio'] = pd.to_numeric(df_fato['Tarifa Envio'], errors='coerce').fillna(0)
        df_fato['Tarifa Envio'] = df_fato['Tarifa Envio'] * -1

    return df_fato