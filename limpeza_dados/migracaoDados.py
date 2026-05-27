import psycopg2
import pandas as pd
import time
import os
from dotenv import load_dotenv

load_dotenv()

time.sleep(5) # Proteção para previnir execução incorreta do codigo de migração quando for aberto pelo docker
# Conexão com o Docker
conn = psycopg2.connect(host=os.getenv("host"), port=os.getenv("port"), database=os.getenv("database"), user=os.getenv("user"), password=os.getenv("password"))

# Mapa para traduzir o nome das colunas do CSV para os turnos do banco
mapa_turnos = {
    'Sintomas (M)': 'Manhã',
    'Sintomas (T)': 'Tarde',
    'Sintomas (N)': 'Noite',
    'Sintomas (P)': 'Persistente'
}

df = pd.read_csv('limpeza_dados/dadosLimpos.csv', encoding = 'utf-8')

# Remove qualquer espaço invisível dos títulos das colunas
df.columns = df.columns.str.strip()

#Substitui todos os NaN por "vazio"
df = df.fillna('') 


sucessos = 0
pulados = 0 # Pra saber quantas linhas pulei
index = " "

try:
    with conn.cursor() as cur:
        # Pega linha por linha do seu Excel limpo
        for index, row in df.iterrows():
            
            # Pula linhas vazias, nulas ou que só têm espaços
            if str(row['Data']).strip() == '' or str(row['Data']).strip() == 'nan':
                continue
            # --- PASSO 0: O Olheiro (Verifica se já existe) ---
            cur.execute(
                """SELECT id FROM registros_saude WHERE data = %s AND nome_remedio = %s AND horario = %s""",
                (row['Data'], row['Nome_Remédio'], row['Horário'])
            )
            registro_existente = cur.fetchone()

            # Se achou algo, pula linha do Excel inteira e vai para a próxima
            if registro_existente:
                pulados += 1
                continue

            # --- PASSO A: Cria o Registro Principal ---
            cur.execute(
                """INSERT INTO registros_saude (data, nome_remedio, dosagem, horario, bem_estar, qualidade_alimentacao) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (row['Data'], row['Nome_Remédio'], row['Dosagem'], row['Horário'], row['Bem-estar'], row['Qualidade Alimentação'])
            )
            registro_id = cur.fetchone()[0]

            # --- PASSO B: Processa os Sintomas e cria as Pontes ---
            for coluna_csv, turno_banco in mapa_turnos.items():
                sintomas_da_celula = str(row[coluna_csv])
                
                # Se a pessoa anotou algo neste turno...
                if sintomas_da_celula.strip():
                    lista_sintomas = sintomas_da_celula.split('|')
                    
                    for sintoma in lista_sintomas:
                        sintoma_limpo = sintoma.strip()
                        if not sintoma_limpo:
                            continue
                            
                        # 1. Garante que o sintoma existe no Dicionário
                        cur.execute(
                            "INSERT INTO sintomas_padrao (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", 
                            (sintoma_limpo,)
                        )
                        
                        # 2. Pega o ID desse sintoma
                        cur.execute("SELECT id FROM sintomas_padrao WHERE nome = %s", (sintoma_limpo,))
                        sintoma_id = cur.fetchone()[0]
                        
                        # 3. Injeta os sintomas na tabela de sintomas
                        cur.execute(
                            "INSERT INTO historico_sintomas (registro_id, sintoma_id, periodo) VALUES (%s, %s, %s)",
                            (registro_id, sintoma_id, turno_banco)
                        )
            sucessos += 1
            
    conn.commit()
    print(f"🚀 MIGRACÃO CONCLUÍDA! {sucessos} novos registros inseridos. {pulados} repetidos foram ignorados.")

except Exception as e:
    print(f"❌ Ocorreu um erro na linha {index} do CSV: {e}")
    conn.rollback()
finally:
    conn.close()