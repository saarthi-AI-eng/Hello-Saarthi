# Figma Design Brief - Saarthi.ai

## Project Overview
**Platform Name:** Saarthi.ai (सारथी = Guide/Charioteer)  
**Project Type:** Proof of Concept - AI Tutor Teaching Assistant  
**Target Audience:** Students (College/University level)  
**Design Philosophy:** Simple, Clean, Minimalist  
**Primary Goal:** Provide an intelligent learning companion that helps students learn faster, prepare for exams, and master technical subjects

---

## Design Principles

### 1. **Minimalism First**
- Clean, uncluttered interfaces
- Ample white space
- Focus on content, not decoration
- Progressive disclosure of features

### 2. **Student-Centric**
- Reduce cognitive load
- Clear visual hierarchy
- Intuitive navigation
- Mobile-first responsive design

### 3. **Trust & Clarity**
- Source attribution visible
- Clear AI vs human-generated content indicators
- Transparent error states
- Confidence indicators for AI responses

---

## Color Palette

### Primary Colors
```
Primary Blue:     #2563EB (Learning, Trust, Focus)
Primary Dark:     #1E40AF (Depth, Authority)
Primary Light:    #DBEAFE (Backgrounds, Highlights)
```

### Secondary Colors
```
Success Green:    #10B981 (Correct answers, Progress)
Warning Amber:    #F59E0B (Hints, Cautions)
Error Red:        #EF4444 (Incorrect, Alerts)
Accent Purple:    #8B5CF6 (Premium features, AI)
```

### Neutral Palette
```
Text Primary:     #1F2937 (Main content)
Text Secondary:   #6B7280 (Descriptions, metadata)
Text Tertiary:    #9CA3AF (Disabled, placeholders)
Background:       #FFFFFF (Main background)
Surface:          #F9FAFB (Cards, elevated surfaces)
Border:           #E5E7EB (Dividers, borders)
```

### Dark Mode
```
Background Dark:  #111827
Surface Dark:     #1F2937
Text Dark:        #F9FAFB
Border Dark:      #374151
```

---

## Typography

### Font Family
- **Primary:** Inter (Clean, modern, excellent readability)
- **Code/Monospace:** JetBrains Mono (Code snippets)
- **Handwritten Notes:** Caveat or Kalam (For digitized handwritten content)

### Type Scale
```
H1 (Page Titles):        32px / 2rem - Bold
H2 (Section Headers):    24px / 1.5rem - Semibold
H3 (Subsections):        20px / 1.25rem - Semibold
H4 (Card Titles):        18px / 1.125rem - Medium
Body Large:              16px / 1rem - Regular
Body:                    14px / 0.875rem - Regular
Small:                   12px / 0.75rem - Regular
Caption:                 11px / 0.6875rem - Regular
```

### Line Heights
- Headings: 1.2
- Body text: 1.6
- Code blocks: 1.5

---

## Component Library

### 1. Navigation Components

#### Top Navigation Bar
- Logo (left)
- Search bar (center)
- User profile, notifications, settings (right)
- Height: 64px
- Shadow: subtle (0px 1px 3px rgba(0,0,0,0.1))

#### Sidebar Navigation
- Width: 280px (expanded), 72px (collapsed)
- Categories:
  - Dashboard
  - AI Chat
  - Code Lab
  - Video Library
  - Notes & Resources
  - Practice Quiz
  - Progress Tracker
  - Settings

### 2. Cards

#### Standard Card
- Border radius: 12px
- Padding: 24px
- Shadow: 0px 2px 8px rgba(0,0,0,0.08)
- Hover: Lift effect (shadow increase)

#### Video Card
- 16:9 aspect ratio thumbnail
- Progress bar at bottom
- Duration badge
- Metadata: views, date

#### Note Card
- Preview snippet (3-4 lines)
- Tags
- Source indicator
- Download/bookmark actions

### 3. Buttons

#### Primary Button
- Background: Primary Blue
- Text: White
- Height: 40px (default), 48px (large), 32px (small)
- Border radius: 8px
- Hover: Darken 10%
- Active: Darken 15%

#### Secondary Button
- Border: 2px solid Primary Blue
- Text: Primary Blue
- Background: Transparent
- Hover: Light blue background

#### Icon Button
- Size: 40x40px
- Border radius: 50% (circular)
- Hover: Background color change

### 4. Form Elements

#### Input Fields
- Height: 44px
- Border: 1px solid Border color
- Border radius: 8px
- Focus: Primary blue border, shadow glow
- Error state: Red border
- Success state: Green border

#### Dropdown/Select
- Same styling as input
- Chevron icon (right)
- Dropdown shadow: elevated

#### Checkbox/Radio
- Size: 20x20px
- Border radius: 4px (checkbox), 50% (radio)
- Checked: Primary blue fill

### 5. AI Chatbot Interface

#### Chat Container
- Max width: 800px
- Centered layout
- Sticky input at bottom

#### Message Bubbles
- **User messages:**
  - Background: Primary Blue
  - Text: White
  - Align: Right
  - Max width: 70%
  - Border radius: 16px 16px 4px 16px

- **AI messages:**
  - Background: Surface color
  - Text: Primary text
  - Align: Left
  - Max width: 70%
  - Border radius: 16px 16px 16px 4px
  - AI avatar icon

#### Special Features
- Code syntax highlighting
- Math equation rendering (LaTeX)
- Source citations (expandable)
- "Copy" button for code
- Regenerate response option
- Thumbs up/down feedback

#### Input Box
- Multi-line support
- Auto-expand (max 5 lines)
- Send button (icon)
- Attachment option (images, files)
- Suggested prompts (chips below)

### 6. Code Development Environment

#### Code Editor
- Split view: Editor (left) | Output/Console (right)
- Syntax highlighting
- Line numbers
- Language selector dropdown
- Run button (prominent, green)
- Theme toggle (light/dark)
- Font size controls
- Auto-complete suggestions

#### Console/Output
- Clear distinction from editor
- Tabs: Output | Console | Test Cases
- Error highlighting
- Clear button

### 7. Video Player

#### Custom Controls
- Play/Pause
- Timeline scrubber with chapter markers
- Speed control (0.5x, 1x, 1.25x, 1.5x, 2x)
- Quality settings
- Fullscreen
- Picture-in-picture
- Bookmarks/Notes integration

#### Annotations
- Timestamped questions appear as overlays
- Quiz questions pause video
- Note-taking side panel (toggleable)

### 8. Notes & Resources

#### Filter Bar
- Subject dropdown
- Topic tags (multi-select chips)
- Sort: Recent, Popular, A-Z
- View toggle: Grid | List

#### Note Viewer
- Title
- Metadata: Subject, date, source
- Download/Print options
- Related resources sidebar
- Quick actions: Bookmark, Share

### 9. Quiz Interface

#### Question Card
- Question number indicator
- Progress bar (top)
- Question text (large, readable)
- Answer options (radio buttons or checkboxes)
- Hint button (optional)
- Previous/Next buttons
- Submit button

#### Results Screen
- Score (large, centered)
- Performance chart
- Correct/Incorrect breakdown
- Review answers button
- Retry option
- Recommendations based on performance

### 10. Progress Dashboard

#### Widgets
- **Study Streak:** Calendar heatmap
- **Topics Mastered:** Progress circles
- **Recent Activity:** Timeline
- **Upcoming Quizzes:** Card list
- **Weak Areas:** Bar chart with recommendations

---

## Page Layouts

### 1. Dashboard (Home)
```
┌─────────────────────────────────────────┐
│  Top Navigation                         │
├───────┬─────────────────────────────────┤
│       │  Welcome Back, [Name]           │
│       │  ┌─────────┐  ┌─────────┐       │
│  Side │  │ Streak  │  │ Topics  │       │
│  Nav  │  │  Card   │  │  Card   │       │
│       │  └─────────┘  └─────────┘       │
│       │                                  │
│       │  Recent Activity                 │
│       │  ┌───────────────────────────┐   │
│       │  │ Activity Timeline         │   │
│       │  └───────────────────────────┘   │
│       │                                  │
│       │  Recommended for You             │
│       │  [Video Cards...]                │
└───────┴─────────────────────────────────┘
```

### 2. AI Chat Page
```
┌─────────────────────────────────────────┐
│  Top Navigation                         │
├───────┬─────────────────────────────────┤
│       │  ┌─────────────────────────┐    │
│       │  │ Chat History (Sidebar)  │ │  │
│  Side │  │ - Session 1             │ │  │
│  Nav  │  │ - Session 2             │ │  │
│       │  └─────────────────────────┘ │  │
│       │                              │  │
│       │  Chat Messages Area          │  │
│       │                              │  │
│       │  ┌───────────────────────┐   │  │
│       │  │ Input Box             │   │  │
│       │  └───────────────────────┘   │  │
│       │  [Suggested Prompts]         │  │
└───────┴─────────────────────────────────┘
```

### 3. Code Lab Page
```
┌─────────────────────────────────────────┐
│  Top Navigation                         │
├───────┬─────────────────────────────────┤
│       │  Language: [Python ▼]  Run ▶    │
│       │  ┌─────────┬─────────┐          │
│  Side │  │  Code   │ Output  │          │
│  Nav  │  │  Editor │ Console │          │
│       │  │         │         │          │
│       │  │         │         │          │
│       │  └─────────┴─────────┘          │
└───────┴─────────────────────────────────┘
```

### 4. Video Library
```
┌─────────────────────────────────────────┐
│  Top Navigation                         │
├───────┬─────────────────────────────────┤
│       │  Search + Filters               │
│       │                                  │
│  Side │  ┌──────┐ ┌──────┐ ┌──────┐     │
│  Nav  │  │Video │ │Video │ │Video │     │
│       │  │ Card │ │ Card │ │ Card │     │
│       │  └──────┘ └──────┘ └──────┘     │
│       │  ┌──────┐ ┌──────┐ ┌──────┐     │
│       │  │Video │ │Video │ │Video │     │
│       │  └──────┘ └──────┘ └──────┘     │
└───────┴─────────────────────────────────┘
```

---

## User Flows

### 1. Ask a Question Flow
1. Navigate to AI Chat
2. See suggested prompts or type question
3. Submit question
4. AI processes (loading indicator)
5. Response appears with sources
6. User can: Ask follow-up, Copy, Regenerate, Rate

### 2. Practice Code Flow
1. Navigate to Code Lab
2. Select language
3. Write/paste code
4. Click Run
5. See output/errors
6. Iterate and debug
7. Save solution (optional)

### 3. Watch & Learn Flow
1. Navigate to Video Library
2. Browse or search videos
3. Click video card
4. Video player opens
5. Watch video with annotations
6. Answer quiz questions (if any)
7. Take notes
8. Mark as completed

### 4. Take Quiz Flow
1. Navigate to Practice Quiz
2. Select topic
3. Start quiz
4. Answer questions sequentially
5. Submit quiz
6. View results
7. Review incorrect answers
8. See recommendations

---

## Responsive Design

### Breakpoints
- **Mobile:** < 640px
- **Tablet:** 640px - 1024px
- **Desktop:** > 1024px

### Mobile Adaptations
- Hamburger menu (sidebar becomes drawer)
- Single column layouts
- Stacked cards
- Bottom navigation bar (key actions)
- Simplified chat interface
- Code editor: full screen mode option

---

## Accessibility

### Standards
- WCAG 2.1 Level AA compliance
- Minimum contrast ratio: 4.5:1 (text), 3:1 (UI elements)
- Keyboard navigation support
- Screen reader optimization
- Focus indicators
- Alt text for all images
- Semantic HTML
- ARIA labels where needed

---

## Micro-interactions

### Hover States
- Buttons: Darken + slight scale (1.02)
- Cards: Lift effect (shadow increase)
- Links: Underline appear

### Loading States
- Skeleton screens (not spinners)
- Progress indicators for long operations
- Optimistic UI updates

### Transitions
- Duration: 200ms (fast), 300ms (standard), 500ms (slow)
- Easing: cubic-bezier(0.4, 0, 0.2, 1)

### Feedback
- Success: Check animation + green toast
- Error: Shake animation + red toast
- Info: Slide-in notification

---

## Empty States

### Guidelines
- Friendly illustration
- Clear explanation
- Actionable suggestion (CTA button)

### Examples
- No chat history: "Start your learning journey"
- No bookmarks: "Save resources for later"
- No quiz results: "Take your first quiz"

---

## Error Handling

### Error Messages
- **User-friendly language** (no technical jargon)
- **Specific:** Explain what went wrong
- **Actionable:** Suggest how to fix
- **Tone:** Helpful, not blaming

### Examples
- "Connection lost. Please check your internet and try again."
- "This video is temporarily unavailable. Try another one?"
- "AI is thinking extra hard. This might take a moment..."

---

## Assets Needed

### Icons
- Feather Icons or Heroicons (consistent set)
- Custom icons for:
  - AI assistant
  - Code lab
  - Video library
  - Notes
  - Quiz
  - Progress

### Illustrations
- Empty states
- Onboarding screens
- Error pages (404, 500)
- Success confirmations

### Images
- Placeholder avatars
- Subject category images
- Background patterns (subtle)

---

## Figma File Structure

```
📁 Educational AI Platform
├── 📄 Cover & Project Info
├── 📄 Design System
│   ├── Colors
│   ├── Typography
│   ├── Spacing & Grid
│   ├── Icons
│   └── Components
├── 📄 Components Library
│   ├── Navigation
│   ├── Cards
│   ├── Buttons
│   ├── Forms
│   ├── Chat Interface
│   ├── Code Editor
│   └── Video Player
├── 📄 Wireframes
│   ├── Dashboard
│   ├── AI Chat
│   ├── Code Lab
│   ├── Video Library
│   ├── Notes
│   ├── Quiz
│   └── Profile
├── 📄 High-Fidelity Mockups (Light)
│   └── [All screens]
├── 📄 High-Fidelity Mockups (Dark)
│   └── [All screens]
├── 📄 Mobile Designs
│   └── [Key screens]
└── 📄 User Flows
    └── [Flow diagrams]
```

---

## Next Steps

1. ✅ Review this design brief
2. Create Figma account/project
3. Set up design system (colors, typography, components)
4. Create wireframes for core screens
5. Design high-fidelity mockups
6. Create interactive prototype
7. User testing (if possible)
8. Developer handoff (specs, assets)

---

## Resources & Inspiration

### Similar Platforms
- Khan Academy (clean, educational)
- Brilliant.org (interactive learning)
- LeetCode (code practice)
- Coursera (video learning)
- Notion (notes organization)

### Design Systems to Reference
- Material Design 3
- Apple Human Interface Guidelines
- Tailwind UI
- Ant Design

### Tools
- **Design:** Figma
- **Icons:** Heroicons, Feather Icons
- **Fonts:** Google Fonts (Inter)
- **Colors:** Coolors.co, Adobe Color
- **Illustrations:** Undraw, Storyset

---

> **Note:** This brief should guide the Figma design process. Adjust based on user feedback and testing results. Keep the student experience at the center of all design decisions.
