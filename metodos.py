import streamlit as st
import psycopg2
import time
import os
from dotenv import load_dotenv

load_dotenv()

# função de conexao de db
@st.cache_resource #mantém o cache de conexão do streamlit
def iniciar_conexao():
    tentativas = 5
    while tentativas > 0:
        # ==========================================
        # GARANTE QUE O BANCO DE DADOS VAI SER CRIADO ANTES DO STREAMLIT INICIAR
        # ==========================================
        try:
            return psycopg2.connect(
                host=os.getenv("host"),
                port=os.getenv("port"),
                database=os.getenv("database"),
                user=os.getenv("user"),
                password=os.getenv("password")
            )
        except psycopg2.OperationalError as e:
            tentativas -= 1
            print(f"Banco de dados ainda não está pronto. Tentando novamente em 2 segundos... ({tentativas} tentativas restantes)")
            if tentativas == 0:
                st.error("Falha fatal: Não foi possível conectar ao banco de dados após várias tentativas.")
                raise e
            time.sleep(2)

def carregar_sintomas():
    conn = iniciar_conexao() 
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM sintomas_padrao ORDER BY nome ASC")
            registros = cur.fetchall()
            return [linha[0] for linha in registros]
    except Exception as e:
        st.error(f"Erro ao carregar sintomas do banco: {e}")
        return []

# ==========================================
#   CRIAÇÃO DE TABELA EM NOVA MAQUINA
# ==========================================

def criar_tabelas_se_nao_existirem():
    conn = iniciar_conexao()
    try:
        with conn.cursor() as cur:
            # 1. Tabela de Rotina
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rotina_medicamentos (
                    id SERIAL PRIMARY KEY,
                    nome_remedio VARCHAR(255) NOT NULL,
                    dosagem VARCHAR(100),
                    horario VARCHAR(50),
                    ativo BOOLEAN DEFAULT TRUE
                );
            """)
            
            # 2. Tabela do Dicionário de Sintomas
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sintomas_padrao (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(100) UNIQUE NOT NULL
                );
            """)
            
            # 3. Tabela Principal de Registros
            cur.execute("""
                CREATE TABLE IF NOT EXISTS registros_saude (
                    id SERIAL PRIMARY KEY,
                    data DATE NOT NULL,
                    nome_remedio VARCHAR(255),
                    dosagem VARCHAR(100),
                    horario VARCHAR(50),
                    bem_estar VARCHAR(50),
                    qualidade_alimentacao VARCHAR(50)
                );
            """)
            
            # 4. Tabela Ponte (Relacional)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS historico_sintomas (
                    id SERIAL PRIMARY KEY,
                    registro_id INTEGER REFERENCES registros_saude(id) ON DELETE CASCADE,
                    sintoma_id INTEGER REFERENCES sintomas_padrao(id) ON DELETE CASCADE,
                    periodo VARCHAR(50)
                );
            """)
        conn.commit()
    except Exception as e:
        st.error(f"Erro Crítico ao montar estrutura do banco: {e}")
        conn.rollback()

def salvar_registro_saude(dados_registro, sintomas_por_periodo):
    """
    dados_registro: tupla (data, nome, dose, hora, bem_estar, alimentacao)
    sintomas_por_periodo: dicionário {'Manhã': [lista], 'Tarde': [lista], etc.}
    """
    conn = iniciar_conexao()
    try:
        with conn.cursor() as cur:
            # 1. Salva na tabela principal e pega o ID gerado
            cur.execute(
                """INSERT INTO registros_saude (data, nome_remedio, dosagem, horario, bem_estar, qualidade_alimentacao) 
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                dados_registro
            )
            res = cur.fetchone()
            if not res:
                return False
            registro_id = res[0]

            # 2. Percorre os sintomas e períodos para salvar na ponte
            for periodo, lista_sintomas in sintomas_por_periodo.items():
                for sintoma in lista_sintomas:
                    if sintoma.strip():
                        # Limpa espaços e coloca em Title Case (ex: "Dor De Cabeça")
                        sintoma_limpo = sintoma.strip().title()
                        
                        # Garante que o sintoma existe no dicionário e obtém seu ID de forma atômica
                        cur.execute(
                            """INSERT INTO sintomas_padrao (nome) VALUES (%s) 
                               ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome 
                               RETURNING id""", 
                            (sintoma_limpo,)
                        )
                        sintoma_id = cur.fetchone()[0]
                        
                        # Cria a ligação na tabela ponte
                        cur.execute(
                            "INSERT INTO historico_sintomas (registro_id, sintoma_id, periodo) VALUES (%s, %s, %s)",
                            (registro_id, sintoma_id, periodo)
                        )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        conn.rollback()
        return False

def importar_sintomas():
    conn = iniciar_conexao()

    dados_sintomas = '''Anedonia
    Ansiedade
    Ansiedade Física
    Azia
    Bruxismo
    Cefaleia
    Confusão Mental
    Depressão
    Desatenção
    Dispneia
    Dor Muscular
    Enjôo
    Febre
    Fraqueza
    Gases
    Hiperatividade
    Hipertensão
    Hipertensão Pós-prandial
    Hipotensão
    Hipotensão Pós-prandial
    Impulsividade
    Indigestão
    Inércia do Sono
    Insônia Terminal
    Irritabilidade
    Letargia
    Lombalgia
    Oleosidade
    Orquialgia
    Otite
    Queimação Abdominal
    Sono Pós-Prandial
    Sonolência
    Stress
    Taquicardia'''
    
    listarapida = [item.strip() for item in dados_sintomas.strip().split('\n')]
    
    with conn.cursor() as cur:
        for sintoma in listarapida:
            cur.execute("INSERT INTO sintomas_padrao (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (sintoma,))
            conn.commit()