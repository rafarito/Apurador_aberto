#!/usr/bin/env python3
"""
Apuração independente a partir dos Boletins de Urna publicados no
Portal de Dados Abertos do TSE (dadosabertos.tse.jus.br).

Usa a API CKAN oficial para localizar os arquivos "bweb" (BU decodificado,
uma linha por seção x cargo x votável), baixa os ZIPs das UFs escolhidas,
confere o hash publicado pelo TSE e soma.

Exemplos:
  python apura_bu.py --ano 2026 --uf AC --turno 1
  python apura_bu.py --ano 2026 --uf TODAS --turno 1      # Brasil inteiro + exterior (ZZ)
  python apura_bu.py --ano 2026 --uf AC ZZ --turno 1
  python apura_bu.py --ano 2026 --uf AC --turno 1 --zona 4 --secao 175   # uma seção
  python apura_bu.py --ano 2026 --listar                  # mostra o que está publicado
  python apura_bu.py --url <link_do_zip> --turno 2        # pula a descoberta
  python apura_bu.py --arquivo a.zip b.zip                # ZIPs/CSVs já baixados

Saídas:
  apuracao.csv          totais por abrangência x cargo x votável (Presidente soma
                        o Brasil todo; os demais cargos são somados por UF)
  apuracao_secoes.csv   votos de cada seção x cargo x votável, com aptos e
                        comparecimento da seção (use .csv.gz para compactar)

Dependências: pip install pandas requests
"""
import argparse
import gzip
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

CKAN = "https://dadosabertos.tse.jus.br/api/3/action"
CACHE = Path("cache_tse")
CHUNK = 500_000

# .../eleicoes2026/buweb/bweb_1t_AC_051020261403.zip
RE_BWEB = re.compile(
    r"/eleicoes(?P<ano>\d{4})/buweb/bweb_(?P<turno>\d)t_(?P<uf>[A-Z]{2})_(?P<data>\d+)\.zip$", re.I
)
CARGOS_NACIONAIS = {"PRESIDENTE"}
TIPOS_VALIDOS = {"NOMINAL", "LEGENDA"}
CHAVE_SECAO = ["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NM_MUNICIPIO", "NR_ZONA", "NR_SECAO",
               "DS_CARGO_PERGUNTA"]
COLS_SECAO = ["QT_APTOS", "QT_COMPARECIMENTO", "QT_ABSTENCOES"]
CHAVE_TOTAL = ["ABRANGENCIA", "DS_CARGO_PERGUNTA", "DS_TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL"]


# ---------------------------------------------------------------- descoberta
def versao(data: str):
    """Ordena o carimbo ddmmaaaa[HHMM[SS]] do nome do arquivo cronologicamente."""
    return data[4:8], data[2:4], data[0:2], data[8:]


def buscar_recursos(ano: int):
    """Procura no CKAN os arquivos bweb do ano (ignora outros anos, hashes e suplementares)."""
    r = requests.get(f"{CKAN}/package_search",
                     params={"q": f"boletim de urna {ano}", "rows": 100}, timeout=60)
    r.raise_for_status()
    urls = {res.get("url", "") for pkg in r.json()["result"]["results"]
            for res in pkg.get("resources", [])}
    recursos = []
    for url in sorted(urls):
        m = RE_BWEB.search(url)
        if m and int(m["ano"]) == ano:
            url_hash = next((url + ext for ext in (".sha512", ".sha1") if url + ext in urls), None)
            recursos.append({"turno": int(m["turno"]), "uf": m["uf"].upper(),
                             "versao": versao(m["data"]), "url": url, "hash": url_hash})
    return recursos


def por_turno(recursos, turno: int):
    """UF -> recurso mais recente daquele turno."""
    escolhidos = {}
    for r in recursos:
        atual = escolhidos.get(r["uf"])
        if r["turno"] == turno and (atual is None or r["versao"] > atual["versao"]):
            escolhidos[r["uf"]] = r
    return escolhidos


def listar(recursos, ano: int):
    if not recursos:
        print(f"Nenhum boletim de urna de {ano} publicado.")
    for turno in sorted({r["turno"] for r in recursos}):
        ufs = por_turno(recursos, turno)
        print(f"\n{ano} - {turno}º turno: {len(ufs)} arquivo(s): {' '.join(sorted(ufs))}")
        for uf in sorted(ufs):
            print(f"   {ufs[uf]['url']}")


def escolher(recursos, ufs: list, turno: int, ano: int):
    disponiveis = por_turno(recursos, turno)
    if not disponiveis:
        sys.exit(f"Nenhum boletim do {turno}º turno de {ano} publicado ainda. Rode com --listar.")
    if ufs == ["TODAS"]:
        return [disponiveis[uf] for uf in sorted(disponiveis)]
    faltando = [uf for uf in ufs if uf not in disponiveis]
    if faltando:
        sys.exit(f"Sem boletim do {turno}º turno de {ano} para: {', '.join(faltando)}. "
                 f"Disponíveis: {' '.join(sorted(disponiveis))}")
    return [disponiveis[uf] for uf in ufs]


# ---------------------------------------------------------------- download
def conferir_hash(arquivo: Path, url_hash: str):
    r = requests.get(url_hash, timeout=60)
    if r.status_code == 404:
        print(f"  (sem hash publicado em {url_hash}; não conferido)")
        return
    r.raise_for_status()
    esperado = r.text.split()[0].lower()
    algoritmo = url_hash.rsplit(".", 1)[-1]
    h = hashlib.new(algoritmo)
    with open(arquivo, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    if h.hexdigest() != esperado:
        arquivo.unlink()
        sys.exit(f"{algoritmo} de {arquivo.name} não confere com o publicado pelo TSE; "
                 "arquivo removido do cache, rode de novo.")
    print(f"  {algoritmo} confere com o publicado pelo TSE")


def baixar(url: str, url_hash: str | None) -> Path:
    CACHE.mkdir(exist_ok=True)
    destino = CACHE / url.rstrip("/").split("/")[-1]
    if destino.exists():
        print(f"Usando cache: {destino}")
    else:
        print(f"Baixando {url}")
        parcial = destino.with_name(destino.name + ".part")
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            feito = 0
            with open(parcial, "wb") as f:
                for bloco in r.iter_content(1 << 20):
                    f.write(bloco)
                    feito += len(bloco)
                    if total:
                        print(f"\r  {feito / total:6.1%}", end="")
        print()
        # Só entra no cache depois de completo: um download interrompido não é reaproveitado
        parcial.replace(destino)
    if url_hash:
        conferir_hash(destino, url_hash)
    return destino


# ---------------------------------------------------------------- apuração
def ler_csvs(caminho: Path):
    """Itera sobre os blocos de todos os CSVs do ZIP (ou de um CSV solto)."""
    def ler(fh):
        return pd.read_csv(fh, sep=";", encoding="latin-1", dtype=str, chunksize=CHUNK)

    if caminho.suffix.lower() == ".zip":
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                if nome.lower().endswith(".csv"):
                    print(f"Lendo {nome}")
                    with z.open(nome) as fh:
                        yield from ler(io.TextIOWrapper(fh, encoding="latin-1"))
    else:
        yield from ler(caminho)


def preparar(df: pd.DataFrame, turno: int | None, filtros: dict):
    df.columns = [c.strip().upper() for c in df.columns]
    if turno and "NR_TURNO" in df.columns:
        df = df[df["NR_TURNO"] == str(turno)]
    for col, valor in filtros.items():
        df = df[df[col].str.strip().str.lstrip("0") == str(valor)]
    df = df.copy()
    for col in ["NR_TURNO", "SG_UF", "NM_MUNICIPIO"]:
        if col not in df.columns:
            df[col] = ""
    if "DS_TIPO_VOTAVEL" not in df.columns:
        # Arquivos antigos: 95 = branco, 96 = nulo, o resto é voto válido
        df["DS_TIPO_VOTAVEL"] = df["NR_VOTAVEL"].map({"95": "Branco", "96": "Nulo"}).fillna("Nominal")
    for col in ["QT_VOTOS"] + [c for c in COLS_SECAO if c in df.columns]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    nacional = df["DS_CARGO_PERGUNTA"].str.upper().isin(CARGOS_NACIONAIS)
    df["ABRANGENCIA"] = df["SG_UF"].where(~nacional, "BR")
    return df


def abrir_saida(caminho: Path):
    if caminho.suffix.lower() == ".gz":
        return gzip.open(caminho, "wt", encoding="utf-8", newline="")
    return open(caminho, "w", encoding="utf-8", newline="")


def apurar(caminhos: list, turno: int | None, filtros: dict, saida_secoes: Path | None):
    votos = []
    secoes = []
    turnos = set()
    fh_secoes = abrir_saida(saida_secoes) if saida_secoes else None
    cabecalho = True
    try:
        for caminho in caminhos:
            for df in ler_csvs(caminho):
                df = preparar(df, turno, filtros)
                if df.empty:
                    continue
                turnos.update(df["NR_TURNO"].unique())
                votos.append(df.groupby(CHAVE_TOTAL)["QT_VOTOS"].sum())
                # Aptos/comparecimento se repetem em cada linha da seção: deduplicar
                cols = [c for c in COLS_SECAO if c in df.columns]
                secoes.append(df[["ABRANGENCIA"] + CHAVE_SECAO + cols].drop_duplicates(CHAVE_SECAO))
                if fh_secoes:
                    extras = [c for c in ["DS_SECOES_AGREGADAS"] + COLS_SECAO if c in df.columns]
                    df[CHAVE_SECAO + extras + ["DS_TIPO_VOTAVEL", "NR_VOTAVEL", "NM_VOTAVEL", "QT_VOTOS"]] \
                        .to_csv(fh_secoes, sep=";", index=False, header=cabecalho)
                    cabecalho = False
    finally:
        if fh_secoes:
            fh_secoes.close()

    if not votos:
        sys.exit("Nenhum dado encontrado (confira o arquivo, o turno e os filtros).")
    if len(turnos) > 1:
        sys.exit(f"Os arquivos têm mais de um turno ({', '.join(sorted(turnos))}); informe --turno.")

    total = pd.concat(votos).groupby(level=list(range(len(CHAVE_TOTAL)))).sum()
    sec = pd.concat(secoes).drop_duplicates(CHAVE_SECAO)

    for (abrangencia, cargo), grupo in total.groupby(level=[0, 1]):
        s = sec[(sec["ABRANGENCIA"] == abrangencia) & (sec["DS_CARGO_PERGUNTA"] == cargo)]
        g = grupo.droplevel([0, 1])
        valido = g.index.get_level_values(0).str.upper().isin(TIPOS_VALIDOS)
        validos = g[valido].sum()
        print(f"\n=== {cargo} - {abrangencia} ===")
        print(f"Seções: {len(s):,}  Aptos: {s.get('QT_APTOS', pd.Series([0])).sum():,}  "
              f"Comparecimento: {s.get('QT_COMPARECIMENTO', pd.Series([0])).sum():,}  "
              f"Abstenções: {s.get('QT_ABSTENCOES', pd.Series([0])).sum():,}")
        outros = "  ".join(f"{tipo}: {qt:,}" for tipo, qt in g[~valido].groupby(level=0).sum().items())
        print(f"Votos: {g.sum():,}  Válidos: {validos:,}  {outros}")
        cand = g[valido].sort_values(ascending=False)
        for (tipo, nr, nome), qt in cand.head(15).items():
            rotulo = f"{nome} (legenda)" if tipo.upper() == "LEGENDA" else nome
            pct = f"{qt / validos:7.2%}" if validos else ""
            print(f"  {nr:>6}  {rotulo[:40]:<40} {qt:>12,}  {pct}")
        if len(cand) > 15:
            print(f"  ... mais {len(cand) - 15} votáveis")
    print("\n% calculado sobre os votos válidos (nominais + legenda), como o TSE divulga.")

    resultado = total.rename("QT_VOTOS").reset_index()
    valido = resultado["DS_TIPO_VOTAVEL"].str.upper().isin(TIPOS_VALIDOS)
    validos = resultado["QT_VOTOS"].where(valido, 0) \
        .groupby([resultado["ABRANGENCIA"], resultado["DS_CARGO_PERGUNTA"]]).transform("sum")
    resultado["PC_VALIDOS"] = (resultado["QT_VOTOS"] / validos).where(valido).round(6)
    saida = Path("apuracao.csv")
    resultado.to_csv(saida, index=False, sep=";")
    print(f"Totais salvos em {saida}")
    if saida_secoes:
        print(f"Votos por seção salvos em {saida_secoes}")


# ---------------------------------------------------------------- main
def main():
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser()
    p.add_argument("--ano", type=int, default=2026)
    p.add_argument("--uf", nargs="+", help="Siglas das UFs (ex.: AC SP ZZ) ou TODAS (inclui o exterior, ZZ)")
    p.add_argument("--turno", type=int, choices=[1, 2])
    p.add_argument("--url", nargs="+", help="Links diretos para ZIPs do bweb")
    p.add_argument("--arquivo", nargs="+", help="ZIPs/CSVs já baixados")
    p.add_argument("--listar", action="store_true")
    p.add_argument("--municipio", type=int, help="Filtra pelo código TSE do município")
    p.add_argument("--zona", type=int, help="Filtra pela zona eleitoral")
    p.add_argument("--secao", type=int, help="Filtra pela seção eleitoral")
    p.add_argument("--saida-secoes", default="apuracao_secoes.csv",
                   help="Arquivo com os votos por seção (termine em .gz para compactar)")
    p.add_argument("--sem-secoes", action="store_true", help="Não grava o arquivo por seção")
    a = p.parse_args()

    if a.arquivo:
        caminhos = [Path(c) for c in a.arquivo]
    elif a.url:
        caminhos = [baixar(u, u + ".sha512") for u in a.url]
    else:
        recursos = buscar_recursos(a.ano)
        if a.listar:
            listar(recursos, a.ano)
            return
        if not a.uf:
            sys.exit("Informe --uf (ou --url / --arquivo).")
        a.turno = a.turno or 1
        escolhidos = escolher(recursos, [uf.upper() for uf in a.uf], a.turno, a.ano)
        caminhos = [baixar(r["url"], r["hash"]) for r in escolhidos]

    filtros = {col: valor for col, valor in [("CD_MUNICIPIO", a.municipio), ("NR_ZONA", a.zona),
                                             ("NR_SECAO", a.secao)] if valor is not None}
    apurar(caminhos, a.turno, filtros, None if a.sem_secoes else Path(a.saida_secoes))


if __name__ == "__main__":
    main()
