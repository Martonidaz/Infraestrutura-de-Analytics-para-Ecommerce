# ⚡ Infraestrutura de Analytics Local

Este repositório contém a arquitetura modular construída em Python para ingestão, processamento incremental e visualização de dados. O objetivo é substituir ferramentas tradicionais de BI fechadas por uma infraestrutura local, rápida e de código aberto.

## 🏛️ Arquitetura do Projeto (Padrão MVC)

O projeto foi dividido em camadas lógicas para separar a interface visual das regras de negócio e manipulação de dados:

```text
📦 infra-analytics
 ┣ 📂 core/                # Regras de Negócio e Controladores (Backend)
 ┃ ┣ 📜 __init__.py
 ┃ ┣ 📜 auth.py            # Autenticação, hash de senhas e gestão de acesso
 ┃ ┗ 📜 file_manager.py    # Motor de arquivos (Excel, Parquet) e Carga Incremental
 ┣ 📂 data/                # Armazenamento Local (Ignorado no Git por segurança)
 ┃ ┣ 📂 .auth/             # Banco de dados de usuários em JSON
 ┃ ┣ 📂 processed/         # Banco histórico consolidado e otimizado (.parquet)
 ┃ ┗ 📂 raw/               # Backups dos arquivos brutos submetidos (.xlsx)
 ┣ 📂 ui/                  # Interface do Usuário (Frontend)
 ┃ ┣ 📜 __init__.py
 ┃ ┗ 📜 views.py           # Telas Streamlit (Login, Dashboards, Ingestão)
 ┣ 📜 .gitignore           # Bloqueia o upload de dados sensíveis para o repositório
 ┣ 📜 main.py              # Arquivo Bootstrap (Ponto de partida do app)
 ┗ 📜 requirements.txt     # Lista de bibliotecas e dependências