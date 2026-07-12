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
    { type: 'system', text: 'NUNMI OS v3.0.0 initializing...' },
    { type: 'system', text: 'Connecting to CENTRAL ORCHESTRATION API... [OK]' },
    { type: 'system', text: 'Select a module from the Navigation to begin ingestion.' }
  ]);

  const [pipelineState, setPipelineState] = useState({
    mail: 'PENDING', vision: 'PENDING', voice: 'PENDING', social: 'PENDING'
  });

  const [activeContext, setActiveContext] = useState(null);
  const [currentView, setCurrentView] = useState('dashboard');
  const [isScanning, setIsScanning] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  
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
      logToTerminal('[OK] Verification complete. Generating Threat Report and Cryptographic QR Signature.');
    }, 1500);
  };

  const processIngestion = (payload) => {
    const module = activeContext.toUpperCase();
    setIsScanning(true);
    
    // Simulate 20s Loading/Buffering Phase for Video/Audio
    if (module === 'VISION' || module === 'VOICE') {
      logToTerminal(`[${module}] Received multipart file. Allocating memory buffer...`);
      logToTerminal(`[${module}] Loading media stream... (Estimated time: 20s)`);
      
      let loadPercent = 0;
      const loadInterval = setInterval(() => {
        loadPercent += 10;
        if (loadPercent <= 100) {
          logToTerminal(`[${module}] Buffer Status: ${loadPercent}% Loaded.`);
        }
      }, 2000); // 20s total roughly

      setTimeout(() => {
        clearInterval(loadInterval);
        runDeepProcessing(module);
      }, 20000);
    } else {
      // Faster processing for Mail/Social
      logToTerminal(`[${module}] Parsing input contracts... [OK]`);
      runFastProcessing(module);
    }
  };

  const runFastProcessing = (module) => {
    setTimeout(() => {
      if (module === 'MAIL') {
        logToTerminal(`[${module}] Scanning email attachments for embedded payloads...`);
        logToTerminal(`[${module}] Analyzing raw_email_source headers (SPF/DKIM/DMARC)...`);
      } else if (module === 'SOCIAL') {
        logToTerminal(`[${module}] Evaluating account_created_date & follow-ratio flags...`);
      }
      
      setTimeout(() => {
        logToTerminal(`[${module}] Running primary AI classification ensemble...`);
        setTimeout(() => {
          logToTerminal(`[${module}] Analysis complete. Threat level registered.`);
          setPipelineState(prev => ({ ...prev, [activeContext]: 'ANALYZED' }));
          setIsScanning(false);
          setActiveContext(null);
          setCurrentView('dashboard');
        }, 1500);
      }, 1500);
    }, 1500);
  };

  const runDeepProcessing = (module) => {
    // 30s Detail Processing
    logToTerminal(`[${module}] Media successfully loaded into memory.`);
    logToTerminal(`[${module}] Initiating 30-second deep chunking and inference pipeline...`);
    
    const steps = module === 'VISION' ? [
      "Initializing OpenCV Frame Extractor...",
      "Segmenting video into temporal chunks... [Chunk 1/5]",
      "Analyzing Chunk 1: Extracted 240 frames.",
      "Running RetinaFace Detection on Chunk 1... Detected 1 Face.",
      "Segmenting video into temporal chunks... [Chunk 2/5]",
      "Analyzing Chunk 2: Extracted 240 frames.",
      "Running RetinaFace Detection on Chunk 2... Detected 1 Face.",
      "Cross-referencing facial landmarks across chunks...",
      "Executing CNN Spatial Feature Analysis on localized faces...",
      "Detecting micro-artifacts and GAN blending edges...",
      "Extracting LSTM Temporal Features (Blinking, Lip Sync)...",
      "Fusing CNN-LSTM spatial-temporal arrays...",
      "Executing final Deepfake Classification model..."
    ] : [
      "Initializing Audio Preprocessor...",
      "Executing noise removal algorithm...",
      "Segmenting audio into 10ms frames...",
      "Resampling stream to 16kHz...",
      "Extracting MFCC features (Mel-frequency cepstral coefficients)...",
      "Analyzing pitch and spectral formants...",
      "Running 1D-CNN over temporal sequence...",
      "Passing features to LSTM layer for context evaluation...",
      "Evaluating synthetic generation signatures (e.g., ElevenLabs, VITS)...",
      "Cross-referencing audio formants with known synthetic models...",
      "Executing final Real vs Fake Voice classification..."
    ];

    let stepIndex = 0;
    const processInterval = setInterval(() => {
      if (stepIndex < steps.length) {
        logToTerminal(`[${module}] ${steps[stepIndex]}`);
        stepIndex++;
      } else {
        clearInterval(processInterval);
        logToTerminal(`[${module}] Analysis complete. Threat level registered.`);
        setPipelineState(prev => ({ ...prev, [activeContext]: 'ANALYZED' }));
        setIsScanning(false);
        setActiveContext(null);
        setCurrentView('dashboard');
      }
    }, 2500); // 13 steps * 2.5s = ~32.5 seconds
  };

  const downloadPDF = () => {
    setIsGenerating(true);
    logToTerminal('[SYSTEM] Compiling PDF Report...');
    const element = reportRef.current;
    const opt = {
      margin:       0.5,
      filename:     'NUNMI_Threat_Report.pdf',
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true, backgroundColor: '#1e1e1e' },
      jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save().then(() => {
      logToTerminal('[OK] PDF downloaded successfully.');
      setIsGenerating(false);
    });
  };

  const qrPayload = JSON.stringify({
    app: "NUNMI",
    user: "Jonah",
    risk_score: 87,
    status: "VERIFIED",
    hash: "0x8F9B2A4C91E4"
  });

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
      <div className="watermark">JONAH</div>
      
      {/* Top Header */}
      <div className="header-pane">
        <div style={{ flex: 1 }}></div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: '1.5em', fontWeight: 'bold' }}>
          <span>NUNMI</span>
        </div>
        <div className="flex-row gap-lg" style={{ color: 'var(--fg-secondary)', flex: 1, justifyContent: 'flex-end' }}>
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
              <button 
                className="nav-btn" 
                onClick={downloadPDF} 
                disabled={isGenerating}
                style={{ marginTop: '10px', color: 'var(--fg-secondary)', border: '1px solid var(--fg-secondary)', padding: '4px', opacity: isGenerating ? 0.5 : 1 }}
              >
                {isGenerating ? '[ GENERATING... ]' : '[ DOWNLOAD PDF ]'}
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
                {activeContext === 'mail' && "Requires raw_email_source for proper SPF/DKIM parsing. Attachments scanned via static analysis."}
                {activeContext === 'vision' && "Accepts .mp4. Buffers into memory (20s) and chunks frames sequentially (30s) for deepfake detection."}
                {activeContext === 'voice' && "Accepts .wav. Buffers stream (20s) and runs spectral formants extraction (30s)."}
                {activeContext === 'social' && "Requires account handle, bio, and posting statistics. Image input optional."}
              </div>
            </WindowPane>
          </div>
        ) : currentView === 'verify' ? (
          <div className="flex-col gap-md" style={{ flex: 1, overflowY: 'auto' }} ref={reportRef}>
             <div style={{ padding: '10px', background: 'var(--bg-color)', height: '100%' }} className="flex-row gap-md">
                <WindowPane title="FINAL VERIFICATION & SIGNATURE" style={{ flex: 1 }}>
                  <div className="flex-col gap-md" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <QRCode payload={qrPayload} size={200} />
                    <div style={{ textAlign: 'center', marginTop: '10px' }}>
                      <TypewriterText text="VALID SIGNATURE GENERATED" delay={40} />
                      <br />
                      <span style={{ fontSize: '0.8em', color: 'var(--fg-secondary)' }}>NUNMI-VERIFY HASH: 0x8F9B2A...E4</span>
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
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', paddingRight: '10px' }}>
              {history.map((line, i) => (
                <div key={i} style={{ color: line.type === 'user' ? 'var(--fg-secondary)' : 'var(--fg-primary)' }}>
                  {line.text}
                </div>
              ))}
              <div ref={terminalEndRef} style={{ height: '1px' }} />
            </div>
            <TerminalInput prompt={activeContext ? `[${activeContext.toUpperCase()}] >` : `root@nunmi:~$`} onSubmit={(cmd) => logToTerminal(`root@nunmi:~$ ${cmd}`, 'user')} />
          </div>
        </WindowPane>
      </div>
    </div>
  );
}

export default App;
