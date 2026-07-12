import React, { useState, useEffect, useRef } from 'react';
import html2pdf from 'html2pdf.js';
import './App.css';
import WindowPane from './components/WindowPane';
import TerminalInput from './components/TerminalInput';
import ProgressBar from './components/ProgressBar';
import TypewriterText from './components/TypewriterText';
import QRCode from './components/QRCode';
import { MailForm, VisionVoiceForm, SocialForm } from './components/IngestionForms';

function App() {
  const [history, setHistory] = useState([
    { type: 'system', text: 'NUNMAI OS v2.0.0 initializing...' },
    { type: 'system', text: 'Connecting to CENTRAL ORCHESTRATION API... [OK]' },
    { type: 'system', text: 'Select a module from the Navigation to begin ingestion.' }
  ]);

  const [pipelineState, setPipelineState] = useState({
    mail: 'PENDING', vision: 'PENDING', voice: 'PENDING', social: 'PENDING'
  });

  const [activeContext, setActiveContext] = useState(null);
  const [currentView, setCurrentView] = useState('dashboard');
  const [isScanning, setIsScanning] = useState(false);
  
  const reportRef = useRef();
  const terminalEndRef = useRef(null);

  const logToTerminal = (text, type = 'system') => {
    setHistory(prev => [...prev, { type, text }]);
  };

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [history]);

  const handleSelectModule = (moduleName) => {
    setActiveContext(moduleName);
    setCurrentView('ingest');
    logToTerminal(`[SWITCH] Opened ${moduleName.toUpperCase()} ingestion interface.`);
  };

  const handleVerifyAll = () => {
    setActiveContext(null);
    setCurrentView('verify');
    logToTerminal('[SYSTEM] Correlating data from all modules... Executing VERIFY ALL sequence.');
    setTimeout(() => {
      logToTerminal('[OK] Verification complete. Generating Threat Report and Signature.');
    }, 1500);
  };

  const processIngestion = (payload) => {
    const module = activeContext.toUpperCase();
    setIsScanning(true);
    
    // Chunked Terminal Output Simulation
    logToTerminal(`[${module}] Receiving payload stream...`);
    
    setTimeout(() => {
      logToTerminal(`[${module}] Parsing input contracts... [OK]`);
      
      setTimeout(() => {
        if (module === 'MAIL') logToTerminal(`[${module}] Analyzing raw_email_source headers (SPF/DKIM/DMARC)...`);
        else if (module === 'VISION') logToTerminal(`[${module}] Extracting frames from multipart video upload... Done (240 frames).`);
        else if (module === 'VOICE') logToTerminal(`[${module}] Running noise removal on audio buffer...`);
        else if (module === 'SOCIAL') logToTerminal(`[${module}] Evaluating account_created_date & follow-ratio flags...`);
        
        setTimeout(() => {
          logToTerminal(`[${module}] Running primary AI classification ensemble... [||||||||  ] 80%`);
          
          setTimeout(() => {
            logToTerminal(`[${module}] Analysis complete. Threat level registered.`);
            setPipelineState(prev => ({ ...prev, [activeContext]: 'ANALYZED' }));
            setIsScanning(false);
            setActiveContext(null);
            setCurrentView('dashboard');
          }, 1000);
        }, 1200);
      }, 1200);
    }, 800);
  };

  const downloadPDF = () => {
    logToTerminal('[SYSTEM] Compiling PDF Report...');
    const element = reportRef.current;
    const opt = {
      margin:       0.5,
      filename:     'NUNMAI_Threat_Report.pdf',
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true, backgroundColor: '#1e1e1e' },
      jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save().then(() => {
      logToTerminal('[OK] PDF downloaded successfully.');
    });
  };

  const renderActiveForm = () => {
    switch (activeContext) {
      case 'mail': return <MailForm onSubmit={processIngestion} isScanning={isScanning} />;
      case 'vision': return <VisionVoiceForm type="VISION" onSubmit={processIngestion} isScanning={isScanning} />;
      case 'voice': return <VisionVoiceForm type="VOICE" onSubmit={processIngestion} isScanning={isScanning} />;
      case 'social': return <SocialForm onSubmit={processIngestion} isScanning={isScanning} />;
      default: return null;
    }
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <div className="header-pane">
        <div><span>NUNMAI: CENTRAL ORCHESTRATION</span></div>
        <div className="flex-row gap-lg" style={{ color: 'var(--fg-secondary)' }}>
          <span>MAIL [{pipelineState.mail === 'ANALYZED' ? 'OK' : 'WAIT'}]</span>
          <span>VISION [{pipelineState.vision === 'ANALYZED' ? 'OK' : 'WAIT'}]</span>
          <span>VOICE [{pipelineState.voice === 'ANALYZED' ? 'OK' : 'WAIT'}]</span>
          <span>SOCIAL [{pipelineState.social === 'ANALYZED' ? 'OK' : 'WAIT'}]</span>
        </div>
      </div>

      {/* Left Sidebar */}
      <div className="sidebar-pane">
        <WindowPane title="NAVIGATION">
          <div className="flex-col gap-sm">
            <div style={{ color: 'var(--fg-secondary)', marginBottom: '5px' }}>-- INGESTION --</div>
            <button className="nav-btn" onClick={() => handleSelectModule('mail')}>&gt; [INGEST] MAIL</button>
            <button className="nav-btn" onClick={() => handleSelectModule('vision')}>&gt; [INGEST] VISION</button>
            <button className="nav-btn" onClick={() => handleSelectModule('voice')}>&gt; [INGEST] VOICE</button>
            <button className="nav-btn" onClick={() => handleSelectModule('social')}>&gt; [INGEST] SOCIAL</button>
            
            <div style={{ color: 'var(--fg-secondary)', margin: '15px 0 5px 0' }}>-- ACTION --</div>
            <button className="nav-btn" onClick={handleVerifyAll} style={{ color: 'var(--fg-primary)', border: '1px solid var(--fg-primary)', padding: '4px' }}>
              [ VERIFY ALL ]
            </button>
            {currentView === 'verify' && (
              <button className="nav-btn" onClick={downloadPDF} style={{ marginTop: '10px', color: 'var(--fg-secondary)', border: '1px solid var(--fg-secondary)', padding: '4px' }}>
                [ DOWNLOAD PDF ]
              </button>
            )}
          </div>
        </WindowPane>
      </div>

      {/* Main Center Area */}
      <div className="main-pane">
        {currentView === 'ingest' ? (
          <div className="flex-row gap-md" style={{ flex: 1 }}>
            <WindowPane title={`DATA INGESTION: ${activeContext.toUpperCase()}`} style={{ flex: 2 }}>
              {renderActiveForm()}
            </WindowPane>
            <WindowPane title="MODULE INFO" style={{ flex: 1 }}>
              <div style={{ color: 'var(--fg-muted)' }}>
                {activeContext === 'mail' && "Requires raw_email_source for proper SPF/DKIM parsing."}
                {activeContext === 'vision' && "Accepts .mp4. Biometrics NOT synced to VERIFY registry."}
                {activeContext === 'voice' && "Accepts .wav. Biometrics NOT synced to VERIFY registry."}
                {activeContext === 'social' && "Requires account handle, bio, and posting statistics."}
              </div>
            </WindowPane>
          </div>
        ) : currentView === 'verify' ? (
          <div className="flex-col gap-md" style={{ flex: 1, overflowY: 'auto' }} ref={reportRef}>
             <div style={{ padding: '10px', background: 'var(--bg-color)', height: '100%' }} className="flex-row gap-md">
                <WindowPane title="FINAL VERIFICATION & SIGNATURE" style={{ flex: 1 }}>
                  <div className="flex-col gap-md" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <QRCode size={14} />
                    <div style={{ textAlign: 'center', marginTop: '10px' }}>
                      <TypewriterText text="VALID SIGNATURE GENERATED" delay={40} />
                      <br />
                      <span style={{ fontSize: '0.8em', color: 'var(--fg-secondary)' }}>NUNMAI-VERIFY HASH: 0x8F9B2A...E4</span>
                    </div>
                  </div>
                </WindowPane>
                <WindowPane title="UNIFIED THREAT REPORT" style={{ flex: 2 }}>
                  <div className="flex-col gap-sm">
                    <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '5px' }}>
                      <strong>AGGREGATED RISK: 87/100 (HIGH)</strong>
                    </div>
                    <div>MAIL: <ProgressBar percent={90} /> [PHISHING LIKELY]</div>
                    <div>VISION: <ProgressBar percent={20} /> [AUTHENTIC]</div>
                    <div>VOICE: <ProgressBar percent={85} /> [SYNTHETIC DETECTED]</div>
                    <div>SOCIAL: <ProgressBar percent={70} /> [BOT AMPLIFICATION]</div>
                    <br />
                    <div style={{ color: 'var(--fg-secondary)' }}>
                      <TypewriterText text="SUGGESTION: Reject communication. Correlation between synthetic voice and phishing email domain suggests coordinated attack vector." delay={20} />
                      <br /><br />
                      <span style={{ color: 'var(--fg-muted)' }}>*Note: Voice and Vision biometrics bypass the global registry cross-check per current architectural specs.</span>
                    </div>
                  </div>
                </WindowPane>
             </div>
          </div>
        ) : (
          <div className="flex-row gap-md" style={{ flex: 1 }}>
            <WindowPane title="SYSTEM STATUS" style={{ flex: 1 }}>
              <div className="flex-col gap-sm" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <div style={{ color: 'var(--fg-secondary)' }}>AWAITING DATA INGESTION</div>
              </div>
            </WindowPane>
          </div>
        )}
      </div>

      {/* Bottom Console */}
      <div className="console-pane">
        <WindowPane title="TERMINAL LOGS">
          <div className="flex-col gap-sm" style={{ height: '100%' }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {history.map((line, i) => (
                <div key={i} style={{ color: line.type === 'user' ? 'var(--fg-secondary)' : 'var(--fg-primary)' }}>
                  {line.text}
                </div>
              ))}
              <div ref={terminalEndRef} />
            </div>
            <TerminalInput prompt={activeContext ? `[${activeContext.toUpperCase()}] >` : `root@nunmai:~$`} onSubmit={(cmd) => logToTerminal(`root@nunmai:~$ ${cmd}`, 'user')} />
          </div>
        </WindowPane>
      </div>
    </div>
  );
}

export default App;
