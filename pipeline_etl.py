import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# 1. CONFIGURAÇÕES GLOBAIS E CONEXÃO
DB_USER = "root"
DB_PASS = "nAkAmOtO102030"  
DB_HOST = "localhost"
DB_PORT = "3306"
DB_NAME = "techstore_dw"

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

import os
import pandas as pd

def extract():
    """Etapa 1: Extração - Lendo o arquivo Excel real da TechStore"""
    print("Iniciando a etapa de Extração dos dados...")
    
    caminho_arquivo = r"C:\Users\nakam\OneDrive\Documentos\Projeto_TechStore\dataset\tabelao_dw_ecommerce_desafio.xlsx"
    
    df_bruto = pd.read_excel(caminho_arquivo)
    
    print(f"Extração concluída com sucesso! Foram carregadas {len(df_bruto)} linhas.\n")
    return df_bruto

# 3. FUNÇÃO TRANSFORM
def transform(df):
    print("Iniciando a etapa de Transformação dos dados...")
    
    # 1. Tratamento das colunas originais do Excel
    df['preco_unitario'] = df['preco_unitario'].fillna(0)
    df['custo_unitario'] = df['custo_unitario'].fillna(0)
    df['quantidade'] = df['quantidade'].fillna(1).astype(int)
    
    df['cliente_nome'] = df['cliente_nome'].fillna('Não Informado').str.strip()
    df['regiao'] = df['regiao'].fillna('Não Informada').str.strip().str.title()
    df['data'] = pd.to_datetime(df['data'])
    
    # 2. Criando df_clientes
    df_clientes = df[['cliente_id', 'cliente_nome', 'regiao']].drop_duplicates(subset=['cliente_id']).copy()
    df_clientes.columns = ['cliente_id_original', 'nome', 'regiao']
    df_clientes['email'] = df_clientes['nome'].str.lower().str.replace(' ', '') + '@email.com'
    df_clientes['cidade'] = 'Belém'
    df_clientes['estado'] = 'PA'
    
    # 3. Criando df_produtos
    df_produtos = df[['produto_id', 'produto', 'categoria', 'custo_unitario', 'preco_unitario']].drop_duplicates(subset=['produto_id']).copy()
    df_produtos.columns = ['produto_id_original', 'nome', 'categoria', 'custo_original', 'preco_original']
    
    # 4. Criando df_datas
    df_datas = pd.DataFrame({'data_completa': df['data'].unique()})
    df_datas['data_sk'] = df_datas['data_completa'].dt.strftime('%Y%m%d').astype(int)
    df_datas['dia'] = df_datas['data_completa'].dt.day
    df_datas['mes'] = df_datas['data_completa'].dt.month
    df_datas['ano'] = df_datas['data_completa'].dt.year
    df_datas['trimestre'] = df_datas['data_completa'].dt.quarter
    df_datas['dia_semana'] = df_datas['data_completa'].dt.day_name()

    # 5. Criando df_fato e calculando os totais financeiros
    df_fato = df.copy()
    df_fato['data_sk'] = df_fato['data'].dt.strftime('%Y%m%d').astype(int)
    
    df_fato['receita_total'] = df_fato['quantidade'] * df_fato['preco_unitario']
    df_fato['custo_total'] = df_fato['quantidade'] * df_fato['custo_unitario']
    df_fato['lucro_total'] = df_fato['receita_total'] - df_fato['custo_total']
    
    # Garante que nenhum cálculo gerou nulo
    df_fato['receita_total'] = df_fato['receita_total'].fillna(0)
    df_fato['custo_total'] = df_fato['custo_total'].fillna(0)
    df_fato['lucro_total'] = df_fato['lucro_total'].fillna(0)
    
    # --- MAPEAMENTO INTELIGENTE DE CHAVES (SK) ---
    dim_clientes_banco = pd.read_sql("SELECT cliente_sk, cliente_id_original FROM dim_clientes", con=engine)
    dim_produtos_banco = pd.read_sql("SELECT produto_sk, produto_id_original FROM dim_produtos WHERE versao_atual = 'S'", con=engine)
    
    df_fato = df_fato.merge(dim_clientes_banco, left_on='cliente_id', right_on='cliente_id_original', how='left')
    
    df_fato = df_fato.merge(dim_produtos_banco, left_on='produto_id', right_on='produto_id_original', how='left')
    
    df_fato['cliente_sk'] = df_fato['cliente_sk'].fillna(1).astype(int)
    df_fato['produto_sk'] = df_fato['produto_sk'].fillna(1).astype(int)
    
    df_fato = df_fato[['id_venda', 'cliente_sk', 'produto_sk', 'data_sk', 'quantidade', 'receita_total', 'custo_total', 'lucro_total']]
    df_fato.columns = ['venda_id', 'cliente_sk', 'produto_sk', 'data_sk', 'quantidade', 'receita_total', 'custo_total', 'lucro_total']
    
    print("Transformação concluída com sucesso!\n")
    return df_clientes, df_produtos, df_datas, df_fato

# 4. FUNÇÃO LOAD
def load(df_clientes, df_produtos, df_datas, df_fato):
    print("Iniciando a etapa de Carga dos dados no MySQL...")
    
    # 1. Carga Datas
    datas_existentes = pd.read_sql("SELECT data_sk FROM dim_datas", con=engine)
    df_datas_novas = df_datas[~df_datas['data_sk'].isin(datas_existentes['data_sk'])]
    if not df_datas_novas.empty:
        df_datas_novas.to_sql('dim_datas', con=engine, if_exists='append', index=False)
        print(f"-> {len(df_datas_novas)} novas datas inseridas.")
        
    # 2. Carga Clientes
    clientes_existentes = pd.read_sql("SELECT cliente_id_original FROM dim_clientes", con=engine)
    df_clientes_novos = df_clientes[~df_clientes['cliente_id_original'].isin(clientes_existentes['cliente_id_original'])]
    if not df_clientes_novos.empty:
        df_clientes_novos.to_sql('dim_clientes', con=engine, if_exists='append', index=False)
        print(f"-> {len(df_clientes_novos)} novos clientes cadastrados.")

    # 3. Carga Produtos (SCD Type 2)
    print("Processando dim_produtos (SCD Type 2)...")
    data_atual_processamento = datetime.now()
    for _, linha in df_produtos.iterrows():
        id_orig = linha['produto_id_original']
        nome_prod = linha['nome']
        cat_prod = linha['categoria']
        custo_prod = linha['custo_original']
        preco_prod = linha['preco_original']
        
        query = f"SELECT * FROM dim_produtos WHERE produto_id_original = {id_orig} AND versao_atual = 'S'"
        prod_banco = pd.read_sql(query, con=engine)
        
        if prod_banco.empty:
            novo_prod = pd.DataFrame([{
                'produto_id_original': id_orig, 'nome': nome_prod, 'categoria': cat_prod,
                'custo_original': custo_prod, 'preco_original': preco_prod,
                'data_inicio': data_atual_processamento, 'data_fim': None, 'versao_atual': 'S'
            }])
            novo_prod.to_sql('dim_produtos', con=engine, if_exists='append', index=False)
        else:
            preco_banco = float(prod_banco['preco_original'].iloc[0])
            custo_banco = float(prod_banco['custo_original'].iloc[0])
            sk_antiga = int(prod_banco['produto_sk'].iloc[0])
            
            if preco_prod != preco_banco or custo_prod != custo_banco:
                with engine.begin() as conexao:
                    conexao.execute(f"UPDATE dim_produtos SET data_fim = '{data_atual_processamento}', versao_atual = 'N' WHERE produto_sk = {sk_antiga}")
                
                nova_versao_prod = pd.DataFrame([{
                    'produto_id_original': id_orig, 'nome': nome_prod, 'categoria': cat_prod,
                    'custo_original': custo_prod, 'preco_original': preco_prod,
                    'data_inicio': data_atual_processamento, 'data_fim': None, 'versao_atual': 'S'
                }])
                nova_versao_prod.to_sql('dim_produtos', con=engine, if_exists='append', index=False)

    # 4. Carga Tabela Fato (Versão definitiva e limpa)
    print("Processando tabela fato_vendas...")
    try:
        from sqlalchemy import text
        
        with engine.begin() as conexao:
            conexao.execute(text("TRUNCATE TABLE fato_vendas;"))
        print("-> Tabela fato_vendas esvaziada (Truncate) com sucesso!")
            
        df_fato.to_sql('fato_vendas', con=engine, if_exists='append', index=False)
        print("-> Tabela fato_vendas carregada com sucesso!")
        
    except Exception as e:
        print(f"Erro ao carregar fato_vendas: {e}")
            
        df_fato.to_sql('fato_vendas', con=engine, if_exists='append', index=False)
        print("-> Tabela fato_vendas carregada com sucesso!")
        
    except Exception as e:
        print(f"Erro ao carregar fato_vendas: {e}")

# --- 4. CARGA DA TABELA FATO VENDAS ---
    print("Processando tabela fato_vendas...")
    try:
        from sqlalchemy import text
        
        with engine.begin() as conexao:
            conexao.execute(text("TRUNCATE TABLE fato_vendas;"))
        print("-> Tabela fato_vendas esvaziada (Truncate) com sucesso!")
            
        df_fato.to_sql('fato_vendas', con=engine, if_exists='append', index=False)
        print("-> Tabela fato_vendas carregada com sucesso!")
        
    except Exception as e:
        print(f"Erro ao carregar fato_vendas: {e}")

# 5. FUNÇÃO VALIDATE
def validate():
    """Etapa 4: Validação - Uma verificação rápida pós-carga"""
    print("Iniciando a etapa de Validação...")
    try:
        total_vendas = pd.read_sql("SELECT COUNT(*) as total FROM fato_vendas", con=engine).iloc[0]['total']
        total_clientes = pd.read_sql("SELECT COUNT(*) as total FROM dim_clientes", con=engine).iloc[0]['total']
        print(f"--- RELATÓRIO DE VALIDAÇÃO ---")
        print(f"Total de Clientes no DW: {total_clientes}")
        print(f"Total de Vendas registradas na Fato: {total_vendas}")
        print(f"-------------------------------")
    except Exception as e:
        print(f"Erro na validação: {e}")

# BLOCO PRINCIPAL DE EXECUÇÃO
if __name__ == "__main__":
    print("--- INICIANDO PIPELINE DE ETL (TECHSTORE) ---")
    
    df_dados_brutos = extract()
    df_cli, df_prod, df_dat, df_fat = transform(df_dados_brutos)
    load(df_cli, df_prod, df_dat, df_fat)
    validate()
    
    print("--- PIPELINE CONCLUÍDO COM SUCESSO ---")