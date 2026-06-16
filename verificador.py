import os
import pandas as pd

RAW_DIR = os.path.join("data", "raw")

def raio_x_arquivos():
    print("="*60)
    print("🔍 RAIO-X DE DADOS VAZIOS NA FONTE (RAW DATA)")
    print("="*60)
    
    if not os.path.exists(RAW_DIR) or len(os.listdir(RAW_DIR)) == 0:
        print("Nenhum ficheiro encontrado na pasta data/raw.")
        return

    for arquivo in os.listdir(RAW_DIR):
        caminho = os.path.join(RAW_DIR, arquivo)
        print(f"\n📂 Analisando ficheiro: {arquivo}")
        
        try:
            if arquivo.endswith('.csv'):
                df = pd.read_csv(caminho, sep=';', encoding='latin1', on_bad_lines='skip', dtype=str)
                df.columns = df.columns.str.replace('ï»¿', '', regex=False)
            elif arquivo.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(caminho, engine='calamine', dtype=str)
            else:
                continue
                
            total_linhas = len(df)
            print(f"Total de Linhas: {total_linhas}")
            print("-" * 40)
            
            # Calcula a percentagem de valores vazios em cada coluna
            for col in df.columns:
                # Conta nulos e strings 'nan' ou espaços em branco
                vazios = df[col].isna().sum() + df[col].astype(str).str.strip().eq("").sum() + df[col].astype(str).str.lower().eq("nan").sum()
                perc_vazio = (vazios / total_linhas) * 100
                
                # Só mostra colunas que têm alguma taxa de vazio para não poluir o ecrã
                if perc_vazio > 0:
                    print(f"⚠️ {col}: {perc_vazio:.1f}% vazio ({vazios} linhas em branco)")
            
        except Exception as e:
            print(f"❌ Erro ao ler {arquivo}: {e}")

if __name__ == "__main__":
    raio_x_arquivos()