#!/usr/bin/env python3
"""Gera o ferramentas/conferir.py de UM lab a partir do roteiro (.mdx).

Lê os <CommitPoint id="tN" task="..." files="..."/> do roteiro e escreve um conferir.py
que confere exatamente esses arquivos, tarefa por tarefa.

Uso (na raiz, com scripts/ e labs-docs/):
    python3 scripts/gerar_conferir.py labs-docs/LAB09.mdx -o caminho/ferramentas/conferir.py
    python3 scripts/gerar_conferir.py labs-docs/LAB09.mdx --listar   # só mostra o que extraiu

O número do lab sai do nome do arquivo (LAB09.mdx -> 09); use --lab para forçar.
"""
import argparse
import re
import sys
from pathlib import Path

PADRAO_CP = re.compile(r"<CommitPoint\b(.*?)/>", re.S)


def atributo(texto, nome):
    m = re.search(rf'\b{nome}\s*=\s*"([^"]*)"', texto)
    return m.group(1) if m else None


def extrair(mdx: Path):
    texto = mdx.read_text(encoding="utf-8")
    tarefas, problemas = {}, []
    for m in PADRAO_CP.finditer(texto):
        linha = texto.count("\n", 0, m.start()) + 1
        attrs = m.group(1)
        tid, task, files = (atributo(attrs, n) for n in ("id", "task", "files"))
        if not tid or not re.fullmatch(r"t\d+", tid):
            problemas.append(f"linha {linha}: CommitPoint sem id=\"tN\" válido")
            continue
        if tid in tarefas:
            problemas.append(f"linha {linha}: {tid} repetido")
            continue
        arquivos = (files or "").split()
        if not arquivos:
            problemas.append(f"linha {linha}: {tid} sem files=\"...\"")
            continue
        for a in arquivos:
            if a.startswith(("/", "./")) or "\\" in a or ".." in a.split("/"):
                problemas.append(f"linha {linha}: {tid}: caminho '{a}' deve ser relativo à raiz, com /")
        tarefas[tid] = (task or tid.upper(), arquivos)
    if not tarefas:
        problemas.append("nenhum <CommitPoint .../> encontrado")
    return dict(sorted(tarefas.items(), key=lambda kv: int(kv[0][1:]))), problemas


def gerar(lab, origem, tarefas):
    linhas = [f"        {tid!r}: ({nome!r}, {arqs!r})," for tid, (nome, arqs) in tarefas.items()]
    return (MODELO.replace("__LAB__", lab)
                  .replace("__ORIGEM__", origem)
                  .replace("__TAREFAS__", "\n".join(linhas)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mdx", type=Path, help="roteiro do lab (ex.: LAB09.mdx)")
    ap.add_argument("-o", "--saida", type=Path, help="arquivo a escrever (ex.: ferramentas/conferir.py)")
    ap.add_argument("--lab", help="número do lab (padrão: do nome do .mdx)")
    ap.add_argument("--listar", action="store_true", help="só mostra as tarefas e os arquivos")
    a = ap.parse_args()

    if not a.mdx.is_file():
        sys.exit(f"roteiro não encontrado: {a.mdx}")
    m = re.search(r"(\d+)", a.lab or a.mdx.stem)
    if not m:
        sys.exit("não consegui tirar o número do lab do nome do arquivo; use --lab 09")
    lab = m.group(1).zfill(2)

    tarefas, problemas = extrair(a.mdx)
    if problemas:
        print(f"{a.mdx.name}: problemas nos CommitPoint:", file=sys.stderr)
        for p in problemas:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    print(f"Lab {lab}: {len(tarefas)} tarefa(s) em {a.mdx.name}")
    for tid, (nome, arqs) in tarefas.items():
        print(f"  {tid}  {nome}: {' '.join(arqs)}")
    if a.listar:
        return
    if not a.saida:
        sys.exit("informe -o caminho/ferramentas/conferir.py (ou use --listar)")

    codigo = gerar(lab, a.mdx.name, tarefas)
    compile(codigo, str(a.saida), "exec")          # falha aqui, e não na mão do aluno
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(codigo, encoding="utf-8", newline="\n")
    print(f"escrito: {a.saida}")


# ----------------------------------------------------------------------------
# Modelo do conferir.py. __LAB__, __ORIGEM__ e __TAREFAS__ são preenchidos acima.
# ----------------------------------------------------------------------------
MODELO = r'''#!/usr/bin/env python3
r"""ELT85B - Lab __LAB__: confere se os arquivos estão nas pastas certas.

Uso (terminal cmd do VS Code, em qualquer pasta do repositório):
    py ferramentas\conferir.py          todas as tarefas
    py ferramentas\conferir.py t3       só a T3

Não altera nada: só lê os arquivos e o Git e diz o que fazer.
Gerado por gerar_conferir.py a partir de __ORIGEM__ (os CommitPoint do roteiro).
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

LAB = "__LAB__"
MANIFESTO = {
    LAB: {
__TAREFAS__
    },
}


IGNORAR_DIRS = {".git", ".pio", "node_modules", "__pycache__", ".venv"}
SEGREDOS = [".env", "include/segredos.h", "credenciais.txt", ".segredos.json"]
ERROS = 0
AVISOS = 0


def erro(msg):
    global ERROS
    ERROS += 1
    print(f"  [ERRO]  {msg}")


def aviso(msg):
    global AVISOS
    AVISOS += 1
    print(f"  [AVISO] {msg}")


def ok(msg):
    print(f"  [ok]    {msg}")


def git(*args, raiz=None):
    try:
        r = subprocess.run(["git", *args], cwd=raiz, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return 127, ""
    return r.returncode, r.stdout.strip()


def win(p):
    """Caminho no formato do cmd (barra invertida)."""
    return str(p).replace("/", "\\") if os.name == "nt" else str(p)


def achar_raiz():
    cod, saida = git("rev-parse", "--show-toplevel")
    if cod != 0:
        print("Esta pasta NÃO está dentro de um repositório Git.")
        print(f"  Pasta atual: {win(Path.cwd())}")
        print("  Entre na pasta do repositório do grupo (a que o clone criou), por exemplo:")
        print("    cd /d %USERPROFILE%\\ELT85BN21\\lab05-grupo-x")
        sys.exit(2)
    return Path(saida).resolve()


def descobrir_lab(raiz, forcado):
    if forcado:
        return forcado.zfill(2), "informado com --lab"
    _, url = git("remote", "get-url", "origin", raiz=raiz)
    for fonte, texto in (("remoto origin", url), ("nome da pasta", raiz.name)):
        m = re.search(r"lab(\d{2})", texto or "", re.I)
        if m:
            return m.group(1), f"{fonte}: {texto}"
    return None, ""


def listar_arquivos(base, max_prof=6):
    """Todos os arquivos sob 'base', sem .git/.pio, até max_prof níveis."""
    base = Path(base)
    if not base.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        prof = len(Path(dirpath).relative_to(base).parts)
        dirnames[:] = [d for d in dirnames if d not in IGNORAR_DIRS] if prof < max_prof else []
        for f in filenames:
            yield Path(dirpath) / f


def candidatos(nome, raiz):
    """Onde um arquivo com este nome foi parar (no repositório e nos lugares de sempre)."""
    nome_l = nome.lower()
    variantes = {nome_l, nome_l + ".txt", nome_l + ".png", nome_l + ".md"}
    lugares = [(raiz, 6), (raiz.parent, 1)]
    casa = Path.home()
    for sub in ("Downloads", "Desktop", "Documents", "Pictures", "Pictures/Screenshots",
                "OneDrive/Desktop", "OneDrive/Documentos", "OneDrive/Imagens/Capturas de Tela",
                "Imagens/Capturas de Tela", "Área de Trabalho", "Documentos"):
        lugares.append((casa / sub, 1))
    vistos, achados = set(), []
    for lugar, prof in lugares:
        for p in listar_arquivos(lugar, prof):
            if p.name.lower() in variantes:
                rp = p.resolve()
                if rp not in vistos:
                    vistos.add(rp)
                    achados.append(rp)
    return achados


def conferir_geral(raiz):
    print("\n== Pasta e repositório")
    aqui = Path.cwd().resolve()
    if aqui != raiz:
        aviso(f"você está em {win(aqui)}, e não na raiz do repositório.")
        print(f"          Os comandos dos roteiros rodam na raiz:  cd /d \"{win(raiz)}\"")
    else:
        ok(f"terminal na raiz do repositório: {win(raiz)}")

    if "onedrive" in str(raiz).lower():
        aviso("o repositório está dentro do OneDrive: a sincronização atrapalha o Git e o PlatformIO."
              " Prefira clonar em %USERPROFILE%\\ELT85BN21\\")

    # repositório dentro de repositório (clonou duas vezes, ou dentro de outra pasta de lab)
    for dirpath, dirnames, _ in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in IGNORAR_DIRS - {".git"}]
        if Path(dirpath) != raiz and ".git" in dirnames:
            erro(f"há um repositório DENTRO do repositório: {win(Path(dirpath).relative_to(raiz))}. "
                 "Os arquivos dele não entram nos commits do grupo.")
        if ".git" in dirnames:
            dirnames.remove(".git")
        if len(Path(dirpath).relative_to(raiz).parts) >= 3:
            dirnames[:] = []
    cod, _ = git("rev-parse", "--show-toplevel", raiz=raiz.parent)
    if cod == 0:
        aviso("a pasta ACIMA do repositório também é um repositório Git (clonou dentro de outro?).")

    # pasta de evidências com nome errado
    for d in raiz.iterdir():
        if d.is_dir() and d.name != "evidencias" and re.fullmatch(r"evid[eê]ncia[s]?", d.name, re.I):
            erro(f"a pasta se chama '{d.name}'; o nome certo é 'evidencias' (minúsculo, sem acento).")

    # evidências soltas na raiz ou com extensão dupla
    for p in raiz.iterdir():
        if p.is_file() and re.match(r"t\d-.*\.(txt|png|md|jpg)$", p.name, re.I):
            erro(f"'{p.name}' está na raiz; evidências ficam em evidencias\\  ->  move \"{p.name}\" evidencias\\")
    for p in listar_arquivos(raiz, 3):
        if re.search(r"\.(txt|png|md|json|jpg)\.(txt|png|md|json|jpg)$", p.name, re.I):
            erro(f"extensão dupla: {win(p.relative_to(raiz))} (o Windows escondia a extensão). "
                 "Renomeie tirando a segunda.")

    # segredos no Git
    for s in SEGREDOS:
        cod, _ = git("ls-files", "--error-unmatch", s, raiz=raiz)
        if cod == 0:
            erro(f"'{s}' está no Git! Tire com:  git rm --cached {s}  e confira o .gitignore")


def conferir_tarefa(raiz, lab, tid, nome, arquivos, ver_commit):
    print(f"\n== Lab {lab} · {tid.upper()} — {nome}")
    sha = ""
    if ver_commit:
        _, sha = git("log", "-1", "--format=%h", "--extended-regexp", f"--grep=^{tid.upper()}:", raiz=raiz)
    for rel in arquivos:
        alvo = raiz / rel
        if alvo.is_file():
            if alvo.stat().st_size == 0:
                aviso(f"{rel} existe, mas está VAZIO")
                continue
            cod, _ = git("ls-files", "--error-unmatch", rel, raiz=raiz)
            if cod != 0:
                cod_ig, _ = git("check-ignore", "-q", rel, raiz=raiz)
                if cod_ig == 0:
                    erro(f"{rel} está no lugar certo, mas o .gitignore o ignora (git check-ignore -v {rel})")
                else:
                    aviso(f"{rel} está no lugar certo, mas ainda não foi para o Git:  git add {rel}")
                continue
            _, st = git("status", "--porcelain", "--", rel, raiz=raiz)
            if st:
                aviso(f"{rel} tem mudanças ainda não commitadas")
            else:
                ok(rel)
            continue

        # não está onde deveria: procura em volta
        achados = [p for p in candidatos(Path(rel).name, raiz) if p != alvo.resolve()]
        if achados:
            erro(f"{rel} NÃO está no lugar certo. Achei:")
            for p in achados[:5]:
                print(f"            {win(p)}")
            destino = win(alvo.parent)
            print("          Mova para a pasta certa e acrescente ao Git:")
            if not alvo.parent.is_dir():
                print(f"            mkdir \"{destino}\"")
            print(f"            move \"{win(achados[0])}\" \"{win(alvo)}\"")
            print(f"            git add {rel}")
        else:
            erro(f"{rel} não existe (nem em outra pasta próxima)")

    if ver_commit:
        if not sha:
            aviso(f"nenhum commit '{tid.upper()}:' ainda")
        else:
            faltam = [r for r in arquivos if git("cat-file", "-e", f"{sha}:{r}", raiz=raiz)[0] != 0]
            if faltam:
                erro(f"o commit {sha} ('{tid.upper()}:') NÃO contém: {', '.join(faltam)}")
            _, rem = git("branch", "-r", "--contains", sha, raiz=raiz)
            if rem:
                ok(f"commit {sha} '{tid.upper()}:' enviado ao GitHub")
            else:
                aviso(f"commit {sha} '{tid.upper()}:' ainda não foi enviado:  git push")


def main():
    ap = argparse.ArgumentParser(description="Confere se os arquivos do lab estão nas pastas certas.")
    ap.add_argument("tarefas", nargs="*", help="t1 t2 ... (padrão: todas)")
    ap.add_argument("--lab", help=argparse.SUPPRESS)  # só para testes
    ap.add_argument("--sem-commit", action="store_true", help="não confere os commits Tn:")
    a = ap.parse_args()

    if os.name == "nt":
        os.system("")  # habilita a saída UTF-8/ANSI do console em alguns Windows
    raiz = achar_raiz()
    detectado, origem = descobrir_lab(raiz, a.lab)
    lab = LAB
    print(f"Lab {lab}")
    if detectado and detectado != LAB:
        print(f"\nATENÇÃO: este conferir.py é do Lab {LAB}, mas o repositório parece ser do Lab "
              f"{detectado} ({origem}).")
        print("  Você está na pasta do lab certo? Use o conferir.py do repositório deste lab.")
        sys.exit(2)
    conferir_geral(raiz)
    pedidas = [t.lower() for t in a.tarefas] or list(MANIFESTO[lab])
    for tid in pedidas:
        if tid not in MANIFESTO[lab]:
            print(f"\nO Lab {lab} não tem a tarefa {tid}. Tarefas: {', '.join(MANIFESTO[lab])}")
            sys.exit(2)
        nome, arquivos = MANIFESTO[lab][tid]
        conferir_tarefa(raiz, lab, tid, nome, arquivos, not a.sem_commit)

    print(f"\nResultado: {ERROS} erro(s), {AVISOS} aviso(s).")
    if ERROS == 0 and AVISOS == 0:
        print("Tudo no lugar.")
    sys.exit(1 if ERROS else 0)


if __name__ == "__main__":
    main()
'''

if __name__ == "__main__":
    main()
