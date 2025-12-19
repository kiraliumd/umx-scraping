# UMX Scraper (Livelo)

Este é um microserviço de automação especializado em extração de saldo do programa **Livelo**, integrado com **AdsPower** para gestão de impressões digitais (fingerprints) e **Supabase** para persistência de dados.

## 🚀 Como Rodar no Windows

### 1. Pré-requisitos
*   **Python 3.10+**: Certifique-se de que o Python está instalado e adicionado ao seu PATH.
*   **AdsPower**: O software AdsPower deve estar aberto e logado.
*   **Google Sheets API**: Se estiver usando o logger de planilhas, certifique-se de ter o arquivo `service_account.json`.

### 2. Configuração do Ambiente
1. Clone o repositório ou baixe os arquivos.
2. Abra o terminal (PowerShell ou CMD) na pasta do projeto.
3. Crie e ative um ambiente virtual:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```

### 3. Configuração das Variáveis (.env)
Crie um arquivo `.env` na raiz do projeto com o seguinte modelo:
```env
SUPABASE_URL=https://sua-url.supabase.co
SUPABASE_KEY=sua-chave-aqui
ADSPOWER_API_URL=http://127.0.0.1:50325
ADSPOWER_API_KEY=sua-chave-api
CLICKUP_API_KEY=pk_...
CLICKUP_LIST_ID=...
CLICKUP_CHANNEL_ID=...
GOOGLE_SHEET_ID=...
```

### 4. Importando Contas
Para importar as contas do arquivo `contas.csv` para o banco de dados Supabase:
```powershell
python src/import_csv.py
```

### 5. Executando o Scraper (Batch)
Para processar todas as contas ativas em lote:
```powershell
python src/batch_runner.py
```

---

## 📂 Organização dos Arquivos

| Arquivo | Descrição |
| :--- | :--- |
| `src/scraper.py` | **Coração do projeto.** Contém toda a lógica de interação com a Livelo, detecção de WAF (Access Denied), login e extração de pontos. |
| `src/batch_runner.py` | Orquestrador que percorre a lista de contas no Supabase, inicia o AdsPower e chama o scraper. |
| `src/adspower.py` | Controlador da API local do AdsPower (Start/Stop de perfis e captura de nomes). |
| `src/sheets_logger.py` | Responsável por registrar o resultado de cada conta em tempo real no Google Sheets. |
| `src/clickup.py` | Envia notificações e cria tarefas no ClickUp quando há divergência de saldo ou erros fatais. |
| `src/import_csv.py` | Script utilitário para levar os dados do CSV para o Supabase. |
| `src/main.py` | (Opcional) Ponto de entrada para rodar como uma API FastAPI. |
| `requirements.txt` | Lista de bibliotecas Python necessárias. |
| `.gitignore` | Protege arquivos sensíveis (`.env`, `service_account.json`) de irem para o Git. |

---

## 🛡️ Defesas Implementadas
O scraper conta com lógicas avançadas de resiliência:
*   **Parallel Blind Freeze**: Congela todas as abas abertas em paralelo para evitar que abas pesadas travem a automação.
*   **WAF Detection (Whitelist/Blacklist)**: Detecta bloqueios "Access Denied" da Akamai sem confundir com a Home Page legítima.
*   **Auto-Recovery (Retry)**: Se for bloqueado após o login, ele fecha a aba, limpa o estado e tenta novamente em uma guia virgem.
*   **Login Guard**: Valida se o perfil do usuário realmente carregou antes de tentar ler os pontos, evitando "Haliucinações" de extração.
