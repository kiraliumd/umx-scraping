import requests

# --- SUAS CREDENCIAIS AQUI ---
CLIENT_ID = "POTZ5M543A58SCZVXJYUR1JCOUQ545M7"
CLIENT_SECRET = "4VFEIPMUB4BPG1XR8C8DJZUMEV8BUY37GJQPBOBI7ZN1G6K0Q5OJ559QXORT355L"
REDIRECT_URI = "https://google.com"
# -----------------------------

def get_access_token():
    # 1. Gerar a URL de Autorização
    auth_url = (
        f"https://app.clickup.com/api?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    
    print("\n⚠️  PASSO 1: AUTORIZAÇÃO MANUAL")
    print("Copie o link abaixo, cole no seu navegador e autorize o App:")
    print("-" * 60)
    print(auth_url)
    print("-" * 60)
    
    # 2. Pegar o CODE
    print("\nDepois de autorizar, você será redirecionado para o Google.")
    print("A URL vai ficar assim: https://google.com/?code=SEU_CODIGO_AQUI")
    code = input("Cole aqui o código que aparece depois de 'code=' na URL: ").strip()
    
    # 3. Trocar CODE por TOKEN
    print("\n🔄 Trocando código por token...")
    token_url = f"https://api.clickup.com/api/v2/oauth/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code
    }
    
    response = requests.post(token_url, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ SUCESSO! Aqui está seu API Key:")
        print("=" * 60)
        print(data['access_token'])
        print("=" * 60)
        print("Copie esse token e coloque no seu arquivo .env como CLICKUP_API_KEY")
    else:
        print("\n❌ ERRO:")
        print(response.text)

if __name__ == "__main__":
    get_access_token()