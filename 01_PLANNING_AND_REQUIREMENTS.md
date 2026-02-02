# Stage 1: Planning & Requirement Analysis
## Saarthi.ai - AI-Based Teaching Assistant PoC

---

## 1. Project Scope Definition

### 1.1 Project Overview
**Saarthi.ai** is an Agentic AI-based Teaching Assistant designed to revolutionize technical education in domains such as Machine Intelligence, Signal Processing, and Computer Science. Unlike generic AI assistants, Saarthi.ai is purpose-built with domain-specific knowledge to provide superior learning experiences.

### 1.2 Project Vision
To create an intelligent teaching platform that understands complex technical concepts and adapts to individual student learning patterns, providing personalized guidance that surpasses traditional learning methods and generic AI solutions.

### 1.3 Project Scope

#### In Scope:
- Multi-modal content ingestion and processing
- Intelligent question-answering system
- Content digitization and annotation
- Student progress tracking and analytics
- Interactive coding environment
- Quiz and assignment management
- Real-time AI tutor chatbot
- Video content integration with annotations

#### Out of Scope (Phase 1):
- Live instructor-led sessions
- Peer-to-peer collaboration features
- Mobile native applications
- Offline mode functionality
- Third-party LMS integrations

---

## 2. Objectives and Goals

### 2.1 Primary Objectives

#### **Objective 1: Demonstrate AI Tutor Capabilities**
- Build an Agentic AI system that can answer complex technical queries
- Outperform generic AI solutions (ChatGPT) in domain-specific topics
- Provide contextual, accurate responses based on institutional data

#### **Objective 2: Multi-Modal Content Integration**
Input sources to be integrated:
- **Datasets**: >10 HMA lab datasets
- **Video Content**: >500 videos from Machine Intelligence YouTube channel
- **Handwritten Notes**: Subject-specific notes (SS, DSP, PR, MBSA)
- **Solved Exercises**: Complete problem solutions
- **Computer Assignments**: Worked-out programming assignments
- **Simulations**: Concept analysis and processing simulations

#### **Objective 3: Enhanced Learning Experience**
- Help students learn faster through personalized guidance
- Prepare students for exams, tests, and interviews
- Provide step-by-step solution explanations
- Measure and track student mastery of concepts

### 2.2 Expected Outputs

#### **Output 1: Question Answering System**
- Natural language query processing
- Context-aware responses
- Multi-turn conversation support
- Source citation and references

#### **Output 2: Digitized Content**
- OCR-processed handwritten notes
- Searchable problem solutions
- Indexed video transcripts
- Structured assignment databases

#### **Output 3: Annotated Videos**
- Timestamp-based topic markers
- Embedded quiz questions
- Related exercise problems
- Computer assignment links
- Interactive concept explanations

---

## 3. Resource Planning

### 3.1 Team Structure

#### Development Team
| Role | Responsibilities | Count |
|------|-----------------|-------|
| **Frontend Developer** | React UI, dashboard, coding IDE | 2 |
| **Backend Developer** | API, authentication, data processing | 2 |
| **AI/ML Engineer** | LLM integration, RAG pipeline, embeddings | 2 |
| **Data Engineer** | Content ingestion, preprocessing, vectorization | 1 |
| **DevOps Engineer** | Infrastructure, deployment, monitoring | 1 |
| **UI/UX Designer** | Interface design, user experience | 1 |
| **QA Engineer** | Testing, quality assurance | 1 |

#### Project Management
| Role | Responsibilities |
|------|-----------------|
| **Project Manager** | Timeline, stakeholder communication, risk management |
| **Product Owner** | Requirements, feature prioritization, acceptance criteria |
| **Technical Architect** | System design, technology decisions, code review |

### 3.2 Technology Stack

#### Frontend
- **Framework**: React.js with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Context API / Zustand
- **Routing**: React Router v6
- **Code Editor**: Monaco Editor / CodeMirror
- **Charts**: Recharts / D3.js

#### Backend
- **Runtime**: Node.js
- **Framework**: Express.js with TypeScript
- **Authentication**: JWT (JSON Web Tokens)
- **API Documentation**: Swagger/OpenAPI

#### Database
- **Primary Database**: MongoDB (document-based, flexible schema)
- **Vector Database**: Pinecone / Weaviate (for embeddings)
- **Cache**: Redis (session management, frequently accessed data)

#### AI/ML Services
- **LLM Provider**: Google Gemini 2.0 / OpenAI GPT-4
- **Embeddings**: Text-embedding-3-large / Gemini Embeddings
- **RAG Framework**: LangChain / LlamaIndex
- **Vector Search**: FAISS / Pinecone

#### Media Processing
- **Video Processing**: FFmpeg
- **OCR**: Tesseract / Google Cloud Vision API
- **Image Processing**: Sharp / Pillow
- **PDF Generation**: PDFKit / Puppeteer

#### Infrastructure
- **Hosting**: AWS EC2 / Google Cloud Run
- **Storage**: AWS S3 / Google Cloud Storage
- **CDN**: CloudFlare
- **Monitoring**: DataDog / New Relic
- **Logging**: Winston / Pino

### 3.3 Infrastructure Requirements

#### Development Environment
- Local development setup with Docker Compose
- MongoDB instance (local or Atlas)
- Redis instance
- S3-compatible storage (MinIO for local)

#### Staging Environment
- Mirror of production with reduced capacity
- Separate database instance
- Testing data set

#### Production Environment
- **Compute**: 4-8 vCPU instances, auto-scaling
- **Database**: MongoDB Atlas M10+ cluster
- **Storage**: 500GB+ S3 storage for media
- **CDN**: Global distribution for video content
- **Bandwidth**: 10TB+ monthly

---

## 4. Project Timeline & Milestones

### Phase 1: Foundation (Weeks 1-4)
**Milestone 1.1: Development Environment Setup**
- Week 1: Infrastructure setup, CI/CD pipeline
- Week 2: Frontend boilerplate, backend scaffolding
- Week 3: Database schema design, API structure
- Week 4: Authentication system, user management

**Milestone 1.2: Core Features**
- User registration and login
- Basic dashboard layout
- Simple Q&A interface
- Initial AI integration

### Phase 2: Content Integration (Weeks 5-8)
**Milestone 2.1: Content Processing Pipeline**
- Week 5: Video upload and processing
- Week 6: OCR for handwritten notes
- Week 7: PDF processing for assignments
- Week 8: Dataset ingestion and storage

**Milestone 2.2: AI Enhancement**
- RAG pipeline implementation
- Vector database setup
- Embedding generation
- Context retrieval optimization

### Phase 3: Feature Completion (Weeks 9-12)
**Milestone 3.1: Interactive Features**
- Week 9: Quiz system with auto-grading
- Week 10: Coding environment integration
- Week 11: Video annotation system
- Week 12: Progress tracking analytics

**Milestone 3.2: AI Tutor Refinement**
- Multi-turn conversation support
- Context-aware responses
- Source citation
- Response quality improvement

### Phase 4: Testing & Deployment (Weeks 13-16)
**Milestone 4.1: Quality Assurance**
- Week 13: Comprehensive testing
- Week 14: Performance optimization
- Week 15: Security audit
- Week 16: User acceptance testing

**Milestone 4.2: Production Launch**
- Production environment setup
- Data migration
- Soft launch with limited users
- Full production release

---

## 5. Risk Analysis & Mitigation

### 5.1 Technical Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| **AI hallucination** | High | Medium | Implement RAG with source verification, add confidence scores |
| **OCR accuracy issues** | Medium | High | Use multiple OCR engines, manual verification for key content |
| **Scalability challenges** | High | Medium | Design for horizontal scaling, implement caching, use CDN |
| **Data privacy concerns** | High | Low | Encryption, secure storage, compliance with data protection laws |
| **Integration complexity** | Medium | High | Use well-documented APIs, comprehensive testing, modular design |

### 5.2 Project Risks

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|---------------------|
| **Scope creep** | High | Medium | Strict change control process, prioritization framework |
| **Resource constraints** | High | Low | Cross-training team members, flexible resource allocation |
| **Timeline delays** | Medium | Medium | Buffer time in schedule, agile methodology, regular reviews |
| **Budget overruns** | Medium | Low | Detailed cost tracking, cloud cost optimization, monthly reviews |

---

## 6. Success Criteria

### 6.1 Quantitative Metrics

#### Performance Metrics
- **Response Time**: AI response < 3 seconds for 95% of queries
- **System Uptime**: 99.5% availability
- **Concurrent Users**: Support 1000+ simultaneous users
- **Content Processing**: Process 100+ videos/day

#### Quality Metrics
- **Answer Accuracy**: >85% accuracy on domain-specific questions
- **User Satisfaction**: >4.0/5.0 rating
- **Content Coverage**: 80%+ syllabus topics covered
- **Quiz Completion Rate**: >60% of started quizzes completed

#### Engagement Metrics
- **Daily Active Users**: 500+ students
- **Session Duration**: Average 30+ minutes
- **Return Rate**: 70%+ weekly return rate
- **Feature Adoption**: 50%+ users try coding environment

### 6.2 Qualitative Criteria

#### User Experience
- Intuitive interface requiring minimal training
- Smooth, responsive interactions
- Clear, understandable AI responses
- Helpful error messages and guidance

#### Content Quality
- Accurate digitization of handwritten notes
- Properly annotated video content
- Relevant quiz questions aligned with topics
- Working code examples with explanations

#### System Reliability
- Graceful error handling
- Data consistency across services
- Secure authentication and authorization
- Regular backups and disaster recovery

---

## 7. Stakeholder Analysis

### 7.1 Primary Stakeholders

#### **Students**
- **Interest**: Better learning outcomes, exam preparation
- **Expectations**: Accurate answers, helpful explanations, easy-to-use interface
- **Engagement**: User testing, feedback surveys, usage analytics

#### **Faculty/Instructors**
- **Interest**: Enhanced teaching tools, student progress insights
- **Expectations**: Quality content, accurate information, progress reports
- **Engagement**: Content validation, curriculum alignment review

#### **Institution Administration**
- **Interest**: Improved student performance, competitive advantage
- **Expectations**: ROI demonstration, adoption metrics, positive feedback
- **Engagement**: Executive updates, strategic planning sessions

### 7.2 Secondary Stakeholders

#### **Technical Team**
- **Interest**: Clean architecture, maintainable code, modern tech stack
- **Expectations**: Clear requirements, reasonable timelines, proper documentation
- **Engagement**: Sprint planning, technical reviews, retrospectives

#### **Content Creators**
- **Interest**: Proper attribution, content organization, quality presentation
- **Expectations**: Accurate transcription, preserved context, accessibility
- **Engagement**: Content review sessions, quality feedback

---

## 8. Assumptions & Constraints

### 8.1 Assumptions

- Students have reliable internet access (minimum 5 Mbps)
- Institutional email addresses are available for authentication
- Source content (videos, notes, datasets) are available in digital format
- Users have modern browsers (Chrome 90+, Firefox 88+, Safari 14+)
- Basic programming knowledge for coding environment features
- English is the primary language of instruction

### 8.2 Constraints

#### Technical Constraints
- Must work with existing institutional IT infrastructure
- API rate limits from LLM providers
- Storage costs must remain within budget
- Processing time for OCR and video annotation
- Browser compatibility requirements

#### Business Constraints
- Budget limitations for cloud services
- Timeline for PoC demonstration (16 weeks)
- Availability of subject matter experts for validation
- Compliance with educational data privacy regulations

#### Operational Constraints
- Limited to specified subjects initially (SS, DSP, PR, MBSA)
- Dependence on quality of source materials
- Manual verification required for critical content
- Support hours limited to institutional working hours (Phase 1)

---

## 9. Compliance & Legal Considerations

### 9.1 Data Protection
- **GDPR Compliance**: For any European students
- **Student Data Privacy**: Protection of personal information
- **Consent Management**: Clear opt-in for data collection
- **Data Retention**: Policies for storing student progress data

### 9.2 Content Rights
- **Copyright Compliance**: Proper licensing for all content
- **Attribution Requirements**: Credit for source materials
- **Fair Use**: Educational use justification
- **User-Generated Content**: Terms of service for submissions

### 9.3 Accessibility
- **WCAG 2.1 AA Compliance**: Web accessibility standards
- **Screen Reader Support**: For visually impaired students
- **Keyboard Navigation**: Full functionality without mouse
- **Captions**: For all video content

---

## Summary

This planning phase establishes the foundation for Saarthi.ai PoC development. Key achievements:

✅ **Clearly defined scope** with measurable objectives
✅ **Identified resources** including team structure and technology stack
✅ **Established timeline** with concrete milestones
✅ **Risk mitigation strategies** for technical and project challenges
✅ **Success criteria** for measuring PoC effectiveness
✅ **Stakeholder alignment** through comprehensive analysis

**Next Steps**: Proceed to Stage 2 - Defining Requirements (Functional & Technical)

---

*Document Version: 1.0*  
*Last Updated: February 2, 2026*  
*Status: APPROVED FOR REQUIREMENTS PHASE*
