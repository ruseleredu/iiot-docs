import React, { useState } from 'react';

export type ActionType = 'create' | 'read' | 'update' | 'delete' | 'professor' | 'notas' | 'generated';

export interface FileTreeProps {
    /** Nome da pasta raiz principal */
    root?: string;
    /** Array de caminhos relativos com ações opcionais. Ex: ["wokwi.toml u", ".github/workflows/grade.yml d"] */
    files: string[];
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

// Mapeamento extensível para CRUD (Aceita iniciais c, r, u, d e termos em PT/EN)
const ACTION_MAP: Record<string, ActionConfig> = {
    // CREATE (Adicionar / Criar)
    c: { type: 'create', defaultLabel: 'Criar Aqui', bg: 'var(--ifm-color-info-lightest)', color: 'var(--ifm-color-info-darkest)', border: 'var(--ifm-color-info)' },
    // READ (Verificar / Ler)
    r: { type: 'read', defaultLabel: 'Verificar', bg: 'var(--ifm-color-primary-lightest)', color: 'var(--ifm-color-primary-darkest)', border: 'var(--ifm-color-primary)' },
    // UPDATE (Editar / Atualizar)
    u: { type: 'update', defaultLabel: 'Edite Aqui', bg: 'var(--ifm-color-warning-lightest)', color: 'var(--ifm-color-warning-darkest)', border: 'var(--ifm-color-warning)' },
    // DELETE (Remover / Deletar)
    d: { type: 'delete', defaultLabel: 'Remover', bg: 'var(--ifm-color-danger-lightest)', color: 'var(--ifm-color-danger-darkest)', border: 'var(--ifm-color-danger)' },
    // PROFESSOR (p)
    p: { type: 'professor', defaultLabel: '(Professor)', bg: 'var(--ifm-color-secondary-lightest, #f0f0f0)', color: 'var(--ifm-color-secondary-darkest, #333)', border: 'var(--ifm-color-secondary, #ccc)' },
    // NOTAS (n)
    n: { type: 'notas', defaultLabel: '(Notas)', bg: 'var(--ifm-color-secondary-lightest, #f0f0f0)', color: 'var(--ifm-color-secondary-darkest, #333)', border: 'var(--ifm-color-secondary, #ccc)' },
    // GENERATED / GERADO (g)
    g: { type: 'generated', defaultLabel: 'Gerado', bg: 'var(--ifm-color-secondary-lightest, #f0f0f0)', color: 'var(--ifm-color-emphasis-700, #555)', border: 'var(--ifm-color-emphasis-400, #bbb)' },
};

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
                                    backgroundColor: isCopied ? 'var(--ifm-color-success-lightest)' : actionCfg.bg,
                                    color: isCopied ? 'var(--ifm-color-success-darkest)' : actionCfg.color,
                                    border: `1px solid ${isCopied ? 'var(--ifm-color-success)' : actionCfg.border}`,
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

export default function FileTree({ root = '', files }: FileTreeProps): React.JSX.Element {
    const [copiedPath, setCopiedPath] = useState<string | null>(null);
    const treeRoot = buildTree(files);
    const displayNodes = Object.values(treeRoot.children);

    const handleCopy = (path: string) => {
        navigator.clipboard.writeText(path);
        setCopiedPath(path);
        setTimeout(() => setCopiedPath(null), 2000);
    };

    return (
        <div style={{
            margin: '1rem 0',
            padding: '1rem',
            borderRadius: 'var(--ifm-global-radius)',
            border: '1px solid var(--ifm-color-emphasis-300)',
            backgroundColor: 'var(--ifm-background-surface-color)',
            fontFamily: 'var(--ifm-font-family-monospace)',
            fontSize: '0.9rem'
        }}>
            {root && (
                <div style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>
                    📂 {root}/
                </div>
            )}
            <RenderBranch nodes={displayNodes} copiedPath={copiedPath} onCopy={handleCopy} />
        </div>
    );
}
