# 📚 Web Scraping & AI Analytics (Arquitetura Medalhão)

Este projeto é um pipeline completo de Engenharia de Dados e IA (Inteligência Artificial). Ele realiza a extração de dados de uma livraria online, estrutura as informações em um banco de dados relacional usando a **Arquitetura Medalhão** (Bronze, Prata e Ouro), e disponibiliza um **Agente SQL Interativo** via Streamlit capaz de responder a perguntas de negócio em linguagem natural consultando diretamente os dados.

---

## 🏗️ Arquitetura do Projeto

O fluxo de dados segue os seguintes passos:

1. **Scraping (Extração):** Um script em Python varre o site [Books to Scrape](http://books.toscrape.com/) para extrair catálogos de livros (título, preço, avaliação, categoria e estoque).
2. **Bronze (Raw Data):** Os dados brutos são inseridos numa tabela PostgreSQL (via Supabase) de forma bruta.
3. **Prata (Clean Data):** Views SQL padronizam nomes, formatam valores, lidam com dados nulos e corrigem tipos de dados.
4. **Ouro (Analytics):** Views SQL criam agregações prontas para análise (ex: preço médio por categoria, distribuição de faixas de preço).
5. **LLM SQL Agent:** Um agente alimentado por IA (Anthropic/Claude) entende a pergunta do usuário, monta a query SQL dinamicamente (somente leitura restrita à Prata e Ouro), valida, executa no banco e devolve a resposta formatada.
6. **Interface Web:** Interface gráfica em Streamlit onde o usuário pode conversar com os dados do catálogo em tempo real.

## 💻 Tecnologias Utilizadas

- **Python 3**
- **Extração:** `requests`, `BeautifulSoup4`
- **Banco de Dados:** PostgreSQL (nuvem Supabase)
- **Driver Postgres:** `psycopg3`
- **Inteligência Artificial:** `Anthropic API` (Modelos Claude)
- **Interface Gráfica:** `Streamlit`, `pandas`

## 📁 Estrutura de Arquivos

- `01_scraper_bronze.py`: Responsável por raspar o site de livros e salvar na camada Bronze.
- `aplicar_sql.py`: Utilitário para executar scripts `.sql` diretamente no banco configurado.
- `sql/`: Pasta que contém as regras de negócio de dados (DDL/DML).
  - `00_bronze.sql`: Criação da tabela de ingestão raw.
  - `01_prata.sql`: Views de limpeza e padronização.
  - `02_ouro.sql`: Views de métricas e agregações financeiras.
- `04_sql_agent.py`: Core lógico contendo o Agent de IA com reflection e guardrails para execução segura de SQL.
- `05_app.py`: Interface em Streamlit que importa o agente e provê um chat para o usuário final.

## 🚀 Como Executar Localmente

### 1. Pré-Requisitos
- Crie um banco PostgreSQL no [Supabase](https://supabase.com).
- Obtenha uma chave de API na [Anthropic](https://www.anthropic.com/) (ou configure o modelo desejado).

### 2. Configurando as Credenciais
Renomeie o arquivo `.env.exemplo` para `.env` e preencha suas variáveis:
```env
DATABASE_URL="postgresql://sua-url-do-supabase:6543/postgres"

# Provedor da IA (Pode ser anthropic, openai, gemini)
LLM_PROVIDER="anthropic"
LLM_MODEL="claude-sonnet-4-6"
ANTHROPIC_API_KEY="sk-ant-..."
```
*(Nota: O arquivo `.env` não é enviado para o Git por questões de segurança)*

### 3. Instalação das Dependências
Recomenda-se criar um ambiente virtual (`.venv`) e instalar as bibliotecas:
```bash
python -m venv .venv
.\.venv\Scripts\activate  # (No Windows)
pip install -r requirements.txt
```

### 4. Executando o Pipeline ETL
Execute os scripts na ordem abaixo para popular o banco de dados e aplicar as regras de negócio (Views):
```bash
python aplicar_sql.py sql/00_bronze.sql
python 01_scraper_bronze.py
python aplicar_sql.py sql/01_prata.sql
python aplicar_sql.py sql/02_ouro.sql
```

### 5. Executando o Assistente Virtual (Streamlit)
Por fim, suba a interface de usuário conversacional:
```bash
streamlit run 05_app.py
```
Seu navegador abrirá em `http://localhost:8501`. Tente perguntar algo como: 
> *"Quantos livros bem avaliados custam menos de £20?"* ou *"Qual a categoria com o maior valor em estoque?"*
