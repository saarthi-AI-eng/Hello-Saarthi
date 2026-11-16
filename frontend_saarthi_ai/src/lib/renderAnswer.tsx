import type { ReactNode } from 'react';
import 'katex/dist/katex.min.css';
import { BlockMath, InlineMath } from 'react-katex';

/** Inline $math$, **bold** and [Source: …] badges inside one line of text. */
export function renderInline(text: string): ReactNode[] {
    const out: ReactNode[] = [];
    const re = /\$([^$]+)\$|\*\*([^*]+)\*\*|\[Source: ([^\]]+)\]/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
        if (m.index > last) out.push(text.slice(last, m.index));
        const [, math, bold, source] = m;
        if (math !== undefined) {
            out.push(<InlineMath key={m.index} math={math} renderError={() => <code>{math}</code>} />);
        } else if (bold !== undefined) {
            out.push(<strong key={m.index}>{renderInline(bold)}</strong>);
        } else {
            out.push(<span key={m.index} className="badge badge-success badge-sm chat-source">📚 {source}</span>);
        }
        last = m.index + m[0].length;
    }
    if (last < text.length) out.push(text.slice(last));
    return out;
}

/** Paragraphs, bullet / numbered lists and $$block math$$ from an LLM's markdown answer. */
export function renderAnswer(text: string, bulletClass = 'an-bullet'): ReactNode[] {
    const blocks = text.split(/(\$\$[\s\S]+?\$\$)/g);
    const out: ReactNode[] = [];
    blocks.forEach((block, b) => {
        if (block.startsWith('$$')) {
            const math = block.slice(2, -2).trim();
            out.push(<BlockMath key={`b${b}`} math={math} renderError={() => <pre>{math}</pre>} />);
            return;
        }
        block.split('\n').forEach((line, i) => {
            const t = line.trim();
            if (!t) return;
            const bullet = t.match(/^(?:[*-]|\d+\.)\s+(.*)$/);
            out.push(
                bullet
                    ? <p key={`${b}-${i}`} className={bulletClass}>• {renderInline(bullet[1])}</p>
                    : <p key={`${b}-${i}`}>{renderInline(t)}</p>,
            );
        });
    });
    return out;
}
