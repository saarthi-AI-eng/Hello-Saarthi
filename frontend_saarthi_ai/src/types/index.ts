// ============================================
// Saarthi.ai - Core TypeScript Types
// ============================================

// --- User Types ---
export interface User {
    _id: string;
    name: string;
    email: string;
    role: 'student' | 'instructor' | 'admin';
    avatar?: string;
    institute?: string;
    bio?: string;
    streak: number;
    totalStudyTime: number;
    enrolledCourses: string[];
    createdAt: string;
}

export interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    login: (email: string, password: string) => Promise<void>;
    signup: (data: SignupData) => Promise<void>;
    logout: () => void;
    setUser: (user: User) => void;
}

export interface SignupData {
    name: string;
    email: string;
    password: string;
    institute?: string;
}

// --- Course Types ---
export interface Course {
    _id: string;
    title: string;
    code: string;
    description: string;
    instructor: string;
    thumbnail?: string;
    category: string;
    difficulty: 'Beginner' | 'Intermediate' | 'Advanced';
    duration: string;
    lessonsCount: number;
    rating: number;
    studentsEnrolled: number;
    modules: Module[];
    tags: string[];
    createdAt: string;
}

export interface Module {
    _id: string;
    title: string;
    lessons: Lesson[];
    duration: string;
}

export interface Lesson {
    _id: string;
    title: string;
    type: 'video' | 'reading' | 'quiz' | 'assignment';
    duration: string;
    isLocked: boolean;
    isCompleted: boolean;
}

// --- Video Types ---
export interface Video {
    _id: string;
    title: string;
    description: string;
    url: string;
    thumbnail: string;
    duration: string;
    courseCode: string;
    courseName: string;
    progress: number;
    views: number;
}

// --- Quiz Types ---
export interface Quiz {
    _id: string;
    title: string;
    courseCode: string;
    courseName: string;
    questionsCount: number;
    duration: number; // in minutes
    difficulty: 'Easy' | 'Medium' | 'Hard';
    bestScore?: number;
    attempts: number;
}

export interface Question {
    _id: string;
    text: string;
    options: string[];
    correctAnswer: number;
    explanation: string;
    difficulty: 'Easy' | 'Medium' | 'Hard';
    tags: string[];
}

export interface QuizResult {
    quizId: string;
    score: number;
    totalQuestions: number;
    timeTaken: number;
    answers: { questionId: string; selected: number; isCorrect: boolean }[];
    date: string;
}

// --- Chat Types ---
export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    sources?: Source[];
}

export interface Source {
    id: string;
    title: string;
    type: 'video' | 'note' | 'textbook';
    url?: string;
}

// --- Progress Types ---
export interface ProgressData {
    coursesEnrolled: number;
    coursesCompleted: number;
    quizzesTaken: number;
    averageScore: number;
    studyStreak: number;
    totalStudyTime: number;
    weeklyStudyData: { day: string; hours: number }[];
    subjectProgress: { subject: string; progress: number; color: string }[];
    recentActivity: ActivityItem[];
}

export interface ActivityItem {
    id: string;
    type: 'quiz' | 'video' | 'course' | 'assignment' | 'achievement';
    title: string;
    description: string;
    timestamp: string;
    icon: string;
}

// --- Dashboard Types ---
export interface DashboardStats {
    coursesEnrolled: number;
    pendingAssignments: number;
    avgQuizScore: number;
    studyTimeThisWeek: string;
}

export interface Deadline {
    id: string;
    title: string;
    courseName: string;
    dueDate: string;
    type: 'assignment' | 'quiz' | 'project';
    urgency: 'high' | 'medium' | 'low';
}

// --- Settings Types ---
export interface UserSettings {
    theme: 'light' | 'dark' | 'auto';
    fontSize: 'small' | 'medium' | 'large';
    language: string;
    timezone: string;
    notifications: {
        courseUpdates: boolean;
        newAssignments: boolean;
        quizReminders: boolean;
        marketingEmails: boolean;
        weeklyReport: boolean;
    };
    privacy: {
        profileVisibility: 'public' | 'private';
        showProgress: boolean;
    };
}
