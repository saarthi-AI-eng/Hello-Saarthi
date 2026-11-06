import { useEffect, type ReactElement } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import AppShell from './components/layout/AppShell';
import AIChatbot from './components/AIChatbot';
import { ToastProvider } from './components/Toast';
import LandingPage from './pages/Landing';
import LoginPage from './pages/auth/Login';
import SignupPage from './pages/auth/Signup';
import DashboardPage from './pages/Dashboard';
import CoursesPage from './pages/Courses';
import CourseDetailPage from './pages/CourseDetail';
import ChatPage from './pages/Chat';
import QuizPage from './pages/Quiz';
import CodeLabPage from './pages/CodeLab';
import VideosPage from './pages/Videos';
import VideoPlayerPage from './pages/VideoPlayer';
import ProgressPage from './pages/Progress';
import StudyMaterialPage from './pages/StudyMaterial';
import SearchPage from './pages/Search';
import SettingsPage from './pages/settings/Settings';
import { useAuthStore } from './stores/auth.store';
import './stores/settings.store'; // Initialize settings (theme/font) on load

function App() {
  const restoreSession = useAuthStore((s) => s.restoreSession);
  const clearSession = useAuthStore((s) => s.clearSession);
  useEffect(() => {
    restoreSession();
    const onAuthExpired = () => clearSession();
    window.addEventListener('saarthi:auth-expired', onAuthExpired);
    return () => window.removeEventListener('saarthi:auth-expired', onAuthExpired);
  }, [restoreSession, clearSession]);

  return (
    <BrowserRouter basename="/Saarthi_-Documentation">
      <ToastProvider>
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
        <Route path="/signup" element={<PublicOnly><SignupPage /></PublicOnly>} />

        {/* App Routes (with Sidebar + Topbar layout) */}
        <Route element={<ProtectedLayout />}>
          <Route path="/dashboard" element={<StudentOnly><DashboardPage /></StudentOnly>} />
          <Route path="/courses" element={<CoursesPage />} />
          <Route path="/join" element={<JoinRedirect />} />
          <Route path="/courses/join" element={<JoinRedirect />} />
          <Route path="/courses/:id" element={<CourseDetailPage />} />
          <Route path="/chat" element={<StudentOnly><ChatPage /></StudentOnly>} />
          <Route path="/quiz" element={<StudentOnly><QuizPage /></StudentOnly>} />
          <Route path="/code-lab" element={<StudentOnly><CodeLabPage /></StudentOnly>} />
          <Route path="/videos" element={<VideosPage />} />
          <Route path="/videos/:id" element={<VideoPlayerPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/notes" element={<Navigate to="/study-material" replace />} />
          <Route path="/study-material" element={<StudentOnly><StudyMaterialPage /></StudentOnly>} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {/* Global Floating AI Chatbot - visible on all pages */}
      <GlobalChatbot />
      </ToastProvider>
    </BrowserRouter>
  );
}

function ProtectedLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isRestoring = useAuthStore((s) => s.isRestoring);
  if (isRestoring) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <AppShell />;
}

function PublicOnly({ children }: { children: ReactElement }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isRestoring = useAuthStore((s) => s.isRestoring);
  if (isRestoring) return null;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return children;
}

/** Invite links (/join?code=…) hand the code to the Courses page, which joins automatically. */
function JoinRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/courses${search}`} replace />;
}

/** Student-only pages: teachers land on their class analytics instead. */
function StudentOnly({ children }: { children: ReactElement }) {
  const role = useAuthStore((s) => s.user?.role);
  if (role === 'teacher') return <Navigate to="/progress" replace />;
  return children;
}

function GlobalChatbot() {
  const location = useLocation();
  const role = useAuthStore((s) => s.user?.role);
  if (role === 'teacher') return null;
  if (location.pathname === '/login' || location.pathname === '/signup') return null;
  return <AIChatbot />;
}

export default App;
