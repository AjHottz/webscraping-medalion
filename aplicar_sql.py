import argparse
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Aplica arquivos SQL ou queries avulsas no Supabase.")
    parser.add_argument("arquivo", nargs="?", help="Caminho para o arquivo .sql")
    parser.add_argument("--query", "-q", help="Query SQL para executar diretamente")
    
    args = parser.parse_args()
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Erro: DATABASE_URL não encontrada no .env")
        return
        
    try:
        with psycopg.connect(db_url, prepare_threshold=None) as conn:
            with conn.cursor() as cur:
                if args.arquivo:
                    with open(args.arquivo, "r", encoding="utf-8") as f:
                        sql = f.read()
                    cur.execute(sql)
                    conn.commit()
                    print(f"Arquivo {args.arquivo} executado com sucesso.")
                elif args.query:
                    cur.execute(args.query)
                    if args.query.strip().lower().startswith("select"):
                        resultados = cur.fetchall()
                        for linha in resultados:
                            print(linha)
                    else:
                        conn.commit()
                        print("Query executada com sucesso.")
                else:
                    print("Especifique um arquivo .sql ou use --query.")
    except Exception as e:
        print(f"Erro ao executar SQL: {e}")

if __name__ == "__main__":
    main()
