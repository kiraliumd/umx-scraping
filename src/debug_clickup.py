import requests

# --- SEUS DADOS REAIS (COLE AQUI DENTRO DAS ASPAS) ---
TOKEN = "254662569_60cac436e864d8b028eb58f22caa23dd1eef30e81a3403cf489df444d3997d76"
LIST_ID = "901323316606" # Seu ID numérico da lista
# -----------------------------------------------------

def testar_conexao():
    url = f"https://api.clickup.com/api/v2/list/{LIST_ID}"
    
    # O SEGREDO ESTÁ AQUI: O ClickUp quer o token PURO no header
    headers = {
        "Authorization": TOKEN, 
        "Content-Type": "application/json"
    }

    print(f"Tentando conectar na Lista {LIST_ID}...")
    
    response = requests.get(url, headers=headers)

    print(f"\nStatus Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ SUCESSO! Conectado na lista: {data.get('name')}")
        print("O token está funcionando perfeitamente.")
    else:
        print("❌ FALHA:")
        print(response.text)

if __name__ == "__main__":
    testar_conexao()