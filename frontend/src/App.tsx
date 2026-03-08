import { type ReactNode, Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from './stores/useAuthStore';
import { Spin } from 'antd';
import MainLayout from './components/layout/MainLayout';

// 懒加载页面
const Login = lazy(() => import('./pages/auth/Login'));
const Bookshelf = lazy(() => import('./pages/student/Bookshelf'));
const TodayTasks = lazy(() => import('./pages/student/TodayTasks'));
const Outline = lazy(() => import('./pages/student/Outline'));
const StudyCabin = lazy(() => import('./pages/student/StudyCabin'));
const KnowledgeForest = lazy(() => import('./pages/student/KnowledgeForest'));
const MistakeHub = lazy(() => import('./pages/student/MistakeHub'));
const StudyPlan = lazy(() => import('./pages/student/StudyPlan'));
const ParentReport = lazy(() => import('./pages/parent/ParentReport'));
const Profile = lazy(() => import('./pages/student/Profile'));
const Diagnostic = lazy(() => import('./pages/student/Diagnostic'));
const Exam = lazy(() => import('./pages/student/Exam'));
const ScoreReport = lazy(() => import('./pages/student/ScoreReport'));

const ProtectedRoute = ({ children }: { children: ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
};

const FallbackLoading = () => (
  <div className="flex items-center justify-center min-h-screen">
    <Spin size="large" />
  </div>
);

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<FallbackLoading />}>
        <Routes>
          {/* 公开路由 */}
          <Route path="/login" element={<Login />} />

          {/* 鉴权路由组 */}
          <Route path="/" element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }>
            <Route index element={<Navigate to="/today" replace />} />
            <Route path="bookshelf" element={<Bookshelf />} />
            <Route path="today" element={<TodayTasks />} />
            <Route path="outline/:materialId" element={<Outline />} />
            <Route path="cabin/:sessionId" element={<StudyCabin />} />
            <Route path="forest/:materialId" element={<KnowledgeForest />} />
            <Route path="mistakes" element={<MistakeHub />} />
            <Route path="plan/:materialId" element={<StudyPlan />} />
            <Route path="report" element={<ParentReport />} />
            <Route path="profile" element={<Profile />} />
            <Route path="diagnostic/:materialId" element={<Diagnostic />} />
            <Route path="exam/:examId" element={<Exam />} />
            <Route path="score/:examId" element={<ScoreReport />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
