#!/usr/bin/env python3
"""
gen_tarefas_toc.py — Mapa de tarefas a partir dos <CommitPoint/> de um MDX.

Lê os <CommitPoint/> na ordem do documento (T1…Tn), com pontos, id, type e
files, e gera um bloco navegável para colar no INÍCIO da aula, ajudando o
aluno a localizar cada tarefa e ver onde estão os pontos.

Formatos (--format):
  list       (padrão) lista de bullets Markdown "- **[Tn](#tN)** — ... *(N pts)*"
  table      tabela: Tarefa | Entrega | Pontos, + total
  checklist  lista de tarefas "- [ ] **Tn** — ... (N pts)" (autoacompanhamento)
  toc        lista numerada de links "1. [Tn — ...](#tN)"

O bloco é delimitado por marcadores e pode ser regenerado:
  <!-- TAREFAS:START (gerado por gen_tarefas_toc.py) -->
  ...
  <!-- TAREFAS:END -->

Uso:
  python3 gen_tarefas_toc.py aula.mdx                     # imprime o bloco (list, com âncoras)
  python3 gen_tarefas_toc.py aula.mdx --format table
  python3 gen_tarefas_toc.py aula.mdx --write             # injeta ids + insere/atualiza
  python3 gen_tarefas_toc.py aula.mdx --no-details        # sem <details> (sempre visível)
  python3 gen_tarefas_toc.py aula.mdx --check             # CI: bloco desatualizado -> rc=1

Notas:
  --anchors / --no-anchors   (padrão: LIGADO) acrescenta id="tN" aos CommitPoint
             sem id, para as âncoras existirem (o componente CommitPoint publica
             um id/âncora). Com --no-anchors, links só saem se TODOS já têm id.
  --details / --no-details   (padrão: LIGADO) envolve o bloco num <details>
             recolhível; --no-details deixa o mapa sempre visível.
  --write    insere o bloco após o primeiro heading H1; se os marcadores já
             existirem, substitui o conteúdo entre eles (idempotente).
"""

from __future__ import annotations
import argparse, re, sys

CP_RE = re.compile(r"<CommitPoint\b(?P<attrs>.*?)/>", re.S)
START = "<!-- TAREFAS:START (gerado por gen_tarefas_toc.py) -->"
END = "<!-- TAREFAS:END -->"
BLOCK_RE = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def parse_commitpoints(src: str) -> list[dict]:
    tarefas = []
    for i, m in enumerate(CP_RE.finditer(src), 1):
        a = m.group("attrs")
        pontos = re.search(r"pontos=\{(\d+)\}", a)
        tarefas.append({
            "n": i,
            "token": f"T{i}",
            "task": _attr(a, "task") or "(sem task)",
            "pontos": int(pontos.group(1)) if pontos else 0,
            "id": _attr(a, "id"),
            "type": _attr(a, "type"),
            "files": _attr(a, "files"),
            "span": m.span(),
        })
    return tarefas


def inject_anchors(src: str) -> tuple[str, list[dict]]:
    """Acrescenta id='tN' aos CommitPoint sem id. Reprocessa do zero (offsets)."""
    out, last, n = [], 0, 0
    for m in CP_RE.finditer(src):
        n += 1
        attrs = m.group("attrs")
        out.append(src[last:m.start()])
        if not re.search(r'\bid="', attrs):
            out.append(f'<CommitPoint id="t{n}"{attrs}/>')
        else:
            out.append(m.group(0))
        last = m.end()
    out.append(src[last:])
    novo = "".join(out)
    return novo, parse_commitpoints(novo)


def link_alvo(t: dict, permitir_auto: bool) -> str | None:
    if t["id"]:
        return f'#{t["id"]}'
    if permitir_auto:
        return f'#t{t["n"]}'
    return None


def render(tarefas: list[dict], fmt: str, permitir_links: bool,
           usar_details: bool) -> str:
    total = sum(t["pontos"] for t in tarefas)
    titulo = f'🗺️ Mapa de tarefas — {len(tarefas)} tarefas · {total} pts'

    def rotulo(t):
        alvo = link_alvo(t, permitir_links)
        return f'[{t["token"]}]({alvo})' if alvo else t["token"]

    if fmt == "list":
        linhas = [f'- **{rotulo(t)}** — {t["task"]} *({t["pontos"]} pts)*'
                  for t in tarefas]
        corpo = "\n".join(linhas) + f'\n\n**Total: {total} pts**'
    elif fmt == "toc":
        linhas = [f'{t["n"]}. {rotulo(t)} — {t["task"]} · **{t["pontos"]} pts**'
                  for t in tarefas]
        corpo = "\n".join(linhas) + f'\n\n**Total: {total} pts**'
    elif fmt == "checklist":
        linhas = [f'- [ ] {rotulo(t)} — {t["task"]} *({t["pontos"]} pts)*'
                  for t in tarefas]
        corpo = "\n".join(linhas) + f'\n\n**Total: {total} pts**'
    else:  # table
        cab = ("| Tarefa | Entrega | Pontos |\n"
               "|:------:|:--------|-------:|\n")
        linhas = "".join(
            f'| {rotulo(t)} | {t["task"]} | {t["pontos"]} |\n' for t in tarefas
        )
        corpo = cab + linhas + f'| | **Total** | **{total}** |'

    if usar_details:
        miolo = (
            f'<details>\n'
            f'<summary>{titulo} (clique para expandir)</summary>\n\n'
            f'{corpo}\n\n'
            f'</details>'
        )
    else:
        miolo = f'**{titulo}**\n\n{corpo}'
    return f'{START}\n\n{miolo}\n\n{END}'


def inserir_ou_substituir(src: str, bloco: str) -> str:
    if BLOCK_RE.search(src):
        return BLOCK_RE.sub(lambda _: bloco, src, count=1)
    # insere após o primeiro heading H1 (linha começando com "# ")
    linhas = src.split("\n")
    for i, ln in enumerate(linhas):
        if re.match(r"^#\s+\S", ln):
            j = i + 1
            # pula linhas em branco imediatamente após o H1
            while j < len(linhas) and linhas[j].strip() == "":
                j += 1
            linhas.insert(j, "\n" + bloco + "\n")
            return "\n".join(linhas)
    # sem H1: coloca no topo (após front matter, se houver)
    return bloco + "\n\n" + src


def main():
    ap = argparse.ArgumentParser(description="Gera o mapa de tarefas dos CommitPoint de um MDX")
    ap.add_argument("mdx", help="arquivo .mdx da aula")
    ap.add_argument("--format", choices=["list", "table", "checklist", "toc"], default="list",
                    help="formato do mapa (padrão: list)")
    ap.add_argument("--anchors", action=argparse.BooleanOptionalAction, default=True,
                    help="injeta id='tN' nos CommitPoint sem id p/ habilitar links (padrão: ligado)")
    ap.add_argument("--details", action=argparse.BooleanOptionalAction, default=True,
                    help="envolve o bloco num <details> recolhível (padrão: ligado)")
    ap.add_argument("--write", action="store_true",
                    help="edita o arquivo: insere/atualiza o bloco (e ids, se --anchors)")
    ap.add_argument("--check", action="store_true",
                    help="CI: falha (rc=1) se o bloco no arquivo estiver desatualizado")
    args = ap.parse_args()

    src = open(args.mdx, encoding="utf-8").read()

    # com --anchors, os ids passam a existir; links auto são permitidos
    if args.anchors:
        novo_src, tarefas = inject_anchors(src)
        permitir_links = True
    else:
        novo_src, tarefas = src, parse_commitpoints(src)
        # links auto só se TODOS já têm id (senão geraria link quebrado)
        permitir_links = all(t["id"] for t in tarefas) if tarefas else False

    if not tarefas:
        sys.exit("Nenhum <CommitPoint/> encontrado.")

    bloco = render(tarefas, args.format, permitir_links, args.details)

    if args.check:
        atual = BLOCK_RE.search(src)
        ok = atual is not None and atual.group(0).strip() == bloco.strip() and novo_src == src
        if ok:
            print("Mapa de tarefas atualizado. OK")
            return
        print("Mapa de tarefas DESATUALIZADO — rode com --anchors --write.", file=sys.stderr)
        sys.exit(1)

    if args.write:
        final = inserir_ou_substituir(novo_src, bloco)
        open(args.mdx, "w", encoding="utf-8").write(final)
        n_ancoras = sum(1 for t in tarefas if not t["id"]) if args.anchors else 0
        extra = f" (+{n_ancoras} ancoras injetadas)" if n_ancoras else ""
        print(f"Bloco inserido/atualizado em {args.mdx}: "
              f"{len(tarefas)} tarefas, {sum(t['pontos'] for t in tarefas)} pts{extra}.")
    else:
        print(bloco)


if __name__ == "__main__":
    main()
