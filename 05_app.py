import streamlit as st
import os
import importlib.util
import sys
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)

# Importando o agente original dinamicamente (reaproveitando a lógica limpa da Etapa 4)
spec = importlib.util.spec_from_file_location("sql_agent", "04_sql_agent.py")
sql_agent = importlib.util.module_from_spec(spec)
sys.modules["sql_agent"] = sql_agent
spec.loader.exec_module(sql_agent)

st.set_page_config(page_title="Agente SQL Medalhão", page_icon="📚", layout="wide")

st.title("📚 Agente Analítico de Livros (Medalhão)")
st.markdown("Faça perguntas sobre o catálogo de livros. O agente converterá sua pergunta em SQL, executará no Supabase e responderá em linguagem natural.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("Ver SQL gerado e Resultados"):
                st.code(msg["sql"], language="sql")
                if "results" in msg:
                    # Renderiza o dataframe
                    st.dataframe(pd.DataFrame(msg["results"][1:], columns=msg["results"][0]), use_container_width=True)

if prompt := st.chat_input("Ex: Qual a categoria com maior valor em estoque?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            st.error("DATABASE_URL não configurada no .env")
            st.stop()
            
        with st.spinner("Lendo esquemas e contexto..."):
            schema_info = sql_agent.get_schema(db_url, sem_contexto=False)
            contexto = sql_agent.ler_arquivo("CONTEXTO.md")
            
            sys_prompt = f"""Você é um agente de dados que usa PostgreSQL para responder perguntas de negócio.
Regras OBRIGATÓRIAS:
1. Gere apenas UMA query SQL dentro de um bloco ```sql ... ``` para responder à pergunta. Não invente colunas.
2. Use apenas instruções SELECT ou WITH.
3. Se a pergunta for ambígua, pergunte ao usuário.
4. Responda em Português do Brasil de forma amigável e direta baseada APENAS nos resultados.

CONTEXTO DO PROJETO:
{contexto}

SCHEMA DO BANCO (somente prata e ouro):
{schema_info}"""

        # Preparar historico pro LLM enviando apenas a instrução e o prompt atual
        llm_messages = [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}]
        
        status_text = st.empty()
        
        sucesso_sql = False
        final_sql = ""
        final_table = []
        
        for tentativa in range(3):
            status_text.info(f"Tentativa {tentativa+1}/3: Consultando LLM para gerar SQL...")
            
            try:
                resposta_llm = sql_agent.call_llm(llm_messages)
            except Exception as e:
                status_text.error(f"Erro na API do LLM: {e}")
                break
                
            sql = sql_agent.extract_sql(resposta_llm)
            
            if not sql:
                status_text.empty()
                st.markdown(resposta_llm)
                st.session_state.messages.append({"role": "assistant", "content": resposta_llm})
                break
                
            final_sql = sql
            status_text.info(f"Executando SQL no Supabase...")
            
            sucesso, resultado = sql_agent.execute_sql_safely(db_url, sql)
            
            if sucesso:
                cols, rows = resultado
                table_data = [cols] + [list(r) for r in rows]
                final_table = table_data
                
                resultado_str = f"Colunas: {cols}\nLinhas:\n" + "\n".join(str(r) for r in rows[:10])
                if len(rows) > 10:
                    resultado_str += f"\n... (mais {len(rows)-10} linhas cortadas)"
                    
                llm_messages.append({"role": "assistant", "content": resposta_llm})
                llm_messages.append({"role": "user", "content": f"Resultados da execução do SQL:\n{resultado_str}\n\nBaseado SOMENTE nesses resultados, formule a resposta final para o usuário em português. Mostre o valor final e seja direto."})
                
                status_text.info("Formatando resposta final para exibição...")
                try:
                    resposta_final = sql_agent.call_llm(llm_messages)
                except Exception as e:
                    status_text.error(f"Erro ao formatar resposta: {e}")
                    break
                
                status_text.empty()
                st.markdown(resposta_final)
                
                with st.expander("Ver SQL gerado e Resultados"):
                    st.code(sql, language="sql")
                    st.dataframe(pd.DataFrame(final_table[1:], columns=final_table[0]), use_container_width=True)
                    
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": resposta_final,
                    "sql": sql,
                    "results": final_table
                })
                sucesso_sql = True
                break
            else:
                status_text.warning(f"Erro no SQL, solicitando correção (Tentativa {tentativa+1}/3)...")
                llm_messages.append({"role": "assistant", "content": resposta_llm})
                llm_messages.append({"role": "user", "content": f"Sua query falhou com o seguinte erro do PostgreSQL:\n{resultado}\n\nCorrija o SQL e tente novamente gerando um novo bloco ```sql."})
                
        if not sucesso_sql and final_sql:
            status_text.error("Não foi possível gerar um SQL válido após 3 tentativas.")
            st.session_state.messages.append({"role": "assistant", "content": "Não consegui gerar um SQL válido para responder sua pergunta devido a limitações ou erros contínuos de sintaxe."})
