# 🎓 Saarthi.ai - Complete UX Design Research & Implementation Plan

> **Educational Platform**: AI-Powered Learning Management System
> **Date**: February 2, 2026
> **Design Expert Analysis**: Deep Research & Figma Implementation Strategy

---

## 📋 Table of Contents
1. [Executive Summary](#executive-summary)
2. [Product Analysis](#product-analysis)
3. [Competitive Research](#competitive-research)
4. [User Research & Personas](#user-research--personas)
5. [Information Architecture](#information-architecture)
6. [Design System](#design-system)
7. [Feature-by-Feature UX Design](#feature-by-feature-ux-design)
8. [Figma AI Prompts](#figma-ai-prompts)
9. [Recommended Plugins](#recommended-plugins)
10. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Executive Summary

### Product Vision
**Saarthi.ai** is an **Agentic AI-based Teaching Assistant** specifically designed for technical education in Machine Intelligence, Signal Processing, and Computer Science domains. Unlike generic AI assistants, Saarthi.ai is purpose-built to understand and teach complex technical concepts through multi-modal learning approaches.

---

## 2. PoC Objectives

### Primary Goal
To demonstrate an AI Tutor that outperforms generic AI systems (like ChatGPT) in teaching domain-specific technical subjects through personalized, multi-modal content delivery.

### Input Data Sources (Multi-Modal Content)
Saarthi.ai is trained/fed with specialized educational content:

1. **HMA Lab Datasets** (>10 datasets)
   - Research data from Machine Intelligence lab
   - Real-world problem sets and solutions
   
2. **Video Content** (>500 videos)
   - Machine Intelligence YouTube channel lectures
   - Concept explanations and demonstrations
   - Problem-solving walkthroughs
   
3. **Handwritten Notes** (Digitized)
   - Signal & Systems (SS)
   - Digital Signal Processing (DSP)
   - Pattern Recognition (PR)
   - Model-Based Systems Analysis (MBSA)
   - Other core subjects
   
4. **Solved Exercises**
   - Step-by-step problem solutions
   - Multiple approaches to single problems
   - Common mistake patterns
   
5. **Computer Assignments** (Worked Out)
   - Complete code implementations
   - Algorithm walkthroughs
   - Debugging examples
   
6. **Concept Simulations**
   - Analysis and processing visualizations
   - Interactive demonstrations
   - Real-time parameter adjustments

### Expected Outputs

#### 1. Intelligent Question Answering System
- **Context-aware responses** to technical queries
- **Multi-step explanations** for complex problems
- **Visual aids** and diagrams in answers
- **Code snippets** with explanations
- **Better than generic AI** for domain-specific questions

#### 2. Digitized Content Repository
- **Handwritten notes** → Searchable digital format
- **Solved problems** with step-by-step solutions
- **Annotated exercises** with common pitfalls
- **Organized by modules** and difficulty levels

#### 3. Annotated Video Content
- **Timestamped segments** for specific concepts
- **Associated quiz questions** at key checkpoints
- **Related exercise problems** linked to video topics
- **Computer assignments** mapped to video content
- **Interactive transcripts** with search functionality

### Salient Features

#### A. Modular Content Approach
- **Subject-wise organization**: SS, DSP, PR, MBSA, etc.
- **Topic-based modules**: Breaking complex subjects into digestible units
- **Progressive difficulty**: Beginner → Intermediate → Advanced
- **Cross-referencing**: Linking related concepts across modules
- **Personalized learning paths**: Adapting to student's level

#### B. Superior Technical Understanding
- **Domain-specific AI**: Trained on specialized datasets
- **Contextual awareness**: Understands technical terminology
- **Better than ChatGPT**: For complex technical queries in specific domains
- **Multi-modal reasoning**: Combines text, code, math, and visuals
- **Nuanced explanations**: Addresses common misconceptions

#### C. Student Learning Acceleration

**Help Students:**
1. **Learn Faster**
   - Interactive explanations with visual aids
   - Multiple learning modalities (video, text, code, diagrams)
   - Instant clarification of doubts
   - Adaptive content delivery

2. **Prepare for Exams, Tests & Interviews**
   - Subject-specific question banks
   - Previous year problems with solutions
   - Mock tests with performance analysis
   - Interview-style problem practice
   - Time-bound practice sessions

3. **Master Complex Concepts**
   - Step-by-step breakdowns
   - Visual simulations
   - Analogies and real-world applications
   - Interactive problem-solving

#### D. Solution Explanation Capabilities
- **Multi-approach solutions**: Different methods for same problem
- **Why & How explanations**: Not just the answer, but the reasoning
- **Common mistakes**: Highlighting where students often go wrong
- **Optimization tips**: Better, more efficient solutions
- **Code walkthroughs**: Line-by-line explanation of implementations

#### E. Progress Measurement & Analytics
- **Mastery tracking**: Per-concept understanding levels
- **Performance dashboards**: Visual progress representation
- **Weak area identification**: AI-detected knowledge gaps
- **Personalized recommendations**: Next topics to study
- **Comparison metrics**: Peer comparison and benchmarking
- **Achievement milestones**: Gamified learning goals

### Key Differentiators from Generic AI

| Feature | Generic AI (ChatGPT) | Saarthi.ai |
|---------|---------------------|------------|
| **Domain Knowledge** | Broad, shallow | Deep, specialized |
| **Problem Solving** | Generic approaches | Subject-specific methods |
| **Code Quality** | Basic examples | Production-level, optimized |
| **Learning Path** | Random | Structured, modular |
| **Progress Tracking** | None | Comprehensive analytics |
| **Content Source** | Internet scraping | Curated academic content |
| **Concept Depth** | Surface level | Research-backed depth |

### Platform Architecture Overview
```
Student Interface
    ↓
Saarthi.ai Agentic System
    ├─ Multi-Modal Content Processing
    │   ├─ Video Analysis Engine
    │   ├─ Handwritten Note OCR
    │   ├─ Code Understanding Module
    │   └─ Visual Simulation Engine
    ├─ AI Teaching Agent
    │   ├─ Question Understanding
    │   ├─ Context-aware Response
    │   ├─ Explanation Generation
    │   └─ Progress Assessment
    └─ Learning Analytics
        ├─ Performance Tracking
        ├─ Mastery Measurement
        └─ Personalization Engine
```

### Target Users
- **Primary**: Engineering students (B.Tech/M.Tech) specializing in:
  - Computer Science & Engineering
  - Electronics & Communication
  - Electrical Engineering
  - Machine Intelligence & AI
- **Secondary**: Research scholars working on ML/AI projects
- **Tertiary**: Working professionals upskilling in AI/ML domains

---

## 2. Product Analysis

### 2.1 Core Feature Breakdown

#### A. Authentication System
**Requirements**:
- Clean, modern login interface
- Signup with: Name, Institute Email, Password, Confirm Password
- Email verification for institutional accounts
- OAuth options (Google, Microsoft for education)
- Password strength indicator
- "Remember me" functionality
- Forgot password flow

**UX Principles**:
- Minimal friction onboarding
- Clear error messages
- Progressive disclosure (don't overwhelm with fields)
- Trust indicators (security badges, privacy policy links)

#### B. Exam Practice Module
**Components**:
1. **Assignment Interface**
   - Question list with progress tracker
   - Timer (optional/required)
   - Auto-save functionality
   - Draft/Submit states
   - Rich text editor for answers

2. **Quiz System (MCQ)**
   - Single/Multiple selection
   - Instant feedback option
   - Score calculation
   - Review incorrect answers
   - Detailed explanations
   - Performance analytics

**UX Patterns**:
- Clear question numbering
- Visual progress indicator (e.g., "5 of 20 completed")
- Flag for review functionality
- Confirmation before submission
- Time remaining alerts

#### C. Search Functionality
**Search Types**:
- Global search (topics, questions, courses)
- Autocomplete suggestions
- Recent searches
- Filters (by subject, difficulty, type)
- Advanced search options

**UX Best Practices**:
- Prominent search bar in header
- Keyboard shortcut (Ctrl+K or /)
- Search results with context snippets
- "No results" with suggestions

#### D. Courses Module
**Structure**:
- Course cards with thumbnails
- Progress bars per course
- Nested folder structure
- Multiple resource types:
  - Video lectures (YouTube integration)
  - PDF notes
  - Practice questions
  - Assignments

**Content Organization**:
- Hierarchical navigation (Course → Module → Lesson)
- Breadcrumb trail
- Table of contents sidebar
- Next/Previous lesson navigation
- Bookmarking functionality

#### E. Visual Interpretation
**Features**:
- Diagram viewer with zoom/pan
- Interactive graphs (hover for data points)
- Circuit simulator (for engineering students)
- Annotate and highlight tools
- Download/Print options
- Fullscreen mode

**Technical Requirements**:
- SVG/Canvas rendering
- Responsive scaling
- Touch gesture support (mobile)

#### F. Coding Environment
**IDE Features**:
- Multi-language support (Python, Java, C++, JavaScript, etc.)
- Syntax highlighting
- Code completion
- Error highlighting
- Console output
- Test case runner
- Code generation assistant (AI-powered)
- "Show Answer" toggle (for learning)
- Split view (code + problem statement)

**UX Considerations**:
- Resizable panels
- Theme selection (dark/light)
- Font size adjustment
- Keyboard shortcuts
- Save/Load code
- Share code snippets

#### G. Settings & Profile
**User Settings**:
- Profile information (name, email, institute)
- Avatar upload
- Password change
- Notification preferences
- Privacy settings
- Language selection
- Timezone

**Display Settings**:
- Dark/Light mode toggle
- Font size preferences
- Auto-save settings

#### H. Footer
**Content**:
- **About Us**: Platform mission and team
- **Contact Us**: Support form, email, social media
- **Location**: Office address, map
- **Courses**: Quick links to popular courses
- **Legal**: Terms of Service, Privacy Policy
- **Social Links**: Twitter, LinkedIn, Instagram

---

## 3. Competitive Research

### 3.1 Key Competitors Analysis

#### Khan Academy
**Strengths**:
- Extremely clean UI
- Excellent video integration
- Gamification (badges, points)
- Progress tracking
- Personalized learning paths

**Weaknesses**:
- Limited coding environment
- No institutional email system
- Less focus on exam preparation

**What to Adopt**:
- Minimalist design approach
- Skill tree visualization
- Video player controls

#### Coursera
**Strengths**:
- Professional design
<truncated>

---

## 4. User Research & Personas

### Persona 1: Priya - Engineering Student
**Demographics**:
- Age: 20, 3rd year Computer Science student
- Tech-savvy, uses multiple learning platforms
- Studies 3-4 hours daily

**Goals**:
- Ace coding interviews
- Understand complex concepts (Data Structures, Algorithms)
- Practice previous year exam questions

**Pain Points**:
- Scattered resources across platforms
- No integrated coding practice
- Difficult to track progress

**Needs**:
- All-in-one platform
- Code execution environment
- Visual explanations for algorithms

### Persona 2: Rahul - Medical Student
**Demographics**:
- Age: 22, preparing for entrance exams
- Prefers visual learning
- Limited coding experience

**Goals**:
- Master MCQ-based exams
- Memorize diagrams (anatomy, biology)
- Track weak areas

**Pain Points**:
- Information overload
- Difficult to practice MCQs efficiently
- No way to review mistakes

**Needs**:
- Clean quiz interface
- Diagram annotations
- Performance analytics

### Persona 3: Ananya - Working Professional
**Demographics**:
- Age: 27, upskilling for career growth
- Limited time (1-2 hours daily)
- Mobile-first user

**Goals**:
- Learn new technologies quickly
- Earn certifications
- Apply knowledge practically

**Pain Points**:
- Complex interfaces
- No mobile-optimized coding
- Lack of practical projects

**Needs**:
- Mobile-responsive design
- Microlearning modules
- Practical assignments

---

## 5. Information Architecture

### 5.1 Site Map
```
Saarthi.ai
├── Landing Page (Unauthenticated)
│   ├── Hero Section
│   ├── Features Overview
│   ├── Testimonials
│   ├── Pricing
│   └── Footer
│
├── Authentication
│   ├── Login
│   ├── Signup
│   ├── Forgot Password
│   └── Email Verification
│
├── Dashboard (Student Home)
│   ├── Quick Stats
│   ├── Continue Learning
│   ├── Upcoming Deadlines
│   └── Recommended Courses
│
├── Courses
│   ├── All Courses (Grid/List View)
│   ├── My Courses
│   ├── Course Detail Page
│   │   ├── Overview
│   │   ├── Curriculum
│   │   ├── Resources
│   │   ├── Discussions
│   │   └── Assignments
│   └── Lesson Page
│       ├── Video Player
│       ├── Notes (PDF/Text)
│       ├── Practice Questions
│       └── Progress Tracker
│
├── Exam Practice
│   ├── Assignment Library
│   ├── Quiz Library
│   ├── Create/Take Assignment
│   ├── Take Quiz
│   ├── Review Results
│   └── Analytics Dashboard
│
├── Coding Environment
│   ├── Problem List
│   ├── Code Editor
│   ├── Test Cases
│   ├── Submissions History
│   └── Solutions (AI-generated)
│
├── Visual Interpretation
│   ├── Diagram Library
│   ├── Interactive Graphs
│   ├── Circuit Simulator
│   └── Annotation Tools
│
├── Search
│   ├── Global Search Results
│   └── Advanced Filters
│
├── Settings
│   ├── Profile
│   ├── Account Settings
│   ├── Preferences
│   └── Privacy
│
└── Footer Pages
    ├── About Us
    ├── Contact Us
    ├── Our Location
    ├── Terms of Service
    └── Privacy Policy
```

---

## 6. Design System

### 6.1 Color Palette

#### Primary Colors
```css
--primary-500: #4F46E5 (Indigo - Main CTA, Links)
--primary-600: #4338CA (Hover states)
--primary-400: #6366F1 (Active states)
--primary-100: #E0E7FF (Backgrounds, badges)
```

#### Secondary Colors
```css
--secondary-500: #10B981 (Green - Success, Progress)
--warning-500: #F59E0B (Orange - Warnings, Pending)
--error-500: #EF4444 (Red - Errors, Failed)
--info-500: #3B82F6 (Blue - Information)
```

#### Neutral Colors
```css
--gray-50: #F9FAFB (Backgrounds)
--gray-100: #F3F4F6 (Cards, Input bg)
--gray-200: #E5E7EB (Borders)
--gray-500: #6B7280 (Secondary text)
--gray-700: #374151 (Primary text)
--gray-900: #111827 (Headings)
```

#### Dark Mode
```css
--dark-bg-primary: #0F172A
--dark-bg-secondary: #1E293B
--dark-text-primary: #F1F5F9
--dark-border: #334155
```

### 6.2 Typography

**Font Families**:
- **Headings**: Inter, -apple-system, sans-serif
- **Body**: Inter, -apple-system, sans-serif
- **Code**: 'Fira Code', 'JetBrains Mono', monospace

**Type Scale**:
```css
--text-xs: 0.75rem (12px) - Captions, labels
--text-sm: 0.875rem (14px) - Secondary text
--text-base: 1rem (16px) - Body text
--text-lg: 1.125rem (18px) - Emphasized text
--text-xl: 1.25rem (20px) - H4
--text-2xl: 1.5rem (24px) - H3
--text-3xl: 1.875rem (30px) - H2
--text-4xl: 2.25rem (36px) - H1
--text-5xl: 3rem (48px) - Hero headings
```

### 6.3 Spacing System
```css
--space-1: 0.25rem (4px)
--space-2: 0.5rem (8px)
--space-3: 0.75rem (12px)
--space-4: 1rem (16px)
--space-6: 1.5rem (24px)
--space-8: 2rem (32px)
--space-12: 3rem (48px)
--space-16: 4rem (64px)
```

### 6.4 Component Library

#### Buttons
1. **Primary Button**: Solid indigo, white text, rounded corners
2. **Secondary Button**: Outline, indigo border
3. **Ghost Button**: No border, indigo text
4. **Danger Button**: Red background for destructive actions

**Sizes**: Small (32px), Medium (40px), Large (48px)

#### Input Fields
- Border radius: 8px
- Border: 1px solid gray-200
- Focus: Primary color border + shadow
- Error state: Red border + error message below
- Helper text: Gray, 14px

#### Cards
- Background: White (Light) / Dark-bg-secondary (Dark)
- Border-radius: 12px
- Shadow: sm (4px blur)
- Padding: 24px

---

## 7. Feature-by-Feature UX Design

### 7.1 Authentication Pages

#### Login Page
**Layout**:
- Split screen (50/50)
- Left: Branding, testimonial, or illustration
- Right: Login form

**Form Elements**:
- Email input (with validation)
- Password input (show/hide toggle)
- Remember me checkbox
- Forgot password link
- Primary CTA: "Sign In"
- Divider: "Or continue with"
- OAuth buttons (Google, Microsoft)
- Footer link: "Don't have an account? Sign Up"

**Micro-interactions**:
- Input focus animations
- Button hover state
- Loading state on submit
- Error shake animation

#### Signup Page
**Fields**:
1. Full Name
2. Institute Email (.edu validation)
3. Password (strength indicator)
4. Confirm Password
5. Terms & Conditions checkbox

**UX Flow**:
1. User fills form
2. Form validation on blur
3. Submit triggers loading state
4. Success → Email verification page
5. Email sent → Check inbox message
6. Click verification link → Success page → Redirect to dashboard

### 7.2 Dashboard (Student Home)

**Layout**: Grid-based, responsive

**Sections**:
1. **Welcome Header**
   - "Welcome back, [Name]!"
   - Current streak, points earned

2. **Quick Stats Cards** (4 cards in row)
   - Courses Enrolled: 5
   - Assignments Pending: 3
   - Quiz Score Average: 85%
   - Study Time This Week: 12h

3. **Continue Learning** (Horizontal scroll)
   - Course card with thumbnail
   - Progress bar
   - "Resume" button
   - Last accessed time

4. **Upcoming Deadlines** (List)
   - Assignment name
   - Course name
   - Due date (with urgency color)
   - Quick action button

5. **Recommended for You** (AI-powered)
   - Course/Quiz suggestions
   - Based on performance and interests

### 7.3 Courses Module

#### All Courses Page
**Filters** (Left sidebar):
- Category (Engineering, Medical, Business, etc.)
- Difficulty (Beginner, Intermediate, Advanced)
- Duration
- Rating

**Course Cards** (Grid layout):
- Thumbnail image
- Course title
- Instructor name with avatar
- Rating (stars + count)
- Duration, lessons count
- Enrollment button
- Price (if applicable)

**Interactions**:
- Hover: Lift effect + shadow
- Click: Navigate to course detail

#### Course Detail Page
**Hero Section**:
- Course thumbnail/video preview
- Title, subtitle
- Instructor info
- Rating, students enrolled
- Enroll/Start Course button
- Share and bookmark icons

**Tabs**:
1. **Overview**
   - What you'll learn (bullet points)
   - Requirements
   - Description

2. **Curriculum** (Accordion)
   - Modules with nested lessons
   - Duration per lesson
   - Lock icon for unenrolled users
   - Video, quiz, assignment icons

3. **Resources**
   - Downloadable files
   - Reference links
   - Supplementary materials

4. **Discussions**
   - Q&A forum
   - Search within discussions
   - Upvote/Downvote
   - Instructor answers highlighted

#### Lesson Page
**Layout**: Full-width video player + sidebar

**Components**:
- Video player (YouTube embedded or custom)
  - Quality selector
  - Speed control
  - Subtitles toggle
  - Fullscreen
  - Picture-in-picture
- Lesson title and description
- Tab navigation:
  - Notes (Rich text with code blocks)
  - Practice Questions
  - Comments

**Sidebar** (Right):
- Course curriculum (mini version)
- Current lesson highlighted
- Next/Previous navigation
- Mark as complete checkbox

### 7.4 Exam Practice

#### Quiz Interface
**Structure**:
- Header: Quiz title, timer, progress (5/20)
- Question card:
  - Question number
  - Question text (supports rich text, images)
  - MCQ options (radio buttons or checkboxes)
  - "Flag for review" link
  - Explanation (shown after answer selection in practice mode)
- Navigation footer:
  - Question navigation grid (numbered boxes)
  - Previous/Next buttons
  - Submit button

**States**:
- Unanswered: Default gray
- Answered: Green check
- Flagged: Orange flag icon
- Current: Highlighted border

**Submission Flow**:
1. Click Submit
2. Confirmation modal: "Are you sure? You have 3 unanswered questions"
3. Confirm → Loading → Results page

#### Results Page
**Summary Card**:
- Score: 17/20 (85%)
- Time taken: 15min 30sec
- Accuracy graph (pie chart)
- Percentile rank

**Question Review**:
- Filter: All, Correct, Incorrect, Skipped
- Each question card shows:
  - Question
  - Your answer (highlighted)
  - Correct answer
  - Explanation
  - Time spent on question

**Actions**:
- Retake quiz
- Share results
- Download PDF report

### 7.5 Coding Environment

**Layout**: 3-Panel Split
1. **Left Panel** (30%): Problem statement
   - Title, difficulty badge
   - Description
   - Input/Output format
   - Constraints
   - Examples
   - Tags

2. **Middle Panel** (40%): Code editor
   - Language selector dropdown
   - Code editor (Monaco/Ace editor)
   - Line numbers
   - Syntax highlighting
   - Auto-complete
   - Theme toggle

3. **Right Panel** (30%): Console & Test Cases
   - Tabs: Test Cases, Console Output, Submissions
   - Run Code button
   - Submit button
   - Show Answer toggle (AI-generated solution)

**Additional Features**:
- Resizable panels (drag handles)
- Save code (auto-save + manual)
- Reset code
- Full-screen mode
- Keyboard shortcuts panel

**Test Case View**:
- Sample test cases (visible)
- Hidden test cases (run on submit)
- Expected vs Actual output
- Pass/Fail indicator

### 7.6 Visual Interpretation Module

**Diagram Viewer**:
- Toolbar: Zoom in/out, Pan, Reset, Fullscreen, Download
- Canvas area with SVG/Image
- Sidebar with diagram list
- Annotation tools:
  - Highlighter
  - Text notes
  - Arrows/Shapes
  - Color picker

**Graph Visualizer**:
- Interactive charts (Chart.js or D3.js)
- Hover tooltips
- Legend toggle
- Export as image

**Circuit Simulator** (for engineering):
- Component library (resistors, capacitors, etc.)
- Drag-and-drop interface
- Wire connections
- Simulation controls (play, pause, reset)
- Voltage/Current indicators

### 7.7 Settings Page

**Sidebar Navigation**:
- Profile
- Account
- Preferences
- Privacy & Security
- Notifications
- Billing (if applicable)

**Profile Section**:
- Avatar upload (circular crop)
- Full Name
- Email (read-only)
- Institute Name
- Bio (textarea)
- Social links
- Save button

**Preferences**:
- Language selection
- Time zone
- Theme (Light/Dark/Auto)
- Default code editor theme
- Font size
- Auto-save interval

**Privacy**:
- Profile visibility (Public/Private)
- Show progress to others
- Email preferences (marketing, updates)

---

## 8. Figma AI Prompts

### 🎨 Recommended Figma Plugins
1. **UX Pilot** - Full page generation from prompts
2. **Musho AI** - Website layout generation
3. **Banani** - App UI generation
4. **Magician** - Icons, images, copy
5. **Freepik AI** - Image generation
6. **FigGPT** - AI copywriting
7. **Auto Layout** - Built-in Figma feature
8. **Stark** - Accessibility checker

---

### Prompt 1: Landing Page (Hero Section)
**Plugin**: UX Pilot or Musho AI

```
Create a modern, clean landing page hero section for "Saarthi.ai", an AI-powered educational platform for students.

Layout:
- Full-width hero section (1440px wide, 800px tall)
- Left side (60%): Content area
- Right side (40%): Illustration or dashboard mockup

Left Content:
- Headline (56px, bold, dark gray): "Your AI-Powered Learning Companion"
- Subheading (20px, medium gray): "Master any subject with personalized AI tutoring, practice exams, and integrated coding environment"
- Two CTAs in a row:
  - Primary button (indigo background, white text): "Start Learning Free"
  - Secondary button (outline, indigo border): "Watch Demo"
- Trust elements below: "Trusted by 50,000+ students from 200+ institutions"

Right Side:
- Modern 3D illustration of students learning with laptops and AI elements
- Or: Floating dashboard mockup showing course interface

Design Style:
- Modern, clean, professional
- Color palette: Indigo primary (#4F46E5), white background, gray text
- Generous whitespace
- Subtle gradient background (light purple to white)
- Rounded corners on buttons (8px)
- Soft shadows

Additional elements:
- Floating achievement badges/icons around the illustration
- Subtle animated elements indicators (suggest with design elements)
```

### Prompt 2: Authentication - Login Page
**Plugin**: UX Pilot or Banani

```
Design a clean, modern login page for Saarthi.ai - an Agentic AI Teaching Assistant for technical education.

Layout: Split screen (1440px wide, 1024px tall)

Left Panel (50%):
- Background: Gradient from indigo (#4F46E5) to purple (#7C3AED)
- Content (centered, vertically aligned):
  - Saarthi.ai logo (white, 48px height)
  - Tagline: "Your Agentic AI Teaching Assistant" (white, 18px, semi-transparent)
  
  - Illustration (center):
    - Modern, technical illustration showing:
      - AI brain/neural network connecting to educational elements
      - Code snippets, mathematical equations, circuit diagrams
      - Student silhouette with laptop
      - Holographic/futuristic learning interface
    - Style: Gradient colors (white, light blue, purple)
    - Size: 400 x 350px
  
  - Feature highlights (bottom, white text with icons):
    Row of 3 benefit items:
    - Icon: Brain + "Domain-Specific AI"
    - Icon: Code + "Integrated Coding Lab"
    - Icon: Chart + "Progress Analytics"
    
    Each item:
    - Icon (24px, white with semi-transparent circle background)
    - Text below (14px, white, semi-transparent)
    - Arranged horizontally with equal spacing

Right Panel (50%):
- White background
- Login form container (centered, max-width 400px):
  - Heading: "Welcome back" (32px, bold, dark gray)
  - Subheading: "Continue mastering technical concepts" (16px, medium gray)
  
  Form fields (with spacing):
  1. Email input:
     - Label: "Institute Email" (14px, gray-700)
     - Placeholder: "you@university.edu"
     - Icon: Email icon on left (gray)
     - Input height: 48px
  
  2. Password input:
     - Label: "Password"
     - Placeholder: "Enter your password"
     - Icon: Lock icon on left
     - Show/hide password toggle (eye icon) on right
     - Input height: 48px
  
  - Row with checkbox and link:
    - Left: "Remember me" checkbox (14px text)
    - Right: "Forgot password?" link (indigo, 14px)
  
  - Primary button (full width, indigo #4F46E5, 48px height, 8px radius): 
    "Sign In"
    - Hover: Darker indigo (#4338CA)
  
  - Divider with text: "Or continue with" (gray line with centered text)
  
  - Social login buttons (2 columns, equal width):
    - Google button (white background, gray border, Google icon + "Google")
    - Microsoft button (white background, gray border, Microsoft icon + "Microsoft")
    - Each: 44px height, 8px radius, hover effect
  
  - Footer text (center, 14px): 
    "Don't have an account?" (gray) + "Sign Up" link (indigo, bold)

Design specifications:
- Input fields: 
  - Light gray background (#F9FAFB)
  - 1px border (#E5E7EB)
  - 8px border-radius
  - 12px padding left (for icon)
  - Focus state: Indigo border (#4F46E5), subtle glow shadow
- Spacing: 20px between form elements
- Font: Inter or system sans-serif
- All elements properly aligned with consistent margins
- Form container: 40px padding
- Professional, academic feel
- No decorative elements, focus on clarity
```


### Prompt 3: Student Dashboard
**Plugin**: UX Pilot

```
Create a comprehensive student dashboard for Saarthi.ai learning platform.

Page layout (1440px wide):

Header (fixed):
- Logo on left
- Search bar (center, 400px wide) with search icon and placeholder "Search courses, topics, questions..."
- Navigation icons on right: Notifications (with badge), Profile dropdown

Sidebar (left, 240px width, light gray background):
- Navigation menu items (with icons):
  - Dashboard (active state - indigo background)
  - My Courses
  - Exam Practice
  - Coding Lab
  - Visual Learning
  - Analytics
  - Settings
- Bottom: Progress summary card showing weekly study time

Main Content Area:

1. Welcome Section:
   - "Welcome back, Priya!" (24px)
   - Current streak: "5 day streak 🔥" with small card

2. Quick Stats (4 cards in a row, equal width):
   Card 1: Courses Enrolled
   - Large number: "5"
   - Icon: Book icon (indigo circle background)
   - Small text: "Active courses"
   
   Card 2: Pending Assignments
   - Large number: "3"
   - Icon: Clipboard (orange circle)
   - Small text: "Due this week"
   
   Card 3: Average Quiz Score
   - Large number: "85%"
   - Icon: Chart (green circle)
   - Small graph trend line
   
   Card 4: Study Time
   - Large number: "12h"
   - Icon: Clock (blue circle)
   - Small text: "This week"

3. Continue Learning Section:
   - Heading: "Continue Learning"
   - 3 course cards (horizontal scroll):
     Each card:
     - Course thumbnail image
     - Course title
     - Progress bar (e.g., 65% complete, green)
     - "Resume" button
     - "Lesson 5 of 12" small text

4. Upcoming Deadlines Section:
   - Heading: "Upcoming Deadlines"
   - List of 4 deadline items:
     Each item:
     - Assignment icon
     - Assignment title
     - Course name (gray, smaller)
     - Due date with urgency color (red if < 24h, orange if < 3 days, green otherwise)
     - Quick action button

5. Recommended Section:
   - "Recommended for You" heading with AI sparkle icon
   - 4 small cards with course suggestions

Design Style:
- Clean, modern, spacious
- Card-based layout
- White cards with subtle shadows (4px blur)
- 16px border radius on all cards
- Indigo (#4F46E5) as primary color
- Icons: Use modern, line-style icons
- Consistent 24px spacing between sections
- Responsive grid layout
```

### Prompt 4: Quiz Interface
**Plugin**: UX Pilot or Banani

```
Design a modern quiz/exam interface for an educational platform (MCQ questions).

Page Layout (1440px wide, full height):

Top Header (fixed, white background, shadow):
- Quiz title on left: "Data Structures - Module 1 Quiz"
- Timer in center (large, bold): "12:45" with clock icon
- Progress indicator on right: "Question 5 of 20" with progress bar

Main Content (centered, max-width 900px):

Question Card (white card, shadow, rounded corners):
1. Question Header:
   - Question number badge: "Question 5" (indigo badge)
   - Difficulty indicator: "Medium" (orange badge)
   - Flag icon button on right: "Flag for review"

2. Question Content:
   - Question text (20px, line-height 1.6):
     "What is the time complexity of binary search algorithm?"
   - Code block (if applicable, with syntax highlighting)
   - Image (if applicable)

3. Answer Options (4 MCQ options):
   Each option:
   - Radio button/checkbox on left
   - Option letter badge (A, B, C, D) with circular background
   - Option text
   - Entire option is clickable card
   - Hover state: light blue background
   - Selected state: indigo border, light indigo background
   - After answer (practice mode): Green for correct, Red for incorrect with checkmark/x icon

4. Explanation section (shown after answering in practice mode):
   - Light blue background box
   - "Explanation" heading
   - Detailed explanation text
   - Reference links if applicable

Bottom Navigation Bar (fixed):
- Left side: "Previous Question" button (secondary style)
- Center: Question navigator grid:
  - Small numbered boxes (1-20)
  - Color coding:
    - Gray: Unanswered
    - Green: Answered
    - Orange: Flagged
    - Indigo: Current question
- Right side: "Next Question" button (primary style)
- Far right: "Submit Quiz" button (accent color, prominent)

Right Sidebar (optional, 280px):
- Mini question overview list
- Show all questions with status
- Jump to question functionality

Design specifications:
- Modern, clean interface
- Generous whitespace
- Clear visual hierarchy
- Option cards: 16px padding, 8px border-radius
- Question card: 32px padding
- Font: Inter or system font
- Smooth transitions on hover
- Accessibility: high contrast, keyboard navigation indicators
```

### Prompt 5: Coding Environment (IDE Interface)
**Plugin**: UX Pilot

```
Create a full-featured online coding IDE interface for an educational platform.

Layout: 3-panel split view (1920px wide, 1080px tall)

Top Toolbar (fixed, dark gray background):
- Left: Problem title "Two Sum - Easy"
- Center: Language selector dropdown (Python, Java, C++, JavaScript)
- Right: 
  - Theme toggle (light/dark)
  - Settings icon
  - Fullscreen toggle

Main 3-Panel Layout:

LEFT PANEL (30% width, white/light gray background):
- Problem Statement Section:
  - Tabs: "Description" (active), "Submissions", "Discuss"
  
  Content:
  1. Title with difficulty badge
     - "1. Two Sum"
     - Badge: "Easy" (green)
     - Tags: "Array", "Hash Table"
  
  2. Description:
     - Problem statement (formatted text)
     - Examples (in code blocks with light background):
       Example 1:
       Input: nums = [2,7,11,15], target = 9
       Output: [0,1]
       Explanation: Because nums[0] + nums[1] == 9
  
  3. Constraints section:
     - List of constraints
  
  - Scroll able content
  - Compact, readable typography

MIDDLE PANEL (45% width, darker background for code):
- Code Editor Area:
  - Line numbers on left
  - Syntax-highlighted code
  - Use monospace font (JetBrains Mono or Fira Code)
  - Auto-complete tooltip (subtle)
  - Current line highlight
  - Minimap on far right edge (like VS Code)

- Editor Header:
  - Reset code icon
  - Font size controls
  - Copy code button

RIGHT PANEL (25% width):
- Tabs: "Testcases", "Console", "Solutions"

TestCases Tab (active):
  - Case 1 (expandable):
    Input section (code block)
    Expected Output section
    Your Output section (when run)
    Pass/Fail badge
  
  - Case 2
  - Add custom testcase button

Bottom Action Bar (spanning middle + right panel):
- Left side: 
  - "Run Code" button (secondary, green accent)
  - "Submit" button (primary, indigo)
- Right side:
  - "Show AI Solution" toggle button
  - Execution time: "Runtime: 48ms"
  - Memory: "Memory: 14.2 MB"

Design Specifications:
- Dark theme option for code panel
- Panel dividers: Resizable (drag handle)
- Code editor: Theme similar to VS Code
- Syntax colors: Keywords (blue), strings (green), comments (gray), functions (yellow)
- Clear visual separation between panels
- Status indicators for test cases (green checkmark, red X)
- Console output: Monospace font, dark background
- Smooth panel resizing
- Professional developer tool aesthetic
```

### Prompt 6: Course Detail Page
**Plugin**: UX Pilot or Musho AI

```
Design a comprehensive course detail page for an online learning platform.

Page width: 1440px

Hero Section (full width):
- Background: Light gradient (light purple to white)
- Left side (70%):
  - Breadcrumb: Home > Courses > Computer Science > Data Structures
  - Course title (48px, bold): "Complete Data Structures & Algorithms"
  - Instructor info row:
    - Small circular avatar
    - Name: "Dr. Rajesh Kumar"
    - Title: "Professor, IIT Delhi"
  - Rating: 4.8 stars (with 1,234 ratings)
  - Students enrolled: "12,450 students"
  - Last updated: "January 2026"
  - Language: English with subtitles
  
  - Course highlights (3 items with icons):
    - "40 hours of content"
    - "150+ practice problems"
    - "Certificate of completion"
  
  - CTA buttons:
    - Primary: "Enroll Now - Free"
    - Secondary: "Add to Wishlist" (heart icon)

- Right side (30%):
  - Course preview card (elevated, white, shadow):
    - Video thumbnail with play button overlay
    - Price (if applicable) or "Free"
    - "This course includes:" list:
      - 40 hours video
      - Downloadable resources
      - Lifetime access
      - Mobile access
    - Prominent enroll button

Content Section (below hero):

Left Sidebar (fitxed width 280px):
- Sticky navigation:
  - Overview
  - Curriculum
  - Instructor
  - Reviews
  - FAQs

Main Content (flexible width):

1. Overview Tab:
   - "What you'll learn" (4-column grid of bullet points with checkmark icons)
   - "Requirements" section
   - "Course Description" (rich formatted text)

2. Curriculum Tab:
   - Sections (accordion style):
     Section 1: Introduction (25 min)
     - Expandable to show lessons:
       Lesson 1.1: Welcome (video icon, 5:00, Preview button)
       Lesson 1.2: Course Overview (video icon, 10:00, locked)
       Quiz 1: Introduction Quiz (quiz icon, 10 questions)
     
     Section 2: Arrays & Strings (2 hours)
     - Similar nested structure
   
   - Each section shows:
     - Section title
     - Duration
     - Lesson count
     - Expand/collapse arrow
   
   - Lessons show:
     - Type icon (video, reading, quiz, assignment)
     - Title
     - Duration
     - Lock/unlock status
     - Preview badge (if available)

3. Instructor Section:
   - Instructor card:
     - Large circular photo
     - Name and title
     - Bio
     - Stats: X courses, X students, X rating
     - Social links

4. Reviews Section:
   - Overall rating summary (large 4.8 with breakdown bar chart)
   - Filter: All ratings, 5 star, 4 star, etc.
   - Review cards:
     - Avatar, name, date
     - Star rating
     - Review text
     - Helpful? buttons (thumbs up/down with counts)

5. FAQs Section:
   - Accordion with common questions

Design Style:
- Clean, professional
- White cards with subtle shadows
- Indigo primary color
- Clear visual hierarchy
- Icons for content types
- Hover effects on interactive elements
- Responsive layout considerations
```

### Prompt 7: Visual Interpretation - Diagram Viewer
**Plugin**: UX Pilot

```
Design an interactive diagram viewer interface for educational content (engineering/medical diagrams, circuits, graphs).

Page Layout (1440px wide, 900px tall):

Top Toolbar (light gray background, 60px height):
- Left:
  - Back button
  - Diagram title: "Binary Tree Traversal Visualization"
  - Category badge: "Data Structures"

- Center:
  - Zoom controls:
    - Zoom out button (-)
    - Zoom percentage display "100%"
    - Zoom in button (+)
    - Fit to screen button
  - Pan tool toggle
  - Reset view button

- Right:
  - Annotation tools:
    - Highlighter tool
    - Text note tool
    - Arrow/Shape tool
    - Color picker
  - Fullscreen toggle
  - Download button
  - Share button

Main Content (3-panel layout):

LEFT SIDEBAR (20% width, white background):
- "Diagrams" heading
- Search bar (small)
- Diagram library list:
  Each item:
  - Small thumbnail
  - Diagram name
  - Category tag
  - Active state highlighted (indigo border)
- Scrollable list

CENTER CANVAS (60% width, light gray background):
- Diagram viewing area:
  - Checkered background pattern(subtle)
  - Main diagram/image centered
  - Annotation overlays:
    - Highlighted areas (semi-transparent yellow)
    - Text notes (small bubble with line pointing to area)
    - Arrows and shapes
  - Zoom controls visible on hover
  - Draggable for panning

- Bottom mini-toolbar (overlay, centered):
  - Previous diagram
  - Play/Pause (for animated diagrams)
  - Next diagram

RIGHT PANEL (20% width, white background):
- Tabs: "Details", "Notes", "Related"

Details Tab (active):
  - Diagram information card:
    - Title
    - Description
    - Subject: "Computer Science"
    - Difficulty: "Intermediate"
    - Views count
  
  - Key Points section:
    - Bullet list of important concepts
    - With small icons
  
  - Tags section:
    - Tag chips (clickable)

Notes Tab:
  - User's saved annotations list
  - Each note:
    - Timestamp
    - Note text
    - Jump to location button
    - Edit/Delete icons

Related Tab:
  - Related diagram thumbnails
  - Click to switch diagram

Bottom Bar (if circuit simulator):
- Component library (for circuits)
- Drag-and-drop components
- Simulation controls (play, pause, reset)
- Value displays (voltage, current)

Design Specifications:
- Clean, professional interface
- High-zoomability support indicated
- Annotation tools easily accessible
- Color coding: Yellow for highlights, blue for notes
- Smooth zoom and pan experience
- Keyboard shortcuts hints (on hover)
- Toolbar icons: Modern, minimal, outlined style
- Canvas: Maximum focus area
- Responsive controls that don't obstruct content
```

### Prompt 8: Settings Page
**Plugin**: UX Pilot

```
Create a modern settings page for a student learning platform.

Page Layout (1440px wide):

Left Sidebar (240px, light gray background):
- Settings navigation menu:
  - Profile (active - indigo background, white text)
  - Account
  - Preferences
  - Privacy & Security
  - Notifications
  - Billing
  - Help & Support

Each menu item:
- Icon on left
- Label text
- Active state clearly indicated
- Hover effect

Main Content Area (1200px):

Header:
- Page title: "Settings" (32px)
- Breadcrumb: Home > Settings > Profile

Profile Section:

1. Profile Picture Card (white card, shadow):
   - Left: Current avatar (large circular, 120px)
   - Right: 
     - "Change Photo" button
     - "Remove" link
     - Hint text: "JPG or PNG. Max size 2MB"

2. Personal Information Card:
   Form fields (2-column grid):
   - Full Name (text input)
   - Email (text input, read-only with lock icon)
   - Institute/University (dropdown)
   - Student ID (text input)
   - Phone Number (text input with country code selector)
   - Date of Birth (date picker)
   
   Each field:
   - Label above
   - Clean input styling
   - Helper text below if needed
   - Proper spacing (16px between fields)

3. Bio Section Card:
   - "About Me" heading
   - Rich text textarea (400px width)
   - Character count: "150/500"

4. Social Links Card:
   - "Connect Your Accounts" heading
   - Social link inputs:
     - LinkedIn (icon + input field)
     - GitHub (icon + input field)
     - Twitter (icon + input field)
   - "+ Add another social link" button

Save Bar (bottom right, sticky):
- "Cancel" button (secondary)
- "Save Changes" button (primary, indigo)

Account Section (when clicked):
  
1. Login Credentials Card:
   - Email display with "Verified" badge
   - Change Password button
   - Two-Factor Authentication:
     - Toggle switch
     - Status: "Enabled" or "Not enabled"
     - Setup button

2. Connected Services Card:
   - List of OAuth connections:
     - Google (icon, email, "Connected" badge, Disconnect button)
     - Microsoft (same format)

3. Danger Zone Card (red accent):
   - Heading: "Danger Zone"
   - Deactivate Account button (outline, red)
   - Delete Account button (solid, red)

Preferences Section:
   
1. Appearance Card:
   - Theme selection:
     - Radio buttons: Light, Dark, Auto (system)
     - Visual previews of each theme
   - Font size slider: Small - Medium - Large

2. Language & Region Card:
   - Language dropdown
   - Timezone dropdown
   - Date format dropdown

3. Learning Preferences Card:
   - Default view: List/Grid (toggle)
   - Auto-play next lecture (toggle)
   - Playback speed default (dropdown)
   - Subtitle language (dropdown)

Notification Section:

1. Email Notifications Card:
   - Toggle switches for:
     - Course updates
     - New assignments
     - Quiz reminders
     - Marketing emails
     - Weekly progress report

2. Push Notifications Card:
   - Similar toggles for mobile
   - "Enable Desktop Notifications" button

Design Specifications:
- Card-based layout with 8px shadows
- Each card: 24px padding, 12px border-radius
- Form inputs: 48px height, 8px border-radius, light gray background
- Consistent spacing: 24px between cards
- Toggle switches: Modern style (iOS-like)
- Icons: Outlined style, 20px
- Save bar: Fixed on scroll with shadow
- Color coding: Red for danger zone, green for verified badges
- Responsive: Stack to single column on smaller screens
```

### Prompt 9: Mobile App - Home Screen
**Plugin**: Banani (optimized for mobile app UI)

```
Design a mobile app home screen for Saarthi.ai educational platform (iOS style).

Device: iPhone 14 Pro (393 x 852 pt)

Top Status Bar:
- Time, battery, signal (standard iOS)

Header (not scrollable):
- Saarthi.ai logo (left, small)
- Notification bell icon (right, with red badge "3")
- Search icon (right)

Greeting Section:
- "Good morning, Priya 👋"
- Subtitle: "Ready to learn today?"
- Current streak card (compact):
  - "5 Day Streak 🔥"
  - Small progress ring

Quick Stats (2x2 grid, compact cards):
- Card 1: "3 Courses" with book icon
- Card 2: "85% Avg" with chart icon
- Card 3: "2 Pending" with alarm icon
- Card 4: "12h Study" with clock icon

Continue Learning Section:
- Section heading: "Continue Learning"
- Horizontal scrollable cards:
  Each card (280px wide):
  - Course thumbnail (16:9)
  - Course title (truncate if long)
  - Progress bar (thin, green)
  - "Resume" button (small, pill-shaped)

Today's Schedule Section:
- Section heading: "Today's Schedule"
- List of 3 time-based items:
  Each item:
  - Time badge on left
  - Event title
  - Course name (gray, small)
  - Type badge (Quiz/Lecture/Assignment)

Bottom Navigation (iOS style tab bar):
- 5  tabs with icons:
  - Home (active, indigo)
  - Courses
  - Practice
  - Code
  - Profile

Design Style:
- iOS design language
- Rounded corners (12px for cards)
- Subtle shadows
- SF Pro or similar font
- White background
- Indigo accent color
- Safe area aware
- Smooth, native feel
- Generous touch targets (44pt minimum)
```

### Prompt 10: Footer Design
**Plugin**: Musho AI or UX Pilot

```
Create a modern, comprehensive website footer for Saarthi.ai educational platform.

Footer Width: Full-width (1440px content max-width)

Layout: 3-tier footer structure

TIER 1 - Main Footer (dark background, indigo-900):

Content (4-column grid with equal spacing):

Column 1: Brand & Description
- Saarthi.ai logo (white version)
- Tagline: "Your AI-powered learning companion"
- Short description (3 lines): "Empowering students with personalized AI tutoring, comprehensive exam preparation, and integrated coding practice."
- Social media icons (row):
  - Twitter, LinkedIn, Instagram, YouTube, Facebook
  - Icons: Outlined style, white, hover effect

Column 2: Quick Links
- Heading: "Platform" (white, bold, 14px)
- Links (white, 14px, opacity 0.8):
  - Browse Courses
  - Exam Practice
  - Coding Lab
  - Visual Learning
  - Student Dashboard
  - Become an Instructor

Column 3: Company
- Heading: "Company"
- Links:
  - About Us
  - Our Story
  - Team
  - Careers (with "Hiring" badge)
  - Press Kit
  - Contact Us

Column 4: Support & Legal
- Heading: "Support"
- Links:
  - Help Center
  - FAQs
  - Community Forum
  - Contact Support
  - System Status
- Divider line
- Legal links:
  - Privacy Policy
  - Terms of Service
  - Cookie Policy

TIER 2 - Contact & Location (medium dark background, indigo-800):

Content (2-column):

Left Column:
- "Get in Touch" heading
- Contact form (inline):
  - Email input (light background, semi-transparent)
  - "Subscribe" button (accent color)
- Small text: "Join 50,000+ students receiving weekly learning tips"

Right Column:
- "Our Office" heading
- Address icon + text:
  "Saarthi Education Pvt. Ltd.
  123 Tech Park, MG Road
  Bengaluru, Karnataka 560001
  India"
- Email icon + "hello@saarthi.ai"
- Phone icon + "+91 80 1234 5678"
- "View on Map" link

TIER 3 - Bottom Bar (darkest background, indigo-950):

Content (flex row, space-between):

Left side:
- "© 2026 Saarthi.ai. All rights reserved."

Center:
- Trust badges/certifications:
  - ISO certified badge
  - SSL secure badge
  - Payment partner logos (if applicable)

Right side:
- Language selector dropdown:
  - Globe icon + "English" + dropdown arrow

Design Specifications:
- Background gradient: indigo-900 to indigo-950
- Text colors: White with varying opacity (0.6 for secondary, 1.0 for primary)
- Link hover: Increase opacity to 1.0 + slight underline
- Section padding: 64px top/bottom
- Column spacing: 32px
- Font: Inter or system font
- Icons: 20px, line style
- Responsive: Stack columns on tablet/mobile
- Dividers between tiers: 1px, semi-transparent white
- Social icons: 32px circular backgrounds on hover
```

---

## 9. Recommended Plugins

### Essential Plugins for This Project

| Plugin Name | Purpose | Use Case |
|-------------|---------|----------|
| **UX Pilot** | Full page generation | Landing pages, dashboards, complex layouts |
| **Musho AI** | Website layouts | Homepage, footer, marketing pages |
| **Banani** | Mobile app UI | Mobile-responsive designs |
| **Magician by Diagram** | Icons & images | Custom icons, placeholder images |
| **Freepik AI** | Image generation | Illustrations, hero images, thumbnails |
| **FigGPT** | Copywriting | Headings, button labels, descriptions |
| **Frontitude** | UX writing | Microcopy, error messages, tooltips |
| **Auto Layout** | Built-in Figma | Responsive components |
| **Stark** | Accessibility | Color contrast checking |
| **Figma Autoname** | Organization | Auto-naming layers |

### How to Use Each Plugin

1. **UX Pilot**: Paste prompts 1-8 directly to generate full pages
2. **Magician**: Use "Magic Icon" for custom course category icons
3. **FigGPT**: Generate alternative button copy, headlines
4. **Stark**: Check color contrast for WCAG AA compliance

---

## 10. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create design system in Figma
- [ ] Set up color styles, typography, spacing
- [ ] Build core component library (buttons, inputs, cards)
- [ ] Create icon set

### Phase 2: Authentication & Onboarding (Week 2-3)
- [ ] Design login page
- [ ] Design signup page
- [ ] Create email verification flow
- [ ] Design welcome/onboarding screens

### Phase 3: Core Pages (Week 3-5)
- [ ] Student dashboard
- [ ] Course listing page
- [ ] Course detail page
- [ ] Lesson/video player page

### Phase 4: Interactive Features (Week 5-7)
- [ ] Quiz interface (all states)
- [ ] Coding environment
- [ ] Visual interpretation module
- [ ] Search interface

### Phase 5: Settings & Supplementary (Week 7-8)
- [ ] Settings pages
- [ ] Profile page
- [ ] Footer
- [ ] About/Contact pages

### Phase 6: Mobile Responsive (Week 8-9)
- [ ] Mobile versions of all key pages
- [ ] Tablet layouts
- [ ] Touch interactions

### Phase 7: Polish & Handoff (Week 9-10)
- [ ] Microinteractions and animations
- [ ] Prototype all user flows
- [ ] Accessibility review
- [ ] Developer handoff documentation

---

## Conclusion

This comprehensive UX research and design plan provides a strong foundation for building Saarthi.ai. The design emphasizes:

✅ **User-Centric Design**: Based on student personas and real needs
✅ **Modern Aesthetics**: Clean, professional, trust-building
✅ **Accessibility**: WCAG compliant, inclusive design
✅ **Scalability**: Component-based system for easy updates
✅ **AI-Ready**: Integrated AI features throughout

### Next Steps:
1. Review and approve this plan
2. Set up Figma workspace
3. Install recommended plugins
4. Start with Phase 1 (Design System)
5. Use AI prompts to accelerate design process

---

**Document Version**: 1.0
**Last Updated**: February 2, 2026
**Status**: Ready for Implementation
