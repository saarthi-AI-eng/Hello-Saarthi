import { useState, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Play, Pause, RotateCcw, Volume2, Settings, Maximize, MessageCircle, FileText, CheckCircle2, ChevronRight, Clock, Plus } from 'lucide-react';
import { api, type VideoResponse, type VideoNoteResponse } from '../lib/api';
import './VideoPlayer.css';

interface Chapter {
    time: number;
    title: string;
}

function parseChapters(chaptersJson?: string | null): Chapter[] {
    if (!chaptersJson || !chaptersJson.trim()) return [];
    try {
        const raw = JSON.parse(chaptersJson) as unknown;
        if (!Array.isArray(raw)) return [];
        return raw.map((item: unknown) => {
            const o = item as Record<string, unknown>;
            const time = typeof o.time === 'number' ? o.time : Number(o.time) || 0;
            const title = typeof o.title === 'string' ? o.title : String(o.title || '');
            return { time, title };
        }).filter((c) => c.title || c.time >= 0);
    } catch {
        return [];
    }
}

export default function VideoPlayerPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const videoRef = useRef<HTMLVideoElement>(null);

    const [video, setVideo] = useState<VideoResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [notes, setNotes] = useState<VideoNoteResponse[]>([]);
    const [newNote, setNewNote] = useState('');
    const [noteTimeSeconds, setNoteTimeSeconds] = useState(0);

    const [playing, setPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [volume, setVolume] = useState(1);
    const [activeTab, setActiveTab] = useState<'notes' | 'discussion'>('notes');

    const isEmbed = Boolean(video?.embedUrl);
    const chapters: Chapter[] = video ? parseChapters(video.chaptersJson) : [];
    const duration = video?.durationSeconds ?? 0;

    useEffect(() => {
        if (!id) {
            setError('Invalid video');
            setLoading(false);
            return;
        }
        let cancelled = false;
        setLoading(true);
        setError(null);
        api.get<VideoResponse>(`/videos/${id}`)
            .then((v) => {
                if (!cancelled) setVideo(v);
            })
            .catch((e) => {
                if (!cancelled) setError(e instanceof Error ? e.message : 'Video not found');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [id]);

    useEffect(() => {
        if (!id || !video) return;
        let cancelled = false;
        api.get<VideoNoteResponse[]>(`/videos/${id}/notes`)
            .then((list) => { if (!cancelled) setNotes(list || []); })
            .catch(() => { if (!cancelled) setNotes([]); });
        return () => { cancelled = true; };
    }, [id, video]);

    const togglePlay = () => {
        if (videoRef.current) {
            if (playing) videoRef.current.pause();
            else videoRef.current.play();
            setPlaying(!playing);
        }
    };

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
            setNoteTimeSeconds(Math.floor(videoRef.current.currentTime));
        }
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const seekTo = (time: number) => {
        if (videoRef.current) {
            videoRef.current.currentTime = time;
            setCurrentTime(time);
            setNoteTimeSeconds(Math.floor(time));
        }
    };

    const addNote = async () => {
        if (!newNote.trim() || !id) return;
        const timeSeconds = isEmbed ? noteTimeSeconds : Math.floor(currentTime);
        try {
            const created = await api.post<VideoNoteResponse>(`/videos/${id}/notes`, {
                timeSeconds,
                text: newNote.trim(),
            });
            setNotes((prev) => [...prev, created].sort((a, b) => a.timeSeconds - b.timeSeconds));
            setNewNote('');
        } catch {
            // ignore
        }
    };

    if (loading) {
        return (
            <div className="video-player-page">
                <div className="video-loading-state">Loading video…</div>
            </div>
        );
    }
    if (error || !video) {
        return (
            <div className="video-player-page">
                <div className="video-error-state">
                    <p>{error || 'Video not found'}</p>
                    <button type="button" className="btn btn-primary" onClick={() => navigate('/videos')}>
                        ← Back to Library
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="video-player-page">
            <div className="video-main-area">
                <div className="video-header">
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => navigate('/videos')}>
                        ← Back to Library
                    </button>
                    <h1>{video.title}</h1>
                </div>

                <div className="video-container">
                    {isEmbed ? (
                        <iframe
                            src={video.embedUrl!}
                            title={video.title}
                            className="video-element video-iframe"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                        />
                    ) : (
                        <>
                            <video
                                ref={videoRef}
                                src={video.url}
                                className="video-element"
                                onTimeUpdate={handleTimeUpdate}
                                onClick={togglePlay}
                            />
                            <div className="video-controls-overlay">
                                <div className="video-progress-container" onClick={(e) => {
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    const pos = (e.clientX - rect.left) / rect.width;
                                    seekTo(pos * duration);
                                }}>
                                    <div className="video-progress-bg">
                                        <div className="video-progress-fill" style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }} />
                                    </div>
                                    {chapters.map((chap, i) => (
                                        <div key={i} className="chapter-marker" style={{ left: `${duration ? (chap.time / duration) * 100 : 0}%` }} title={chap.title} />
                                    ))}
                                </div>
                                <div className="video-controls-row">
                                    <div className="controls-left">
                                        <button type="button" onClick={togglePlay} className="control-btn">
                                            {playing ? <Pause size={20} /> : <Play size={20} />}
                                        </button>
                                        <button type="button" className="control-btn" onClick={() => seekTo(currentTime - 10)}>
                                            <RotateCcw size={18} />
                                        </button>
                                        <div className="volume-control">
                                            <Volume2 size={18} />
                                            <input
                                                type="range"
                                                min={0}
                                                max={1}
                                                step={0.1}
                                                value={volume}
                                                onChange={(e) => {
                                                    const v = parseFloat(e.target.value);
                                                    setVolume(v);
                                                    if (videoRef.current) videoRef.current.volume = v;
                                                }}
                                                className="volume-slider"
                                            />
                                        </div>
                                        <span className="time-display">
                                            {formatTime(currentTime)} / {formatTime(duration)}
                                        </span>
                                    </div>
                                    <div className="controls-right">
                                        <button type="button" className="control-btn"><Settings size={18} /></button>
                                        <button type="button" className="control-btn"><Maximize size={18} /></button>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                <div className="video-content-tabs">
                    <div className="tabs-header">
                        <button type="button" className={`tab-btn ${activeTab === 'notes' ? 'active' : ''}`} onClick={() => setActiveTab('notes')}>
                            <FileText size={16} /> My Notes
                        </button>
                        <button type="button" className={`tab-btn ${activeTab === 'discussion' ? 'active' : ''}`} onClick={() => setActiveTab('discussion')}>
                            <MessageCircle size={16} /> Discussion
                        </button>
                    </div>
                    <div className="tab-content">
                        {activeTab === 'notes' && (
                            <div className="notes-section">
                                <div className="add-note-box">
                                    {isEmbed && (
                                        <input
                                            type="number"
                                            min={0}
                                            value={noteTimeSeconds}
                                            onChange={(e) => setNoteTimeSeconds(parseInt(e.target.value, 10) || 0)}
                                            className="input input-sm"
                                            placeholder="Time (sec)"
                                            style={{ width: 80 }}
                                        />
                                    )}
                                    <span className="timestamp-badge"><Clock size={12} /> {formatTime(isEmbed ? noteTimeSeconds : currentTime)}</span>
                                    <input
                                        type="text"
                                        placeholder="Add a timestamped note..."
                                        value={newNote}
                                        onChange={(e) => setNewNote(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && addNote()}
                                        className="input"
                                    />
                                    <button type="button" className="btn btn-primary btn-sm" onClick={addNote}>
                                        <Plus size={14} /> Add
                                    </button>
                                </div>
                                <div className="notes-list">
                                    {notes.map((note) => (
                                        <div key={note.id} className="note-item" onClick={() => !isEmbed && seekTo(note.timeSeconds)}>
                                            <span className="note-time">{formatTime(note.timeSeconds)}</span>
                                            <p className="note-text">{note.text}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {activeTab === 'discussion' && (
                            <div className="discussion-placeholder">
                                <p>Join the conversation with other students…</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="video-sidebar">
                <div className="sidebar-header">
                    <h3>Course Content</h3>
                </div>
                <div className="chapters-list">
                    {chapters.length > 0 ? (
                        chapters.map((chap, i) => {
                            const isActive = currentTime >= chap.time && (i === chapters.length - 1 || currentTime < chapters[i + 1].time);
                            return (
                                <button
                                    key={i}
                                    type="button"
                                    className={`chapter-item ${isActive ? 'active' : ''}`}
                                    onClick={() => seekTo(chap.time)}
                                >
                                    <div className="chapter-status">
                                        {!isEmbed && currentTime > chap.time + 30 ? <CheckCircle2 size={16} className="text-success" /> : <div className="chapter-dot" />}
                                    </div>
                                    <div className="chapter-info">
                                        <span className="chapter-title">{chap.title}</span>
                                        <span className="chapter-time">{formatTime(chap.time)}</span>
                                    </div>
                                    {isActive && <ChevronRight size={16} className="chapter-active-icon" />}
                                </button>
                            );
                        })
                    ) : (
                        <p className="video-sidebar-empty">No chapters. Duration: {formatTime(duration)}</p>
                    )}
                </div>
            </div>
        </div>
    );
}
