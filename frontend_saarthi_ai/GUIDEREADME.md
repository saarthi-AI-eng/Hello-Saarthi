# 🎓 Saarthi.ai — Frontend Documentation

> An AI-powered educational platform built with React 19, TypeScript, and Vite.  
> Saarthi.ai provides a full-featured learning management system with AI tutoring, interactive coding labs, video library, quizzes, study materials, and progress analytics.

---

## 📸 Application Screenshots

### Student Dashboard
![Student Dashboard — Shows the personalized student view with stats cards, enrolled courses progress, upcoming deadlines, streak tracking, and the full navigation sidebar.](studentpage.png)

The **Student Dashboard** is the primary landing page after login. It displays:
- **Welcome banner** with the student's name and current learning streak (4 Day Streak 🔥)
- **Four stat cards** — Courses Enrolled (3), Pending Assignments (2 Due), Avg Quiz Score (85%), Study Time (12.5h Total)
- **Continue Learning** section showing in-progress courses (e.g., "Digital Signal Processing — DSP401" at 65% complete) with a Resume button
- **Upcoming Deadlines** panel with urgency badges (Due Soon, This Week, Upcoming) for assignments, quizzes, and projects
- **Recommended for You** section at the bottom for course discovery
- **Collapsible sidebar** with all navigation modules and a "5 Day Streak!" motivation card
- **Floating AI Chatbot** button (bottom-right corner) for instant help

---

### Admin / Instructor Dashboard
![Admin Dashboard — Shows the instructor/admin view with management capabilities, the same dashboard layout, and admin-level navigation.](adminpage.png)

The **Admin/Instructor Dashboard** shares the same layout but provides elevated access:
- Logged in as **Prof. Admin** with the `Admin` role badge in the top-right profile area
- Same stat cards and dashboard widgets — instructors can monitor overall platform health
- Access to **course management** tools: create/edit courses, add assignments, upload materials
- **People tab** in Course Detail — view enrolled students and their progress
- Admin-level search and content management across the platform

---

## 🏆 What Has Been Developed

Saarthi.ai's frontend is a **production-ready, full-featured Learning Management System (LMS)** with 16 distinct modules. Here is a complete breakdown of everything that has been built:

### ✅ Core Platform (Fully Implemented)

| # | Module | Status | Description |
|---|--------|--------|-------------|
| 1 | **Landing Page** | ✅ Complete | Public marketing page with hero, feature highlights, stats, and CTA buttons |
| 2 | **Authentication** | ✅ Complete | Login & Signup with JWT tokens, remember-me, role selection (Student/Teacher), session persistence |
| 3 | **Student Dashboard** | ✅ Complete | Personalized home with stats cards, course progress, deadlines, streak tracker, and recommendations |
| 4 | **Course Catalog** | ✅ Complete | Browse/search/filter courses, enroll/unenroll, pagination, emoji thumbnails |
| 5 | **Course Detail** | ✅ Complete | Tabbed view — Stream (announcements), Coursework (assignments + submissions), People, Materials (upload/download/PDF viewer) |
| 6 | **AI Tutor Chat** | ✅ Complete | Multi-conversation AI chat with history, rename/delete, markdown rendering, code block syntax highlighting |
| 7 | **Global AI Chatbot** | ✅ Complete | Floating chatbot widget visible on every page, suggested questions, real-time responses |
| 8 | **Exam Practice (Quiz)** | ✅ Complete | Topic-based quiz generator, timed sessions, MCQ with instant feedback, score summaries with explanations |
| 9 | **Coding Lab** | ✅ Complete | Browser code editor with syntax highlighting, line numbers, multi-language (Python, JS, C++, Java), API execution, graph output |
| 10 | **Video Library** | ✅ Complete | Video catalog with thumbnails, search, category filter |
| 11 | **Video Player** | ✅ Complete | Embedded player with timestamped note-taking and chapter navigation |
| 12 | **Analytics / Progress** | ✅ Complete | Learning stats, weekly study time charts (Recharts), subject progress bars, activity feed |
| 13 | **Study Materials** | ✅ Complete | Full Markdown editor with **LaTeX math rendering** (KaTeX), CRUD notes, topic tagging, search/filter |
| 14 | **Global Search** | ✅ Complete | Cross-module search across courses, materials, and videos with categorized results |
| 15 | **Settings** | ✅ Complete | Profile editing, theme (light/dark/auto), font size, notification preferences, privacy controls, account deletion |
| 16 | **App Shell & Navigation** | ✅ Complete | Collapsible sidebar with **drag-to-reorder** nav items (persisted), top bar with search, theme toggle, notification bell, profile dropdown |

### ✅ Role-Based Access

| Role | Capabilities |
|------|-------------|
| **Student** | Enroll in courses, take quizzes, watch videos, chat with AI, track progress, manage study notes |
| **Teacher / Admin** | All student features + create/edit courses, add assignments & materials, view enrolled students, manage content |

### ✅ Cross-Cutting Features

| Feature | Implementation |
|---------|---------------|
| **Dark / Light Theme** | CSS custom properties with `data-theme` attribute, system auto-detection, one-click toggle |
| **Responsive Design** | Mobile-friendly collapsible sidebar, adaptive layouts |
| **Toast Notifications** | Global success/error toasts via React Context (auto-dismiss 4.5s) |
| **Confirmation Dialogs** | Reusable modal for destructive actions (delete, unenroll) |
| **File Upload** | Drag-and-drop dropzone with size validation, upload/select modes |
| **Session Persistence** | JWT stored in localStorage, auto-restore on page reload, auto-logout on 401 |
| **Graceful Degradation** | Mock/fallback data when backend returns 404 — UI never breaks |
| **Drag-to-Reorder Sidebar** | Users can customize navigation order, persisted to localStorage |

---

## 📑 Table of Contents

- [Application Screenshots](#-application-screenshots)
- [What Has Been Developed](#-what-has-been-developed)
- [Tech Stack](#-tech-stack)
- [Project Architecture](#-project-architecture)
- [Directory Structure](#-directory-structure)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [Routing & Navigation](#-routing--navigation)
- [State Management](#-state-management)
- [API Layer](#-api-layer)
- [Component Guide](#-component-guide)
- [Pages Guide](#-pages-guide)
- [Styling System](#-styling-system)
- [Authentication Flow](#-authentication-flow)
- [Deployment](#-deployment)
- [Bundle File](#-bundle-file)

---

## 🛠 Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| **React** | `^19.2.0` | UI component library (latest with React Compiler support) |
| **TypeScript** | `~5.9.3` | Static type checking across the entire codebase |
| **Vite** | `^7.3.1` | Lightning-fast dev server and build tool |
| **React Router DOM** | `^7.13.0` | Client-side routing (App Router pattern) |
| **Zustand** | `^5.0.11` | Lightweight state management (auth, settings) |
| **Framer Motion** | `^12.34.0` | Declarative animations and page transitions |
| **Recharts** | `^3.7.0` | Data visualization charts (Progress, CodeLab graphs) |
| **Lucide React** | `^0.563.0` | Modern SVG icon library |
| **Axios** | `^1.13.5` | HTTP client (available, though `fetch` is primary) |
| **date-fns** | `^4.1.0` | Date formatting utilities |
| **KaTeX / react-katex** | `^0.17.0` / `^3.1.0` | LaTeX math rendering in study materials |
| **react-syntax-highlighter** | `^16.1.0` | Code syntax highlighting (Chat, CodeLab) |
| **clsx** | `^2.1.1` | Conditional CSS class merging |

### Dev Dependencies

| Tool | Purpose |
|---|---|
| `@vitejs/plugin-react` | React Fast Refresh + JSX transform for Vite |
| `eslint` + `typescript-eslint` | Linting & code quality |
| `eslint-plugin-react-hooks` | Enforce React hooks rules |
| `eslint-plugin-react-refresh` | Validate HMR-safe exports |
| `gh-pages` | GitHub Pages deployment |

---

## 🏗 Project Architecture

```
┌─────────────────────────────────────────────────────┐
│                    index.html                        │
│                    main.tsx                           │
│                      │                               │
│                    App.tsx                            │
│              ┌──────┼──────────┐                     │
│              │      │          │                     │
│         BrowserRouter          │                     │
│              │                 │                     │
│     ┌────────┴────────┐   GlobalChatbot              │
│     │                 │   (AIChatbot)                │
│  Public Routes    Protected Routes                   │
│  ┌──────────┐    ┌──────────────┐                    │
│  │ Landing  │    │  AppShell    │                    │
│  │ Login    │    │ ┌──────────┐ │                    │
│  │ Signup   │    │ │ Sidebar  │ │                    │
│  └──────────┘    │ │ Topbar   │ │                    │
│                  │ │ <Outlet> │ │                    │
│                  │ └──────────┘ │                    │
│                  └──────────────┘                    │
│                                                      │
│  State: Zustand (auth.store, settings.store)         │
│  API:   lib/api.ts (fetch + JWT Bearer tokens)       │
│  Types: types/index.ts                               │
└─────────────────────────────────────────────────────┘
```

---

## 📂 Directory Structure

```
frontend/
├── index.html                 # HTML entry point (loads Google Fonts: Outfit)
├── vite.config.ts             # Vite config (React plugin, base path for GH Pages)
├── package.json               # Dependencies & scripts
├── tsconfig.json              # TypeScript project references
├── tsconfig.app.json          # App-level TS config
├── tsconfig.node.json         # Node-level TS config (Vite)
├── eslint.config.js           # ESLint flat config
├── public/                    # Static assets (favicons, images)
├── dist/                      # Production build output
├── docs/                      # 📁 All frontend documentation, screenshots & code bundle
│
└── src/
    ├── main.tsx               # React entry — mounts <App /> into #root
    ├── App.tsx                # Root component: Router, Routes, Auth guards
    ├── App.css                # Minimal app-level CSS
    ├── index.css              # 🎨 Global design system (CSS variables, themes, utilities)
    │
    ├── types/
    │   └── index.ts           # All TypeScript interfaces (User, Course, Quiz, etc.)
    │
    ├── lib/
    │   ├── api.ts             # API client: fetch wrapper with JWT auth & error handling
    │   └── utils.ts           # Utility functions (cn, formatDate, getInitials, etc.)
    │
    ├── stores/
    │   ├── auth.store.ts      # Zustand auth store (login, signup, logout, restoreSession)
    │   └── settings.store.ts  # Zustand settings store (theme, fontSize, language)
    │
    ├── components/
    │   ├── AIChatbot.tsx/.css       # Floating AI chatbot widget (global)
    │   ├── ConfirmModal.tsx/.css    # Reusable confirmation dialog
    │   ├── EmptyState.tsx/.css      # Empty state placeholder component
    │   ├── FileDropzone.tsx/.css    # Drag-and-drop file upload component
    │   ├── GraphOutput.tsx          # Recharts frequency response graph
    │   ├── LogoIcon.tsx             # SVG logo component
    │   ├── Pagination.tsx/.css      # Pagination controls
    │   ├── Toast.tsx/.css           # Toast notification system (Context + Provider)
    │   │
    │   └── layout/
    │       ├── AppShell.tsx/.css    # Main layout shell (Sidebar + Topbar + Outlet)
    │       ├── Sidebar.tsx/.css     # Collapsible sidebar with drag-reorder nav
    │       └── Topbar.tsx/.css      # Top navigation bar (search, theme, profile)
    │
    ├── pages/
    │   ├── Landing.tsx/.css         # Public landing/marketing page
    │   ├── Dashboard.tsx/.css       # Student dashboard with stats & charts
    │   ├── Courses.tsx/.css         # Course catalog listing
    │   ├── CourseDetail.tsx/.css    # Single course view (modules, materials, people)
    │   ├── Chat.tsx/.css            # AI tutor chat page (conversations)
    │   ├── Quiz.tsx/.css            # Interactive quiz engine
    │   ├── CodeLab.tsx/.css         # Code editor with execution & graph output
    │   ├── Videos.tsx/.css          # Video library browser
    │   ├── VideoPlayer.tsx/.css     # Video player with timestamped notes
    │   ├── Progress.tsx/.css        # Learning analytics dashboard
    │   ├── StudyMaterial.tsx/.css   # Notes & study material manager (Markdown + LaTeX)
    │   ├── Search.tsx/.css          # Global search results page
    │   │
    │   ├── auth/
    │   │   ├── Auth.css             # Shared auth page styles
    │   │   ├── Login.tsx            # Login page with remember-me
    │   │   └── Signup.tsx           # Signup page with role selection (student/teacher)
    │   │
    │   └── settings/
    │       ├── Settings.css         # Settings page styles
    │       └── Settings.tsx         # User settings (profile, theme, notifications, privacy)
    │
    └── assets/
        └── react.svg              # React logo asset
```

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** ≥ 18.x  
- **npm** ≥ 9.x

### Installation

```bash
cd react-frontend/frontend
npm install
```

### Development Server

```bash
npm run dev
```

Opens at `http://localhost:5173/Saarthi_-Documentation/` (Vite default port with base path).

> The dev server uses `--host` flag to expose on the network for mobile testing.

### Production Build

```bash
npm run build
```

Output goes to `dist/`. The build runs TypeScript compilation (`tsc -b`) then Vite bundling.

### Preview Production Build

```bash
npm run preview
```

### Lint

```bash
npm run lint
```

---

## ⚙ Configuration

### Vite Config (`vite.config.ts`)

```ts
export default defineConfig({
  plugins: [react()],
  base: '/Saarthi_-Documentation/',  // GitHub Pages base path
})
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://<hostname>:8000/api` | Backend API base URL |

In development, the API URL auto-detects the hostname so it works across network devices.

### TypeScript Config

- **Strict mode** enabled
- **Path aliases**: None (relative imports used)
- **Target**: ES2020
- **Module**: ESNext with bundler resolution

---

## 🗺 Routing & Navigation

Defined in `App.tsx` using React Router v7:

| Route | Component | Auth | Description |
|---|---|---|---|
| `/` | `LandingPage` | Public | Marketing landing page |
| `/login` | `LoginPage` | Public only | Login form |
| `/signup` | `SignupPage` | Public only | Registration form |
| `/dashboard` | `DashboardPage` | Protected | Student overview dashboard |
| `/courses` | `CoursesPage` | Protected | Course catalog |
| `/courses/:id` | `CourseDetailPage` | Protected | Individual course view |
| `/chat` | `ChatPage` | Protected | AI tutor conversations |
| `/quiz` | `QuizPage` | Protected | Quiz engine |
| `/code-lab` | `CodeLabPage` | Protected | Interactive code editor |
| `/videos` | `VideosPage` | Protected | Video library |
| `/videos/:id` | `VideoPlayerPage` | Protected | Video player |
| `/progress` | `ProgressPage` | Protected | Analytics dashboard |
| `/study-material` | `StudyMaterialPage` | Protected | Notes manager |
| `/search` | `SearchPage` | Protected | Global search |
| `/settings` | `SettingsPage` | Protected | User preferences |

### Route Guards

- **`ProtectedLayout`** — Wraps all authenticated routes; redirects to `/login` if unauthenticated.
- **`PublicOnly`** — Wraps login/signup; redirects to `/dashboard` if already authenticated.
- **`GlobalChatbot`** — Renders `AIChatbot` on all pages except login/signup.

---

## 🗄 State Management

### Zustand Stores

#### `auth.store.ts`

| Property | Type | Description |
|---|---|---|
| `user` | `User \| null` | Current authenticated user |
| `token` | `string \| null` | JWT access token |
| `isAuthenticated` | `boolean` | Auth status |
| `isLoading` | `boolean` | Login/signup in progress |
| `isRestoring` | `boolean` | Session restoration in progress |

**Actions**: `login()`, `signup()`, `logout()`, `restoreSession()`, `clearSession()`

- Uses `zustand/persist` middleware with `localStorage` key: `saarthi-auth`
- Only persists: `user`, `token`, `isAuthenticated`
- On app load, `restoreSession()` validates the stored token via `/auth/profile`

#### `settings.store.ts`

| Property | Type | Default | Description |
|---|---|---|---|
| `theme` | `'light' \| 'dark' \| 'auto'` | `'light'` | Color theme |
| `fontSize` | `'small' \| 'medium' \| 'large'` | `'medium'` | Base font size |
| `language` | `string` | `'en'` | UI language |

- Persisted to `localStorage` key: `saarthi-settings`
- Applies theme via `data-theme` attribute on `<html>`
- Listens for system `prefers-color-scheme` changes when `auto` is selected

---

## 🌐 API Layer

### `lib/api.ts`

The API client is a thin wrapper around `fetch`:

```ts
api.get<T>(path, params?)     // GET with query params
api.post<T>(path, body?)      // POST with JSON body
api.patch<T>(path, body)      // PATCH with JSON body
api.delete(path)              // DELETE
```

**Key features:**
- **JWT Auth**: Reads token from `localStorage('saarthi-auth')`, sends as `Authorization: Bearer <token>`
- **Auto-logout**: On 401 response, clears auth state and dispatches `saarthi:auth-expired` event
- **Fallback data**: Returns mock data for 404 on progress/enrollment endpoints (graceful degradation)
- **204 handling**: Safely returns `undefined` for no-content responses

### Additional API utilities:

| Function | Purpose |
|---|---|
| `uploadFile(file)` | Multipart file upload via `/courses/upload` |
| `getUploadFullUrl(path)` | Convert relative upload path to absolute URL |
| `getMaterialFileUrl(courseId, materialId)` | Generate URL for viewing course materials |
| `attemptRefresh()` | Attempt token refresh (single-flight) |

### API Response Types

All response interfaces are exported from `lib/api.ts`:
- `PaginatedResponse<T>` — Standard paginated list
- `CourseResponse`, `EnrollmentWithCourseResponse`
- `AssignmentResponse`, `MaterialResponse`, `StreamItemResponse`
- `ConversationResponse`, `ChatMessageItemResponse`, `SendMessageResponse`
- `VideoResponse`, `VideoNoteResponse`, `NoteResponse`
- `SearchResponse`, `ProgressResponse`

---

## 🧩 Component Guide

### Layout Components

| Component | File | Description |
|---|---|---|
| **AppShell** | `components/layout/AppShell.tsx` | Main app layout — renders `Sidebar` + `Topbar` + `<Outlet>` |
| **Sidebar** | `components/layout/Sidebar.tsx` | Collapsible navigation with **drag-to-reorder** items. Persists order to `localStorage`. Shows streak card and Settings link. |
| **Topbar** | `components/layout/Topbar.tsx` | Top bar with global search, theme toggle (Sun/Moon), notification bell, and profile dropdown with logout. |

### Shared UI Components

| Component | File | Description |
|---|---|---|
| **AIChatbot** | `components/AIChatbot.tsx` | Floating chat widget (FAB button) — connects to `/chat/message` API. Shows suggested questions, renders markdown-like formatting with code blocks. |
| **Toast** | `components/Toast.tsx` | Toast notification system using React Context. `<ToastProvider>` wraps the app; use `useToast()` hook to show success/error toasts. Auto-dismisses after 4.5s. |
| **ConfirmModal** | `components/ConfirmModal.tsx` | Reusable confirmation dialog with danger/primary variants. Supports Escape key to close. |
| **EmptyState** | `components/EmptyState.tsx` | Empty state placeholder with icon, title, description, and optional action button. |
| **FileDropzone** | `components/FileDropzone.tsx` | Drag-and-drop file upload with two modes: `'upload'` (immediate upload) and `'select'` (parent handles upload). Shows file size validation and progress. |
| **GraphOutput** | `components/GraphOutput.tsx` | Recharts line chart for frequency response visualization (used in CodeLab). |
| **Pagination** | `components/Pagination.tsx` | Page navigation with Prev/Next buttons. Shows page X of Y with total count. |
| **LogoIcon** | `components/LogoIcon.tsx` | Custom SVG logo for Saarthi.ai brand. |

---

## 📄 Pages Guide

### Landing Page (`pages/Landing.tsx`)
The public marketing page. Features hero section, feature cards, statistics, and call-to-action buttons. Not behind auth.

### Dashboard (`pages/Dashboard.tsx`)
Student home showing:
- Stats cards (courses enrolled, pending assignments, quiz score, study time)
- Enrolled courses with progress bars
- Upcoming deadlines list
- Weekly study activity chart (Recharts)

### Courses (`pages/Courses.tsx`)
Course catalog with:
- Search and category filtering
- Course cards with emoji thumbnails
- Enrollment management
- Pagination

### Course Detail (`pages/CourseDetail.tsx`)
Tabbed course view with:
- **Stream** — Announcements and activity feed
- **Coursework** — Assignments with file attachments, due dates, submission
- **People** — Enrolled students with progress
- **Materials** — Course files (upload/download/view PDFs)
- Instructor tools for creating assignments and materials

### Chat (`pages/Chat.tsx`)
Conversational AI tutor:
- Multi-conversation support
- Create/rename/delete conversations
- Full message history
- Markdown rendering with code blocks

### Quiz (`pages/Quiz.tsx`)
Interactive quiz system:
- Topic-based quiz generation
- Timed quiz sessions
- Multiple choice with instant feedback
- Score summary and explanations

### CodeLab (`pages/CodeLab.tsx`)
Browser-based code editor:
- Syntax-highlighted editor with line numbers
- Multi-language support (Python, JavaScript, C++, Java)
- Code execution via API
- Graph output visualization
- Code templates

### Videos (`pages/Videos.tsx`)
Video library browser:
- Video cards with thumbnails
- Category filtering
- Search functionality

### VideoPlayer (`pages/VideoPlayer.tsx`)
Video playback with:
- Embedded video player
- Timestamped notes (add notes at current playback time)
- Chapter navigation

### Progress (`pages/Progress.tsx`)
Learning analytics:
- Progress stats overview
- Weekly study time bar chart
- Subject progress bars
- Recent activity feed

### Study Material (`pages/StudyMaterial.tsx`)
Notes and study material manager:
- Full-featured Markdown editor
- **LaTeX math rendering** (KaTeX)
- Create, edit, delete notes
- Topic categorization
- Search and filter

### Search (`pages/Search.tsx`)
Global search across courses, materials, and videos with categorized results.

### Settings (`pages/settings/Settings.tsx`)
Multi-section settings page:
- **Profile**: Name, email, institute, avatar
- **Appearance**: Theme (light/dark/auto), font size
- **Notifications**: Toggle various notification types
- **Privacy**: Profile visibility, progress sharing
- **Account**: Delete account (with confirmation)

### Auth Pages (`pages/auth/Login.tsx`, `Signup.tsx`)
- Login with email/password + remember me
- Signup with name, email, password, institute, role selection (student/teacher)
- Form validation and error handling
- Auto-redirect after auth

---

## 🎨 Styling System

### CSS Architecture

The project uses **vanilla CSS** with **CSS custom properties** (variables) for theming:

#### Global Design System (`src/index.css`)

```css
:root {
  /* Color palette */
  --primary: #2563EB;
  --primary-dark: #1D4ED8;
  --accent: #8B5CF6;
  --background: #F8FAFC;
  --foreground: #0F172A;
  --card-bg: #FFFFFF;
  --border: #E2E8F0;
  /* ... and many more */
}

[data-theme="dark"] {
  --background: #0F172A;
  --foreground: #F1F5F9;
  --card-bg: #1E293B;
  --border: #334155;
  /* ... dark overrides */
}
```

#### Styling Conventions

- Each component/page has a co-located `.css` file (e.g., `Dashboard.tsx` + `Dashboard.css`)
- CSS class names follow **BEM-like** naming: `.sidebar-link`, `.topbar-search-input`
- No CSS-in-JS or Tailwind — pure vanilla CSS for maximum control
- The `AIChatbot` component uses **inline styles** for the chat window (design decision for portability)
- Google Font: **Outfit** (weights 400–900) loaded via `index.html`

### Theming

Themes are toggled via:
1. Settings store `setTheme()` updates `data-theme` attribute
2. Topbar provides a quick Sun/Moon toggle
3. `auto` mode respects `prefers-color-scheme` media query

### Font Sizes

Applied globally via `document.documentElement.style.fontSize`:
- Small: `14px`
- Medium: `16px` (default)
- Large: `18px`

---

## 🔐 Authentication Flow

```
┌──────────┐     POST /auth/signin      ┌──────────┐
│  Login   │ ──────────────────────────▶ │ Backend  │
│  Page    │ ◀────────────────────────── │ API      │
│          │     { user, token }         │          │
└──────────┘                             └──────────┘
     │
     │ Zustand persist → localStorage('saarthi-auth')
     │
     ▼
┌──────────────────────────────────────────┐
│  App.tsx: restoreSession() on mount      │
│  → GET /auth/profile (Bearer token)      │
│  → Success: set isAuthenticated = true   │
│  → Failure: clear session                │
└──────────────────────────────────────────┘
     │
     │ 401 Response anywhere
     ▼
┌──────────────────────────────────────────┐
│  api.ts: clearPersistedAuthState()       │
│  → Remove localStorage                   │
│  → Dispatch 'saarthi:auth-expired' event │
│  → App.tsx listener calls clearSession() │
│  → Redirect to /login                    │
└──────────────────────────────────────────┘
```

---

## 🚢 Deployment

### GitHub Pages

The project is configured for GitHub Pages deployment:

```bash
npm run deploy
```

This runs:
1. `npm run build` (predeploy hook)
2. `gh-pages -d dist` (publishes dist/ folder)

**Base URL**: `https://raghavendrak04.github.io/Saarthi_-Documentation/`

### Custom Deployment

For other platforms (Vercel, Netlify, etc.):

1. Set `VITE_API_URL` environment variable to your backend URL
2. Update `base` in `vite.config.ts` to `/` (or your subdirectory)
3. Update `basename` in `App.tsx` `<BrowserRouter>` accordingly
4. Run `npm run build` and serve the `dist/` directory

---

## 📄 Bundle File

The file **`FRONTEND_CODEBASE.txt`** contains all 58 source files (`.tsx`, `.ts`, `.css`) concatenated into a single file for easy reference, code review, or AI analysis.

**Contents include:**
- Configuration files (package.json, vite.config.ts, tsconfig, index.html)
- All TypeScript/TSX source files
- All CSS stylesheets
- Table of contents at the top

To regenerate:
```powershell
# PowerShell command to rebuild the bundle
$srcDir = ".\src"
$files = Get-ChildItem -Path $srcDir -Recurse -Include *.tsx,*.ts,*.css | Sort-Object FullName
# ... (see FRONTEND_CODEBASE.txt header for full script)
```

---

## 📝 Key Design Decisions

1. **Zustand over Redux** — Minimal boilerplate for a small number of global stores (auth + settings only). Component-level state uses React `useState`.

2. **Vanilla CSS over Tailwind** — Each component has a dedicated CSS file. This keeps styles explicit, debuggable, and avoids utility class bloat.

3. **Fetch over Axios** — The `api.ts` module wraps native `fetch` with auth headers and error handling. Axios is available but unused as the primary client.

4. **JWT Bearer Tokens** — Stored in Zustand/localStorage (not cookies). Sent via `Authorization` header. Auto-clears on 401.

5. **Graceful Degradation** — API client returns mock/fallback data for certain 404s so the UI always renders something meaningful, even if the backend is incomplete.

6. **Co-located Styles** — Each page and component has its `.css` right next to its `.tsx` file, making it easy to find and maintain styles.

---

*Built with ❤️ for Saarthi.ai*
