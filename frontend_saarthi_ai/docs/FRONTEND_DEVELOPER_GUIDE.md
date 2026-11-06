# Saarthi.ai Frontend Developer Guide

## 📌 Project Overview
The **Saarthi.ai** frontend is an interactive, React-based web application that serves as an intelligent learning platform. It is designed to act as an "AI Tutor" to help students master technical subjects (like Digital Signal Processing, Computer Science, etc.) by combining structured learning modules with real-time AI assistance, dynamic code execution, and rich note-taking capabilities.

The platform relies on a **Vanilla CSS design system**, prioritizing clean, bespoke styling utilizing CSS Variables over utility frameworks like Tailwind. It leverages modern React patterns (hooks, context, and external stores) for a highly performant and scalable architecture.

---

## 🏗️ Technical Architecture & Stack

- **Core Framework**: React 19 with Vite (for fast HMR and optimized building).
- **Routing**: React Router v7 (`BrowserRouter` configured with basename for GitHub Pages).
- **State Management**: Zustand (lightweight, hook-based global state for auth, settings, and UI toggles).
- **Styling**: Pure Vanilla CSS (`index.css` acts as the root Design System). No Tailwind or Bootstrap.
- **Data Fetching & API**: Axios (configured in `lib/api.ts` with interceptors for JWT injection and automated error handling).
- **Markdown & Math Processing**: 
  - `react-syntax-highlighter` for the Code Lab and Chat block rendering.
  - `react-katex` / `KaTeX` for beautifully rendering complex math equations (like the Z-Transform) in the Study Materials section.
- **Data Visualization**: `Recharts` for plotting dynamic output generated from the Code Lab execution (e.g., Butterworth filter frequency responses).

---

## 📁 Project Structure

```text
react-frontend/frontend/
├── public/                 # Static assets (images, static JSON notes)
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── layout/         # AppShell, Sidebar, Topbar (Core layout wrappers)
│   │   ├── AIChatbot.tsx   # Global floating AI Chat widget
│   │   ├── GraphOutput.tsx # Recharts wrapper for Code Lab output
│   │   └── ...
│   ├── lib/
│   │   └── api.ts          # Centralized Axios API client & typings
│   ├── pages/              # Route-level components
│   │   ├── auth/           # Login & Signup flows
│   │   ├── CodeLab.tsx     # In-browser Python/Matlab execution environment
│   │   ├── StudyMaterial.tsx # Markdown/KaTeX reader with dynamic TOC sidebar
│   │   ├── Dashboard.tsx   # User analytics and progress
│   │   └── ...
│   ├── stores/             # Zustand state stores
│   │   ├── auth.store.ts   # JWT and user session management
│   │   └── settings.store.ts # Dark mode and typography settings
│   ├── App.tsx             # Route definitions and layout mapping
│   └── index.css           # Global Design System (CSS tokens, dark mode)
```

---

## 🔑 Key Architectural Decisions

### 1. The Design System (`index.css`)
Rather than relying on Tailwind, the app uses a strict CSS Variable system. 
- Colors are defined semantically (`--primary`, `--card-bg`, `--foreground`).
- **Dark Mode Implementation**: Instead of adding `.dark` classes to every element, the app uses a `[data-theme='dark']` attribute on the `<html>` or `<body>` tag. When active, it reassigns the base CSS variables to their dark equivalents. All components automatically inherit these inverted tokens, ensuring smooth and flawless transitions between themes.

### 2. State Management (`Zustand`)
We use Zustand over Redux/Context for global state because it avoids provider wrappers and re-render hell.
- **Auth Store**: Handles token persistence in `localStorage`, decoding JWT payloads, and triggering global logout events.
- **Settings Store**: Handles theme preferences (Light/Dark) and font size scaling.

### 3. Study Materials Reader (`StudyMaterial.tsx`)
A complex component designed to parse Markdown-like structures.
- It scans raw text for headers, paragraphs, lists, and LaTeX block markers.
- **Math Rendering**: Extracts elements enclosed in `$$` or `\\[ \\]` and passes them to `react-katex`. 
- **Dark Mode Fixes**: Explicit CSS mappings ensure that generated math blocks (`.sm-math-block`) contrast perfectly against dark backgrounds.

### 4. Dynamic Code Lab (`CodeLab.tsx`)
Allows users to write code (like Python DSP algorithms) and see output.
- **API Integration**: Sends code to the backend, which communicates with Judge0 or a similar execution engine.
- **Dynamic Graphing**: Code can `print()` specific JSON structures (e.g., `<plot-data>[...]</plot-data>`). The frontend parses this stdout and intercepts it, routing the data directly into a Recharts `<LineChart>` instead of just printing raw console text.

---

## 🚀 Deployment Pipeline

The project is configured for continuous deployment on GitHub Pages.
1. **Routing Setup**: `vite.config.ts` defines `base: '/Saarthi_-Documentation/'`, and `App.tsx` defines `<BrowserRouter basename="/Saarthi_-Documentation">`. This ensures asset paths don't 404 when served from a subdirectory.
2. **Build Script**: `npm run build` compiles TS and bundles via Vite.
3. **Deploy Script**: `npm run deploy` uses the `gh-pages` package to automatically push the `dist/` folder to the `gh-pages` branch on GitHub.

## 🔮 Next Steps & Roadmap
- Implement Quiz backend synchronization to store scores persistently.
- Migrate static JSON notes in the `public/` directory to the MongoDB backend.
- Enhance the AI Chatbot context awareness by feeding it the exact active page content.
