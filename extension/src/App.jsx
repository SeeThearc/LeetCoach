import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom/client';
import Markdown from 'react-markdown';

const API = 'http://localhost:8000/api/v1';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [slug, setSlug] = useState('');
  const [title, setTitle] = useState('');
  const [language, setLanguage] = useState('cpp');
  const [sessionId] = useState(crypto.randomUUID());
  const bottomRef = useRef(null);

  // On mount: ask the content script for problem data
  useEffect(() => {
    async function loadProblem() {
      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab?.id) {
          const data = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PROBLEM_DATA' });
          if (data?.slug) {
            setSlug(data.slug);
            setLanguage(data.language || 'python');
            // Use slug as a readable title until backend gives us the real one
            setTitle(data.slug.replace(/-/g, ' '));
          }
        }
      } catch {
        // Not on a LeetCode page — that's fine
      }
    }
    loadProblem();
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Send message to our backend
  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    // Add user message to the chat
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    try {
      // Get fresh code from the editor (user might have changed it)
      let userCode = '';
      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (tab?.id) {
          const data = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PROBLEM_DATA' });
          userCode = data?.code || '';
        }
      } catch { /* ignore */ }

      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          problem_slug: slug || 'two-sum',
          session_id: sessionId,
          language: language,
          user_code: userCode,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || 'Server error');
      }

      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
      if (data.problem_title) setTitle(data.problem_title);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `⚠️ Error: ${err.message}. Is the backend running?` },
      ]);
    }

    setLoading(false);
  }

  return (
    <div className="app">
      {/* Header */}
      <div className="header">
        <h1>🤖 AI LeetCode Coach</h1>
        {title && <span className="problem-tag">{title}</span>}
      </div>

      {/* Not on LeetCode warning */}
      {!slug && (
        <div className="not-leetcode">
          Navigate to a LeetCode problem to auto-detect it, or just type below.
        </div>
      )}

      {/* Messages */}
      <div className="messages">
        {messages.length === 0 && (
          <div className="welcome">
            <div className="emoji">🧠</div>
            <h2>Ready to learn!</h2>
            <p>
              I'll teach you how to solve problems — not just give you answers.
              Ask me to explain a concept, give you a hint, or review your code.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.role === 'assistant' ? (
              <Markdown>{msg.content}</Markdown>
            ) : (
              msg.content
            )}
          </div>
        ))}

        {loading && <div className="thinking">Thinking</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="input-area">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Ask me about this problem..."
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}

// Mount React into the page
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
