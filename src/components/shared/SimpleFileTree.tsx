import React, { useMemo } from 'react';
import ThemeCodeBlock from '@theme/CodeBlock';

export interface SimpleFileTreeProps {
    /** Título do grupo/detalhes */
    title?: string;
    /** Nome do nó raiz */
    root?: string;
    /** Lista de caminhos com atalhos opcionais ao final (ex: "p", "n", "u", "d") */
    files?: string[];
    /** Se deve envolver em uma tag <details> */
    details?: boolean;
    /** Se o <details> deve iniciar aberto */
    defaultOpen?: boolean;
    /** Perfil pré-configurado de estrutura (ex: "lab00", "lab01", "lab02") */
    profile?: string;
}

// Mapeamento das letras de atalho para os rótulos de sufixo
const CRUD_MAP: Record<string, string> = {
    c: '# Criar',
    r: '# Ler',
    u: '# Editar',
    d: '# Deletar',
    p: '# (Professor)',
    n: '# (Notas)',
    g: '# Gerado',
};

interface TreeNode {
    name: string;
    suffix?: string;
    children: Record<string, TreeNode>;
}

// Gera arquivos padrão dinamicamente com base na tag do lab (ex: lab00, lab01)
function getProfileFiles(labPrefix: string): string[] {
    return [
        'Times/Grupo-A',
        'Times/...',
        'Times/Grupo-P p',
        'Times/Grupo-N n',
        `Repositórios/${labPrefix}-template`,
        `Repositórios/${labPrefix}-grupo-a`,
        `Repositórios/...`,
        `Repositórios/${labPrefix}-grupo-p p`,
        `Repositórios/${labPrefix}-grupo-n n`,
    ];
}

// Converte a lista de caminhos em estrutura de árvore ASCII
function generateAsciiTree(files: string[], rootName?: string): string[] {
    const root: TreeNode = { name: 'root', children: {} };

    files.forEach((pathItem) => {
        const trimmed = pathItem.trim();
        if (!trimmed) return;

        // Separa o caminho (primeira palavra antes do espaço) do restante (rótulo/sufixo)
        const spaceIndex = trimmed.search(/\s/);
        let pathPart = trimmed;
        let rawSuffix = '';

        if (spaceIndex !== -1) {
            pathPart = trimmed.slice(0, spaceIndex);
            rawSuffix = trimmed.slice(spaceIndex).trim();
        }

        let suffixText = '';
        if (rawSuffix) {
            const lower = rawSuffix.toLowerCase();
            suffixText = CRUD_MAP[lower] ? CRUD_MAP[lower] : rawSuffix;
        }

        const segments = pathPart.split('/').filter(Boolean);
        let current = root;

        segments.forEach((seg, index) => {
            const isLast = index === segments.length - 1;
            if (!current.children[seg]) {
                current.children[seg] = {
                    name: seg,
                    children: {},
                };
            }
            if (isLast && suffixText) {
                current.children[seg].suffix = suffixText;
            }
            current = current.children[seg];
        });
    });

    const lines: string[] = [];

    if (rootName) {
        lines.push(rootName);
    }

    function renderNodes(nodesObj: Record<string, TreeNode>, prefix: string = '') {
        const keys = Object.keys(nodesObj);
        keys.forEach((key, index) => {
            const node = nodesObj[key];
            const isLast = index === keys.length - 1;

            const connector = isLast ? '└── ' : '├── ';
            const suffixDisplay = node.suffix ? `  ${node.suffix}` : '';

            lines.push(`${prefix}${connector}${node.name}${suffixDisplay}`);

            const childPrefix = prefix + (isLast ? '    ' : '│   ');
            renderNodes(node.children, childPrefix);
        });
    }

    renderNodes(root.children, '');

    return lines;
}

export default function SimpleFileTree({
    title,
    root,
    files,
    details = false,
    defaultOpen = true,
    profile,
}: SimpleFileTreeProps): React.ReactNode {
    // Resolve valores padrão baseados no profile fornecido
    const isLabProfile = profile && /^lab\d+/i.test(profile);
    const labPrefix = isLabProfile ? profile.toLowerCase() : 'lab00';

    const resolvedTitle = title ?? (profile ? 'Estrutura organizacional dos repositórios' : undefined);
    const resolvedRoot = root ?? (profile ? 'ELT73A-S22-2026-2' : undefined);
    const resolvedFiles = files ?? (profile ? getProfileFiles(labPrefix) : []);

    const treeText = useMemo(
        () => generateAsciiTree(resolvedFiles, resolvedRoot).join('\n'),
        [resolvedFiles, resolvedRoot]
    );

    const content = <ThemeCodeBlock language="txt">{treeText}</ThemeCodeBlock>;

    if (details) {
        return (
            <details open={defaultOpen} style={{ marginBottom: '1rem' }}>
                {resolvedTitle && (
                    <summary style={{ cursor: 'pointer', fontWeight: 'bold', marginBottom: '0.5rem' }}>
                        {resolvedTitle}
                    </summary>
                )}
                {content}
            </details>
        );
    }

    return (
        <div style={{ marginBottom: '1rem' }}>
            {resolvedTitle && (
                <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>{resolvedTitle}</div>
            )}
            {content}
        </div>
    );
}
