# data/raw/videos/

Drop lecture video files here. Supported extensions: `.mp4`, `.mkv`, `.mov`,
`.avi`, `.webm`.

Optional sidecar files, matched by stem (`lecture_05.mp4` + `lecture_05.vtt`):

- `<name>.vtt` or `<name>.srt` — an existing timestamped transcript. When
  present, `scripts/ingest_videos.py` parses it directly instead of running
  speech-to-text, so a demo can run without any transcription model
  installed.
- `<name>.json` — optional manifest with `course`, `lecture`, `topic`
  overrides for this file (see `scripts/ingest_videos.py --help`).

Videos themselves are git-ignored — do not commit raw lecture footage.
