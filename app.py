import streamlit as st
import pandas as pd
import psycopg2
import warnings
import threading
import time
import os
import signal
from datetime import date
from streamlit_tags import st_tags
import streamlit.components.v1 as components
from streamlit.runtime import get_instance
from metodos import iniciar_conexao, carregar_sintomas, salvar_registro_saude, criar_tabelas_se_nao_existirem, importar_sintomas

# ====================================
# Simulação de Aplicativo Desktop
# ====================================

# --- LÓGICA DE AUTO-SHUTDOWN ---
def shutdown_watchdog():
    # Dá um tempo para a primeira conexão acontecer
    time.sleep(20) 
    
    idle_start = None
    
    def has_active_connections(port=8501):
        port_hex = f"{port:04X}"
        try:
            with open("/proc/net/tcp", "r") as f:
                lines = f.readlines()[1:] # ignora o cabeçalho
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        local_addr = parts[1]
                        state = parts[3]
                        # state '01' é ESTABLISHED
                        if local_addr.endswith(f":{port_hex}") and state == "01": 
                            return True
            return False
        except Exception as e:
            print(f"Watchdog erro ao ler tcp: {e}")
            return False

    while True:
        time.sleep(2)
        try:
            if has_active_connections():
                idle_start = None  # Reseta o timer se houver alguém
            else:
                if idle_start is None:
                    idle_start = time.time()
                
                # Se ficar 10 segundos sem nenhuma aba aberta
                if time.time() - idle_start > 3:
                    print("Nenhuma aba ativa detectada. Desligando HealthOS...")
                    os._exit(0) # Mata o processo imediatamente
        except Exception as e:
            print(f"Watchdog exception: {e}")

if not any(t.name == "ShutdownWatchdog" for t in threading.enumerate()):
    threading.Thread(target=shutdown_watchdog, name="ShutdownWatchdog", daemon=True).start()

# 1. Configuração da Página para celular
st.set_page_config(page_title="Healthos", page_icon="💊", layout="centered")

conn = iniciar_conexao()

# GERA TABELAS SE FOR PRIMEIRA VEZ RODANDO
criar_tabelas_se_nao_existirem()

# IMPORTA SINTOMAS
importar_sintomas()

st.title("📱 HealthOS")

# 3. Criando as Abas da Interface
tab_diario, tab_rotina, tab_dashboard = st.tabs(["📝 Registro Diário", "⚙️ Configurar Rotina", "📊 Dashboard"])

# ==========================================
# ABA 1: PADRÃO DE PREENCHIMENTO E FORMULÁRIO
# ==========================================
with tab_diario:
    st.write("Registre sua saúde de hoje.")
    
    # --- PERGUNTAS GERAIS DO DIA (Ficam no topo, visíveis para todos os botões) ---
    col_b, col_a = st.columns(2)
    with col_b:
        bem_estar_geral = st.selectbox("Bem-estar hoje", ["Normal", "Ruim", "Muito Ruim"])
    with col_a:
        alimentacao_geral = st.selectbox("Alimentação hoje", ["Excelente", "Boa", "Mediana", "Ruim", "Muito Ruim"])

    st.divider()

    # ==========================================
    #           INSERÇÃO DE ROTINA
    # ==========================================
    st.info("💡 Dica: Use o botão abaixo para preencher automaticamente os remédios que você toma todos os dias.")
    if st.button("🚀 Preencher com a Rotina Padrão", use_container_width=True, type="primary"):
        with conn.cursor() as cur:
            cur.execute("SELECT nome_remedio, dosagem, horario FROM rotina_medicamentos WHERE ativo = TRUE")
            rotina = cur.fetchall()
            
            if rotina:
                for remedio in rotina:
                    cur.execute(
                        """INSERT INTO registros_saude 
                        (data, nome_remedio, dosagem, horario, bem_estar, qualidade_alimentacao) 
                        VALUES (%s, %s, %s, %s, %s, %s)""",
                        # Usa as variáveis do topo
                        (date.today(), remedio[0], remedio[1], remedio[2], bem_estar_geral, alimentacao_geral)
                    )
                conn.commit()
                st.toast(f'Rotina injetada com sucesso! ({len(rotina)} itens)', icon='🚀')
            else:
                st.warning("Nenhuma rotina configurada. Vá na aba 'Configurar Rotina'.")

    st.divider()

    # ==========================================
    #           FORMULÁRIO MANUAL
    # ==========================================
    lista_sintomas_db = carregar_sintomas()

    with st.form("registro_form", clear_on_submit=True):
        st.markdown("<h4 style='text-align: center;'>Registrar remédio extra ou sintoma</h4>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1: 
            data_registro = st.date_input("Data", date.today())
            nome_remedio = st.text_input("Nome do Remédio")
            
        with col2: 
            horario = st.selectbox("Horário", ["Manhã", "Tarde", "Noite", "P/Ref", "Alm", "Multiplos", "Ceia"])
            dosagem = st.text_input("Dosagem")        
        st.divider() 
        
        st.markdown("<h5 style='text-align: center;'>🤒 Sintomas por Período</h5>", unsafe_allow_html=True)        
        col_m, col_t, col_n, col_p = st.columns(4)
        
        with col_m:
            sintomasM = st_tags(label='Manhã', text='Adicionar...', suggestions=lista_sintomas_db, maxtags=10, key='sintomas_manha')
        with col_t:
            sintomasT = st_tags(label='Tarde', text='Adicionar...', suggestions=lista_sintomas_db, maxtags=10, key='sintomas_tarde')
        with col_n:
            sintomasN = st_tags(label='Noite', text='Adicionar...', suggestions=lista_sintomas_db, maxtags=10, key='sintomas_noite')
        with col_p:
            sintomasP = st_tags(label='Persistentes', text='Adicionar...', suggestions=lista_sintomas_db, maxtags=10, key='sintomas_persistentes')
        
        st.write("") 
        submit_button = st.form_submit_button("Salvar Registro Manual", use_container_width=True)
        st.write("")
        undo_changes = st.form_submit_button("Desfazer Alterações", use_container_width=True)
        
    # --- LÓGICA DE SALVAR O FORMULÁRIO ---
    if submit_button:
        if dosagem and not nome_remedio:
            st.error("⚠️ Se for registrar um remédio extra, por favor digite o nome dele.")
        else:
            nome_final = nome_remedio if nome_remedio != "" else "Padrão"
            dosagem_final = dosagem if dosagem != "" else "Padrão"
            horario_final = horario if nome_remedio != "" else "Padrão"

            # Usa as variáveis do topo aqui também
            dados_registro = (data_registro, nome_final, dosagem_final, horario_final, bem_estar_geral, alimentacao_geral)
            
            sintomas_map = {
                'Manhã': sintomasM,
                'Tarde': sintomasT,
                'Noite': sintomasN,
                'Persistente': sintomasP
            }

            sucesso = salvar_registro_saude(dados_registro, sintomas_map) 
            
            if sucesso:
                st.toast('✅ Registro salvo com sucesso!', icon='🎉')
            else:
                st.error('❌ Falha ao salvar o registro no banco de dados.')
    if undo_changes:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM registros_saude WHERE data = %s", (date.today(),))
            conn.commit()
            st.toast("Tudo o que foi inserido hoje foi apagado!", icon="🗑️")
            st.rerun()

# ==========================================
#        ABA 2: CONFIGURAR ROTINA
# ==========================================
with tab_rotina:
    st.subheader("1. Adicionar ao Padrão Diário")
    st.write("Adicione os remédios que você toma todos os dias.")
    
    with st.form("rotina_form", clear_on_submit=True):
        r_nome = st.text_input("Nome do Remédio Fixo")
        r_dose = st.text_input("Dosagem Fixa")
        r_hora = st.selectbox("Horário Fixo", ["Manhã", "Tarde", "Noite", "P/Ref", "Alm", "Multiplos", "Ceia"])
        
        btn_salvar_rotina = st.form_submit_button("Salvar na Rotina", use_container_width=True)
        
        if btn_salvar_rotina and r_nome:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO rotina_medicamentos (nome_remedio, dosagem, horario) VALUES (%s, %s, %s)",
                    (r_nome, r_dose, r_hora)
                )
                conn.commit()
            st.success("Adicionado à rotina!")
            st.rerun()
            
    st.divider()
    
    st.subheader("2. Minha Rotina Atual")
    
    # Inicia um bloco de contexto para capturar e manipular avisos (warnings) do sistema
    with warnings.catch_warnings():
        # Configura o filtro de avisos para ignorar (não exibir) alertas do tipo UserWarning
        warnings.simplefilter("ignore", UserWarning)
        # Executa uma consulta SQL no banco para buscar os medicamentos ativos e salva o resultado em um DataFrame do pandas
        df_rotina = pd.read_sql("SELECT id, nome_remedio, dosagem, horario FROM rotina_medicamentos WHERE ativo = TRUE", conn)
    
    # Verifica se o DataFrame criado não está vazio (ou seja, se a pessoa possui alguma rotina cadastrada)
    if not df_rotina.empty:
        # Mostra a tabela na interface do Streamlit, com as colunas específicas, ocupando a largura total e escondendo o índice numérico
        st.dataframe(df_rotina[['nome_remedio', 'dosagem', 'horario']], use_container_width=True, hide_index=True)
        # Escreve um texto de instrução na tela para orientar o usuário sobre alterações nas doses
        st.write("Se o médico mudar a dose, remova o antigo abaixo e crie um novo acima:")
        
        # Cria um dicionário onde a chave é o ID e o valor é o "Nome (Dosagem)", iterando pelas linhas do DataFrame
        opcoes_remover = {row['id']: f"{row['nome_remedio']} ({row['dosagem']})" for index, row in df_rotina.iterrows()}
        # Cria uma caixa de seleção interativa na tela com as opções criadas acima e guarda o ID do remédio selecionado
        id_para_remover = st.selectbox("Escolha um remédio para remover da rotina:", options=list(opcoes_remover.keys()), format_func=lambda x: opcoes_remover[x])
        
        if st.button("🗑️ Remover da Rotina", type="primary"):
            with conn.cursor() as cur:
                cur.execute("UPDATE rotina_medicamentos SET ativo = FALSE WHERE id = %s", (id_para_remover,))
                conn.commit()
            st.success("Removido da rotina!")
            st.rerun()
    else:
        st.info("Sua rotina está vazia.")

# ==========================================
# ABA 3: DASHBOARD METABASE
# ==========================================
with tab_dashboard:
    st.subheader("📊 Metabase")
    st.write("Análise avançada dos seus registros e hábitos.")
    
    # Exibe o iframe do Metabase
    components.iframe("http://localhost:3001/public/dashboard/3e08bf1f-2bcd-44bc-b98c-c1bf708ee306#theme=night", height=800, scrolling=True)