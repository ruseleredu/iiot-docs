# Componente `CommitPoint` (Docusaurus, TypeScript)

Insere no roteiro da aula um **ponto de commit** para o aluno, renderizado como um
**Admonition** do tema (`@theme/Admonition`, com o `type` que você escolher) e um
**CodeBlock** do tema (`@theme/CodeBlock`, que já traz destaque de sintaxe e botão
de copiar nativos). O comando segue a convenção que o autograder espera —
`T<n>: <tarefa>` — e o número **`<n>` é incrementado automaticamente** na ordem em
que os pontos aparecem na página.

## Instalação

Copie para o seu projeto Docusaurus (TypeScript):

```
src/components/CommitPoint/index.tsx
src/theme/MDXComponents.tsx        # registra <CommitPoint/> globalmente
```

Se você usava a versão anterior em JavaScript, **remova** os arquivos antigos para
não haver conflito de resolução do mesmo diretório:

```
src/components/CommitPoint/index.jsx         (apagar)
src/components/CommitPoint/styles.module.css (apagar — o estilo agora vem do tema)
src/theme/MDXComponents.js                   (apagar — substituido pelo .tsx)
```

O `src/theme/MDXComponents.tsx` deixa o componente disponível em **qualquer**
`.mdx` sem `import`. Se você já tem um `MDXComponents`, apenas acrescente a linha do
`CommitPoint`.

## Uso no MDX

```mdx
<CommitPoint task="implementa os cinco niveis de log" pontos={15} />

<CommitPoint task="filtra logs com CORE_DEBUG_LEVEL=2" pontos={10} files="platformio.ini" type="info" />

<CommitPoint task="log com dados formatados" pontos={15} />
```

Renderiza três admonitions numerados (`T1`, `T2`, `T3`), cada um com um bloco de
código copiável:

```bash
git add . && git commit -m "T1: implementa os cinco niveis de log" && git push
git add platformio.ini && git commit -m "T2: filtra logs com CORE_DEBUG_LEVEL=2" && git push
git add . && git commit -m "T3: log com dados formatados" && git push
```

Os tokens `T1`, `T2`, … coincidem com os `token` da rubrica em `autograde/grade.py`,
no repositório de notas. Um `CommitPoint` por tarefa, na ordem, e a numeração casa
com a correção.

## Props

| Prop     | Tipo                                                 | Padrão  | Descrição                                                              |
| -------- | ---------------------------------------------------- | ------- | ---------------------------------------------------------------------- |
| `task`   | `string`                                             | —       | Descrição da tarefa (obrigatória).                                     |
| `type`   | `'note' \| 'tip' \| 'info' \| 'warning' \| 'danger'` | `'tip'` | Tipo do admonition.                                                    |
| `pontos` | `number`                                             | —       | Pontos da tarefa; exibidos no título. (`points` também aceito.)        |
| `files`  | `string`                                             | `'.'`   | Arquivos do `git add` (ex.: `"src/main.cpp"`).                         |
| `prefix` | `string`                                             | `'T'`   | Prefixo do token.                                                      |
| `push`   | `boolean`                                            | `true`  | Inclui `&& git push` no comando.                                       |
| `n`      | `number`                                             | auto    | Força o número, ignorando o incremento automático.                     |
| `title`  | `ReactNode`                                          | auto    | Título; sobrescreve o padrão "Ponto de commit · T<n>".                 |
| `id`     | `string`                                             | auto    | Id da âncora para deep-link; padrão = token em minúsculas (ex.: `t1`). |


## Âncoras (referência rápida)

Cada `CommitPoint` renderiza dentro de um elemento com `id` derivado do token em
minúsculas (`T1` → `t1`), permitindo deep-link direto ao ponto:

- Na mesma página: `[ir para T3](#t3)`
- De outra página: `/lab/estruturas-de-controle#t3`

O título exibe um `#` clicável (copia o link) e a rolagem já respeita a altura da
navbar via `scroll-margin-top`. Para um id personalizado:

```mdx
<CommitPoint task="entrega final do projeto" id="entrega-final" pontos={20} />
```


## Numeração automática

Cada `CommitPoint` recebe um número sequencial na ordem do documento, por página. A
contagem é estável sob re-render e é **zerada ao sair da página**, então navegar e
voltar renumera corretamente. Para um commit intermediário que não é tarefa
avaliada, use `n` para fixar o número ou `prefix` para diferenciar.

## Observações

- Evite aspas duplas (`"`) dentro de `task`, pois o comando usa `-m "..."`.
- O botão de copiar e o destaque `bash` vêm do `@theme/CodeBlock`; nada de CSS
  próprio é necessário.
- O componente foi verificado com `tsc --strict` sob `@types/react` 18 e 19.

