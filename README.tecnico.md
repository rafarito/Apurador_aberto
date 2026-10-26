# Apuração dos Boletins de Urna (BU) — documentação técnica

> Esta é a versão técnica. Se você nunca usou terminal ou Python, comece pelo
> [guia passo a passo](README.md).

Ferramentas para apurar, seção por seção, os votos publicados pelo TSE no
[Portal de Dados Abertos](https://dadosabertos.tse.jus.br) e consultar o resultado com SQL.

| Arquivo | Para que serve |
|---|---|
| `apura_bu.py` | Baixa os boletins de urna (arquivos `bweb`), confere o hash e soma os votos de cada seção |
| `consulta.py` | Prompt de SQL (DuckDB) sobre os resultados da apuração |
| `leitor_log_urna.py` | Leitor de logs de urna (`.jez` / `logd.dat`) — ferramenta separada |

## Como a apuração funciona

O TSE publica, para cada UF (e `ZZ` = exterior), um arquivo `bweb` com o conteúdo do
boletim de urna de **cada seção**: uma linha por seção × cargo × candidato.
O `apura_bu.py` soma essas linhas — **não usa as tabelas já totalizadas pelo TSE**.

- O hash `.sha512` publicado pelo TSE é conferido depois de cada download.
- Presidente é somado no Brasil todo (estados + exterior); os demais cargos, por UF.
- As porcentagens são sobre os **votos válidos** (nominais + legenda), como o TSE divulga.
- Seções agregadas aparecem somadas na seção principal (é assim no próprio BU).
- Limitação: os números de cada seção vêm do CSV gerado pelo TSE a partir dos BUs,
  não dos arquivos `.bu` assinados de cada urna.

## Instalação

Requer Python 3.10+. Crie um ambiente virtual, ative e instale as dependências:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O `requirements.txt` fixa as versões usadas na apuração de referência (Python 3.14.8,
pandas 3.1.0, requests 2.34.2, duckdb 2.0.0), para que o resultado seja reproduzível.

> Se o PowerShell bloquear o `Activate.ps1`, rode antes
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, ou use `.\.venv\Scripts\python.exe`
> no lugar de `python` nos comandos abaixo.

Os exemplos a seguir assumem o venv ativado e o terminal na pasta do projeto.

## Rodando a apuração

### Ver o que o TSE já publicou

```powershell
python apura_bu.py --ano 2026 --listar
```

Mostra, por turno, as UFs disponíveis. Se um turno não aparece, ele ainda não foi publicado
(historicamente, o 2º turno sai no dia seguinte à eleição, entre o fim da manhã e o fim da tarde).

### Brasil inteiro + exterior (a apuração completa)

```powershell
python -u apura_bu.py --uf TODAS --turno 1 --saida-secoes secoes_brasil.csv.gz | Tee-Object -FilePath log_apuracao.txt
```

- `-u` + `Tee-Object` mostram o andamento na tela **e** gravam o log em tempo real.
- Na primeira vez baixa ~5 GB (28 arquivos) para `cache_tse\`; depois reaproveita o cache.
- Referência de tempo (1º turno de 2026): ~9 min de download + ~14 min de processamento,
  com uso de até ~2,5 GB de RAM.
- **Não feche o terminal** durante a execução: se interromper, o processamento recomeça do zero
  (os downloads já concluídos ficam no cache).

### Outros recortes

```powershell
# Uma ou mais UFs (ZZ = exterior)
python apura_bu.py --uf AC ZZ --turno 1

# Uma seção específica (mostra o BU dela na tela)
python apura_bu.py --uf SP --turno 1 --zona 1 --secao 10 --saida-secoes minha_secao.csv

# Uma zona inteira, ou um município (código TSE, não IBGE)
python apura_bu.py --uf BA --turno 1 --zona 5
python apura_bu.py --uf BA --turno 1 --municipio 38490

# Outro ano
python apura_bu.py --ano 2022 --uf TODAS --turno 2 --saida-secoes secoes_2022_2t.csv.gz

# Arquivos já baixados ou link direto
python apura_bu.py --arquivo cache_tse\bweb_1t_AC_051020261403.zip --turno 1
python apura_bu.py --url https://cdn.tse.jus.br/.../bweb_1t_AC_....zip --turno 1
```

| Opção | Descrição |
|---|---|
| `--ano` | Ano da eleição (padrão: 2026) |
| `--uf` | Siglas das UFs (`AC SP ZZ`) ou `TODAS` |
| `--turno` | 1 ou 2 (padrão: 1) |
| `--municipio`, `--zona`, `--secao` | Filtram o recorte apurado |
| `--saida-secoes` | Arquivo por seção (padrão `apuracao_secoes.csv`; termine em `.gz` para compactar) |
| `--sem-secoes` | Não grava o arquivo por seção |
| `--listar` | Só lista os arquivos publicados |
| `--url`, `--arquivo` | Pulam a busca no portal |

### Saídas

| Arquivo | Conteúdo |
|---|---|
| `apuracao.csv` | Totais por abrangência (`BR` ou UF) × cargo × candidato, com `PC_VALIDOS` |
| `secoes_brasil.csv.gz` (ou o nome dado em `--saida-secoes`) | Votos de cada seção × cargo × candidato, com aptos, comparecimento e abstenções da seção |
| `cache_tse\` | ZIPs originais do TSE |

O arquivo por seção do Brasil inteiro tem ~68 milhões de linhas: **não abre no Excel**
(limite de ~1 milhão). Use a ferramenta de consulta abaixo.

## Consultando os resultados (DuckDB)

### Preparar: converter o arquivo por seção para Parquet

O DuckDB consulta o `.csv.gz` direto, mas relê o arquivo inteiro a cada consulta (~20 s).
Convertido para Parquet, a mesma consulta leva ~1 s. Faça uma vez após cada apuração
(~3 min; gera `secoes_brasil.parquet`, ~250 MB):

```powershell
python consulta.py "COPY (SELECT * FROM 'secoes_brasil.csv.gz' ORDER BY SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO) TO 'secoes_brasil.parquet' (FORMAT parquet, COMPRESSION zstd)"
```

### Abrir o prompt

```powershell
python consulta.py
```

Aparece `sql>`. Digite a consulta e **termine com `;`** (pode ocupar várias linhas).
Para sair, digite `sair`.

Também dá para rodar uma consulta só, ou um arquivo `.sql`:

```powershell
python consulta.py "SELECT count(*) FROM secoes"
python consulta.py minha_consulta.sql
```

Tabelas disponíveis:

| Tabela | Origem | Conteúdo |
|---|---|---|
| `secoes` | `secoes_brasil.parquet` | Uma linha por seção × cargo × candidato |
| `totais` | `apuracao.csv` | Totais por abrangência × cargo × candidato |

Colunas de `secoes`: `NR_TURNO`, `SG_UF`, `CD_MUNICIPIO`, `NM_MUNICIPIO`, `NR_ZONA`, `NR_SECAO`,
`DS_CARGO_PERGUNTA`, `DS_SECOES_AGREGADAS`, `QT_APTOS`, `QT_COMPARECIMENTO`, `QT_ABSTENCOES`,
`DS_TIPO_VOTAVEL` (Nominal / Legenda / Branco / Nulo), `NR_VOTAVEL`, `NM_VOTAVEL`, `QT_VOTOS`.

### O básico de SQL

```
SELECT   colunas
FROM     tabela
WHERE    filtro
GROUP BY agrupar (para somar por grupo)
ORDER BY ordenar (DESC = decrescente)
LIMIT    quantas linhas mostrar
```

### Exemplos

```sql
-- Ver as colunas e uma amostra
DESCRIBE secoes;
SELECT * FROM secoes LIMIT 5;

-- O BU de uma seção
SELECT DS_CARGO_PERGUNTA, NR_VOTAVEL, NM_VOTAVEL, QT_VOTOS
FROM secoes
WHERE SG_UF = 'SP' AND NR_ZONA = 1 AND NR_SECAO = 10
ORDER BY DS_CARGO_PERGUNTA, QT_VOTOS DESC;

-- Resultado nacional para Presidente
SELECT NM_VOTAVEL, QT_VOTOS, round(100 * PC_VALIDOS, 2) AS pct_validos
FROM totais
WHERE ABRANGENCIA = 'BR' AND PC_VALIDOS IS NOT NULL
ORDER BY QT_VOTOS DESC;

-- Presidente por estado (13 e 22)
SELECT SG_UF, NM_VOTAVEL, sum(QT_VOTOS) AS votos
FROM secoes
WHERE DS_CARGO_PERGUNTA = 'Presidente' AND NR_VOTAVEL IN (13, 22)
GROUP BY SG_UF, NM_VOTAVEL
ORDER BY SG_UF, votos DESC;

-- Achar o código de um município pelo nome (ILIKE ignora maiúsculas; % = qualquer texto)
SELECT DISTINCT SG_UF, CD_MUNICIPIO, NM_MUNICIPIO
FROM secoes
WHERE NM_MUNICIPIO ILIKE '%feira de santana%';

-- Votação no exterior por cidade
SELECT NM_MUNICIPIO, sum(QT_VOTOS) AS votos
FROM secoes
WHERE SG_UF = 'ZZ' AND DS_CARGO_PERGUNTA = 'Presidente'
GROUP BY NM_MUNICIPIO
ORDER BY votos DESC LIMIT 10;

-- Seções com maior abstenção (aptos/abstenções se repetem por linha: DISTINCT por seção)
SELECT DISTINCT SG_UF, NM_MUNICIPIO, NR_ZONA, NR_SECAO, QT_APTOS, QT_ABSTENCOES,
       round(100.0 * QT_ABSTENCOES / QT_APTOS, 1) AS pct_abst
FROM secoes
WHERE DS_CARGO_PERGUNTA = 'Presidente' AND QT_APTOS >= 100
ORDER BY pct_abst DESC LIMIT 20;

-- Exportar um recorte para abrir no Excel
COPY (SELECT * FROM secoes WHERE SG_UF = 'BA' AND NM_MUNICIPIO = 'SALVADOR')
TO 'salvador.csv' (HEADER, DELIMITER ';');
```

### Cuidados

- **Texto entre aspas simples** (`'SP'`); números sem aspas (`NR_ZONA = 1`).
- **Nomes de cargo** como estão no arquivo: `'Presidente'`, `'Governador'`, `'Senador'`,
  `'Deputado Federal'`, `'Deputado Estadual'` e, no DF, `'Deputado Distrital'` e
  `'Conselheiro Distrital'`. Para ver a lista: `SELECT DISTINCT DS_CARGO_PERGUNTA FROM secoes;`
- **Aptos / comparecimento / abstenções** se repetem em todas as linhas da seção: para somá-los,
  filtre um cargo e use `SELECT DISTINCT` por seção, senão o valor é contado várias vezes.
- **Senador** em 2026 tem 2 vagas: cada eleitor vota duas vezes, então os votos somam o dobro
  do comparecimento.
- **Acentos no Excel**: o CSV exportado é UTF-8; abra por *Dados → De Texto/CSV*
  (com duplo clique o Excel pode estragar os acentos).
- **Não use `python -c "..."` no PowerShell** com SQL — as aspas quebram. Use o `consulta.py`.
