# Stage 2: Defining Requirements
## Saarthi.ai - Functional & Technical Requirements Specification

---

# Part A: Functional Requirements

## 1. User Authentication & Account Management

### FR-1.1: User Registration
**Priority**: CRITICAL  
**Description**: New users must be able to create an account using institutional credentials.

**Acceptance Criteria**:
- User provides: Full Name, Institutional Email (edu domain), Password, Confirm Password
- Email validation: Must match institutional domain pattern
- Password requirements:
  - Minimum 8 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one number
  - At least one special character
- Real-time password strength indicator with 5 levels
- Terms and conditions acceptance required
- Email verification link sent upon registration
- Account created only after email verification

**User Flow**:
1. User clicks "Sign Up" button
2. Fills registration form
3. Submits form
4. Receives verification email
5. Clicks verification link
6. Account activated, redirected to login

### FR-1.2: User Login
**Priority**: CRITICAL  
**Description**: Registered users must authenticate to access the platform.

**Acceptance Criteria**:
- Login with institutional email and password
- "Remember Me" option for persistent session
- JWT token generation upon successful authentication
- Token expiry: 24 hours (extendable with "Remember Me

")
- Failed login attempts tracked (max 5, then temporary lock)
- Clear error messages for invalid credentials
- Password visibility toggle

**User Flow**:
1. User enters email and password
2. Optionally checks "Remember Me"
3. Clicks "Sign In"
4. System validates credentials
5. JWT token stored in localStorage
6. Redirected to dashboard

### FR-1.3: User Logout
**Priority**: HIGH  
**Description**: Users must be able to securely terminate their session.

**Acceptance Criteria**:
- Logout button accessible from all pages (header/account menu)
- JWT token removed from localStorage
- Session data cleared
- Redirected to login page
- Confirmation dialog before logout (optional)

### FR-1.4: Settings & Profile Management
**Priority**: MEDIUM  
**Description**: Users can view and edit their profile information.

**Acceptance Criteria**:
- View current profile information
- Edit fields: Full Name, Profile Picture, Bio, Preferences
- Cannot edit: Email (requires re-verification if changed)
- Save changes with validation
- Success/error notifications
- Profile picture upload (max 5MB, JPG/PNG)

---

## 2. AI Chatbot (Real-Time Tutor)

### FR-2.1: Persistent Chatbot Interface
**Priority**: CRITICAL  
**Description**: An always-accessible AI chatbot for student queries.

**Acceptance Criteria**:
- Floating action button (FAB) visible on all pages
- Click FAB to open chat popover
- Chat history persists across sessions
- Real-time typing indicators
- Support for multi-turn conversations
- Context retention within session

**UI Requirements**:
- Position: Bottom-right corner
- Icon: AI assistant icon with notification badge
- Popover size: 400px × 600px (desktop), fullscreen (mobile)
- Minimize/maximize functionality
- Close button to hide popover

### FR-2.2: Question Answering
**Priority**: CRITICAL  
**Description**: Chatbot provides accurate, context-aware answers to technical queries.

**Acceptance Criteria**:
- Natural language query processing
- Domain-specific knowledge retrieval (SS, DSP, PR, MBSA)
- Response generation within 3 seconds
- Source citations for answers (links to notes, videos, datasets)
- Ability to ask follow-up questions
- "I don't know" response for out-of-scope queries

**Response Format**:
- Clear, structured answers
- Code snippets with syntax highlighting (if applicable)
- Mathematical equations rendered (LaTeX support)
- Diagrams/images embedded when relevant
- References section with clickable links

### FR-2.3: Context-Aware Assistance
**Priority**: HIGH  
**Description**: Chatbot understands user's current context (page, topic, progress).

**Acceptance Criteria**:
- Auto-detect current page/topic
- Suggest relevant questions based on context
- Reference current course/module in responses
- Personalized recommendations based on user progress
- Quick action buttons (e.g., "Start Quiz", "View Solution")

---

## 3. Search Functionality

### FR-3.1: Global Search
**Priority**: HIGH  
**Description**: Users can search across all platform content.

**Acceptance Criteria**:
- Search bar prominently displayed in header
- Search categories: Topics, Questions, Videos, Notes, Assignments
- Auto-complete suggestions as user types
- Recent searches history
- Search results grouped by content type
- Pagination for large result sets (20 per page)

**Search Capabilities**:
- Full-text search across notes, videos, assignments
- Fuzzy matching for typos
- Filters: Content type, subject, difficulty level
- Sort by: Relevance, Date, Popularity

### FR-3.2: Topic-Specific Search
**Priority**: MEDIUM  
**Description**: Refined search within specific subjects or modules.

**Acceptance Criteria**:
- Filter search results by subject (SS, DSP, PR, MBSA)
- Filter by content type (video, notes, quiz, code)
- Date range filter
- Difficulty level filter
- Tag-based filtering

---

## 4. Courses & Learning Content

### FR-4.1: Course Catalog
**Priority**: HIGH  
**Description**: Display available courses with structured content.

**Acceptance Criteria**:
- List of available courses (SS, DSP, PR, MBSA)
- Course cards showing: Title, Description, Progress %, Thumbnail
- Enroll/Unenroll functionality
- Prerequisites display
- Estimated completion time

### FR-4.2: Course Detail View
**Priority**: HIGH  
**Description**: Comprehensive view of course materials and structure.

**Acceptance Criteria**:
- Module/chapter breakdown
- Content types: Videos, Notes, Quizzes, Assignments, Simulations
- Progress indicators for each module
- Recommended learning path
- Download options for offline content (notes, assignments)

### FR-4.3: Video Integration
**Priority**: HIGH  
**Description**: Seamless video playback with annotations and interactions.

**Acceptance Criteria**:
- Embedded video player with controls
- Playback speed control (0.5x, 1x, 1.5x, 2x)
- Timestamp-based navigation
- Annotations overlay:
  - Key concept markers
  - Quiz questions at specific timestamps
  - Related notes/assignments links
- Transcript display with search
- Bookmarking favorite moments

### FR-4.4: Notes & Study Materials
**Priority**: HIGH  
**Description**: Access to digitized notes and documents.

**Acceptance Criteria**:
- Digitized handwritten notes (OCR-processed)
- Downloadable PDF versions
- Search within notes
- Highlight and annotate functionality
- Share notes with others (optional)

### FR-4.5: Solved Exercises & Assignments
**Priority**: HIGH  
**Description**: Repository of worked-out problems and solutions.

**Acceptance Criteria**:
- Browse exercises by topic
- Step-by-step solution walkthroughs
- Similar problems recommendations
- Difficulty rating
- User submission option (flagged for review)

---

## 5. Exam Practice System

### FR-5.1: Quiz Management
**Priority**: HIGH  
**Description**: Interactive multiple-choice quizzes for self-assessment.

**Acceptance Criteria**:
- Quiz types: Topic-based, Full-length mock exams
- Multiple choice questions (single/multiple correct answers)
- Timed quizzes with countdown timer
- Instant feedback after submission
- Correct answers revealed with explanations
- Score calculation and display
- Retry option

**Quiz Features**:
- Question randomization
- Answer shuffle
- Progress bar
- Flag questions for review
- Submit quiz confirmation dialog

### FR-5.2: Assignment Tracker
**Priority**: MEDIUM  
**Description**: Track assignments, deadlines, and submissions.

**Acceptance Criteria**:
- List view of all assignments
- Status indicators: Not Started, In Progress, Submitted, Graded
- Deadline countdown
- Submission interface (file upload)
- View graded assignments with feedback
- Late submission warnings

---

## 6. Coding Environment

### FR-6.1: Integrated Code Editor
**Priority**: HIGH  
**Description**: In-browser coding environment for programming exercises.

**Acceptance Criteria**:
- Syntax highlighting for multiple languages:
  - Python, MATLAB, C++, JavaScript
- Auto-completion and code suggestions
- Syntax error indicators
- Line numbers and code folding
- Theme options (light/dark)

### FR-6.2: Code Execution
**Priority**: HIGH  
**Description**: Run code and view output within the platform.

**Acceptance Criteria**:
- Execute button to run code
- Console output display
- Error messages with line numbers
- Execution time display
- Resource limits (CPU, memory, time)
- Support for standard input

**Supported Languages**:
- Python 3.x
- MATLAB/Octave
- C++ (GCC compiler)
- JavaScript (Node.js)

### FR-6.3: Code Generation & Hints
**Priority**: MEDIUM  
**Description**: AI-powered code suggestions and solution generation.

**Acceptance Criteria**:
- "Get Hint" button for stuck students
- Progressive hints (don't reveal full solution)
- "View Solution" option (unlocked after attempts)
- Code explanation feature
- Debugging assistance

---

## 7. Visual Interpretation

### FR-7.1: Diagram & Graph Rendering
**Priority**: MEDIUM  
**Description**: Display and interact with technical diagrams.

**Acceptance Criteria**:
- Support for: Block diagrams, Signal flow graphs, Circuit diagrams
- Zoom and pan functionality
- Annotations on diagrams
- Export as PNG/SVG
- Interactive elements (hover for details)

### FR-7.2: Mathematical Notation
**Priority**: HIGH  
**Description**: Render mathematical equations and formulas.

**Acceptance Criteria**:
- LaTeX equation rendering
- Inline and block equations
- Interactive equation editor
- Copy equation as LaTeX or image
- Equation references in chatbot responses

---

## 8. Progress Tracking & Analytics

### FR-8.1: Student Dashboard
**Priority**: HIGH  
**Description**: Personalized overview of learning progress.

**Acceptance Criteria**:
- Welcome banner with student name
- Stats cards: Active Courses, Pending Assignments, Average Score, Study Time
- Course progress visualization  
- Upcoming deadlines (color-coded by urgency)
- Study streak tracker
- Quick action buttons

### FR-8.2: Progress Analytics
**Priority**: MEDIUM  
**Description**: Detailed insights into learning performance.

**Acceptance Criteria**:
- Performance graphs (scores over time)
- Topic mastery breakdown
- Time spent per subject
- Strengths and weaknesses analysis
- Comparison with class average (anonymized)
- Study recommendations based on performance

---

## 9. Footer & Static Pages

### FR-9.1: Footer Navigation
**Priority**: LOW  
**Description**: Consistent footer across all pages with essential links.

**Content Requirements**:
- **About Us**: Platform mission, team information
- **Contact Us**: Email, phone, physical address
- **Our Location**: Embedded map, office hours
- **Courses**: Link to course catalog
- **Privacy Policy**: Data handling practices
- **Terms of Service**: User agreement
- **Help Center**: FAQs, tutorials

### FR-9.2: Contact Form
**Priority**: LOW  
**Description**: Allow users to send inquiries.

**Acceptance Criteria**:
- Form fields: Name, Email, Subject, Message
- CAPTCHA verification
- Email notification to admin
- Confirmation message to user
- Response within 24-48 hours

---

# Part B: Technical Requirements

## 1. System Architecture

### TR-1.1: Frontend Architecture
**Technology**: React.js with TypeScript

**Components Structure**:
```
src/
├── components/
│   ├── common/          # Reusable UI components
│   ├── auth/            # Authentication components
│   ├── chatbot/         # AI chatbot interface
│   ├── courses/         # Course-related components
│   ├── coding/          # Code editor components
│   └── dashboard/       # Dashboard widgets
├── pages/               # Route components
├── hooks/               # Custom React hooks
├── services/            # API service layer
├── utils/               # Helper functions
├── contexts/            # React Context providers
└── types/               # TypeScript type definitions
```

**State Management**:
- Context API for auth state
- Zustand for global state (user, courses, chatbot)
- React Query for server state management

### TR-1.2: Backend Architecture
**Technology**: Node.js + Express.js with TypeScript

**Microservices Architecture**:
```
backend/
├── auth-service/        # Authentication & user management
├── content-service/     # Course content management
├── ai-service/          # AI/LLM integration
├── quiz-service/        # Quiz & assessment logic
├── code-exec-service/   # Code execution sandbox
├── analytics-service/   # Progress tracking
└── api-gateway/         # Central routing
```

**API Design Patterns**:
- RESTful APIs for CRUD operations
- WebSocket for real-time chatbot
- Server-Sent Events (SSE) for notifications
- GraphQL for complex queries (optional)

### TR-1.3: Database Design

**Primary Database: MongoDB**

**Collections**:
1. **users**: User profiles and authentication
2. **courses**: Course metadata and structure
3. **modules**: Course modules and content
4. **videos**: Video metadata and annotations
5. **quizzes**: Quiz questions and answers
6. **assignments**: Assignment details and submissions
7. **chat_history**: Chatbot conversation logs
8. **progress**: Student progress tracking
9. **analytics**: Aggregated performance data

**Vector Database: Pinecone/Weaviate**
- Embeddings for RAG system
- Indexed content: Notes, video transcripts, solutions
- Similarity search for context retrieval

**Cache: Redis**
- Session storage
- Frequently accessed content
- Rate limiting data
- Temporary code execution results

---

## 2. AI/ML Integration

### TR-2.1: RAG Pipeline
**Retrieval Augmented Generation** for context-aware responses

**Pipeline Steps**:
1. **Ingestion**: Process source content (videos, notes, datasets)
2. **Chunking**: Split content into semantic chunks
3. **Embedding**: Generate vector embeddings
4. **Storage**: Store in vector database
5. **Retrieval**: Find relevant chunks for user query
6. **Generation**: LLM generates response with context

**Technologies**:
- LangChain for orchestration
- Text-embedding-3-large for embeddings
- Pinecone for vector search
- Gemini 2.0 / GPT-4 for generation

### TR-2.2: Content Processing

**Video Processing**:
- FFmpeg for video manipulation
- Whisper API for transcription
- Gemini Vision for visual analysis
- Timestamp extraction for annotations

**OCR Processing**:
- Tesseract for handwritten notes
- Google Cloud Vision API for complex equations
- Post-processing for LaTeX conversion
- Manual verification step for accuracy

**PDF Processing**:
- pdf.js for text extraction
- MathJax for equation recognition
- Table extraction for structured data

---

## 3. Security Requirements

### TR-3.1: Authentication & Authorization
- JWT with RS256 algorithm
- Access tokens (15 min expiry)
- Refresh tokens (7 days expiry)
- Role-based access control (RBAC): Student, Instructor, Admin
- Multi-factor authentication (optional)

### TR-3.2: Data Security
- TLS 1.3 for data in transit
- AES-256 encryption for sensitive data at rest
- Password hashing with bcrypt (salt rounds: 12)
- CSRF token protection
- XSS prevention (Content Security Policy)
- Input sanitization and validation

### TR-3.3: API Security
- Rate limiting (100 req/min per user)
- API key authentication for services
- Request signing for sensitive operations
- IP whitelisting for admin endpoints

---

## 4. Performance Requirements

### TR-4.1: Response Time
- Page load: < 2 seconds (95th percentile)
- API response: < 500ms (95th percentile)
- Chatbot response: < 3 seconds
- Search results: < 1 second
- Code execution: < 5 seconds

### TR-4.2: Scalability
- Support 1,000 concurrent users initially
- Horizontal scaling capability
- Auto-scaling based on load
- Database sharding for large datasets
- CDN for static assets and videos

### TR-4.3: Availability
- 99.5% uptime SLA
- Redundant database instances
- Load balancer for traffic distribution
- Health checks every 30 seconds
- Automated failover mechanisms

---

## 5. Integration Requirements

### TR-5.1: Third-Party Integrations

**AI/LLM Providers**:
- Google Gemini 2.0 API
- OpenAI GPT-4 API (fallback)
- Anthropic Claude (optional)

**Media Services**:
- YouTube API for video metadata
- Cloudinary for image optimization
- AWS S3 for file storage
- FFmpeg for video processing

**Analytics**:
- Google Analytics for user behavior
- Mixpanel for event tracking
- Custom analytics dashboard

### TR-5.2: Code Execution Sandbox
- Docker containers for isolation
- Resource limits (CPU: 1 core, RAM: 512MB, Time: 5s)
- Network isolation (no external requests)
- Supported runtimes: Python, Node.js, GCC

---

## 6. Deployment Requirements

### TR-6.1: Environment Configuration

**Development Environment**:
- Local MongoDB instance
- Redis local instance
- Mock AI responses for testing
- Hot module replacement

**Staging Environment**:
- Replica of production
- Test data set
- Performance testing tools
- Load testing with 500 concurrent users

**Production Environment**:
- MongoDB Atlas M10+ cluster
- AWS ElastiCache for Redis
- AWS EC2 Auto Scaling Group
- CloudFront CDN
- Route 53 DNS

### TR-6.2: CI/CD Pipeline
- GitHub Actions for automation
- Automated testing on PR
- Staging deployment on merge to `develop`
- Production deployment on merge to `main`
- Rollback capability

---

## 7. Monitoring & Logging

### TR-7.1: Application Monitoring
- DataDog / New Relic for APM
- Error tracking with Sentry
- Real User Monitoring (RUM)
- Synthetic monitoring for critical paths

### TR-7.2: Logging Strategy
- Structured logging (JSON format)
- Log levels: ERROR, WARN, INFO, DEBUG
- Centralized log aggregation (ELK stack)
- Log retention: 30 days

### TR-7.3: Alerts
- Error rate > 5%: Immediate alert
- Response time > 5s: Warning
- Server CPU > 80%: Scaling trigger
- Database connection failures: Critical alert

---

## 8. Accessibility Requirements

### TR-8.1: WCAG 2.1 AA Compliance
- Keyboard navigation for all features
- Screen reader compatibility
- Focus indicators on interactive elements
- Sufficient color contrast (4.5:1 minimum)
- Alt text for all images
- Captions for videos
- Accessible forms with labels

### TR-8.2: Responsive Design
- Mobile-first approach
- Breakpoints: 320px, 768px, 1024px, 1440px
- Touch-friendly buttons (min 44×44px)
- Adaptive layouts for different screen sizes

---

## Summary

This requirements specification defines:

✅ **9 major functional areas** with detailed acceptance criteria
✅ **8 technical domains** covering architecture, AI, security, performance
✅ **Clear user flows** for each feature
✅ **Measurable success metrics** for validation
✅ **Integration points** with third-party services
✅ **Deployment strategy** across environments

**Next Steps**: Proceed to Stage 3 - Design (HLD & LLD)

---

*Document Version: 1.0*  
*Last Updated: February 2, 2026*  
*Status: READY FOR DESIGN PHASE*
