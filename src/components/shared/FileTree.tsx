import React, { useState } from 'react';
import ThemeCodeBlock from '@theme/CodeBlock';

export type ActionType = 'create' | 'read' | 'update' | 'delete' | 'professor' | 'notas' | 'generated';

export interface FileTreeProps {
    /** Título do grupo/detalhes */
    title?: string;
    /** Nome da pasta raiz principal */
    root?: string;
    /** Array de caminhos relativos com ações opcionais. Ex: ["wokwi.toml u", ".github/workflows/grade.yml d"] */
    files: string[];
    /** Se deve envolver em uma tag <details> */
    details?: boolean;
    /** Se o <details> deve iniciar aberto */
    defaultOpen?: boolean;
    /**
     * Mostra, abaixo da árvore, o `git conferir` (alias do Lab 01, 2.2) com os arquivos a criar,
     * editar ou verificar (ações c, u, r). Default: só nas árvores sem `details`; as de visão
     * geral ("no fim da aula") listam o projeto inteiro e acusariam FALTA em tudo.
     */
    check?: boolean;
}

interface TreeNode {
    name: string;
    relativePath: string;
    isFolder: boolean;
    action?: ActionType;
    customLabel?: string;
    children: Record<string, TreeNode>;
}

interface ActionConfig {
    type: ActionType;
    defaultLabel: string;
    bg: string;
    color: string;
    border: string;
}

type InfimaColor = 'primary' | 'secondary' | 'success' | 'info' | 'warning' | 'danger';

// Gera a paleta de um badge a partir de uma cor semântica do Infima.
// As variáveis *-contrast-* se adaptam automaticamente ao modo escuro.
const infima = (color: InfimaColor) => ({
    bg: `var(--ifm-color-${color}-contrast-background)`,
    color: `var(--ifm-color-${color}-contrast-foreground)`,
    border: `var(--ifm-color-${color}-dark)`,
});

// Mapeamento extensível para CRUD (Aceita iniciais c, r, u, d e termos em PT/EN)
const ACTION_MAP: Record<string, ActionConfig> = {
    // CREATE (Adicionar / Criar)
    c: { type: 'create', defaultLabel: 'Criar Aqui', ...infima('info') },
    // READ (Verificar / Ler)
    r: { type: 'read', defaultLabel: 'Verificar', ...infima('primary') },
    // UPDATE (Editar / Atualizar)
    u: { type: 'update', defaultLabel: 'Edite Aqui', ...infima('warning') },
    // DELETE (Remover / Deletar)
    d: { type: 'delete', defaultLabel: 'Remover', ...infima('danger') },
    // PROFESSOR (p)
    p: { type: 'professor', defaultLabel: '(Professor)', ...infima('secondary') },
    // NOTAS (n)
    n: { type: 'notas', defaultLabel: '(Notas)', ...infima('secondary') },
    // GENERATED / GERADO (g)
    g: {
        type: 'generated',
        defaultLabel: 'Gerado',
        bg: 'var(--ifm-color-emphasis-100)',
        color: 'var(--ifm-color-emphasis-700)',
        border: 'var(--ifm-color-emphasis-400)',
    },
};

// Estilo do badge após copiar o caminho
const COPIED_STYLE = infima('success');

function buildTree(paths: string[]): TreeNode {
    const treeRoot: TreeNode = { name: '', relativePath: '', isFolder: true, children: {} };

    paths.forEach((rawPath) => {
        const trimmed = rawPath.trim();
        if (!trimmed) return;

        const parts = trimmed.split(/\s+/);
        const pathPart = parts[0];
        const rawAction = parts[1]?.toLowerCase();

        const segments = pathPart.split('/').filter(Boolean);
        let current = treeRoot;
        let accumulatedPath = '';

        segments.forEach((segment, index) => {
            const isLast = index === segments.length - 1;
            accumulatedPath = accumulatedPath ? `${accumulatedPath}/${segment}` : segment;

            if (!current.children[segment]) {
                current.children[segment] = {
                    name: segment,
                    relativePath: accumulatedPath,
                    isFolder: !isLast,
                    children: {},
                };
            }

            if (isLast) {
                if (rawAction && ACTION_MAP[rawAction]) {
                    current.children[segment].action = ACTION_MAP[rawAction].type;
                    current.children[segment].customLabel = ACTION_MAP[rawAction].defaultLabel;
                }
            }

            current = current.children[segment];
        });
    });

    return treeRoot;
}

// Ações cujos arquivos têm de existir no repositório (vão para o `git conferir`).
const CONFERIR: ActionType[] = ['create', 'update', 'read'];

function caminhosParaConferir(paths: string[]): string[] {
    const lista: string[] = [];
    paths.forEach((rawPath) => {
        const [pathPart, rawAction] = rawPath.trim().split(/\s+/);
        const cfg = rawAction ? ACTION_MAP[rawAction.toLowerCase()] : undefined;
        const caminho = (pathPart ?? '').replace(/\/+$/, '');
        if (caminho && cfg && CONFERIR.includes(cfg.type) && !lista.includes(caminho)) {
            lista.push(caminho);
        }
    });
    return lista;
}

const getIcon = (name: string, isFolder: boolean) => {
    if (isFolder) return '📂';
    if (name.endsWith('.md')) return '📝';
    if (name.endsWith('.yml') || name.endsWith('.yaml')) return '🚀';
    if (name.endsWith('.json') || name.endsWith('.toml') || name.endsWith('.ini')) return '🔧';
    return '📄';
};

function RenderBranch({ nodes, copiedPath, onCopy }: { nodes: TreeNode[]; copiedPath: string | null; onCopy: (path: string) => void }) {
    return (
        <ul style={{ listStyle: 'none', paddingLeft: '1.2rem', margin: 0 }}>
            {nodes.map((node, index) => {
                const isLast = index === nodes.length - 1;
                const prefix = isLast ? '└── ' : '├── ';
                const actionCfg = node.action ? Object.values(ACTION_MAP).find(a => a.type === node.action) : null;
                const childNodes = Object.values(node.children);
                const isCopied = copiedPath === node.relativePath;

                return (
                    <li key={node.name} style={{ margin: '0.15rem 0', lineHeight: '1.6rem' }}>
                        <span style={{ color: 'var(--ifm-color-emphasis-500)', fontFamily: 'monospace' }}>
                            {prefix}
                        </span>
                        <span style={{ marginRight: '0.35rem' }}>{getIcon(node.name, node.isFolder)}</span>

                        {node.action ? (
                            <span
                                onClick={() => onCopy(node.relativePath)}
                                title={`Clique para copiar caminho: ${node.relativePath}`}
                                style={{
                                    cursor: 'pointer',
                                    fontWeight: 'bold',
                                    color: actionCfg?.color,
                                    textDecoration: 'underline',
                                    textDecorationStyle: 'dotted',
                                    transition: 'opacity 0.2s',
                                }}
                            >
                                {node.name}
                            </span>
                        ) : (
                            <span style={{ fontWeight: 'normal' }}>{node.name}</span>
                        )}

                        {actionCfg && (
                            <span
                                onClick={() => onCopy(node.relativePath)}
                                title={`Clique para copiar caminho: ${node.relativePath}`}
                                style={{
                                    marginLeft: '0.6rem',
                                    padding: '0.1rem 0.45rem',
                                    fontSize: '0.75rem',
                                    borderRadius: '4px',
                                    fontWeight: 'bold',
                                    backgroundColor: isCopied ? COPIED_STYLE.bg : actionCfg.bg,
                                    color: isCopied ? COPIED_STYLE.color : actionCfg.color,
                                    border: `1px solid ${isCopied ? COPIED_STYLE.border : actionCfg.border}`,
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: '0.2rem',
                                    cursor: 'pointer',
                                    userSelect: 'none',
                                    transition: 'all 0.2s ease-in-out',
                                }}
                            >
                                {isCopied ? '✅ Copiado!' : `👈 ${node.customLabel}`}
                            </span>
                        )}

                        {childNodes.length > 0 && (
                            <RenderBranch nodes={childNodes} copiedPath={copiedPath} onCopy={onCopy} />
                        )}
                    </li>
                );
            })}
        </ul>
    );
}

export default function FileTree({
    title,
    root = '',
    files,
    details = false,
    defaultOpen = true,
    check = !details,
}: FileTreeProps): React.JSX.Element {
    const [copiedPath, setCopiedPath] = useState<string | null>(null);
    const treeRoot = buildTree(files);
    const displayNodes = Object.values(treeRoot.children);
    const conferir = check ? caminhosParaConferir(files) : [];

    const handleCopy = (path: string) => {
        navigator.clipboard.writeText(path);
        setCopiedPath(path);
        setTimeout(() => setCopiedPath(null), 2000);
    };

    const content = (
        <div style={{
            margin: details ? 0 : '1rem 0',
            padding: '1rem',
            borderRadius: 'var(--ifm-global-radius)',
            border: details ? 'none' : '1px solid var(--ifm-color-emphasis-300)',
            backgroundColor: 'var(--ifm-background-surface-color)',
            fontFamily: 'var(--ifm-font-family-monospace)',
            fontSize: '0.9rem'
        }}>
            {!details && title && (
                <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>
                    {title}
                </div>
            )}
            {root && (
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                    📂 {root}/
                </div>
            )}
            <RenderBranch nodes={displayNodes} copiedPath={copiedPath} onCopy={handleCopy} />
            {conferir.length > 0 && (
                <div style={{ marginTop: '0.75rem', fontFamily: 'var(--ifm-font-family-base)' }}>
                    <ThemeCodeBlock language="bash" title="Conferir estes arquivos (de qualquer pasta do repositório)">
                        {`git conferir ${conferir.join(' ')}`}
                    </ThemeCodeBlock>
                </div>
            )}
        </div>
    );

    if (details) {
        return (
            <details open={defaultOpen} style={{
                marginBottom: '1rem',
                padding: '1rem',
                borderRadius: 'var(--ifm-global-radius)',
                border: '1px solid var(--ifm-color-emphasis-300)',
                backgroundColor: 'var(--ifm-background-surface-color)'
            }}>
                {title && (
                    <summary style={{ cursor: 'pointer', fontWeight: 'bold', outline: 'none' }}>
                        {title}
                    </summary>
                )}
                <div style={{ marginTop: title ? '0.75rem' : 0 }}>
                    {content}
                </div>
            </details>
        );
    }

    return content;
}
