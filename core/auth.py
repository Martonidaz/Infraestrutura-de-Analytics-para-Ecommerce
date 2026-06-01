import os
import json
import hashlib
from datetime import datetime

AUTH_DIR = os.path.join("data", ".auth")
USERS_DB = os.path.join(AUTH_DIR, "users_db.json")
REMEMBER_ME_FILE = os.path.join(AUTH_DIR, "remember_cache.json")

os.makedirs(AUTH_DIR, exist_ok=True)

def gerar_hash(senha: str) -> str:
    return hashlib.sha256(senha.encode('utf-8')).hexdigest()

def inicializar_banco_usuarios():
    if not os.path.exists(USERS_DB):
        banco_inicial = {
            "martonroot": { 
                "nome": "Daniel Marton",
                "email": "martonroot@gmail.com",
                "senha": gerar_hash("root"),
                "role": "root",
                "status": "ativo",
                "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
        }
        salvar_usuarios(banco_inicial)

def carregar_usuarios() -> dict:
    inicializar_banco_usuarios()
    with open(USERS_DB, "r") as f:
        return json.load(f)

def salvar_usuarios(db: dict):
    with open(USERS_DB, "w") as f:
        json.dump(db, f, indent=4)

def validar_login(username, password_plana) -> tuple[bool, dict]:
    db = carregar_usuarios()
    if username in db:
        user_info = db[username]
        if user_info["senha"] == gerar_hash(password_plana) and user_info["status"] == "ativo":
            return True, user_info
        elif user_info["status"] != "ativo":
            return False, {"erro": "Usuário bloqueado."}
    return False, {"erro": "Credenciais incorretas."}

def registrar_usuario(nome, username, email, senha_plana, role) -> tuple[bool, str]:
    db = carregar_usuarios()
    if username in db: return False, "Username já em uso!"
    db[username] = {
        "nome": nome, "email": email if email else "Não informado",
        "senha": gerar_hash(senha_plana), "role": role, "status": "ativo",
        "data_criacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    }
    salvar_usuarios(db)
    return True, "Usuário criado!"

# --- NOVAS FUNÇÕES DO PAINEL ROOT ---
def alterar_privilegio(username, novo_role) -> tuple[bool, str]:
    db = carregar_usuarios()
    if username in db:
        if username == "martonroot": return False, "Não é possível alterar o privilégio do super-admin."
        db[username]["role"] = novo_role
        salvar_usuarios(db)
        return True, f"Privilégio de {username} atualizado para {novo_role}!"
    return False, "Usuário não encontrado."

def excluir_usuario(username) -> tuple[bool, str]:
    db = carregar_usuarios()
    if username in db:
        if username == "martonroot": return False, "Não é possível excluir o super-admin."
        del db[username]
        salvar_usuarios(db)
        return True, f"Usuário {username} deletado com sucesso!"
    return False, "Usuário não encontrado."
# ------------------------------------

def carregar_lembrete():
    if os.path.exists(REMEMBER_ME_FILE):
        try:
            with open(REMEMBER_ME_FILE, "r") as f: return json.load(f).get("last_username", "")
        except: pass
    return ""

def salvar_lembrete(username, lembrar):
    with open(REMEMBER_ME_FILE, "w") as f:
        json.dump({"last_username": username if lembrar else ""}, f)