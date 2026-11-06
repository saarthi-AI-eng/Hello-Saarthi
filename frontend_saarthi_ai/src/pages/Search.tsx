import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { BookOpen, FileText, Play, ExternalLink } from 'lucide-react';
import { api, type SearchResponse } from '../lib/api';
import Pagination from '../components/Pagination';
import './Search.css';

export default function SearchPage() {
    const [searchParams, setSearchParams] = useSearchParams();
    const q = searchParams.get('q') ?? '';
    const offset = Math.max(0, parseInt(searchParams.get('offset') ?? '0', 10));
    const limit = 20;

    const [data, setData] = useState<SearchResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!q || q.trim().length < 2) {
            setData(null);
            setLoading(false);
            return;
        }
        let cancelled = false;
        setLoading(true);
        setError(null);
        api.get<SearchResponse>('/courses/search', { q: q.trim(), limit, offset })
            .then((res) => {
                if (!cancelled) setData(res);
            })
            .catch((e) => {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Search failed');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [q, offset]);

    return (
        <div className="search-page">
            <h1>Search</h1>
            <p className="search-page-desc">Courses, materials, and videos (min 2 characters)</p>
            {error && <div className="search-error" role="alert">{error}</div>}
            {!q.trim() || q.trim().length < 2 ? (
                <p className="search-placeholder">Enter at least 2 characters to search.</p>
            ) : loading && !data ? (
                <p className="search-loading">Searching…</p>
            ) : data ? (
                <>
                    <div className="search-results">
                        {data.courses.length > 0 && (
                            <section className="search-section">
                                <h2><BookOpen size={18} /> Courses ({data.totalCourses})</h2>
                                <ul className="search-list">
                                    {data.courses.map((item) => (
                                        <li key={`c-${item.id}`}>
                                            <a href={item.link ?? `/courses/${item.id}`} className="search-item">
                                                <span className="search-item-title">{item.title}</span>
                                                {item.subtitle && <span className="search-item-sub">{item.subtitle}</span>}
                                                <ExternalLink size={14} />
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}
                        {data.materials.length > 0 && (
                            <section className="search-section">
                                <h2><FileText size={18} /> Materials ({data.totalMaterials})</h2>
                                <ul className="search-list">
                                    {data.materials.map((item) => (
                                        <li key={`m-${item.id}`}>
                                            <a href={item.link ?? '#'} target="_blank" rel="noopener noreferrer" className="search-item">
                                                <span className="search-item-title">{item.title}</span>
                                                {item.subtitle && <span className="search-item-sub">{item.subtitle}</span>}
                                                <ExternalLink size={14} />
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}
                        {data.videos.length > 0 && (
                            <section className="search-section">
                                <h2><Play size={18} /> Videos ({data.totalVideos})</h2>
                                <ul className="search-list">
                                    {data.videos.map((item) => (
                                        <li key={`v-${item.id}`}>
                                            <a href={item.link ?? `/videos/${item.id}`} className="search-item">
                                                <span className="search-item-title">{item.title}</span>
                                                {item.subtitle && <span className="search-item-sub">{item.subtitle}</span>}
                                                <ExternalLink size={14} />
                                            </a>
                                        </li>
                                    ))}
                                </ul>
                            </section>
                        )}
                    </div>
                    {(data.totalCourses > limit || data.totalMaterials > limit || data.totalVideos > limit) && (
                        <Pagination
                            total={Math.max(data.totalCourses, data.totalMaterials, data.totalVideos)}
                            limit={data.limit}
                            offset={data.offset}
                            onPageChange={(newOffset) => setSearchParams((prev) => {
                                prev.set('offset', String(newOffset));
                                return prev;
                            })}
                        />
                    )}
                    {data.courses.length === 0 && data.materials.length === 0 && data.videos.length === 0 && (
                        <p className="search-empty">No results for &quot;{q}&quot;</p>
                    )}
                </>
            ) : null}
        </div>
    );
}
