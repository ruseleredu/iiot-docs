import React, { useState, useMemo, ReactNode, ReactElement } from 'react';

/**
 * Props definition for the MDX-passed children.
 * MDX transforms the Markdown table into a React component structure.
 */
interface EmojiTableProps {
    children: ReactElement<{
        children: ReactNode[];
    }>;
}

export default function EmojiTable({ children }: EmojiTableProps) {
    const [query, setQuery] = useState('');

    // 1. Convert children to an array and find the <tbody> element
    // MDX tables usually consist of <thead> and <tbody>
    const childrenArray = React.Children.toArray(children.props.children);

    const tbody = childrenArray.find(
        (child): child is ReactElement => React.isValidElement(child) && child.type === 'tbody'
    );

    // 2. Extract all rows (tr) from the tbody
    const allRows = useMemo(() => {
        const tbodyProps = (tbody as any)?.props;
        if (!tbodyProps || !tbodyProps.children) return [];

        // Filter out any non-element children (like newlines "\n")
        return React.Children.toArray(tbodyProps.children).filter(React.isValidElement);
    }, [tbody]);

    // 3. Filter rows based on the search query
    const filteredRows = useMemo(() => {
        if (!query) return allRows;

        return allRows.filter((row) => {
            const rowProps = (row as any)?.props;
            if (!rowProps || !rowProps.children) return false;

            // Get the cells (td); Shortcode is usually the second column (index 1)
            const cells = React.Children.toArray(rowProps.children).filter(React.isValidElement);
            if (cells.length < 2) return false;

            // Extract the text content from the shortcode cell
            const shortcodeCell = (cells[1] as any).props.children;

            // Normalize content (handles strings, arrays, or <code> wrappers)
            const textContent = Array.isArray(shortcodeCell)
                ? shortcodeCell.join('')
                : (typeof shortcodeCell === 'object' ? (shortcodeCell as any)?.props?.children : shortcodeCell);

            return String(textContent || "").toLowerCase().includes(query.toLowerCase());
        });
    }, [query, allRows]);

    // 4. Copy logic for Icons (URL) or Shortcodes (Text)
    const copyToClipboard = async (text: string, type: string) => {
        try {
            await navigator.clipboard.writeText(text);
            console.log(`Copied ${type}: ${text}`);
        } catch (err) {
            console.error('Failed to copy to clipboard', err);
        }
    };

    return (
        <div className="emoji-search-container">
            {/* Search Input Field */}
            <input
                type="text"
                placeholder="🔍 Search emojis (e.g. 'rocket', 'fire', 'check')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{
                    width: '100%',
                    padding: '12px',
                    marginBottom: '20px',
                    borderRadius: '8px',
                    border: '1px solid var(--ifm-color-emphasis-300)',
                    fontSize: '1rem',
                    backgroundColor: 'var(--ifm-background-color)',
                    color: 'var(--ifm-font-color-base)',
                    position: 'sticky',
                    top: '70px', // Adjust based on your Navbar height
                    zIndex: 10,
                }}
            />

            <div style={{ marginBottom: '10px', fontSize: '0.85rem', opacity: 0.6 }}>
                Showing {filteredRows.length} emojis. Click to copy.
            </div>

            <div className="emoji-table-container">
                <table
                    style={{ width: '100%', display: 'table' }}
                    onClick={(e) => {
                        const target = e.target as HTMLElement;

                        // Clicked an image: copy the source URL
                        if (target.tagName === 'IMG') {
                            const src = (target as HTMLImageElement).src;
                            copyToClipboard(src, "URL");
                            return;
                        }

                        // Clicked text or code: copy the shortcode
                        if (target.tagName === 'CODE' || target.tagName === 'TD') {
                            const text = target.innerText.replace(/`/g, '');
                            copyToClipboard(text, "Shortcode");
                        }
                    }}
                >
                    {/* Render the original table header (thead) */}
                    {childrenArray.find(c => React.isValidElement(c) && c.type === 'thead')}

                    <tbody>
                        {filteredRows}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
