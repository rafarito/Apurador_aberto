#!/usr/bin/env python3
"""Leitor simples de log de urna eletrônica (pacotes .jez / logd.dat).

Baseado no documento "Log dos aplicativos do Ecossistema da Urna" (TSE).
Usa apenas a biblioteca padrão do Python.

Uso:
    python leitor_log_urna.py [diretório ou arquivo] [opções]

Exemplos:
    python leitor_log_urna.py                     # resumo dos .jez no diretório atual
    python leitor_log_urna.py . --eventos         # lista todos os eventos
    python leitor_log_urna.py . --severidade ALERTA ERRO
    python leitor_log_urna.py . --aplicativo VOTA --buscar "Eleitor foi habilitado"
    python leitor_log_urna.py . --csv saida.csv   # exporta os eventos para CSV
    python leitor_log_urna.py . --tudo --saida log.txt  # grava tudo em UTF-8
"""

import argparse
import csv
import io
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# Expressões regulares do documento (seção "Exemplo de expressão regular...")
RE_LINHA_URNA = re.compile(
    r"^([0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2})\t([^\t\r\n]+)\t([0-9]{8,})"
    r"\t([^\t\r\n]+)\t([^\t\r\n]*)\t([0-9A-F]{16})\r?$"
)
# Também cobre registros de rotação ("Rotacionado para"), sem urna/aplicativo
RE_LINHA_DESKTOP = re.compile(
    r"^([0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2})\t([^\t\r\n]+)\t([^\t\r\n]*)\t([0-9A-F]{16})\r?$"
)

# Nome do pacote gravado pela urna: [fase][ppppp][uf][MMMMM][ZZZZ][SSSS][ext]
RE_NOME_PACOTE = re.compile(
    r"^(?P<fase>[sto])(?P<pleito>\d{5})(?P<uf>[a-z]{2})(?P<municipio>\d{5})"
    r"(?P<zona>\d{4})(?P<secao>\d{4})(?P<ext>-log\.jez|-logsa\.jez)$"
)
FASES = {"s": "simulado", "t": "treinamento", "o": "oficial"}

SEVERIDADES = ["INFO", "ALERTA", "EXTERNO", "ERRO", "TRACE", "WHAT"]


@dataclass
class Evento:
    origem: str  # caminho do logd.dat dentro do(s) pacote(s)
    linha: int
    data_hora: str
    severidade: str
    urna: str
    aplicativo: str
    mensagem: str
    autenticador: str


@dataclass
class LinhaInvalida:
    origem: str
    linha: int
    conteudo: str


def decodificar(dados: bytes) -> str:
    # O logd.dat costuma vir em Latin-1; tenta UTF-8 primeiro por segurança.
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def ler_texto_log(texto: str, origem: str, eventos: list, invalidas: list) -> None:
    for n, linha in enumerate(texto.split("\n"), start=1):
        if not linha.strip():
            continue
        m = RE_LINHA_URNA.match(linha)
        if m:
            eventos.append(Evento(origem, n, *m.groups()))
            continue
        m = RE_LINHA_DESKTOP.match(linha)
        if m:
            data_hora, sev, msg, mac = m.groups()
            eventos.append(Evento(origem, n, data_hora, sev, "", "", msg, mac))
            continue
        invalidas.append(LinhaInvalida(origem, n, linha.rstrip("\r")))


def ler_zip(dados: bytes, origem: str, eventos: list, invalidas: list) -> None:
    """Lê um pacote .jez/.zip, inclusive pacotes arquivados aninhados."""
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        for nome in z.namelist():
            caminho = f"{origem}/{nome}"
            conteudo = z.read(nome)
            if nome.lower().endswith((".jez", ".zip")):
                ler_zip(conteudo, caminho, eventos, invalidas)
            elif nome.lower().endswith((".dat", ".log")):
                ler_texto_log(decodificar(conteudo), caminho, eventos, invalidas)


def identificar_pacote(nome: str) -> dict | None:
    m = RE_NOME_PACOTE.match(nome)
    if not m:
        return None
    d = m.groupdict()
    d["fase"] = FASES[d["fase"]]
    d["uf"] = d["uf"].upper()
    return d


def extrair_valor(eventos: list, prefixo: str) -> str | None:
    for e in eventos:
        if e.mensagem.startswith(prefixo):
            return e.mensagem[len(prefixo):].strip()
    return None


def contar(eventos: list, mensagem: str) -> int:
    return sum(1 for e in eventos if e.mensagem.startswith(mensagem))


def imprimir_resumo(arquivo: Path, eventos: list, invalidas: list) -> None:
    print("=" * 78)
    print(f"Pacote: {arquivo.name}")
    info = identificar_pacote(arquivo.name)
    if info:
        print(
            f"  Fase: {info['fase']} | Pleito: {info['pleito']} | UF: {info['uf']} | "
            f"Município: {info['municipio']} | Zona: {info['zona']} | Seção: {info['secao']}"
        )
    origens = sorted({e.origem for e in eventos} | {i.origem for i in invalidas})
    print(f"  Arquivos de log lidos: {', '.join(origens) or '(nenhum)'}")
    print(f"  Eventos válidos: {len(eventos)} | Linhas fora do formato: {len(invalidas)}")
    if not eventos:
        return

    print(f"  Período: {eventos[0].data_hora} -> {eventos[-1].data_hora} (ordem de gravação)")
    urnas = Counter(e.urna for e in eventos if e.urna)
    print(f"  Urnas (número interno): {', '.join(urnas)}")
    for rotulo, prefixo in [
        ("Modelo de urna", "Identificação do Modelo de Urna:"),
        ("Versão", "Versão da aplicação:"),
        ("Município (log)", "Município:"),
        ("Zona (log)", "Zona Eleitoral:"),
        ("Local de votação", "Local de Votação:"),
        ("Seção (log)", "Seção Eleitoral:"),
    ]:
        valor = extrair_valor(eventos, prefixo)
        if valor:
            print(f"  {rotulo}: {valor}")

    print("\n  Eventos por severidade:")
    for sev, n in Counter(e.severidade for e in eventos).most_common():
        print(f"    {sev:<10} {n}")
    print("\n  Eventos por aplicativo:")
    for app, n in Counter(e.aplicativo or "(desktop/rotação)" for e in eventos).most_common():
        print(f"    {app:<10} {n}")

    print("\n  Indicadores da votação:")
    for rotulo, msg in [
        ("Eleitores habilitados", "Eleitor foi habilitado"),
        ("Votos computados", "O voto do eleitor foi computado"),
        ("Habilitações biométricas", "Tipo de habilitação do eleitor [biométrica]"),
        ("Habilitações manuais por mesário", "Solicitação de dado pessoal do eleitor para habilitação manual"),
        ("Justificativas recebidas", "Justificativa recebida"),
        ("Eleitores suspensos", "Eleitor foi suspenso pelo mesário"),
        ("Eleitor já votou (tentativas)", "O eleitor identificado já votou"),
        ("Mesários registrados", "Mesário "),
    ]:
        if msg == "Mesário ":
            n = sum(1 for e in eventos if e.mensagem.startswith(msg) and e.mensagem.endswith(" registrado"))
        else:
            n = contar(eventos, msg)
        print(f"    {rotulo:<34} {n}")

    # Um mesmo log pode conter mais de um turno; mostra os votos por dia
    votos_por_dia = Counter(
        e.data_hora[:10] for e in eventos if e.mensagem.startswith("O voto do eleitor foi computado")
    )
    if len(votos_por_dia) > 1:
        print("\n  Votos computados por dia:")
        for dia, n in votos_por_dia.items():
            print(f"    {dia:<34} {n}")

    externos = [e for e in eventos if e.severidade == "EXTERNO"]
    if externos:
        print("\n  Referências a logs arquivados (EXTERNO):")
        for e in externos:
            print(f"    {e.data_hora}  {e.mensagem}")

    criticos = [e for e in eventos if e.severidade in ("ALERTA", "ERRO", "WHAT")]
    if criticos:
        print(f"\n  Alertas e erros ({len(criticos)}):")
        for e in criticos:
            print(f"    {e.data_hora}  {e.severidade:<7} {e.aplicativo:<6} {e.mensagem}")

    if invalidas:
        print(f"\n  Linhas fora do formato esperado ({len(invalidas)}, até 10 exibidas):")
        for i in invalidas[:10]:
            print(f"    {i.origem}:{i.linha}  {i.conteudo[:100]}")


def imprimir_tudo(eventos: list, invalidas: list) -> None:
    """Imprime todas as linhas na ordem de gravação, sem filtros nem omissões."""
    print(f"\n  Todas as linhas ({len(eventos) + len(invalidas)}):")
    print("  origem:linha | data_hora | severidade | urna | aplicativo | mensagem | autenticador")
    linhas = [(e.origem, e.linha, e) for e in eventos] + [(i.origem, i.linha, i) for i in invalidas]
    for origem, n, item in sorted(linhas, key=lambda t: (t[0], t[1])):
        if isinstance(item, Evento):
            print(f"{origem}:{n} | {item.data_hora} | {item.severidade} | {item.urna} | "
                  f"{item.aplicativo} | {item.mensagem} | {item.autenticador}")
        else:
            print(f"{origem}:{n} | [FORA DO FORMATO] {item.conteudo}")


def filtrar(eventos: list, args) -> list:
    sev = {s.upper() for s in args.severidade} if args.severidade else None
    apps = {a.upper() for a in args.aplicativo} if args.aplicativo else None
    termo = args.buscar.lower() if args.buscar else None
    return [
        e for e in eventos
        if (sev is None or e.severidade.upper() in sev)
        and (apps is None or e.aplicativo.upper() in apps)
        and (termo is None or termo in e.mensagem.lower())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Leitor de log de urna eletrônica (.jez / logd.dat)")
    parser.add_argument("caminho", nargs="?", default=".", help="diretório ou arquivo .jez/.dat (padrão: .)")
    parser.add_argument("--eventos", action="store_true", help="lista os eventos (aplicando os filtros)")
    parser.add_argument("--severidade", nargs="+", metavar="SEV", help=f"filtra por severidade ({', '.join(SEVERIDADES)})")
    parser.add_argument("--aplicativo", nargs="+", metavar="APP", help="filtra por aplicativo (VOTA, GAP, ATUE, SCUE, LOGD...)")
    parser.add_argument("--buscar", metavar="TEXTO", help="filtra eventos cuja mensagem contém o texto")
    parser.add_argument("--csv", metavar="ARQUIVO", help="exporta os eventos (filtrados) para CSV")
    parser.add_argument("--tudo", action="store_true",
                        help="mostra o resumo e todas as linhas, com todos os campos, inclusive as fora do formato")
    parser.add_argument("--saida", metavar="ARQUIVO",
                        help="grava a saída num arquivo texto UTF-8 (use no lugar de '>' no PowerShell)")
    args = parser.parse_args()

    if args.saida:
        # Grava direto em UTF-8: o '>' do PowerShell 5.1 recodifica a saída e corrompe os acentos
        sys.stdout = open(args.saida, "w", encoding="utf-8-sig", newline="\r\n")
    elif hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    alvo = Path(args.caminho)
    if alvo.is_dir():
        arquivos = sorted(p for p in alvo.iterdir() if p.suffix.lower() in (".jez", ".dat", ".log"))
    elif alvo.is_file():
        arquivos = [alvo]
    else:
        print(f"Caminho não encontrado: {alvo}", file=sys.stderr)
        return 1
    if not arquivos:
        print(f"Nenhum arquivo .jez/.dat/.log em {alvo}", file=sys.stderr)
        return 1

    todos = []
    for arquivo in arquivos:
        eventos, invalidas = [], []
        try:
            if zipfile.is_zipfile(arquivo):
                ler_zip(arquivo.read_bytes(), arquivo.name, eventos, invalidas)
            else:
                ler_texto_log(decodificar(arquivo.read_bytes()), arquivo.name, eventos, invalidas)
        except zipfile.BadZipFile as exc:
            print(f"Falha ao abrir {arquivo.name}: {exc}", file=sys.stderr)
            continue
        if args.tudo or not (args.eventos or args.csv):
            imprimir_resumo(arquivo, eventos, invalidas)
        if args.tudo:
            imprimir_tudo(eventos, invalidas)
        todos.extend(eventos)

    selecionados = filtrar(todos, args)
    if args.eventos:
        for e in selecionados:
            print(f"{e.data_hora}  {e.severidade:<7} {e.urna:<8} {e.aplicativo:<6} {e.mensagem}")
        print(f"\n{len(selecionados)} evento(s).")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["origem", "linha", "data_hora", "severidade", "urna", "aplicativo", "mensagem", "autenticador"])
            for e in selecionados:
                w.writerow([e.origem, e.linha, e.data_hora, e.severidade, e.urna, e.aplicativo, e.mensagem, e.autenticador])
        print(f"{len(selecionados)} evento(s) exportado(s) para {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
