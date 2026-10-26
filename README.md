# Confira você mesmo a apuração da eleição

> **Tem familiaridade com Python e terminal?** Leia a [versão técnica deste guia](README.tecnico.md),
> com todas as opções, detalhes de funcionamento e consultas avançadas.

Este guia é para quem **nunca programou**. Seguindo os passos, você refaz no seu próprio
computador a soma dos votos de todas as urnas do Brasil e do exterior, e consegue ver o
resultado de **qualquer seção eleitoral**, inclusive a sua.

---

## O que esta ferramenta faz, em palavras simples

1. Quando a votação termina, cada urna emite um **Boletim de Urna (BU)**: o "extrato" com
   quantos votos cada candidato teve naquela seção. Uma cópia fica colada na porta da seção.
2. O TSE publica na internet os dados de **todos os BUs** do país, gratuitamente.
3. Esta ferramenta **baixa esses dados, confere que não foram corrompidos no download e soma
   os votos urna por urna**. Ela não usa o resultado final divulgado pelo TSE: chega ao total
   sozinha, a partir de cada seção.

Assim, qualquer pessoa pode comparar o total que obteve com o divulgado oficialmente, ou
comparar o BU da sua seção com o que está nos dados.

---

## O que você precisa

| | |
|---|---|
| **Computador** | Windows 10 ou 11 (no Mac/Linux funciona também — veja a [versão técnica](README.tecnico.md)) |
| **Espaço livre** | 10 GB para o Brasil inteiro (um estado só ocupa bem menos) |
| **Memória (RAM)** | 4 GB no mínimo; 8 GB recomendado para o Brasil inteiro |
| **Internet** | O Brasil inteiro são ~5 GB de download |
| **Tempo** | ~5 minutos para preparar; ~2 minutos para testar com um estado; 30–40 minutos para o Brasil inteiro |

Você vai digitar (ou copiar e colar) alguns comandos. Não precisa entender o que eles fazem
por dentro — cada passo explica o que esperar.

---

## Passo 1 — Instalar o Python (uma vez só)

O Python é o programa que "lê" e executa a ferramenta.

1. Acesse **https://www.python.org/downloads/** e clique no botão amarelo **Download Python**.
2. Abra o arquivo baixado e siga a instalação.
3. **Se aparecer** a caixa **"Add python.exe to PATH"**, marque-a antes de clicar em **Install Now**.
4. Aguarde terminar.

Para conferir, depois do Passo 3, digite `py --version` no PowerShell. Deve aparecer algo
como `Python 3.14.8`.

## Passo 2 — Baixar a ferramenta

1. Na página deste projeto no GitHub, clique no botão verde **Code** e depois em **Download ZIP**.
2. Clique com o botão direito no arquivo baixado → **Extrair tudo...**
3. Coloque a pasta em um lugar fácil de achar, por exemplo `Documentos\apuracao`.

## Passo 3 — Abrir o PowerShell dentro da pasta

O PowerShell é a janela onde você digita os comandos.

1. Abra a pasta da ferramenta no Explorador de Arquivos (onde está este `README.md`).
2. Clique na **barra de endereço** no topo da janela (onde aparece o caminho da pasta).
3. Apague o que está escrito, digite `powershell` e aperte **Enter**.

Vai abrir uma janela azul ou preta. É nela que você vai colar os comandos dos próximos passos.

> Para colar um comando: copie aqui, clique na janela do PowerShell e aperte **Ctrl+V**
> (ou clique com o botão direito). Depois aperte **Enter**.

## Passo 4 — Preparar a ferramenta (uma vez só)

Cole os dois comandos, um de cada vez:

```powershell
py -m venv .venv
```

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

O primeiro cria um "espaço" separado para a ferramenta; o segundo instala nele as peças de
que ela precisa, sempre nas mesmas versões, para que o seu resultado seja igual ao de qualquer
outra pessoa. Leva um ou dois minutos. No final deve aparecer **"Successfully installed..."**.

## Passo 5 — Teste rápido com um estado pequeno (Acre)

Antes do Brasil inteiro, faça um teste rápido com o Acre (17 MB de download):

```powershell
.\.venv\Scripts\python apura_bu.py --ano 2026 --uf AC --turno 1
```

Você vai ver mensagens como `Baixando...`, `sha512 confere com o publicado pelo TSE` e
`Lendo...`, e depois o resultado de cada cargo. **Se tudo deu certo**, o bloco de Presidente
deve mostrar exatamente estes números:

```
=== Presidente - BR ===
Seções: 2,270  Aptos: 613,742  Comparecimento: 488,330  Abstenções: 125,412
Votos: 488,330  Válidos: 469,089  Branco: 5,579  Nulo: 13,662
      22  FLAVIO BOLSONARO                              302,807   64.55%
      13  LULA                                          134,770   28.73%
```

> O "BR" aparece porque Presidente é um cargo nacional. Como você apurou só o Acre, os
> números são só do Acre.

**"sha512 confere"** significa que o arquivo baixado é idêntico, byte a byte, ao que o TSE
publicou — não foi corrompido nem alterado no caminho.

## Passo 6 — Apurar o Brasil inteiro (+ exterior)

```powershell
.\.venv\Scripts\python -u apura_bu.py --ano 2026 --uf TODAS --turno 1 --saida-secoes secoes_brasil.csv.gz | Tee-Object -FilePath log_apuracao.txt
```

- Primeiro ele baixa os 28 arquivos (27 estados + exterior), depois soma tudo.
- Tudo o que aparece na tela também é gravado em `log_apuracao.txt`.
- **Não feche a janela** até aparecer `Votos por seção salvos em secoes_brasil.csv.gz`.
- Se fechar sem querer, **rode o mesmo comando de novo**: o que já foi baixado é
  reaproveitado e ele só refaz a soma.

**Se tudo deu certo**, o resultado de Presidente deve ser exatamente:

```
=== Presidente - BR ===
Seções: 499,206  Aptos: 158,745,007  Comparecimento: 125,275,835  Abstenções: 33,469,172
Votos: 125,275,835  Válidos: 119,306,034  Branco: 2,300,798  Nulo: 3,669,003
      22  FLAVIO BOLSONARO                           56,104,503   47.03%
      13  LULA                                       53,879,538   45.16%
```

> Estes números de referência foram obtidos com os arquivos que o TSE publicou em
> 05/10/2026 (nomes terminados em `_051020261403.zip`). Se o TSE publicar uma versão
> atualizada, o nome do arquivo muda e os números podem mudar. O `log_apuracao.txt` mostra
> exatamente quais arquivos foram usados.

**2º turno:** troque `--turno 1` por `--turno 2`. Para saber se o TSE já publicou, rode:

```powershell
.\.venv\Scripts\python apura_bu.py --ano 2026 --listar
```

## Passo 7 — Ver os resultados

### O resultado geral, no Excel

O arquivo `apuracao.csv` tem o total de cada candidato. Para abrir com os acentos certos:

1. Abra o Excel → aba **Dados** → **De Texto/CSV**.
2. Escolha `apuracao.csv`.
3. Em **Delimitador**, escolha **Ponto e vírgula** e clique em **Carregar**.

A coluna `PC_VALIDOS` é o percentual sobre os votos válidos (0,4703 = 47,03%).

### A sua seção (ou qualquer outra)

O número da sua **zona** e **seção** está no seu título de eleitor ou no aplicativo **e-Título**.
Troque `SP`, `1` e `10` pelos seus dados:

```powershell
.\.venv\Scripts\python apura_bu.py --ano 2026 --uf SP --turno 1 --zona 1 --secao 10 --saida-secoes minha_secao.csv
```

Aparece na tela o resultado da seção, cargo por cargo. Você pode comparar com o **Boletim de
Urna impresso** que fica colado na porta da seção, ou com uma foto dele.

## Passo 8 (opcional) — Fazer perguntas aos dados

Para perguntas como "quantos votos o candidato X teve na minha cidade?", existe a
ferramenta de consulta. Primeiro, converta o arquivo das seções para um formato mais rápido
(uma vez só, ~3 minutos):

```powershell
.\.venv\Scripts\python consulta.py "COPY (SELECT * FROM 'secoes_brasil.csv.gz' ORDER BY SG_UF, CD_MUNICIPIO, NR_ZONA, NR_SECAO) TO 'secoes_brasil.parquet' (FORMAT parquet, COMPRESSION zstd)"
```

Depois, abra a consulta:

```powershell
.\.venv\Scripts\python consulta.py
```

Vai aparecer `sql>`. Cole uma das perguntas abaixo e aperte **Enter** (cada pergunta termina
com `;`). Para sair, digite `sair`.

**Resultado de Presidente na sua cidade** (troque `BA` e `SALVADOR`; o nome vai em
maiúsculas e entre aspas simples):

```sql
SELECT NM_VOTAVEL, sum(QT_VOTOS) AS votos FROM secoes
WHERE SG_UF = 'BA' AND NM_MUNICIPIO = 'SALVADOR' AND DS_CARGO_PERGUNTA = 'Presidente'
GROUP BY NM_VOTAVEL ORDER BY votos DESC;
```

**Não sabe como o nome da cidade está escrito?** (o `%` significa "qualquer coisa")

```sql
SELECT DISTINCT SG_UF, NM_MUNICIPIO FROM secoes WHERE NM_MUNICIPIO ILIKE '%feira de%';
```

**Presidente por estado:**

```sql
SELECT SG_UF, NM_VOTAVEL, sum(QT_VOTOS) AS votos FROM secoes
WHERE DS_CARGO_PERGUNTA = 'Presidente' AND NR_VOTAVEL IN (13, 22)
GROUP BY SG_UF, NM_VOTAVEL ORDER BY SG_UF, votos DESC;
```

**Salvar o resultado de uma cidade para abrir no Excel:**

```sql
COPY (SELECT * FROM secoes WHERE SG_UF = 'BA' AND NM_MUNICIPIO = 'SALVADOR')
TO 'salvador.csv' (HEADER, DELIMITER ';');
```

Mais exemplos na [versão técnica](README.tecnico.md#consultando-os-resultados-duckdb).

---

## Glossário

| Termo | Significado |
|---|---|
| **Seção** | O grupo de eleitores que vota numa mesma urna |
| **Zona** | Conjunto de seções sob responsabilidade de um mesmo cartório eleitoral |
| **BU (Boletim de Urna)** | O resultado de uma urna, emitido ao fim da votação |
| **Aptos** | Eleitores que poderiam votar naquela seção |
| **Comparecimento** | Eleitores que votaram |
| **Abstenções** | Eleitores aptos que não votaram |
| **Votos válidos** | Votos em candidatos ou partidos (sem brancos e nulos). É sobre eles que o TSE calcula os percentuais |
| **Legenda** | Voto só no número do partido (em deputados) |
| **ZZ** | Código usado pelo TSE para os eleitores que votam no **exterior** |
| **sha512 (hash)** | Uma "impressão digital" do arquivo. Se um único byte mudar, ela muda totalmente |

Em **Senador**, quando há duas vagas, cada eleitor vota duas vezes: por isso o total de
votos para Senador é o dobro do comparecimento.

---

## Problemas comuns

| O que aparece | O que fazer |
|---|---|
| `py não é reconhecido...` ou abre a Microsoft Store | O Python não foi instalado corretamente. Refaça o Passo 1 (marcando **"Add python.exe to PATH"**, se aparecer) e abra um PowerShell novo |
| `Nenhum boletim do 2º turno ... publicado ainda` | O TSE ainda não publicou. Costuma sair no dia seguinte à eleição. Use `--listar` para conferir |
| `sha512 ... não confere` | O download veio corrompido. O arquivo ruim já foi apagado: rode o mesmo comando de novo |
| O computador ficou muito lento ou apareceu `MemoryError` | Feche outros programas, ou apure um estado por vez (`--uf SP`, depois `--uf MG`...) |
| Fechei a janela no meio | Rode o mesmo comando de novo; os downloads já feitos são reaproveitados |
| Acentos estranhos no Excel | Abra pelo caminho **Dados → De Texto/CSV** (Passo 7), não com duplo clique |
| `Sem boletim ... para: XX` | A sigla do estado está errada. A mensagem lista as siglas disponíveis |

---

## Limitações (para ser transparente)

- A ferramenta soma os dados que o TSE gerou a partir dos BUs. Ela confere que o arquivo
  baixado é o mesmo publicado pelo TSE, mas **não** lê os arquivos assinados digitalmente
  de cada urna. Para isso, comparar com o BU impresso da seção (Passo 7) é um bom caminho.
- Quando duas seções votam na mesma urna ("seções agregadas"), os votos aparecem juntos na
  seção principal — é assim no próprio BU.
