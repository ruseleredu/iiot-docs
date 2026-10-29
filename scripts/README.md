# docusaurus-shared-scripts

docusaurus-shared-scripts

## Add Remote

```bash
git remote add shared-scripts https://github.com/ruseleredu/docusaurus-shared-scripts.git
```

## Add Subtrees

```bash
git subtree add --prefix=scripts shared-scripts main --squash
```

## List existing remotes

```bash
git remote -v
```

## Pull Updates

```bash
git subtree pull --prefix=scripts shared-scripts main --squash
```

## Push Changes

```bash
git subtree push --prefix=scripts shared-scripts main
```

## List existing remotes

```bash
git remote remove shared-scripts
```

## Add another remote

```bash
git remote add shared-components https://github.com/ruseleredu/docusaurus-shared-components.git
```

---

# Scripts

```bash
node scripts/generate-emojis.js
```

```bash
node scripts/download-katex.js
```

# Template LABs (IIOT)

- Empty

```bash
./scripts/iiot/create-lab-template.sh
```

- PIO init
  
```bash
./scripts/iiot/create-lab-pio-template.sh
```

- Inicializa repo pro grupo
  
```bash
./scripts/iiot/create-lab-from-template.sh
```


# Template LABs (MIC)

- Empty

```bash
./scripts/mic/create-lab-template.sh
```

- PIO init
  
```bash
./scripts/mic/create-lab-pio-template.sh
```

- Inicializa repo pro grupo
  
```bash
./scripts/mic/create-lab-from-template.sh
```


Um repositório criado a partir de um template recebe uma cópia dos arquivos com um histórico novo, sem ligação com o template. Por isso não dá para fazer `git pull` do template. O script `sync-lab-from-template.sh` resolve isso assim:

1. Clona o template e gera um patch para cada commit novo, com `git format-patch BASE..HEAD`.
2. Em cada repositório de grupo, aplica esses patches com `git am -3`, que faz um merge de 3 vias, e depois faz o push.

Um grupo que já editou outros arquivos (o `main.cpp`, por exemplo) recebe as alterações sem problema. Se um grupo mexeu exatamente no mesmo trecho que você mudou, o script não toca no repositório desse grupo e o lista como falha no final.

**Como usar:**

Primeiro, descubra o commit base, ou seja, o último commit do template antes das suas alterações:

```bash
gh repo clone ELT73A-S22-2026-2/lab05-template /tmp/t && git -C /tmp/t log --oneline
```

Depois rode o script com esse commit:

```bash
./scripts/mic/sync-lab-from-template.sh <commit-base>
```

**Opções:**

- Se os alunos já começaram a trabalhar, use `USE_PR=1 ./sync-lab-from-template.sh <commit-base>`. Assim o script abre um Pull Request em cada repositório em vez de escrever direto na `main`.
- No final, o script mostra o comando para refazer apenas os grupos que falharam, usando `GROUP_LIST="C F"`.
- Não rode o script de novo nos grupos que já foram atualizados. O `git am` recusa patches que já foram aplicados.

Se nenhum grupo mexeu nos repositórios ainda, a opção mais simples é apagar os repositórios dos grupos (`gh repo delete`) e rodar de novo o `create-lab-from-template.sh`.




```bash
gh repo clone ELT85B-N21-2026-2/lab08-template /tmp/t && git -C /tmp/t log --oneline
```
