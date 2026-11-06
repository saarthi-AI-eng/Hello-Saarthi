# Saarthi.ai - Comprehensive SDLC Documentation Index
## Pre-Development Phase Planning & Design

---

## 📋 Overview

This document serves as the master index for all Saarthi.ai PoC planning and design documentation, following the Software Development Life Cycle (SDLC) pre-development stages.

**Project**: Saarthi.ai - AI-Based Teaching Assistant  
**Type**: Proof of Concept (PoC)  
**Documentation Phase**: Planning → Requirements → Design  
**Status**: ✅ APPROVED FOR DEVELOPMENT

---

## 📚 Documentation Structure

### **Stage 1: Planning & Requirement Analysis**
📄 **Document**: [`STAGE1_PLANNING_AND_REQUIREMENTS.md`](./STAGE1_PLANNING_AND_REQUIREMENTS.md)

**Contents**:
1. Project Scope Definition
2. Objectives and Goals
3. Resource Planning
4. Project Timeline & Milestones
5. Risk Analysis & Mitigation
6. Success Criteria
7. Stakeholder Analysis
8. Assumptions & Constraints
9. Compliance & Legal Considerations

**Key Deliverables**:
- ✅ Project vision and scope
- ✅ Team structure (10 roles identified)
- ✅ Technology stack selection
- ✅ 16-week timeline with 8 milestones
- ✅ Risk mitigation strategies
- ✅ Success metrics defined

---

### **Stage 2: Defining Requirements**
📄 **Document**: [`STAGE2_REQUIREMENTS_SPECIFICATION.md`](./STAGE2_REQUIREMENTS_SPECIFICATION.md)

**Part A - Functional Requirements**:
1. User Authentication & Account Management (FR-1)
2. AI Chatbot - Real-Time Tutor (FR-2)  
3. Search Functionality (FR-3)
4. Courses & Learning Content (FR-4)
5. Exam Practice System (FR-5)
6. Coding Environment (FR-6)
7. Visual Interpretation (FR-7)
8. Progress Tracking & Analytics (FR-8)
9. Footer & Static Pages (FR-9)

**Part B - Technical Requirements**:
1. System Architecture (TR-1)
2. AI/ML Integration (TR-2)
3. Security Requirements (TR-3)
4. Performance Requirements (TR-4)
5. Integration Requirements (TR-5)
6. Deployment Requirements (TR-6)
7. Monitoring & Logging (TR-7)
8. Accessibility Requirements (TR-8)

**Key Deliverables**:
- ✅ 27 functional requirements with acceptance criteria
- ✅ 8 technical domains specified
- ✅ User flows for each feature
- ✅ Performance benchmarks
- ✅ Security protocols defined

---

### **Stage 3A: High-Level Design (HLD)**
📄 **Document**: [`STAGE3A_HIGH_LEVEL_DESIGN.md`](./STAGE3A_HIGH_LEVEL_DESIGN.md)

**Contents**:
1. System Architecture Overview
   - Microservices architecture diagram
   - 7 specialized services
2. Service Breakdown
   - Authentication Service (Port 8001)
   - AI Service (Port 8002)
   - Content Service (Port 8003)
   - Quiz Service (Port 8004)
   - Code Execution Service (Port 8005)
   - Analytics Service (Port 8006)
   - Media Service (Port 8007)
3. Database Schema Design
   - 8 MongoDB collections
   - Vector database structure
   - Redis caching strategy
4. API Gateway
5. Frontend Architecture
6. Frontend-Backend Communication
7. Security Architecture
8. Deployment Architecture (AWS)

**Key Deliverables**:
- ✅ Microservices architecture
- ✅ Complete database schemas
- ✅ Component hierarchy
- ✅ Communication patterns
- ✅ AWS deployment diagram

---

### **Stage 3B: Low-Level Design (LLD)**
📄 **Document**: [`STAGE3B_LOW_LEVEL_DESIGN.md`](./STAGE3B_LOW_LEVEL_DESIGN.md)

**Contents**:
1. Frontend-Backend Communication Guide
   - **Pattern 1**: User Authentication Flow
   - **Pattern 2**: Real-Time AI Chatbot (WebSocket)
   - **Pattern 3**: Code Execution (SSE)
2. API Specifications
   - Auth Service APIs
   - Content Service APIs
   - Quiz Service APIs
   - Complete request/response formats
3. Data Flow Examples
   - Video watching with annotations
   - Progress tracking pipeline
4. Detailed Component Implementations
   - CodeEditor Component (Monaco)
   - VideoPlayer Component
   - Production-ready TypeScript code

**Key Deliverables**:
- ✅ 3 complete communication patterns
- ✅ API endpoint specifications
- ✅ Data flow diagrams
- ✅ Production code examples
- ✅ WebSocket, REST, and SSE implementations

---

## 🎯 Project Objectives Recap

### Input Sources
- ✅ >10 HMA lab datasets
- ✅ >500 YouTube videos (Machine Intelligence channel)
- ✅ Handwritten notes (SS, DSP, PR, MBSA)
- ✅ Solved exercises
- ✅ Computer assignments
- ✅ Concept simulations

### Expected Outputs
- ✅ Question answering system
- ✅ Digitized content (OCR-processed notes)
- ✅ Annotated videos with quizzes

### Salient Features
- ✅ Modular subject content approach
- ✅ Domain-specific AI (better than ChatGPT)
- ✅ Faster learning for students
- ✅ Exam/interview preparation
- ✅ Solution explanations
- ✅ Progress measurement

---

## 🏗️ Technical Architecture Summary

### Frontend
- **Framework**: React.js + TypeScript + Vite
- **Styling**: Tailwind CSS
- **State**: Context API + Zustand + React Query
- **Router**: React Router v6
- **Code Editor**: Monaco Editor
- **Charts**: Recharts

### Backend
- **Services**: 7 microservices (Node.js + Express)
- **AI Service**: FastAPI (Python) with LangChain
- **API Gateway**: Kong / NGINX

### Databases
- **Primary**: MongoDB Atlas (8 collections)
- **Vector**: Pinecone/Weaviate (embeddings)
- **Cache**: Redis (sessions, rate limiting)
- **Storage**: AWS S3 (media files)

### AI/ML
- **LLM**: Google Gemini 2.0 / OpenAI GPT-4
- **Embeddings**: text-embedding-3-large
- **RAG**: LangChain orchestration
- **OCR**: Tesseract + Google Cloud Vision

### Infrastructure
- **Cloud**: AWS (EC2, S3, CloudFront, Route 53)
- **CI/CD**: GitHub Actions
- **Monitoring**: DataDog / New Relic
- **Logging**: Winston + ELK Stack

---

## 🔐 Security Highlights

- ✅ JWT authentication (RS256 algorithm)
- ✅ Bcrypt password hashing (12 rounds)
- ✅ TLS 1.3 encryption
- ✅ CSRF protection
- ✅ XSS prevention (CSP headers)
- ✅ Rate limiting (100 req/min)
- ✅ Docker isolation for code execution
- ✅ RBAC (Student, Instructor, Admin)

---

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| **Page Load** | < 2s (95th percentile) |
| **API Response** | < 500ms (95th percentile) |
| **AI Response** | < 3s |
| **Code Execution** | < 5s |
| **Concurrent Users** | 1,000+ |
| **Uptime SLA** | 99.5% |

---

## 📝 Functional Requirements Summary

### Core Features

1. **Authentication** ✅
   - Signup with email verification
   - JWT-based login
   - Password reset
   - Profile management

2. **AI Chatbot** ✅
   - Real-time WebSocket chat
   - RAG-based responses
   - Context-aware suggestions
   - Source citations
   - Multi-turn conversations

3. **Course Management** ✅
   - Course catalog
   - Module breakdown
   - Video player with annotations
   - OCR-processed notes
   - Solved exercises repository

4. **Assessment System** ✅
   - Timed quizzes (MCQ)
   - Auto-grading
   - Assignment tracking
   - Instant feedback

5. **Coding Environment** ✅
   - Multi-language support
   - Monaco code editor
   - Docker-based execution
   - Output capture
   - Syntax validation

6. **Analytics Dashboard** ✅
   - Course progress tracking
   - Performance graphs
   - Study time analytics
   - Personalized recommendations

7. **Search** ✅
   - Global content search
   - Topic/question search
   - ElasticSearch backend
   - Fuzzy matching

---

## 🗂️ Database Collections

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `users` | User accounts | email, password_hash, role |
| `courses` | Course metadata | code, modules, prerequisites |
| `videos` | Video data | youtube_url, annotations, transcript |
| `notes` | Digitized notes | content, ocr_processed, tags |
| `quizzes` | Quiz questions | questions, answers, explanations |
| `quiz_sessions` | Quiz attempts | user_id, answers, score |
| `chat_history` | Chatbot logs | user_id, messages, sources |
| `progress` | Learning progress | videos_watched, quizzes_taken |

---

## 🔄 Frontend-Backend Communication

### Communication Methods

1. **REST API** (Primary)
   - CRUD operations
   - Standard request-response
   - JSON format
   - JWT authentication

2. **WebSocket** (Real-Time)
   - AI chatbot conversations
   - Live notifications
   - Bi-directional streaming

3. **Server-Sent Events (SSE)**
   - Code execution status
   - Progress updates
   - One-way server push

---

## 🚀 Development Roadmap

### Phase 1: Foundation (Weeks 1-4)
- Development environment setup
- Frontend/backend boilerplate
- Authentication system
- Basic UI components

### Phase 2: Content Integration (Weeks 5-8)
- Video processing pipeline
- OCR for notes
- Dataset ingestion
- RAG pipeline setup

### Phase 3: Feature Completion (Weeks 9-12)
- Quiz system
- Coding environment
- Video annotations
- Progress tracking

### Phase 4: Testing & Deployment (Weeks 13-16)
- Comprehensive testing
- Performance optimization
- Security audit
- Production launch

---

## ✅ Deliverables Checklist

### Documentation ✅
- [x] Planning & Requirements Analysis
- [x] Functional Requirements
- [x] Technical Requirements
- [x] High-Level Design
- [x] Low-Level Design
- [x] API Specifications
- [x] Database Schemas
- [x] Frontend-Backend Integration Guide

### Design Artifacts ✅
- [x] System architecture diagram
- [x] Microservices breakdown
- [x] Database schema design
- [x] Component hierarchy
- [x] Communication patterns
- [x] Deployment architecture
- [x] Security architecture

### Code Samples ✅
- [x] Authentication flow (frontend + backend)
- [x] WebSocket chatbot implementation
- [x] Code execution with Docker
- [x] React components (Video Player, Code Editor)
- [x] API route handlers
- [x] Database models

---

## 📁 File Structure

```
docs/planning/
├── README.md (this file)
├── STAGE1_PLANNING_AND_REQUIREMENTS.md
├── STAGE2_REQUIREMENTS_SPECIFICATION.md
├── STAGE3A_HIGH_LEVEL_DESIGN.md
└── STAGE3B_LOW_LEVEL_DESIGN.md
```

---

## 🎯 Next Steps

### Development Phase
1. **Environment Setup**
   - Initialize Git repository
   - Set up development containers
   - Configure MongoDB Atlas
   - Create AWS accounts

2. **Sprint 1 (Weeks 1-2)**
   - Frontend boilerplate (React + Vite)
   - Backend scaffolding (Express + TypeScript)
   - Authentication service
   - Database models

3. **Sprint 2 (Weeks 3-4)**
   - Login/Signup UI
   - JWT implementation
   - Protected routes
   - User profile management

4. **Sprint 3 (Weeks 5-6)**
   - AI service setup (FastAPI)
   - LangChain integration
   - Vector database (Pinecone)
   - Basic chatbot UI

5. **Sprint 4 (Weeks 7-8)**
   - Content ingestion pipeline
   - Video processing
   - OCR implementation
   - RAG pipeline refinement

---

## 📞 Stakeholder Communication

### Weekly Updates
- Progress against timeline
- Blockers and risks
- Demo of completed features
- Next week's goals

### Sprint Reviews
- Feature demos
- Stakeholder feedback
- Backlog prioritization
- Release planning

---

## 🏆 Success Metrics

### Technical Metrics
- **Code Coverage**: >80%
- **API Response Time**: <500ms (p95)
- **AI Accuracy**: >85% on domain questions
- **System Uptime**: 99.5%

### Business Metrics
- **User Adoption**: 500+ students in first month
- **Engagement**: 70% weekly return rate
- **Satisfaction**: >4.0/5.0 rating
- **Completion Rate**: 60%+ quiz completion

### Quality Metrics
- **Bug Density**: <5 bugs per 1000 LOC
- **Mean Time to Recovery**: <30 minutes
- **Deployment Frequency**: Weekly releases
- **Change Failure Rate**: <5%

---

## 📖 References

### Internal Documents
- STAGE1_PLANNING_AND_REQUIREMENTS.md
- STAGE2_REQUIREMENTS_SPECIFICATION.md
- STAGE3A_HIGH_LEVEL_DESIGN.md
- STAGE3B_LOW_LEVEL_DESIGN.md

### External Resources
- React.js Documentation: https://react.dev
- LangChain: https://python.langchain.com
- MongoDB Atlas: https://www.mongodb.com/atlas
- Google Gemini API: https://ai.google.dev/gemini-api
- AWS Documentation: https://docs.aws.amazon.com

---

## 📝 Document Control

| Field | Value |
|-------|-------|
| **Document Title** | Saarthi.ai SDLC Documentation Index |
| **Version** | 1.0 |
| **Reviewers** | Product Owner, Technical Architect |
| **Approval Date** | February 2, 2026 |

---

## ✅ Summary

**All pre-development SDLC documentation is complete!**

This comprehensive documentation package includes:
- ✅ **Stage 1**: Planning & Requirement Analysis (9 sections)
- ✅ **Stage 2**: Functional & Technical Requirements (17 modules)
- ✅ **Stage 3A**: High-Level Design (8 components)
- ✅ **Stage 3B**: Low-Level Design (detailed implementations)

**Total Pages**: 150+ pages of detailed documentation  
**Total Diagrams**: 10+ architecture and flow diagrams  
**Code Examples**: 15+ production-ready implementations  

**The project is now READY FOR DEVELOPMENT PHASE!** 🚀

---

*End of Documentation Index*
