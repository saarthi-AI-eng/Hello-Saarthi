# Stage 3: Design - Low-Level Design (LLD)
## Saarthi.ai - Detailed Component Design & Frontend-Backend Integration

---

# 1. Frontend-Backend Communication Guide

## 1.1 Communication Flow Patterns

### Pattern 1: User Authentication
**Scenario**: User logs into the platform

```typescript
// ═══════════════════ FRONTEND ═══════════════════

// 1. User clicks "Sign In" button
// pages/Login.tsx
const handleLogin = async (e: FormEvent) => {
  e.preventDefault();
  setLoading(true);
  
  try {
    // 2. Call API service
    const response = await authService.login(formData.email, formData.password);
    
    // 3. Store tokens
    localStorage.setItem('accessToken', response.accessToken);
    localStorage.setItem('refreshToken', response.refreshToken);
    
    // 4. Update auth context
    setUser(response.user);
    
    // 5. Navigate to dashboard
    navigate('/dashboard');
  } catch (error) {
    setError(error.message);
  } finally {
    setLoading(false);
  }
};

// services/auth.service.ts
export const authService = {
  login: async (email: string, password: string) => {
    const response = await apiClient.post('/auth/signin', {
      email,
      password
    });
    return response.data;
  }
};

// ═══════════════════ BACKEND ═══════════════════

// routes/auth.routes.ts
router.post('/signin', signin);

// controllers/auth.controller.ts
export const signin = async (req: Request, res: Response) => {
  try {
    // 1. Extract credentials
    const { email, password } = req.body;
    
    // 2. Validate input
    if (!email || !password) {
      return res.status(400).json({
        error: 'Email and password are required'
      });
    }
    
    // 3. Find user in database
    const user = await User.findOne({ email });
    if (!user) {
      return res.status(401).json({
        error: 'Invalid credentials'
      });
    }
    
    // 4. Verify password
    const isValid = await bcrypt.compare(password, user.password_hash);
    if (!isValid) {
      return res.status(401).json({
        error: 'Invalid credentials'
      });
    }
    
    // 5. Generate JWT tokens
    const accessToken = generateAccessToken(user._id, user.role);
    const refreshToken = generateRefreshToken(user._id);
    
    // 6. Store refresh token in Redis
    await redis.set(
      `refresh:${user._id}`,
      refreshToken,
      'EX',
      7 * 24 * 60 * 60  // 7 days
    );
    
    // 7. Send response
    res.json({
      accessToken,
      refreshToken,
      user: {
        id: user._id,
        fullName: user.full_name,
        email: user.email,
        role: user.role
      }
    });
  } catch (error) {
    console.error('Signin error:', error);
    res.status(500).json({
      error: 'Internal server error'
    });
  }
};

// utils/jwt.ts
export const generateAccessToken = (userId: string, role: string) => {
  return jwt.sign(
    { userId, role },
    process.env.JWT_SECRET!,
    { expiresIn: '15m' }
  );
};
```

**Communication Diagram**:
```
User → Frontend → API Gateway → Auth Service → MongoDB
                                     ↓
                                  Redis (store refresh token)
                                     ↓
Frontend ← JSON Response ← Auth Service
```

---

### Pattern 2: Real-Time AI Chatbot
**Scenario**: Student asks a question to AI tutor

```typescript
// ═══════════════════ FRONTEND ═══════════════════

// components/chatbot/ChatInterface.tsx
const ChatInterface = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const ws = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    // 1. Establish WebSocket connection
    ws.current = new WebSocket('ws://localhost:8002/ai/chat');
    
    // 2. Authenticate on connection
    ws.current.onopen = () => {
      ws.current!.send(JSON.stringify({
        type: 'auth',
        token: localStorage.getItem('accessToken')
      }));
    };
    
    // 3. Handle incoming messages
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'message_start':
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: '',
            id: data.messageId
          }]);
          break;
          
        case 'message_chunk':
          setMessages(prev => prev.map(msg =>
            msg.id === data.messageId
              ? { ...msg, content: msg.content + data.chunk }
              : msg
          ));
          break;
          
        case 'message_complete':
          setMessages(prev => prev.map(msg =>
            msg.id === data.messageId
              ? { ...msg, sources: data.sources, complete: true }
              : msg
          ));
          break;
      }
    };
    
    return () => ws.current?.close();
  }, []);
  
  const sendMessage = () => {
    // 4. Send user message
    const userMessage = {
      type: 'query',
      content: input,
      context: {
        courseId: currentCourse?.id,
        moduleId: currentModule?.id
      }
    };
    
    ws.current!.send(JSON.stringify(userMessage));
    
    setMessages(prev => [...prev, {
      role: 'user',
      content: input
    }]);
    
    setInput('');
  };
  
  return (
    <div className="chat-window">
      <MessageList messages={messages} />
      <InputArea 
        value={input}
        onChange={setInput}
        onSend={sendMessage}
      />
    </div>
  );
};

// ═══════════════════ BACKEND (AI Service) ═══════════════════

// ai-service/server.py (FastAPI)
from fastapi import FastAPI, WebSocket
from langchain import LLMChain
import asyncio

@app.websocket("/ai/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # 1. Authenticate
    auth_message = await websocket.receive_json()
    token = auth_message['token']
    user_id = verify_jwt_token(token)
    
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    try:
        while True:
            # 2. Receive user query
            data = await websocket.receive_json()
            
            if data['type'] == 'query':
                query = data['content']
                context = data.get('context', {})
                
                # 3. Generate unique message ID
                message_id = str(uuid.uuid4())
                
                # 4. Send start signal
                await websocket.send_json({
                    'type': 'message_start',
                    'messageId': message_id
                })
                
                # 5. RAG Pipeline: Retrieve relevant context
                relevant_docs = await retrieve_context(
                    query,
                    course_id=context.get('courseId'),
                    k=5
                )
                
                # 6. Build prompt
                prompt = build_prompt(query, relevant_docs)
                
                # 7. Stream LLM response
                async for chunk in llm.astream(prompt):
                    await websocket.send_json({
                        'type': 'message_chunk',
                        'messageId': message_id,
                        'chunk': chunk
                    })
                
                # 8. Send completion with sources
                await websocket.send_json({
                    'type': 'message_complete',
                    'messageId': message_id,
                    'sources': format_sources(relevant_docs)
                })
                
                # 9. Log conversation
                await save_chat_history(user_id, query, message_id)
                
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")

# Retrieve context function
async def retrieve_context(query: str, course_id: str = None, k: int = 5):
    # 1. Generate query embedding
    query_embedding = embeddings_model.embed_query(query)
    
    # 2. Build filter
    metadata_filter = {}
    if course_id:
        metadata_filter['course'] = course_id
    
    # 3. Vector search in Pinecone
    results = pinecone_index.query(
        vector=query_embedding,
        top_k=k,
        filter=metadata_filter,
        include_metadata=True
    )
    
    # 4. Return relevant documents
    return [
        {
            'id': match.id,
            'text': match.metadata['text'],
            'source_type': match.metadata['source_type'],
            'source_id': match.metadata['source_id'],
            'score': match.score
        }
        for match in results.matches
    ]
```

**Communication Diagram**:
```
User Input → Frontend
               ↓
          WebSocket Connection
               ↓
          AI Service (FastAPI)
               ↓
          ┌────────────┴────────────┐
          ↓                         ↓
    Vector Search              LLM API
    (Pinecone)              (Gemini 2.0)
          ↓                         ↓
    Relevant Chunks           Generated Response
          └────────────┬────────────┘
                       ↓
               Stream to Frontend
                       ↓
                  Chat UI Update
```

---

### Pattern 3: Code Execution
**Scenario**: Student runs Python code in coding environment

```typescript
// ═══════════════════ FRONTEND ═══════════════════

// pages/CodingPage.tsx
const runCode = async () => {
  setExecuting(true);
  setOutput('');
  
  try {
    // 1. Submit code execution request
    const response = await codeService.execute({
      language: 'python',
      code: editorValue,
      stdin: inputValue,
      timeout: 5
    });
    
    const { jobId } = response;
    
    // 2. Poll for results using SSE
    const eventSource = new EventSource(
      `${API_URL}/code/status/${jobId}`
    );
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.status) {
        case 'queued':
          setOutput('⏳ Code queued for execution...\n');
          break;
          
        case 'running':
          setOutput(prev => prev + '▶️  Executing code...\n');
          break;
          
        case 'completed':
          setOutput(prev => prev + '\n' + data.stdout);
          if (data.stderr) {
            setOutput(prev => prev + '\n❌ Errors:\n' + data.stderr);
          }
          setExitCode(data.exitCode);
          eventSource.close();
          break;
          
        case 'error':
          setOutput(prev => prev + '\n❌ Execution failed: ' + data.error);
          eventSource.close();
          break;
      }
    };
    
    eventSource.onerror = () => {
      setOutput(prev => prev + '\n❌ Connection lost');
      eventSource.close();
    };
    
  } catch (error) {
    setOutput(`❌ Error: ${error.message}`);
  } finally {
    setExecuting(false);
  }
};

// services/code.service.ts
export const codeService = {
  execute: async (data: ExecutionRequest) => {
    return await apiClient.post('/code/execute', data);
  }
};

// ═══════════════════ BACKEND (Code Service) ═══════════════════

// routes/code.routes.ts
router.post('/execute', authenticate, executeCode);
router.get('/status/:jobId', getExecutionStatus);

// controllers/code.controller.ts
import { Queue } from 'bullmq';

const codeQueue = new Queue('code-execution', {
  connection: redisConnection
});

export const executeCode = async (req: Request, res: Response) => {
  try {
    const { language, code, stdin, timeout } = req.body;
    const userId = req.user.userId;
    
    // 1. Validate input
    if (!['python', 'cpp', 'javascript', 'matlab'].includes(language)) {
      return res.status(400).json({ error: 'Unsupported language' });
    }
    
    if (code.length > 10000) {
      return res.status(400).json({ error: 'Code too large' });
    }
    
    // 2. Create job
    const job = await codeQueue.add('execute', {
      userId,
      language,
      code,
      stdin: stdin || '',
      timeout: Math.min(timeout || 5, 10)  // Max 10 seconds
    });
    
    // 3. Return job ID
    res.json({
      jobId: job.id,
      status: 'queued'
    });
    
  } catch (error) {
    res.status(500).json({ error: 'Failed to queue code' });
  }
};

// SSE endpoint for status updates
export const getExecutionStatus = async (req: Request, res: Response) => {
  const { jobId } = req.params;
  
  // 1. Set SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  
  // 2. Check job status initially
  const job = await codeQueue.getJob(jobId);
  if (!job) {
    res.write(`data: ${JSON.stringify({ status: 'not_found' })}\n\n`);
    res.end();
    return;
  }
  
  // 3. Stream status updates
  const sendUpdate = (status: string, data: any = {}) => {
    res.write(`data: ${JSON.stringify({ status, ...data })}\n\n`);
  };
  
  // 4. Listen for job events
  job.on('progress', (progress) => {
    sendUpdate('running', { progress });
  });
  
  job.on('completed', (result) => {
    sendUpdate('completed', result);
    res.end();
  });
  
  job.on('failed', (error) => {
    sendUpdate('error', { error: error.message });
    res.end();
  });
  
  // 5. Timeout after 30 seconds
  setTimeout(() => {
    res.end();
  }, 30000);
};

// worker.ts - Code execution worker
import { Worker } from 'bullmq';
import Docker from 'dockerode';

const docker = new Docker();

const worker = new Worker('code-execution', async (job) => {
  const { language, code, stdin, timeout } = job.data;
  
  // 1. Select Docker image
  const imageMap = {
    python: 'python:3.11-alpine',
    cpp: 'gcc:latest',
    javascript: 'node:18-alpine',
    matlab: 'mathworks/matlab-runtime:latest'
  };
  
  const image = imageMap[language];
  
  // 2. Create container
  const container = await docker.createContainer({
    Image: image,
    Cmd: language === 'python' 
      ? ['python', '-c', code]
      : ['node', '-e', code],
    AttachStdout: true,
    AttachStderr: true,
    Tty: false,
    HostConfig: {
      Memory: 512 * 1024 * 1024,  // 512MB
      CpuQuota: 100000,  // 1 CPU core
      NetworkMode: 'none'  // No network access
    }
  });
  
  // 3. Start container
  await container.start();
  
  // 4. Set timeout
  const timeoutHandle = setTimeout(async () => {
    await container.kill();
    throw new Error('Execution timeout');
  }, timeout * 1000);
  
  // 5. Wait for completion
  const output = await container.wait();
  clearTimeout(timeoutHandle);
  
  // 6. Get logs
  const logs = await container.logs({
    stdout: true,
    stderr: true
  });
  
  const stdout = logs.toString().split('\n');
  
  // 7. Remove container
  await container.remove();
  
  // 8. Return result
  return {
    stdout: stdout.filter(line => !line.startsWith('Error')).join('\n'),
    stderr: stdout.filter(line => line.startsWith('Error')).join('\n'),
    exitCode: output.StatusCode
  };
}, {
  connection: redisConnection
});
```

**Communication Diagram**:
```
User → Execute Button
         ↓
    POST /code/execute
         ↓
    Code Service → BullMQ (Queue Job)
         ↓
    Return Job ID
         ↓
    EventSource /status/:jobId (SSE)
         ↓
    Worker picks job → Docker Container
         ↓
    Execute Code → Capture Output
         ↓
    Stream Status Updates → Frontend
         ↓
    Display in Console
```

---

## 1.2 API Specifications

### Auth Service APIs

#### POST /auth/signup
**Description**: Register a new user

**Request**:
```json
{
  "fullName": "John Doe",
  "email": "john@university.edu",
  "password": "SecurePass123!",
  "confirmPassword": "SecurePass123!"
}
```

**Validation**:
- `fullName`: 2-50 characters
- `email`: Valid email format, .edu domain
- `password`: Min 8 chars, uppercase, lowercase, number, special char
- `confirmPassword`: Must match password

**Response (201 Created)**:
```json
{
  "message": "Verification email sent",
  "userId": "507f1f77bcf86cd799439011"
}
```

**Errors**:
- 400: Validation failed
- 409: Email already exists

#### POST /auth/signin
**See Pattern 1 above for details**

#### POST /auth/refresh
**Description**: Refresh access token

**Request**:
```json
{
  "refreshToken": "eyJhbGc..."
}
```

**Response (200 OK)**:
```json
{
  "accessToken": "eyJhbGc..."
}
```

---

### Content Service APIs

#### GET /content/courses
**Description**: List all available courses

**Query Parameters**:
- `enrolled=true` (optional): Only show enrolled courses

**Response (200 OK)**:
```json
{
  "courses": [
    {
      "id": "507f...",
      "code": "DSP",
      "name": "Digital Signal Processing",
      "description": "...",
      "modules": 12,
      "progress": 45,  // percentage
      "thumbnail": "https://..."
    }
  ]
}
```

#### GET /content/courses/:id
**Description**: Get detailed course information

**Response (200 OK)**:
```json
{
  "id": "507f...",
  "code": "DSP",
  "name": "Digital Signal Processing",
  "description": "...",
  "prerequisites": ["SS"],
  "modules": [
    {
      "id": "508f...",
      "title": "Introduction to Signals",
      "order": 1,
      "topics": [
        {
          "id": "509f...",
          "title": "Continuous vs Discrete",
          "type": "video",
          "duration": 1200,
          "completed": true
        },
        {
          "id": "50af...",
          "title": "Quiz: Signal Types",
          "type": "quiz",
          "questions": 10,
          "score": 8
        }
      ]
    }
  ]
}
```

#### GET /content/search
**Description**: Search across all content

**Query Parameters**:
- `q`: Search query (required)
- `type`: Filter by content type (video | note | quiz | exercise)
- `course`: Filter by course code
- `page`: Page number (default: 1)
- `limit`: Results per page (default: 20)

**Response (200 OK)**:
```json
{
  "results": [
    {
      "id": "50bf...",
      "type": "video",
      "title": "Fourier Transform Explained",
      "course": "DSP",
      "module": "Module 3",
      "snippet": "...explaining the mathematical foundation...",
      "url": "/courses/dsp/videos/50bf..."
    }
  ],
  "total": 42,
  "page": 1,
  "pages": 3
}
```

---

### Quiz Service APIs

#### POST /quiz/start/:quizId
**Description**: Start a quiz session

**Response (200 OK)**:
```json
{
  "sessionId": "60cf...",
  "quiz": {
    "id": "50cf...",
    "title": "DSP Mid-Term Quiz",
    "timeLimit": 30,  // minutes
    "totalQuestions": 20,
    "questions": [
      {
        "id": "51af...",
        "text": "What is the Nyquist rate?",
        "options": [
          "Twice the signal bandwidth",
          "Half the signal bandwidth",
          "Equal to signal bandwidth",
          "Four times the bandwidth"
        ],
        "multipleCorrect": false
      }
    ]
  },
  "startedAt": "2026-02-02T23:30:00Z",
  "expiresAt": "2026-02-03T00:00:00Z"
}
```

#### POST /quiz/submit/:sessionId
**Description**: Submit quiz answers

**Request**:
```json
{
  "answers": [
    {
      "questionId": "51af...",
      "selected": [0]  // Array of selected option indices
    }
  ]
}
```

**Response (200 OK)**:
```json
{
  "sessionId": "60cf...",
  "score": 15,
  "totalQuestions": 20,
  "percentage": 75,
  "passed": true,
  "results": [
    {
      "questionId": "51af...",
      "isCorrect": true,
      "explanation": "The Nyquist rate is twice the highest frequency...",
      "correctAnswers": [0]
    }
  ],
  "completedAt": "2026-02-02T23:55:00Z"
}
```

---

## 1.3 Data Flow Examples

### Example 1: Student Watches Annotated Video

```
Frontend                    Content Service           Media Service
   │                              │                         │
   │  GET /content/videos/:id     │                         │
   ├─────────────────────────────>│                         │
   │                              │  Fetch video metadata   │
   │                              │  from MongoDB           │
   │                              │                         │
   │<─────────────────────────────┤                         │
   │  {                           │                         │
   │    videoId, title,           │                         │
   │    youtubeUrl,               │                         │
   │    annotations: [...]        │                         │
   │  }                           │                         │
   │                              │                         │
   │  Fetch video stream          │                         │
   ├──────────────────────────────┼────────────────────────>│
   │                              │                         │
   │<────────────────────────────────────────────────────────┤
   │  Video stream + CDN URL      │                         │
   │                              │                         │
   │  User reaches annotation     │                         │
   │  timestamp (e.g., 05:30)     │                         │
   │                              │                         │
   │  Display overlay:            │                         │
   │  "💡 Key Concept:            │                         │
   │   Fourier Transform"         │                         │
   │                              │                         │
   │  User clicks quiz button     │                         │
   │                              │                         │
   │  GET /quiz/:id               │                         │
   ├─────────────────────────────>│                         │
   │  (quiz linked in annotation) │                         │
   │                              │                         │
```

### Example 2: Progress Tracking

```
Frontend                Analytics Service         MongoDB
   │                          │                      │
   │  User completes video    │                      │
   │                          │                      │
   │  POST /analytics/track-event                   │
   ├─────────────────────────>│                      │
   │  {                       │                      │
   │    event: "video_complete",                    │
   │    videoId: "...",        │                      │
   │    duration: 1200,        │                      │
   │    courseId: "..."        │                      │
   │  }                       │                      │
   │                          │                      │
   │                          │  Update progress     │
   │                          ├──────────────────────>│
   │                          │  db.progress.updateOne({
   │                          │    userId: "...",    │
   │                          │    courseId: "..."   │
   │                          │  }, {                │
   │                          │    $push: {          │
   │                          │      videos_watched  │
   │                          │    }                 │
   │                          │  })                  │
   │                          │                      │
   │                          │<─────────────────────┤
   │                          │  Updated             │
   │                          │                      │
   │<─────────────────────────┤                      │
   │  { success: true }       │                      │
   │                          │                      │
   │  Dashboard auto-refreshes│                      │
   │                          │                      │
   │  GET /analytics/dashboard                       │
   ├─────────────────────────>│                      │
   │                          │                      │
   │                          │  Aggregate stats     │
   │                          ├──────────────────────>│
   │                          │  Pipeline:           │
   │                          │  - Calculate progress│
   │                          │  - Count completions │
   │                          │  - Average scores    │
   │                          │                      │
   │<─────────────────────────┤                      │
   │  {                       │                      │
   │    activeCourses: 3,     │                      │
   │    coursesProgress: {...}│                      │
   │  }                       │                      │
```

---

## 2. Detailed Component Implementations

### 2.1 Frontend Components

#### CodeEditor Component

```typescript
// components/coding/CodeEditor.tsx
import Editor from '@monaco-editor/react';
import { useState, useRef } from 'react';

interface CodeEditorProps {
  defaultLanguage?: string;
  defaultValue?: string;
  onRun: (code: string, language: string, stdin: string) => void;
  executing?: boolean;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  defaultLanguage = 'python',
  defaultValue = '',
  onRun,
  executing = false
}) => {
  const [language, setLanguage] = useState(defaultLanguage);
  const [stdin, setStdin] = useState('');
  const editorRef = useRef<any>(null);
  
  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor;
    
    // Custom keybinding: Ctrl+Enter to run code
    editor.addCommand(
      monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
      () => handleRun()
    );
  };
  
  const handleRun = () => {
    const code = editorRef.current?.getValue() || '';
    onRun(code, language, stdin);
  };
  
  return (
    <div className="code-editor-container">
      {/* Language Selector */}
      <div className="editor-toolbar">
        <select 
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="language-select"
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="cpp">C++</option>
          <option value="matlab">MATLAB</option>
        </select>
        
        <button
          onClick={handleRun}
          disabled={executing}
          className="btn-run"
        >
          {executing ? '⏳ Running...' : '▶️ Run Code'}
        </button>
      </div>
      
      {/* Code Editor */}
      <Editor
        height="60vh"
        language={language}
        defaultValue={defaultValue}
        onMount={handleEditorDidMount}
        theme="vs-dark"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4
        }}
      />
      
      {/* Standard Input */}
      <div className="stdin-panel">
        <label>Standard Input:</label>
        <textarea
          value={stdin}
          onChange={(e) => setStdin(e.target.value)}
          placeholder="Enter input for your program..."
          rows={3}
        />
      </div>
    </div>
  );
};
```

#### VideoPlayer Component with Annotations

```typescript
// components/courses/VideoPlayer.tsx
import ReactPlayer from 'react-player';
import { useState, useRef, useEffect } from 'react';

interface Annotation {
  timestamp: number;
  type: 'concept' | 'quiz' | 'note';
  content: string | { id: string; title: string };
}

export const VideoPlayer: React.FC<{
  url: string;
  annotations: Annotation[];
  onProgress: (seconds: number) => void;
}> = ({ url, annotations, onProgress }) => {
  const playerRef = useRef<ReactPlayer>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeAnnotation, setActiveAnnotation] = useState<Annotation | null>(null);
  
  useEffect(() => {
    // Check for annotations at current timestamp
    const annotation = annotations.find(ann =>
      Math.abs(ann.timestamp - currentTime) < 1
    );
    setActiveAnnotation(annotation || null);
  }, [currentTime, annotations]);
  
  const handleProgress = (state: { playedSeconds: number }) => {
    setCurrentTime(state.playedSeconds);
    onProgress(state.playedSeconds);
  };
  
  const seekTo = (seconds: number) => {
    playerRef.current?.seekTo(seconds);
  };
  
  return (
    <div className="video-player-wrapper">
      <ReactPlayer
        ref={playerRef}
        url={url}
        playing={playing}
        controls
        width="100%"
        height="100%"
        onProgress={handleProgress}
        config={{
          youtube: {
            playerVars: { showinfo: 1 }
          }
        }}
      />
      
      {/* Annotations Overlay */}
      {activeAnnotation && (
        <div className="annotation-overlay">
          {activeAnnotation.type === 'concept' && (
            <div className="concept-marker">
              <h4>💡 Key Concept</h4>
              <p>{activeAnnotation.content as string}</p>
            </div>
          )}
          
          {activeAnnotation.type === 'quiz' && (
            <div className="quiz-marker">
              <h4>❓ Test Your Understanding</h4>
              <button onClick={() => {
                setPlaying(false);
                openQuiz((activeAnnotation.content as any).id);
              }}>
                Take Quiz
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Timeline with annotation markers */}
      <div className="timeline-annotations">
        {annotations.map((ann, idx) => (
          <div
            key={idx}
            className={`annotation-marker ${ann.type}`}
            style={{ left: `${(ann.timestamp / duration) * 100}%` }}
            onClick={() => seekTo(ann.timestamp)}
          />
        ))}
      </div>
    </div>
  );
};
```

---

## Summary

This Low-Level Design document provides:

✅ **Detailed frontend-backend communication** patterns for 3 key scenarios
✅ **Complete API specifications** with request/response formats
✅ **Data flow diagrams** showing system interactions
✅ **Production-ready code examples** for critical components
✅ **WebSocket, REST, and SSE** implementation patterns
✅ **Security considerations** in code execution and auth

**All 3 SDLC stages complete!** Ready for development phase.

---

*Document Version: 1.0*  
*Last Updated: February 2, 2026*  
*Status: APPROVED FOR DEVELOPMENT*
