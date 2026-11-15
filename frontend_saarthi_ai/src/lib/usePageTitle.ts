import { useEffect } from 'react';

/** Sets document.title to "{title} · Saarthi.ai" for the lifetime of the
 * calling page, restoring the previous title on unmount. */
export function usePageTitle(title: string): void {
    useEffect(() => {
        const previous = document.title;
        document.title = `${title} · Saarthi.ai`;
        return () => {
            document.title = previous;
        };
    }, [title]);
}
