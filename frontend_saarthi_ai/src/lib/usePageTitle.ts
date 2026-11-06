import { useEffect } from 'react';

/** Set the browser tab title for a page, e.g. "Courses · Saarthi.ai". Restores the old title on unmount. */
export function usePageTitle(title: string) {
  useEffect(() => {
    const previous = document.title;
    document.title = `${title} · Saarthi.ai`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
