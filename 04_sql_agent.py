import argparse
import os
import re
import sys
import json
import psycopg
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

load_dotenv(override=True)

def ler_arquivo(caminho):
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ""

def get_schema(db_url, sem_contexto):
    schemas = ('public', 'bronze', 'prata', 'ouro') if sem_contexto else ('prata', 'ouro')
    query = """
    SELECT table_schema, table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = ANY(%s)
    ORDER BY table_schema, table_name, ordinal_position;
    """
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (list(schemas),))
            rows = cur.fetchall()
            
    schema_str = ""
    current_table = None
    for r in rows:
        t = f"{r[0]}.{r[1]}"
        if t != current_table:
            schema_str += f"\nTable: {t}\n"
            current_table = t
        schema_str += f" - {r[2]} ({r[3]})\n"
    return schema_str

def execute_sql_safely(db_url, sql):
    if not re.search(r'^\s*(SELECT|WITH)\b', sql, re.IGNORECASE):
        return False, "Erro: Apenas queries SELECT/WITH são permitidas."
    
    sql = sql.strip().rstrip(';')
    if not re.search(r'\bLIMIT\b', sql, re.IGNORECASE):
        sql += " LIMIT 50"
        
    try:
        with psycopg.connect(db_url, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN READ ONLY")
                cur.execute("SET statement_timeout = '10s'")
                cur.execute(sql)
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return True, (cols, rows)
    except Exception as e:
        return False, str(e)

def call_llm(messages):
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    model = os.environ.get("LLM_MODEL", "gpt-4o")
    
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        data = {"model": model, "messages": messages, "temperature": 0.0}
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        contents = []
        system_instruction = None
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
            else:
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
                
        data = {"contents": contents, "generationConfig": {"temperature": 0.0}}
        if system_instruction:
            data["systemInstruction"] = system_instruction
            
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=data)
        if resp.status_code != 200:
            print(f"Erro Gemini: {resp.status_code} - {resp.text}")
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        sys_msg = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                sys_msg += m["content"] + "\n"
            else:
                user_msgs.append(m)
        data = {"model": model, "system": sys_msg, "messages": user_msgs, "max_tokens": 1024, "temperature": 0.0}
        resp = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]

def extract_sql(text):
    match = re.search(r'```sql\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-contexto", action="store_true")
    args = parser.parse_args()
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL não configurada.")
        return

    schema_info = get_schema(db_url, args.sem_contexto)
    contexto = "" if args.sem_contexto else ler_arquivo("CONTEXTO.md")
    
    sys_prompt = f"""Você é um agente de dados que usa PostgreSQL para responder perguntas de negócio.
Regras OBRIGATÓRIAS:
1. Gere apenas UMA query SQL dentro de um bloco ```sql ... ``` para responder à pergunta. Não invente colunas.
2. Use apenas instruções SELECT ou WITH.
3. Se a pergunta for ambígua, pergunte ao usuário.
4. Responda em Português do Brasil de forma amigável e direta baseada APENAS nos resultados."""

    if args.sem_contexto:
        sys_prompt += f"\n\nSCHEMA DO BANCO:\n{schema_info}"
    else:
        sys_prompt += f"\n\nCONTEXTO DO PROJETO:\n{contexto}\n\nSCHEMA DO BANCO (somente prata e ouro):\n{schema_info}"

    while True:
        try:
            pergunta = input("\nPergunta: ")
            if not pergunta.strip():
                continue
            if pergunta.lower() in ('sair', 'exit'):
                break
                
            messages = [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": pergunta}
            ]
            
            sucesso_sql = False
            for tentativa in range(3):
                print(f"[{tentativa+1}/3] Pensando...")
                resposta_llm = call_llm(messages)
                
                sql = extract_sql(resposta_llm)
                if not sql:
                    # Se não encontrou SQL, pode ser que o agente fez uma pergunta (ambiguidade)
                    print(f"\n[Resposta do Agente]\n{resposta_llm}")
                    break
                    
                print(f"\n--- SQL Gerado ---\n{sql}\n------------------")
                sucesso, resultado = execute_sql_safely(db_url, sql)
                
                if sucesso:
                    cols, rows = resultado
                    print(f"Resultados obtidos: {len(rows)} linhas.")
                    
                    resultado_str = f"Colunas: {cols}\nLinhas:\n" + "\n".join(str(r) for r in rows[:10])
                    if len(rows) > 10:
                        resultado_str += f"\n... (mais {len(rows)-10} linhas cortadas)"
                        
                    messages.append({"role": "assistant", "content": resposta_llm})
                    messages.append({"role": "user", "content": f"Resultados da execução do SQL:\n{resultado_str}\n\nBaseado SOMENTE nesses resultados, formule a resposta final para o usuário em português. Mostre o valor final e seja direto."})
                    
                    print("Formatando resposta...")
                    resposta_final = call_llm(messages)
                    print(f"\n[Resposta Final]\n{resposta_final}")
                    sucesso_sql = True
                    break
                else:
                    print(f"Erro do banco: {resultado}")
                    messages.append({"role": "assistant", "content": resposta_llm})
                    messages.append({"role": "user", "content": f"Sua query falhou com o seguinte erro do PostgreSQL:\n{resultado}\n\nCorrija o SQL e tente novamente gerando um novo bloco ```sql."})
                    
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro inesperado na execução: {e}")

if __name__ == "__main__":
    main()
