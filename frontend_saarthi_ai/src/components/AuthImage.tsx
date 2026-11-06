import { useEffect, useState } from 'react';
import { authFetch } from '../lib/api';

interface Props {
    src: string;
    alt: string;
    className?: string;
}

/** Image from a route that needs the login token. Renders nothing if the file is not an image. */
export default function AuthImage({ src, alt, className }: Props) {
    const [objectUrl, setObjectUrl] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        let url: string | null = null;
        authFetch(src)
            .then((res) => (res.ok ? res.blob() : null))
            .then((blob) => {
                if (cancelled || !blob || !blob.type.startsWith('image/')) return;
                url = URL.createObjectURL(blob);
                setObjectUrl(url);
            })
            .catch(() => { /* no preview; the link still works */ });
        return () => {
            cancelled = true;
            if (url) URL.revokeObjectURL(url);
        };
    }, [src]);

    return objectUrl ? <img src={objectUrl} alt={alt} className={className} /> : null;
}
