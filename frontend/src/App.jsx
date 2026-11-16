import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainApp from './pages/MainApp';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainApp defaultTab="home" />} />
        <Route path="/route" element={<MainApp defaultTab="route" />} />
        <Route path="/system" element={<MainApp defaultTab="system" />} />
        <Route path="/live" element={<MainApp defaultTab="live" />} />
        <Route path="/signals" element={<MainApp defaultTab="signals" />} />
        <Route path="/dashboard" element={<MainApp defaultTab="signals" />} />
        <Route path="/detection" element={<MainApp defaultTab="live" />} />
        <Route path="/progress" element={<MainApp defaultTab="progress" />} />
        <Route path="*" element={<MainApp defaultTab="home" />} />
      </Routes>
    </BrowserRouter>
  );
}
