import React, { useState } from 'react';
import './App.css';
import WindowPane from './components/WindowPane';
import TerminalInput from './components/TerminalInput';
import ProgressBar from './components/ProgressBar';
import TypewriterText from './components/TypewriterText';

function App() {
  const [history, setHistory] = useState([
    { type: 'system', text: 'NUNMAI OS v1.0.0 initializing...' },
    { type: 'system', text: 'Connecting to CENTRAL ORCHESTRATION API... [OK]' }
  ]);

  const handleCommand = (cmd) => {
    setHistory(prev => [...prev, { type: 'user', text: `root@nunmai:~$ ${cmd}` }]);
    
    // Simple command parser for mockup
    setTimeout(() => {
      let response = '';
      if (cmd.toLowerCase() === 'help') {
        response = 'AVAILABLE COMMANDS: fetch latest_risks, analyze mail_01, verify source @user';
      } else if (cmd.toLowerCase().startsWith('analyze')) {
        response = `[OK] Initiating Deepfake Analysis on ${cmd.split(' ')[1]}... Confidence: 98% (SYNTHETIC)`;
      } else {
        response = `[ERR] Command not found: ${cmd}`;
      }
      setHistory(prev => [...prev, { type: 'system', text: response }]);
    }, 500);
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <div className="header-pane">
        <div>
          <span>NUNMAI: CENTRAL ORCHESTRATION</span>
        </div>
        <div className="flex-row gap-lg" style={{ color: 'var(--fg-secondary)' }}>
          <span>MAIL [OK]</span>
          <span>VISION [OK]</span>
          <span>VOICE [OK]</span>
          <span>SOCIAL [OK]</span>
          <span>VERIFY [OK]</span>
        </div>
      </div>

      {/* Left Sidebar */}
      <div className="sidebar-pane">
        <WindowPane title="NAVIGATION">
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <li><a href="#">&gt; INVESTOR PORTAL</a></li>
            <li><a href="#">&gt; BROKER DASHBOARD</a></li>
            <li><a href="#">&gt; REGTECH DASHBOARD</a></li>
            <li style={{ color: 'var(--fg-secondary)' }}>&gt; THREAT TIMELINE</li>
          </ul>
        </WindowPane>
      </div>

      {/* Main Center Area */}
      <div className="main-pane">
        <div className="flex-row gap-md" style={{ flex: 1 }}>
          <WindowPane title="UNIFIED RISK SCORE" style={{ flex: 1 }}>
            <div className="flex-col gap-sm" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <pre style={{ fontSize: '3rem', margin: 0, color: 'var(--fg-error)' }}>
                {` 87 `}
              </pre>
              <div style={{ color: 'var(--fg-error)' }}>[HIGH RISK DETECTED]</div>
            </div>
          </WindowPane>
          <WindowPane title="EXPLAINABLE AI" style={{ flex: 2 }}>
            <div className="flex-col gap-sm">
              <div>TARGET: MAIL_01</div>
              <div>CLASSIFICATION: PHISHING</div>
              <div>MODEL: RoBERTa + DistilBERT Ensemble</div>
              <div>URL RISK: <ProgressBar percent={90} /></div>
              <div>NLP URGENCY: <ProgressBar percent={85} /></div>
              <br />
              <div style={{ color: 'var(--fg-secondary)' }}>
                <TypewriterText text="WARNING: Unverified sender domain detected (SPF/DKIM failed). AI-text signal indicates high perplexity consistent with LLM generation." delay={20} />
              </div>
            </div>
          </WindowPane>
        </div>
        <WindowPane title="THREAT TIMELINE" style={{ flex: 1 }}>
          <div className="flex-col gap-sm">
            <div>14:02:11 [WARN] Synthetic Voice Detected - Confidence 92% (Caller Not Verified)</div>
            <div>14:05:30 [INFO] Social Media Post Analyzed - Source Verified (Authentic)</div>
            <div style={{ color: 'var(--fg-error)' }}>14:10:45 [CRIT] Deepfake Video Flagged! Blinking/Lip Sync anomalies detected.</div>
          </div>
        </WindowPane>
      </div>

      {/* Bottom Console */}
      <div className="console-pane">
        <WindowPane title="TERMINAL">
          <div className="flex-col gap-sm" style={{ height: '100%' }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {history.map((line, i) => (
                <div key={i} style={{ color: line.type === 'user' ? 'var(--fg-secondary)' : 'var(--fg-primary)' }}>
                  {line.text}
                </div>
              ))}
            </div>
            <TerminalInput onSubmit={handleCommand} />
          </div>
        </WindowPane>
      </div>
    </div>
  );
}

export default App;
