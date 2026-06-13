-- 1. Criação do Banco de Dados do Data Warehouse
CREATE DATABASE IF NOT EXISTS techstore_dw;
USE techstore_dw;

-- 2. Criação da Dimensão Clientes
CREATE TABLE IF NOT EXISTS dim_clientes (
    cliente_sk INT AUTO_INCREMENT PRIMARY KEY, -- Surrogate Key (Chave Substituta)
    cliente_id_original INT NOT NULL,          -- ID vindo do sistema de origem
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(150),
    cidade VARCHAR(100),
    estado VARCHAR(50),
    regiao VARCHAR(50)                         -- Calculado no ETL (ex: Norte, Nordeste)
);

-- 3. Criação da Dimensão Produtos (Com suporte a SCD Tipo 2)
CREATE TABLE IF NOT EXISTS dim_produtos (
    produto_sk INT AUTO_INCREMENT PRIMARY KEY, -- Surrogate Key para histórico
    produto_id_original INT NOT NULL,          -- ID vindo do sistema de origem
    nome VARCHAR(150) NOT NULL,
    categoria VARCHAR(100),
    preco_original DECIMAL(10, 2),
    custo_original DECIMAL(10, 2),
    data_inicio DATETIME NOT NULL,             -- Início da vigência desta versão
    data_fim DATETIME,                         -- Fim da vigência (NULL se for o atual)
    versao_atual CHAR(1) DEFAULT 'S'           -- 'S' para Atual, 'N' para Antigo
);

-- 4. Criação da Dimensão Datas (Inteligência de Tempo)
CREATE TABLE IF NOT EXISTS dim_datas (
    data_sk INT PRIMARY KEY,                   -- Formato AAAAMMDD (Ex: 20260612)
    data_completa DATE NOT NULL,
    dia INT NOT NULL,
    mes INT NOT NULL,
    ano INT NOT NULL,
    trimestre INT NOT NULL,
    dia_semana VARCHAR(20) NOT NULL
);

-- 5. Criação da Tabela Fato Vendas
CREATE TABLE IF NOT EXISTS fato_vendas (
    venda_id INT NOT NULL,                     -- ID da venda original
    cliente_sk INT NOT NULL,                   -- Chave estrangeira para cliente
    produto_sk INT NOT NULL,                   -- Chave estrangeira para produto (versão exata)
    data_sk INT NOT NULL,                      -- Chave estrangeira para a data
    quantidade INT NOT NULL,
    receita_total DECIMAL(12, 2) NOT NULL,     -- quantidade * preco_original
    custo_total DECIMAL(12, 2) NOT NULL,       -- quantidade * custo_original
    lucro_total DECIMAL(12, 2) NOT NULL,       -- receita_total - custo_total
    
    PRIMARY KEY (venda_id, produto_sk),        -- Chave primária composta
    
    -- Restrições de Chave Estrangeira (Garante a integridade do DW)
    FOREIGN KEY (cliente_sk) REFERENCES dim_clientes(cliente_sk),
    FOREIGN KEY (produto_sk) REFERENCES dim_produtos(produto_sk),
    FOREIGN KEY (data_sk) REFERENCES dim_datas(data_sk)
);
