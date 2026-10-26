#!/usr/bin/env python3
"""
Consulta SQL (DuckDB) sobre os resultados do apura_bu.py.

Tabelas disponíveis:
  secoes   votos por seção x cargo x votável (secoes_brasil.parquet)
  totais   totais por abrangência x cargo x votável (apuracao.csv)

Uso:
  python consulta.py                         # prompt interativo; termine cada consulta com ';'
  python consulta.py "SELECT ... FROM secoes"
  python consulta.py minha_consulta.sql

Para exportar para o Excel, dentro do SQL:
  COPY (SELECT ...) TO 'saida.csv' (HEADER, DELIMITER ';');

Dependência: pip install duckdb
"""
import sys
from pathlib import Path

import duckdb

PASTA = Path(__file__).resolve().parent
TABELAS = {"secoes": "secoes_brasil.parquet", "totais": "apuracao.csv"}


def conectar():
    con = duckdb.connect()
    con.sql("SET enable_progress_bar = false")
    for nome, arquivo in TABELAS.items():
        caminho = PASTA / arquivo
        if caminho.exists():
            con.sql(f"CREATE VIEW {nome} AS SELECT * FROM '{caminho.as_posix()}'")
        else:
            print(f"(aviso: {arquivo} não encontrado; tabela '{nome}' indisponível)")
    return con


def executar(con, sql: str):
    try:
        resultado = con.sql(sql)
        if resultado is not None:
            resultado.show(max_rows=100, max_width=200)
    except duckdb.Error as e:
        print(f"Erro: {e}")


def interativo(con):
    print("Tabelas: secoes, totais.  Termine cada consulta com ';'.  'sair' para encerrar.")
    buffer = []
    while True:
        try:
            linha = input("sql> " if not buffer else "...> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not buffer and linha.strip().lower() in ("sair", "exit", "quit"):
            return
        buffer.append(linha)
        if linha.rstrip().endswith(";"):
            executar(con, "\n".join(buffer))
            buffer = []


def main():
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")
    con = conectar()
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        executar(con, Path(arg).read_text(encoding="utf-8") if arg.endswith(".sql") else arg)
    else:
        interativo(con)


if __name__ == "__main__":
    main()
