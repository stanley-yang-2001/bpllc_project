import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedLayout } from "./auth/ProtectedRoute";
import Home from "./routes/Home";
import Login from "./routes/Login";
import Privacy from "./routes/Privacy";
import { ComingSoon, NotFound } from "./routes/Placeholder";
import Settings from "./routes/Settings";
import Vocabulary from "./routes/Vocabulary";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/privacy" element={<Privacy />} />
      <Route element={<ProtectedLayout />}>
        <Route index element={<Home />} />
        <Route path="vocabulary" element={<Vocabulary />} />
        <Route path="settings" element={<Settings />} />
        <Route path="chat" element={<ComingSoon title="Chat" milestone="M5" note="Needs the Langflow per-user check (M0) first." />} />
        <Route path="studio" element={<ComingSoon title="Story Studio" milestone="M6" note="Needs tutor_core extraction (M3)." />} />
        <Route path="library" element={<ComingSoon title="Library" milestone="M7" note="Saved stories arrive with Story Studio." />} />
        <Route path="practice" element={<ComingSoon title="Practice" milestone="M7" note="Flashcards and cloze exercises." />} />
        <Route path="home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
