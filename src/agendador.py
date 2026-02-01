import schedule
import time
import subprocess
import sys
import os
from datetime import datetime

# --- CONFIGURAÇÃO ---
HORARIO_EXECUCAO = "01:00"  # Hora que você quer rodar (Formato 24h)
SCRIPT_ALVO = "src/batch_runner.py"
# --------------------

def tarefa():
    print(f"[{datetime.now().strftime('%H:%M')}] Disparando execução do robô...")
    
    # Usa o mesmo interpretador Python atual para rodar o script alvo
    # Isso garante que ele use as bibliotecas do venv
    try:
        subprocess.run([sys.executable, SCRIPT_ALVO], check=True)
        print("Execução agendada finalizada.")
    except Exception as e:
        print(f"Erro ao rodar script agendado: {e}")

# Configura o agendamento
schedule.every().day.at(HORARIO_EXECUCAO).do(tarefa)

# Se quiser rodar a cada X horas, descomente a linha abaixo:
# schedule.every(4).hours.do(tarefa) 

print(f"Agendador Ativo! O robo rodara todo dia as {HORARIO_EXECUCAO}")
print("Mantenha este terminal aberto.")

# Loop infinito para checar o horário
contador = 0
while True:
    schedule.run_pending()
    time.sleep(60) # Checa a cada minuto
    contador += 1
    
    # A cada 50 minutos mostra um "estou vivo" para dar feedback visual
    if contador >= 50:
        print(f"[{datetime.now().strftime('%H:%M')}] Agendador aguardando proxima execucao...")
        contador = 0