# 🎨 FRONTEND DEVELOPMENT - Priority Build Plan

## Overview
Building a **robust, modern, premium frontend** for Saarthi.ai based on planning documentation.

---

## 🎯 Design Principles (from UX Research)

### Visual Excellence
- **Colors**: Emerald primary (#10B981), Violet secondary (#8B5CF6)
- **Typography**: Inter font family (clean, modern)
- **Dark Mode**: True black backgrounds with vibrant accents
- **Animations**: Smooth transitions, micro-interactions
- **Components**: Glassmorphism, subtle shadows, rounded corners

### User Experience
- **Intuitive Navigation**: Clear information architecture
- **Responsive Design**: Mobile-first approach
- **Accessibility**: WCAG 2.1 AA compliance
- **Performance**: Fast page loads, optimized assets

---

## 📦 Frontend Dependencies to Add

```json
{
  "dependencies": {
    // State Management
    "zustand": "^4.5.0",
    "@tanstack/react-query": "^5.17.0",
    
    // UI Components
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-tabs": "^1.0.4",
    "@radix-ui/react-toast": "^1.1.5",
    "@radix-ui/react-popover": "^1.0.7",
    "lucide-react": "^0.309.0",
    
    // Code Editor
    "@monaco-editor/react": "^4.6.0",
    
    // Charts & Visualizations
    "recharts": "^2.10.3",
    
    // Video Player
    "react-player": "^2.14.1",
    
    // Markdown & Code Highlighting
    "react-markdown": "^9.0.1",
    "react-syntax-highlighter": "^15.5.0",
    
    // Math Rendering
    "katex": "^0.16.9",
    "react-katex": "^3.0.1",
    
    // WebSocket
    "socket.io-client": "^4.7.2",
    
    // HTTP Client
    "axios": "^1.6.5",
    
    // Animations
    "framer-motion": "^10.18.0",
    
    // Form Handling
    "react-hook-form": "^7.49.3",
    "zod": "^3.22.4",
    "@hookform/resolvers": "^3.3.4",
    
    // Utilities
    "clsx": "^2.1.0",
    "date-fns": "^3.0.6",
    "class-variance-authority": "^0.7.0"
  }
}
```

---

## 🏗️ Frontend Structure

```
frontend/src/
├── app/
│   ├── layout.tsx                    # Root layout with providers
│   ├── page.tsx                      # Landing/Home page
│   ├── globals.css                   # Global styles
│   │
│   ├── (auth)/
│   │   ├── layout.tsx                # Auth layout
│   │   ├── login/page.tsx            ✅ EXISTS
│   │   └── signup/page.tsx           ✅ EXISTS
│   │
│   ├── (app)/                        # Protected routes
│   │   ├── layout.tsx                # App layout with sidebar
│   │   │
│   │   ├── dashboard/
│   │   │   └── page.tsx              # Main dashboard
│   │   │
│   │   ├── chat/
│   │   │   └── page.tsx              # AI Chatbot interface
│   │   │
│   │   ├── courses/
│   │   │   ├── page.tsx              # Course catalog
│   │   │   └── [code]/
│   │   │       └── page.tsx          # Course details
│   │   │
│   │   ├── videos/
│   │   │   ├── page.tsx              # Video library
│   │   │   └── [id]/page.tsx         # Video player
│   │   │
│   │   ├── code-lab/
│   │   │   └── page.tsx              # Coding environment
│   │   │
│   │   ├── quiz/
│   │   │   ├── page.tsx              # Quiz list
│   │   │   ├── [id]/page.tsx         # Take quiz
│   │   │   └── results/[id]/page.tsx # Quiz results
│   │   │
│   │   ├── notes/
│   │   │   └── page.tsx              # Study resources
│   │   │
│   │   └── progress/
│   │       └── page.tsx              # Analytics dashboard
│   │
├── components/
│   ├── ui/                           # Base UI components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── badge.tsx
│   │   ├── dialog.tsx
│   │   ├── dropdown.tsx
│   │   ├── tabs.tsx
│   │   └── ...
│   │
│   ├── layout/                       # Layout components
│   │   ├── Sidebar.tsx
│   │   ├── Topbar.tsx
│   │   ├── Footer.tsx
│   │   └── AppShell.tsx
│   │
│   ├── chat/                         # Chat components
│   │   ├── ChatInterface.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageItem.tsx
│   │   ├── ChatInput.tsx
│   │   ├── SourceCitation.tsx
│   │   └── SuggestedQuestions.tsx
│   │
│   ├── code/                         # Code editor components
│   │   ├── CodeEditor.tsx
│   │   ├── LanguageSelector.tsx
│   │   ├── ConsoleOutput.tsx
│   │   └── TestCasePanel.tsx
│   │
│   ├── video/                        # Video player components
│   │   ├── VideoPlayer.tsx
│   │   ├── VideoControls.tsx
│   │   ├── AnnotationOverlay.tsx
│   │   └── NotePanel.tsx
│   │
│   ├── quiz/                         # Quiz components
│   │   ├── QuizCard.tsx
│   │   ├── QuestionDisplay.tsx
│   │   ├── AnswerOptions.tsx
│   │   ├── QuizTimer.tsx
│   │   └── ResultsSummary.tsx
│   │
│   └── dashboard/                    # Dashboard components
│       ├── StatCard.tsx
│       ├── ProgressChart.tsx
│       ├── StudyStreak.tsx
│       ├── RecentActivity.tsx
│       └── RecommendedContent.tsx
│   
├── lib/
│   ├── api.ts                        # API client
│   ├── websocket.ts                  # WebSocket client
│   └── utils.ts                      # Utilities
│
├── hooks/
│   ├── useAuth.ts                    # Auth hook
│   ├── useChat.ts                    # Chat hook
│   ├── useProgress.ts                # Progress tracking
│   └── useWebSocket.ts               # WebSocket hook
│
├── stores/
│   ├── auth.store.ts                 # Auth state
│   ├── chat.store.ts                 # Chat state
│   └── progress.store.ts             # Progress state
│
└── types/
    └── index.ts                      # TypeScript types
```

---

##  Premium UI Component Examples

### 1. Stat Card (Dashboard)
```tsx
<Card className="bg-gradient-to-br from-emerald-500 to-emerald-600 text-white">
  <CardContent className="p-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-emerald-100 text-sm font-medium">Study Streak</p>
        <h3 className="text-4xl font-bold mt-2">12 Days</h3>
        <p className="text-emerald-100 text-xs mt-1">Keep it up! 🔥</p>
      </div>
      <div className="p-4 bg-white/20 rounded-full">
        <FlameIcon className="w-8 h-8" />
      </div>
    </div>
  </CardContent>
</Card>
```

### 2. Chat Message (AI Chatbot)
```tsx
<div className="flex gap-3 p-4 hover:bg-muted/50 transition-colors">
  <Avatar className="w-10 h-10">
    <AvatarImage src="/ai-avatar.png" />
    <AvatarFallback>AI</AvatarFallback>
  </Avatar>
  <div className="flex-1">
    <div className="prose prose-sm max-w-none">
      <ReactMarkdown>{message.content}</ReactMarkdown>
    </div>
    {message.sources && (
      <div className="mt-2 flex gap-2">
        {message.sources.map(source => (
          <SourceBadge key={source.id} source={source} />
        ))}
      </div>
    )}
  </div>
</div>
```

### 3. Video Card (Video Library)
```tsx
<Card className="group cursor-pointer overflow-hidden hover:shadow-lg transition-all">
  <div className="relative aspect-video">
    <Image 
      src={video.thumbnail} 
      alt={video.title}
      fill
      className="object-cover group-hover:scale-105 transition-transform"
    />
    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
      <PlayCircleIcon className="w-16 h-16 text-white" />
    </div>
    <Badge className="absolute top-2 right-2">{video.duration}</Badge>
  </div>
  <CardContent className="p-4">
    <h4 className="font-semibold line-clamp-2">{video.title}</h4>
    <p className="text-sm text-muted-foreground mt-1">{video.courseCode}</p>
    <Progress value={video.progress} className="mt-3" />
  </CardContent>
</Card>
```

---

## 🎨 Color System

```css
/* globals.css */
@layer base {
  :root {
    /* Light Mode */
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 142.1 76.2% 36.3%;          /* Emerald */
    --primary-foreground: 355.7 100% 97.3%;
    --secondary: 262.1 83.3% 57.8%;        /* Violet */
    --secondary-foreground: 210 40% 98%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --destructive: 0 84.2% 60.2%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 142.1 76.2% 36.3%;
    --radius: 0.5rem;
  }

  .dark {
    /* Dark Mode */
    --background: 0 0% 0%;                 /* True black */
    --foreground: 210 40% 98%;
    --primary: 142.1 70.6% 45.3%;          /* Brighter emerald */
    --primary-foreground: 144.9 80.4% 10%;
    --secondary: 262.1 83.3% 57.8%;        /* Violet */
    --secondary-foreground: 210 40% 98%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --destructive: 0 62.8% 30.6%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 142.1 70.6% 45.3%;
  }
}
```

---

## 🚀 Development Priority

### PHASE 1: Foundation (Days 1-2)
1. ✅ Update package.json with all dependencies
2. ✅ Install dependencies
3. ✅ Set up Tailwind config with custom colors
4. ✅ Create base UI components (button, card, input, etc.)
5. ✅ Build layout components (Sidebar, Topbar)

### PHASE 2: Dashboard (Days 3-4)
1. ✅ Rebuild dashboard with stat cards
2. ✅ Add progress charts
3. ✅ Study streak widget
4. ✅ Recent activity timeline
5. ✅ Recommended content carousel

### PHASE 3: AI Chatbot (Days 5-7)
1. ✅ Chat interface with message history
2. ✅ WebSocket integration for streaming
3. ✅ Code block rendering with syntax highlighting
4. ✅ Math equation rendering (KaTeX)
5. ✅ Source citations display

### PHASE 4: Learning Features (Days 8-12)
1. ✅ Course catalog and details
2. ✅ Video player with controls
3. ✅ Code editor (Monaco)
4. ✅ Quiz interface
5. ✅ Progress analytics

### PHASE 5: Polish & Testing (Days 13-14)
1. ✅ Animations and transitions
2. ✅ Responsiveness testing
3. ✅ Performance optimization
4. ✅ Accessibility audit

---

## 📱 Responsive Design Breakpoints

```typescript
// tailwind.config.ts
screens: {
  'sm': '640px',   // Mobile landscape
  'md': '768px',   // Tablet
  'lg': '1024px',  // Desktop
  'xl': '1280px',  // Large desktop
  '2xl': '1536px', // Extra large
}
```

---

## ♿ Accessibility Checklist

- [ ] All interactive elements keyboard accessible
- [ ] Focus indicators visible
- [ ] ARIA labels for screen readers
- [ ] Color contrast ratios meet WCAG AA
- [ ] Alt text for all images
- [ ] Form validation messages
- [ ] Skip navigation links

---

**Next Steps**: Start building the UI components and pages systematically!
