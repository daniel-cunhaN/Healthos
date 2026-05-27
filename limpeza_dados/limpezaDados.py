import pandas as pd
import numpy as np

df = pd.read_csv('limpeza_dados/dadosNaoFormatados.csv', encoding='utf-8', skipinitialspace=True, sep=";")
df.columns = df.columns.str.strip()

# Tratamento da coluna 'Remédio'
df['Remédio'] = df['Remédio'].astype(str).str.split('|')
df = df.explode('Remédio')
df['Remédio'] = df['Remédio'].str.strip()

# Extração de Dosagem, Horário e Nome
df['Dosagem'] = df['Remédio'].str.extract(r'\((.*?)\)') 
df['Horário'] = df['Remédio'].str.split('-').str[1].str.strip()
df.loc[df['Horário'].astype(str).str.contains(',', na=False), 'Horário'] = np.nan
df['Nome_Remédio'] = df['Remédio'].str.split(r'\(|-').str[0].str.strip()

# Tratamento de Nulos
df = df.fillna('')

# Padronização da Data (Converte de qualquer formato para YYYY-MM-DD)
df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce').dt.date

# Remove coluna remédio desnecessária
colunas_finais = ['Data', 'Nome_Remédio', 'Dosagem', 'Horário', 'Bem-estar', 'Qualidade Alimentação', 'Sintomas (M)', 'Sintomas (T)', 'Sintomas (N)', 'Sintomas (P)']
df = df[colunas_finais]

#Substituições de nomes legado
# Dicionário de Traduções (Corrigido com os dados reais)
dicionario_sintomas = {
    'Ansiedade Física (L)': 'Ansiedade Física',
    'Ansiedade Física (M)': 'Ansiedade Física',
    'Ansiedade Física (A)': 'Ansiedade Física',
    'Autofagia': 'Ansiedade Física',
    'Pensamento Acelerado': 'Ansiedade',
    'Dor de cabeca': 'Cefaleia',
    'Brain Fog': 'Confusão Mental' 
}

def corrigir_celula_sintomas(texto_celula):
    # Se a célula estiver vazia no CSV (NaN), pula para a próxima
    if pd.isna(texto_celula):
        return texto_celula
        
    # Fatiamos a célula usando a barra
    sintomas = str(texto_celula).split('|')
    
    sintomas_limpos = []
    
    for s in sintomas:
        s_sem_espaco = s.strip() # Remove espaços acidentais (ex: " Ansiedade")
        
        # .get(): procura a palavra no dicionário. 
        # Se achar, devolve o nome novo. Se NÃO achar, devolve o nome original.
        s_novo = dicionario_sintomas.get(s_sem_espaco, s_sem_espaco).title()
        
        sintomas_limpos.append(s_novo)
        
    # Junta tudo de novo com a barra e os espaços bonitinhos
    return ' | '.join(sintomas_limpos)

# 3. Aplica a função nas 4 colunas de uma vez só
colunas_para_limpar = ['Sintomas (M)', 'Sintomas (T)', 'Sintomas (N)', 'Sintomas (P)']

for coluna in colunas_para_limpar:
    # O comando apply roda a função em todas as linhas da coluna instantaneamente
    df[coluna] = df[coluna].apply(corrigir_celula_sintomas)

df.to_csv('limpeza_dados/dadosLimpos.csv', index=False, encoding='utf-8')

print(f"Limpeza concluída! {len(df)} linhas prontas para injeção.")
