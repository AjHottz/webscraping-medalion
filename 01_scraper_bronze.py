import argparse
import os
import uuid
import json
import psycopg
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://books.toscrape.com/catalogue/"

def scrape_detalhe(url_detalhe):
    headers = {"User-Agent": "BotMedallion/1.0"}
    try:
        resp = requests.get(url_detalhe, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None
        
    soup = BeautifulSoup(resp.content, "html.parser")
    
    titulo = soup.select_one("div.product_main h1")
    titulo = titulo.text if titulo else None
    
    preco_raw = soup.select_one("div.product_main p.price_color")
    preco_raw = preco_raw.text if preco_raw else None
    
    rating_raw = None
    star_elem = soup.select_one("p.star-rating")
    if star_elem:
        classes = star_elem.get("class", [])
        if len(classes) > 1:
            rating_raw = classes[1]
            
    estoque_raw = None
    upc = None
    n_reviews_raw = None
    
    table = soup.select_one("table.table")
    if table:
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                if th.text == "UPC":
                    upc = td.text
                elif th.text == "Availability":
                    estoque_raw = td.text
                elif th.text == "Number of reviews":
                    n_reviews_raw = td.text
                    
    categoria_raw = None
    breadcrumb = soup.select("ul.breadcrumb li a")
    if len(breadcrumb) >= 3:
        categoria_raw = breadcrumb[2].text
        
    descricao = soup.select_one("#product_description ~ p")
    descricao = descricao.text if descricao else None
        
    payload = {
        "url": url_detalhe,
        "titulo": titulo,
        "preco_raw": preco_raw,
        "rating_raw": rating_raw,
        "estoque_raw": estoque_raw,
        "upc": upc,
        "n_reviews_raw": n_reviews_raw,
        "categoria_raw": categoria_raw,
        "descricao": descricao
    }
    
    return payload

def processa_pagina(n_pagina):
    # Trata URL para pag 1 (page-1 as vezes é index.html, mas page-1 funciona redirecionado ou index.html? books.toscrape is static)
    # Na verdade na raiz os links podem variar, mas page-x.html sempre existe exceto a 1 que é page-1.html.
    # books.toscrape suporta catalogue/page-1.html
    url_listagem = f"{BASE_URL}page-{n_pagina}.html"
    headers = {"User-Agent": "BotMedallion/1.0"}
    try:
        resp = requests.get(url_listagem, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
    except requests.RequestException:
        return []
        
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select("article.product_pod h3 a")
    
    resultados = []
    # Links estão como 'a-light-in-the-attic_1000/index.html'
    urls_detalhe = [BASE_URL + a["href"].replace("../", "") for a in links]
    
    for url in urls_detalhe:
        payload = scrape_detalhe(url)
        if payload:
            resultados.append((url, payload))
            
    return resultados

def init_db(db_url):
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS bronze;
                CREATE TABLE IF NOT EXISTS bronze.livros (
                    id bigserial PRIMARY KEY,
                    fonte_url text NOT NULL,
                    payload jsonb NOT NULL,
                    _execucao_id text NOT NULL,
                    _ingestao_em timestamptz DEFAULT now()
                );
            """)
            conn.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paginas", type=int, required=True, help="Número de páginas para raspar")
    args = parser.parse_args()
    
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Erro: DATABASE_URL não encontrada no .env")
        return
        
    init_db(db_url)
    execucao_id = str(uuid.uuid4())
    print(f"Execucao: {execucao_id} - Raspando {args.paginas} páginas...")
    
    todos_resultados = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(processa_pagina, i) for i in range(1, args.paginas + 1)]
        for future in as_completed(futures):
            todos_resultados.extend(future.result())
            
    if not todos_resultados:
        print("Nenhum livro coletado.")
        return
        
    print(f"Coletados {len(todos_resultados)} livros. Salvando na bronze...")
    with psycopg.connect(db_url, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            for url, payload in todos_resultados:
                cur.execute(
                    "INSERT INTO bronze.livros (fonte_url, payload, _execucao_id) VALUES (%s, %s, %s)",
                    (url, json.dumps(payload), execucao_id)
                )
        conn.commit()
    print("Sucesso!")

if __name__ == "__main__":
    main()
