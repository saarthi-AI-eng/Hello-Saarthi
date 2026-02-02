# Stage 3: Design - High-Level Design (HLD)
## Saarthi.ai - System Architecture & Design

---

# 1. System Architecture Overview

## 1.1 Architecture Pattern
**Pattern**: Microservices Architecture with API Gateway

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Web Browser │  │ Mobile Web   │  │  Future:     │          │
│  │  (React App) │  │  (Responsive)│  │  Native Apps │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS / WSS
┌───────────────────────────────┴─────────────────────────────────┐
│                        CDN / LOAD BALANCER                       │
│                    (CloudFlare / AWS CloudFront)                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────┐
│                        API GATEWAY                               │
│              (Rate Limiting, Routing, Auth)                      │
└─────┬─────┬─────┬─────┬─────┬─────┬─────┬────────────────────

┘
      │     │     │     │     │     │     │
  ┌───┴─┐ ┌─┴──┐ ┌┴──┐ ┌┴──┐ ┌┴──┐ ┌┴──┐ ┌┴────┐
  │Auth │ │AI  │ │Cont│ │Quiz│ │Code│ │Ana│ │Media│
  │Svc  │ │Svc │ │Svc │ │Svc │ │Exec│ │Svc│ │ Svc │
  └──┬──┘ └─┬──┘ └┬──┘ └┬──┘ └┬──┘ └┬──┘ └┬────┘
     │      │     │     │     │     │     │
     └──────┴─────┴─────┴─────┴─────┴─────┘
                       │
     ┌─────────────────┴──────────────────┐
     │         DATA LAYER                  │
     │  ┌──────────┐  ┌────────┐  ┌────┐ │
     │  │ MongoDB  │  │ Redis  │  │ S3 │ │
     │  │ (Primary)│  │ (Cache)│  │Files│ │
     │  └──────────┘  └────────┘  └────┘ │
     │  ┌──────────┐                      │
     │  │ Pinecone │  Vector Database     │
     │  │ /Weaviate│  (Embeddings)        │
     │  └──────────┘                      │
     └───────────────────────────────────┘
```

## 1.2 Service Breakdown

### **1. Authentication Service** (Port 8001)
**Responsibilities**:
- User registration and email verification
- Login with JWT token generation
- Token refresh and validation
- Password reset functionality
- Role-based access control

**Tech Stack**:
- Express.js + TypeScript
- MongoDB (User collection)
- Redis (Session storage, blacklist)
- JWT (jsonwebtoken library)
- bcrypt for password hashing

**APIs**:
- `POST /auth/signup` - User registration
- `POST /auth/signin` - User login
- `POST /auth/refresh` - Token refresh
- `POST /auth/logout` - Invalidate token
- `POST /auth/forgot-password` - Request reset link
- `POST /auth/reset-password` - Set new password

---

### **2. AI Service** (Port 8002)
**Responsibilities**:
- Process user queries
- RAG pipeline execution
- LLM integration (Gemini/GPT-4)
- Context retrieval from vector database
- Response generation with citations

**Tech Stack**:
- FastAPI (Python) for async performance
- LangChain for RAG orchestration
- Pinecone/Weaviate for vector search
- Google Gemini 2.0 / OpenAI API
- Redis for response caching

**APIs**:
- `POST /ai/query` - Submit question
- `POST /ai/explain` - Explain concept/solution
- `POST /ai/hint` - Get progressive hints
- `GET /ai/suggested-questions` - Context-based suggestions
- `WebSocket /ai/chat` - Real-time conversation

**RAG Pipeline**:
```
User Query
    │
    ├─> Embedding Generation (text-embedding-3-large)
    │
    ├─> Vector Search (Pinecone) → Top 5 relevant chunks
    │
    ├─> Context Assembly
    │       ├─ Notes
    │       ├─ Video transcripts
    │       ├─ Solved exercises
    │       └─ Datasets
    │
    ├─> Prompt Engineering
    │       System: "You are Saarthi.ai, expert in SS/DSP/PR/MBSA"
    │       Context: Retrieved chunks
    │       Query: User question
    │
    ├─> LLM Generation (Gemini 2.0)
    │
    └─> Response + Citations
```

---

### **3. Content Service** (Port 8003)
**Responsibilities**:
- Manage courses, modules, topics
- Video metadata and annotations
- Notes storage and retrieval
- Solved exercises repository
- Search functionality

**Tech Stack**:
- Express.js + TypeScript
- MongoDB (Courses, Videos, Notes collections)
- ElasticSearch for full-text search
- Redis for caching popular content

**APIs**:
- `GET /content/courses` - List all courses
- `GET /content/courses/:id` - Course details
- `GET /content/videos/:id` - Video with annotations
- `GET /content/notes/:id` - Digitized notes
- `GET /content/search?q=...` - Global search
- `GET /content/exercises?topic=...` - Solved exercises

---

### **4. Quiz Service** (Port 8004)
**Responsibilities**:
- Quiz creation and management
- Question bank
- Assignment tracking
- Submission handling
- Auto-grading (MCQ)

**Tech Stack**:
- Express.js + TypeScript
- MongoDB (Quizzes, Assignments collections)
- Redis for active quiz sessions

**APIs**:
- `GET /quiz/list?course=...` - Available quizzes
- `POST /quiz/start/:id` - Start quiz session
- `POST /quiz/submit/:id` - Submit answers
- `GET /quiz/result/:sessionId` - View results
- `POST /assignment/submit` - Upload assignment
- `GET /assignment/status/:id` - Assignment status

---

### **5. Code Execution Service** (Port 8005)
**Responsibilities**:
- Secure code execution in sandboxed environment
- Multi-language support (Python, C++, MATLAB, JS)
- Resource management and timeouts
- Output capture and error handling

**Tech Stack**:
- Node.js + Docker
- Python SafeExec / Judge0 API
- Docker containers for isolation
- Queue system (BullMQ) for job management

**APIs**:
- `POST /code/execute` - Run code
  ```json
  {
    "language": "python",
    "code": "print('Hello')",
    "stdin": "",
    "timeout": 5
  }
  ```
- `GET /code/status/:jobId` - Check execution status
- `POST /code/validate` - Syntax validation only

**Security Measures**:
- Network isolation (no external requests)
- CPU limit: 1 core
- Memory limit: 512MB
- Time limit: 5 seconds
- Blacklist dangerous imports (`os`, `subprocess`, etc.)

---

### **6. Analytics Service** (Port 8006)
**Responsibilities**:
- Track student progress
- Calculate performance metrics
- Generate insights and recommendations
- Leaderboards (optional)

**Tech Stack**:
- Express.js + TypeScript
- MongoDB (Progress, Analytics collections)
- Aggregation pipelines for reports
- Redis for real-time counters

**APIs**:
- `GET /analytics/dashboard` - Student dashboard stats
- `GET /analytics/progress/:userId` - Detailed progress
- `GET /analytics/performance/:courseId` - Course performance
- `POST /analytics/track-event` - Log learning events
- `GET /analytics/recommendations` - Personalized suggestions

---

### **7. Media Service** (Port 8007)
**Responsibilities**:
- Video upload and processing
- Image optimization
- File storage management
- CDN integration
- Thumbnail generation

**Tech Stack**:
- Express.js + TypeScript
- AWS S3 / Google Cloud Storage
- FFmpeg for video processing
- Sharp for image optimization
- CloudFront / Cloudinary CDN

**APIs**:
- `POST /media/upload/video` - Upload video
- `POST /media/upload/image` - Upload image
- `GET /media/video/:id/thumbnail` - Get thumbnail
- `POST /media/process/ocr` - OCR on image
- `DELETE /media/:id` - Delete file

---

## 1.3 Database Schema Design

### MongoDB Collections

#### **users**
```javascript
{
  "_id": ObjectId,
  "full_name": String,
  "email": String (unique, indexed),
  "password_hash": String,
  "role": String ("student" | "instructor" | "Admin"),
  "email_verified": Boolean,
  "profile_picture_url": String,
  "created_at": Date,
  "updated_at": Date
}
```

#### **courses**
```javascript
{
  "_id": ObjectId,
  "code": String (e.g., "SS", "DSP"),
  "name": String,
  "description": String,
  "prerequisites": [ObjectId],
  "modules": [
    {
      "module_id": ObjectId,
      "title": String,
      "order": Number,
      "topics": [ObjectId]
    }
  ],
  "created_at": Date
}
```

#### **videos**
```javascript
{
  "_id": ObjectId,
  "course_id": ObjectId,
  "module_id": ObjectId,
  "title": String,
  "youtube_url": String,
  "duration": Number (seconds),
  "transcript": String,
  "annotations": [
    {
      "timestamp": Number,
      "type": String ("concept" | "quiz" | "note"),
      "content": String | ObjectId
    }
  ],
  "created_at": Date
}
```

#### **notes**
```javascript
{
  "_id": ObjectId,
  "course_id": ObjectId,
  "module_id": ObjectId,
  "title": String,
  "content": String (markdown or HTML),
  "ocr_processed": Boolean,
  "source_image_url": String,
  "tags": [String],
  "created_at": Date
}
```

#### **quizzes**
```javascript
{
  "_id": ObjectId,
  "course_id": ObjectId,
  "title": String,
  "questions": [
    {
      "question_id": ObjectId,
      "text": String,
      "options": [String],
      "correct_answers": [Number],
      "explanation": String,
      "difficulty": Number (1-5)
    }
  ],
  "time_limit": Number (minutes),
  "created_at": Date
}
```

#### **quiz_sessions**
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "quiz_id": ObjectId,
  "started_at": Date,
  "submitted_at": Date,
  "answers": [
    {
      "question_id": ObjectId,
      "selected": [Number],
      "is_correct": Boolean
    }
  ],
  "score": Number,
  "total_questions": Number
}
```

#### **chat_history**
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "session_id": String,
  "messages": [
    {
      "role": String ("user" | "assistant"),
      "content": String,
      "timestamp": Date,
      "sources": [
        {
          "type": String ("video" | "note" | "exercise"),
          "id": ObjectId,
          "excerpt": String
        }
      ]
    }
  ],
  "created_at": Date
}
```

#### **progress**
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId (indexed),
  "course_id": ObjectId (indexed),
  "modules_completed": [ObjectId],
  "videos_watched": [
    {
      "video_id": ObjectId,
      "last_position": Number (seconds),
      "completed": Boolean
    }
  ],
  "quizzes_taken": [ObjectId],
  "assignments_submitted": [ObjectId],
  "overall_progress": Number (percentage),
  "updated_at": Date
}
```

### Vector Database (Pinecone)

**Index Structure**:
```
{
  "id": "doc_video_123_chunk_5",
  "values": [0.123, 0.456, ...],  // 1536-dim embedding
  "metadata": {
    "source_type": "video",
    "source_id": "ObjectId",
    "course": "DSP",
    "module": "Module 3",
    "timestamp": 123,  // For videos
    "text": "Original chunk text",
    "page": 5  // For notes
  }
}
```

---

## 1.4 API Gateway

**Technology**: Kong / NGINX / Express Gateway

**Responsibilities**:
- Central entry point for all client requests
- Route requests to appropriate microservices
- Authentication verification
- Rate limiting
- Request/response logging
- CORS handling

**Routing Rules**:
```
/api/auth/*       → Auth Service (8001)
/api/ai/*         → AI Service (8002)
/api/content/*    → Content Service (8003)
/api/quiz/*       → Quiz Service (8004)
/api/code/*       → Code Execution Service (8005)
/api/analytics/*  → Analytics Service (8006)
/api/media/*      → Media Service (8007)
```

**Rate Limiting**:
- General API: 100 req/min per user
- AI Service: 20 req/min per user
- Code Execution: 10 req/min per user

---

## 1.5 Frontend Architecture

### Component Hierarchy

```
App
├── AuthProvider (Context)
├── ThemeProvider (Context)
└── Router
    ├── PublicRoutes
    │   ├── LoginPage
    │   ├── SignupPage
    │   ├── ForgotPasswordPage
    │   └── LandingPage
    │
    └── ProtectedRoutes (RequireAuth wrapper)
        ├── DashboardPage
        │   ├── WelcomeBanner
        │   ├── StatsGrid
        │   │   ├── CoursesStat
        │   │   ├── AssignmentsStat
        │   │   ├── ScoreStat
        │   │   └── StudyTimeStat
        │   ├── CourseProgress
        │   ├── UpcomingDeadlines
        │   └── QuickActions
        │
        ├── CoursesPage
        │   ├── CourseList
        │   │   └── CourseCard (multiple)
        │   └── CourseDetailModal
        │
        ├── CourseViewPage
        │   ├── CourseNavigation (sidebar)
        │   ├── VideoPlayer
        │   │   ├── CustomControls
        │   │   ├── AnnotationsOverlay
        │   │   └── TranscriptPanel
        │   ├── NotesViewer
        │   └── QuizEmbed
        │
        ├── QuizPage
        │   ├── QuizHeader (timer, progress)
        │   ├── QuestionCard
        │   └── SubmitModal
        │
        ├── CodingPage
        │   ├── CodeEditor (Monaco)
        │   ├── ProblemDescription
        │   ├── ConsoleOutput
        │   └── TestCases
        │
        ├── AnalyticsPage
        │   ├── PerformanceCharts
        │   ├── TopicMastery
        │   └── StudyTimeGraph
        │
        ├── SettingsPage
        │   ├── ProfileSection
        │   ├── PasswordChange
        │   └── Preferences
        │
        └── GlobalComponents
            ├── Header (always visible)
            │   ├── Logo
            │   ├── SearchBar
            │   ├── Notifications
            │   └── UserMenu
            ├── Chatbot  (FAB, always accessible)
            │   ├── ChatWindow
            │   ├── MessageList
            │   ├── InputArea
            │   └── SuggestedQuestions
            └── Footer (static pages)
```

### State Management

**User Auth State** (Context API):
```typescript
interface AuthContext {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  signup: (data: SignupData) => Promise<void>;
}
```

**Global State** (Zustand):
```typescript
interface AppStore {
  // Chatbot
  chatOpen: boolean;
  chatHistory: Message[];
  toggleChat: () => void;
  sendMessage: (text: string) => Promise<void>;
  
  // Courses
  courses: Course[];
  currentCourse: Course | null;
  fetchCourses: () => Promise<void>;
  
  // Progress
  userProgress: ProgressData;
  updateProgress: (data: Partial<ProgressData>) => void;
  
  // UI
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}
```

**Server State** (React Query):
- Caching API responses
- Auto-refetching on window focus
- Optimistic updates
- Pagination support

---

## 1.6 Frontend-Backend Communication

### Communication Patterns

#### **1. REST API (Primary)**
**Use Cases**: CRUD operations, standard request-response

**Example Flow**: User Login
```
CLIENT                          BACKEND
  │                               │
  ├─ POST /api/auth/signin ─────>│
  │  { email, password }          │
  │                               ├─ Validate credentials
  │                               ├─ Generate JWT token
  │<──── { token, user } ─────────┤
  │                               │
  ├─ Store in localStorage        │
  │                               │
```

**Request Format**:
```typescript
// Client-side API service
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired, redirect to login
      logout();
    }
    return Promise.reject(error);
  }
);
```

#### **2. WebSocket (Real-Time)**
**Use Cases**: AI chatbot, live notifications

**Example Flow**: Chatbot Conversation
```
CLIENT                          AI SERVICE
  │                               │
  ├─ WebSocket Connect ─────────>│
  │  ws://api.com/ai/chat         │
  │                               ├─ Authenticate token
  │<──── Connected ───────────────┤
  │                               │
  ├─ Send: "Explain DSP" ───────>│
  │                               ├─ RAG Pipeline
  │                               ├─ LLM Generation
  │<──── Stream response ─────────┤
  │    (chunk by chunk)           │
  │                               │
```

**Implementation**:
```typescript
// Frontend
const chatSocket = new WebSocket('ws://localhost:8002/ai/chat');

chatSocket.onopen = () => {
  chatSocket.send(JSON.stringify({
    type: 'auth',
    token: localStorage.getItem('token')
  }));
};

chatSocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'message_chunk') {
    appendToResponse(data.content);
  }
};

// Backend (Express + ws library)
wss.on('connection', (ws, req) => {
  ws.on('message', async (message) => {
    const { query } = JSON.parse(message);
    const stream = await generateAIResponse(query);
    
    for await (const chunk of stream) {
      ws.send(JSON.stringify({
        type: 'message_chunk',
        content: chunk
      }));
    }
  });
});
```

#### **3. Server-Sent Events (SSE)**
**Use Cases**: Notifications, progress updates

**Example Flow**: Code Execution Status
```
CLIENT                          CODE SERVICE
  │                               │
  ├─ POST /code/execute ────────>│
  │<──── { jobId: "abc123" } ─────┤
  │                               ├─ Queue job
  │                               │
  ├─ EventSource ────────────────>│
  │  /code/status/abc123          │
  │                               ├─ Execute code
  │<──── data: {status: "running"} │
  │<──── data: {status: "done", output: "..."} │
  │                               │
```

---

## 1.7 Security Architecture

### Authentication Flow

```
┌─────────┐                  ┌─────────────┐                ┌──────────┐
│ Client  │                  │ Auth Service│                │ Database │
└────┬────┘                  └──────┬──────┘                └─────┬────┘
     │                              │                             │
     │  1. POST /auth/signin        │                             │
     ├─────────────────────────────>│                             │
     │  { email, password }         │  2. Find user by email      │
     │                              ├────────────────────────────>│
     │                              │ <───────────────────────────┤
     │                              │  3. Compare password hash   │
     │                              │  (bcrypt.compare)           │
     │                              │                             │
     │                              │  4. Generate JWT            │
     │                              │  Payload: {userId, role}    │
     │                              │  Secret: ENV variable       │
     │                              │  Expiry: 15 minutes (access)│
     │                              │                             │
     │  5. Return tokens            │                             │
     │<─────────────────────────────┤                             │
     │  {                           │                             │
     │    accessToken,              │                             │
     │    refreshToken              │                             │
     │  }                           │                             │
     │                              │                             │
     │  6. Store in localStorage    │                             │
     │                              │                             │
```

### Authorization Middleware

```typescript
// Backend middleware
export const authenticate = async (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded;
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Invalid token' });
  }
};

// Role-based authorization
export const authorize = (...roles: string[]) => {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) {
      return res.status(403).json({ error: 'Access denied' });
    }
    next();
  };
};

// Usage
app.get('/api/analytics/all-users',
  authenticate,
  authorize('admin'),
  getAllUsersAnalytics
);
```

---

## 1.8 Deployment Architecture

### Production Environment (AWS)

```
                      ┌─────────────────┐
                      │  Route 53 (DNS) │
                      └────────┬─────────┘
                               │
                      ┌────────┴─────────┐
                      │   CloudFront CDN │
                      │  (Static Assets) │
                      └────────┬─────────┘
                               │
                       ┌───────┴────────┐
                       │ React App (S3) │
                       │ Static Hosting │
                       └────────────────┘
                               │
                               │ API Calls
                               ▼
                    ┌──────────────────────┐
                    │ Application Load     │
                    │ Balancer (ALB)       │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
    ┌────────▼────────┐ ┌─────▼──────┐ ┌───────▼──────┐
    │ EC2 Instance 1  │ │ EC2 Inst 2 │ │ EC2 Inst 3   │
    │ (API Gateway +  │ │ (Services) │ │ (Services)   │
    │  Microservices) │ │            │ │              │
    └────────┬────────┘ └─────┬──────┘ └───────┬──────┘
             │                │                 │
             └────────────────┼─────────────────┘
                              │
                   ┌──────────┴──────────┐
                   │                     │
            ┌──────▼──────┐      ┌──────▼──────┐
            │  MongoDB    │      │   Redis     │
            │  Atlas      │      │ ElastiCache │
            │  (Cluster)  │      │             │
            └─────────────┘      └─────────────┘
                   │
            ┌──────▼──────┐
            │ S3 Bucket   │
            │ (Media)     │
            └─────────────┘
```

---

## Summary

This High-Level Design document defines:

✅ **Microservices architecture** with 7 specialized services
✅ **Database schema** for MongoDB with 8 collections
✅ **Frontend component hierarchy** with clear structure
✅ **Communication patterns** (REST, WebSocket, SSE)
✅ **Security architecture** for authentication & authorization
✅ **Deployment strategy** on AWS cloud

**Next**: Low-Level Design (LLD) for detailed component implementations

---

*Document Version: 1.0*  
*Last Updated: February 2, 2026*  
*Status: APPROVED FOR LLD PHASE*
