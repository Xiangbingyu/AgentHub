import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Chat from './pages/Chat/Chat';
import Team from './pages/Team/Team';
import Workspace from './pages/Workspace/Workspace';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/session" replace />} />
          <Route path="session" element={<Chat />} />
          <Route path="chat" element={<Navigate to="/session" replace />} />
          <Route path="workspace" element={<Workspace />} />
          <Route path="team" element={<Team />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
