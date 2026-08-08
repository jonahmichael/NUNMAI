import React, { useState, useEffect, useRef } from 'react';
import html2pdf from 'html2pdf.js';
import './App.css';
import WindowPane from './components/WindowPane';
import TerminalInput from './components/TerminalInput';
import ProgressBar from './components/ProgressBar';
import TypewriterText from './components/TypewriterText';
import QRCode from './components/QRCode';
import { MailForm, VisionVoiceForm, SocialForm } from './components/IngestionForms';

const GlossaryTooltip = ({ term, definition }) => (
  <span className="glossary-tooltip" data-tip={definition}>{term}</span>
);

function App() {
  const [history, setHistory] = useState([
    { type: 'system', text: 'NUNM.AI OS v3.0.0 initializing...' },
    { type: 'system', text: 'Connecting to API Gateway... [OK]' },
    { type: 'system', text: 'System ready.' }
  ]);

  const [pipelineState, setPipelineState] = useState({
    mail: 'PENDING', vision: 'PENDING', voice: 'PENDING', social: 'PENDING'
  });

  const [activeContext, setActiveContext] = useState(null);
  const [currentView, setCurrentView] = useState('home'); // changed from dashboard
  const [isScanning, setIsScanning] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeVerdict, setActiveVerdict] = useState(null);
  
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
    setActiveVerdict(null);
    logToTerminal(`Opened ${moduleName.toUpperCase()} analysis tool.`);
  };

  const handleVerifyAll = () => {
    setActiveContext(null);
    setCurrentView('verify');
    logToTerminal('Correlating data from all previous scans...');
    setTimeout(() => {
      logToTerminal('Verification complete. Generating Threat Report.');
    }, 1500);
  };

  const handleGoHome = () => {
    setActiveContext(null);
    setCurrentView('home');
    setActiveVerdict(null);
  };

  const processIngestion = async (payload) => {
    const module = activeContext.toUpperCase();
    setIsScanning(true);
    setActiveVerdict(null);
    
    logToTerminal(`Initializing secure connection to API Gateway...`);
    
    let endpoint = 'http://localhost:8080';
    let options = { method: 'POST' };

    try {
      if (module === 'MAIL') {
        endpoint += '/mail/scan-email';
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify({
          body_text: payload.bodyText || ' ',
          raw_email_source: payload.rawEmail || ' '
        });
      } else if (module === 'VISION') {
        endpoint += '/vision/scan-video';
        const formData = new FormData();
        formData.append('file', payload.file);
        if (payload.claimed_speaker_name) formData.append('claimed_speaker_name', payload.claimed_speaker_name);
        options.body = formData;
      } else if (module === 'VOICE') {
        endpoint += '/voice/scan-audio';
        const formData = new FormData();
        formData.append('file', payload.file);
        if (payload.claimed_speaker_name) formData.append('claimed_speaker_name', payload.claimed_speaker_name);
        options.body = formData;
      } else if (module === 'SOCIAL') {
        endpoint += '/social/scan-post';
        const formData = new FormData();
        formData.append('post_text', payload.post_text || ' ');
        if (payload.handle) formData.append('handle', payload.handle);
        if (payload.followers) formData.append('followers', payload.followers);
        options.body = formData;
      }

      logToTerminal(`Uploading payload for analysis...`);
      
      const narrativeSteps = {
        'MAIL': ["Scanning email headers for forgery...", "Analyzing language for urgency and pressure tactics...", "Checking embedded links against known threat databases..."],
        'VISION': ["Processing video frames...", "Isolating faces using MTCNN...", "Analyzing spatial features for GAN blending artifacts..."],
        'VOICE': ["Extracting audio spectral formants...", "Analyzing vocal frequencies for cloning signatures...", "Cross-referencing with known synthetic generation models..."],
        'SOCIAL': ["Analyzing account age and follower ratio...", "Checking for bot-like posting patterns...", "Evaluating post text for manipulation..."]
      };

      let stepIdx = 0;
      const steps = narrativeSteps[module];
      let fallbackPrinted = false;
      
      const loadingInterval = setInterval(() => {
        if(stepIdx < steps.length) {
            logToTerminal(`${steps[stepIdx]}`);
            stepIdx++;
        } else if (!fallbackPrinted) {
            logToTerminal(`Finalizing multi-layered AI analysis...`);
            fallbackPrinted = true;
        }
      }, 2500);

      const response = await fetch(endpoint, options);
      clearInterval(loadingInterval);
      
      const data = await response.json();
      
      if (!response.ok) {
        logToTerminal(`[Error] Backend failure: ${data.detail || 'Unknown error'}`);
        setIsScanning(false);
        return;
      }

      const riskTier = data.risk_tier || data.fused_risk_score;
      logToTerminal(`Analysis complete.`);
      
      // Print the detailed metrics to the terminal so the user can inspect them
      if (module !== 'MAIL') {
         logToTerminal(`[RAW METRICS] ${JSON.stringify(data, null, 2)}`);
      }
      
      // Determine Plain English Verdict
      let verdictObj = { text: "", type: "verdict-green", rawData: data };
      
      if (module === 'MAIL') {
          if (riskTier === 'PHISHING') { verdictObj.text = "This email shows strong signs of being a phishing scam."; verdictObj.type = "verdict-red"; }
          else if (riskTier === 'SUSPICIOUS') { verdictObj.text = "This email looks suspicious. Proceed with caution."; verdictObj.type = "verdict-yellow"; }
          else { verdictObj.text = "This email appears to be safe and authentic."; verdictObj.type = "verdict-green"; }
          
          verdictObj.riskSignals = data.top_risk_signals || [];
          verdictObj.trustSignals = data.top_trust_signals || [];
          verdictObj.textMatches = data.text_matches || {};
      } 
      else if (module === 'VISION') {
          if (riskTier === 'DEEPFAKE') { verdictObj.text = "This video shows strong evidence of AI manipulation (Deepfake)."; verdictObj.type = "verdict-red"; }
          else if (riskTier === 'SUSPICIOUS') { verdictObj.text = "This video has suspicious artifacts. It may be manipulated."; verdictObj.type = "verdict-yellow"; }
          else { verdictObj.text = "This video appears to be an authentic recording."; verdictObj.type = "verdict-green"; }
      }
      else if (module === 'VOICE') {
          if (riskTier === 'DEEPFAKE' || riskTier === 'SYNTHETIC') { verdictObj.text = "This voice recording appears to be AI-generated or cloned."; verdictObj.type = "verdict-red"; }
          else if (riskTier === 'SUSPICIOUS') { verdictObj.text = "This voice recording has unnatural audio signatures."; verdictObj.type = "verdict-yellow"; }
          else { verdictObj.text = "This voice recording appears to be human and authentic."; verdictObj.type = "verdict-green"; }
      }
      else if (module === 'SOCIAL') {
          if (riskTier === 'HIGH_RISK') { verdictObj.text = "This account or post shows strong signs of being a malicious bot."; verdictObj.type = "verdict-red"; }
          else if (riskTier === 'SUSPICIOUS') { verdictObj.text = "This post exhibits suspicious, coordinated behavior."; verdictObj.type = "verdict-yellow"; }
          else { verdictObj.text = "This post appears to be from a genuine user."; verdictObj.type = "verdict-green"; }
      }

      setActiveVerdict(verdictObj);
      setPipelineState(prev => ({ ...prev, [activeContext]: 'ANALYZED' }));
      setIsScanning(false);

    } catch (err) {
      logToTerminal(`[Error] Network failure. Is API Gateway running on port 8080? ${err.message}`);
      setIsScanning(false);
    }
  };

  const downloadPDF = () => {
    setIsGenerating(true);
    logToTerminal('Compiling PDF Report...');
    const element = reportRef.current;
    const opt = {
      margin:       0.5,
      filename:     'NUNM.AI_Threat_Report.pdf',
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true, backgroundColor: '#1e1e1e' },
      jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save().then(() => {
      logToTerminal('PDF downloaded successfully.');
      setIsGenerating(false);
    });
  };

  const exportLogsToJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(history, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "nunmai_system_logs.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    logToTerminal('Logs exported to JSON.');
  };

  const formatSignal = (feature) => {
    if (!feature) return "Unknown signal";
    
    // First, gather any matched words for this specific feature category if it exists
    let matchedWordsStr = "";
    if (activeVerdict && activeVerdict.textMatches) {
      if (feature.includes('urgency') && activeVerdict.textMatches.urgency?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.urgency.join('", "')}")`;
      }
      else if (feature.includes('financial') && activeVerdict.textMatches.financial?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.financial.join('", "')}")`;
      }
      else if (feature.includes('llm_trope') && activeVerdict.textMatches.llm_tropes?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.llm_tropes.join('", "')}")`;
      }
      else if (feature.includes('prompt_leakage') && activeVerdict.textMatches.prompt_leakage?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.prompt_leakage.join('", "')}")`;
      }
      else if (feature.includes('out_of_band') && activeVerdict.textMatches.out_of_band_excuses?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.out_of_band_excuses.join('", "')}")`;
      }
      else if (feature.includes('causal') && activeVerdict.textMatches.causal_connectives?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.causal_connectives.join('", "')}")`;
      }
      else if (feature.includes('personal') && activeVerdict.textMatches.personal_osint?.length > 0) {
        matchedWordsStr = ` ("${activeVerdict.textMatches.personal_osint.join('", "')}")`;
      }
    }

    const map = {
      'text__urgency_word_count': 'Contains high-urgency keywords or pressure tactics',
      'text__financial_action_word_count': 'Contains demands for financial actions or credentials',
      'text__llm_trope_word_count': 'Contains unusual vocabulary favored by AI bots',
      'text__llm_trope_phrase_count': 'Contains phrases commonly generated by AI',
      'text__prompt_leakage_detected': 'Contains leaked AI prompt artifacts (sloppy bot)',
      'text__out_of_band_excuse_count': 'Contains excuses to avoid phone verification',
      'text__causal_connective_count': 'Over-justifies its request (common AI behavior)',
      'text__personal_osint_word_count': 'Uses scraped personal details',
      'text__personalization_financial_mismatch': 'Abruptly pivots from personal chat to asking for money',
      'text__sentence_count': 'Abnormal email length (too short or too long)',
      'text__word_count': 'Abnormal word count for a professional email',
      'text__burstiness_score': 'Structural monotony: sentence lengths are unusually uniform (indicates AI generation)',
      'text__low_burstiness_flag': 'Flagged for highly robotic/uniform sentence structure',
      
      'url__has_suspicious_tld': 'Contains links to suspicious or unusual domains (.xyz, etc.)',
      'url__num_urls': 'High volume of embedded links',
      'url__has_ip': 'Contains raw IP addresses instead of domains',
      'url__has_https': 'Uses secure HTTPS (Standard)',
      
      'header__spf_result_fail': 'Sender Policy Framework (SPF) authentication failed',
      'header__dkim_result_fail': 'DomainKeys Identified Mail (DKIM) signature failed or missing',
      'header__dmarc_result_fail': 'DMARC alignment failed (domain owner policies violated)',
      'header__spf_result_pass': 'SPF authentication passed',
      'header__dkim_result_pass': 'DKIM signature verified',
      'header__dmarc_result_pass': 'DMARC alignment passed',
      'header__message_id_domain_mismatch': 'Forged Sender: Message-ID domain does not match the sender domain',
      'header__received_chain_missing': 'Missing tracking headers: Email likely generated by a malicious script',
      'header__auth_all_failed': 'Critical Warning: Failed all cryptographic email authentication checks (SPF/DKIM/DMARC)',
    };
    
    for (let key in map) {
      if (feature === key || feature.includes(key)) {
        return map[key] + matchedWordsStr;
      }
    }
    
    // Fallback cleanup for unmapped features
    let clean = feature.replace(/_/g, ' ').replace('text  ', '').replace('header  ', '').replace('url  ', '');
    return clean.charAt(0).toUpperCase() + clean.slice(1) + matchedWordsStr;
  };

  const renderHumanReadableMetrics = (context, rawData) => {
    if (!rawData) return null;

    if (context === 'mail') {
      return (
        <ul style={{ paddingLeft: '20px', lineHeight: '1.8' }}>
          <li>
            <strong>Phishing Probability:</strong> {rawData.phishing_probability !== undefined ? (rawData.phishing_probability * 100).toFixed(1) : 'N/A'}% 
            <span style={{ color: 'var(--fg-muted)' }}> — Overall confidence that this email is a malicious phishing attempt.</span>
          </li>
          {rawData.sender_verification && (
            <li>
              <strong>Sender Authentication:</strong> <strong style={{ color: rawData.sender_verification.all_passed ? 'var(--fg-primary)' : 'var(--fg-error)' }}>{rawData.sender_verification.all_passed ? 'PASSED (Cryptographically Verified)' : 'FAILED (Spoofing Likely)'}</strong>
              <span style={{ color: 'var(--fg-muted)' }}> — Checks SPF, DKIM, and DMARC records to verify the sender's true identity.</span>
            </li>
          )}
        </ul>
      );
    }

    if (context === 'social') {
      return (
        <ul style={{ paddingLeft: '20px', lineHeight: '1.8' }}>
          <li>
            <strong>Text Analysis Score:</strong> {rawData.text_risk_score !== undefined ? (rawData.text_risk_score * 100).toFixed(1) : 'N/A'}% 
            <span style={{ color: 'var(--fg-muted)' }}> — Evaluates the language for manipulative financial hype or bot-like patterns.</span>
          </li>
          {rawData.image_applicable && (
            <li>
              <strong>Image Analysis Score:</strong> {rawData.image_risk_score !== undefined ? (rawData.image_risk_score * 100).toFixed(1) : 'N/A'}% 
              <span style={{ color: 'var(--fg-muted)' }}> — Checks attached images for deepfake or GAN blending artifacts.</span>
            </li>
          )}
          <li>
            <strong>Behavioral Risk Score:</strong> {rawData.behavioral_risk_score !== undefined ? (rawData.behavioral_risk_score * 100).toFixed(1) : 'N/A'}% 
            <span style={{ color: 'var(--fg-muted)' }}> — Analyzes account history, follower ratio, and unusual posting frequency.</span>
          </li>
        </ul>
      );
    }
    
    if (context === 'voice') {
      return (
        <div className="flex-col gap-sm">
          <div>
            <strong>Summary:</strong> Analyzed {rawData.num_segments_analyzed} audio segments for synthetic frequencies.
          </div>
          {rawData.executive_verification && (
            <div>
              <strong>Executive Authorization:</strong> <strong style={{ color: rawData.executive_verification.authorized ? 'var(--fg-primary)' : 'var(--fg-error)' }}>{rawData.executive_verification.status}</strong>
              <span style={{ color: 'var(--fg-muted)' }}> — Cross-checked claimed name against SEBI Trust Chain.</span>
            </div>
          )}
          <div><strong>Segment Breakdown:</strong></div>
          <ul style={{ paddingLeft: '20px', lineHeight: '1.5', maxHeight: '150px', overflowY: 'auto', background: 'rgba(255,255,255,0.05)', padding: '10px' }}>
            {rawData.per_segment_results && rawData.per_segment_results.map((res, i) => (
              <li key={i}>
                Segment {i + 1}: <strong style={{ color: (res.label || '').toUpperCase() === 'FAKE' ? 'var(--fg-error)' : 'var(--fg-primary)' }}>{res.label}</strong> ({(res.fake_probability * 100).toFixed(1)}% confident)
              </li>
            ))}
          </ul>
        </div>
      );
    }

    if (context === 'vision') {
      return (
        <div className="flex-col gap-sm">
          <div>
            <strong>Summary:</strong> Analyzed {rawData.num_faces_analyzed} face(s) across {rawData.num_frames_sampled} frames.
          </div>
          {rawData.executive_verification && (
            <div>
              <strong>Executive Authorization:</strong> <strong style={{ color: rawData.executive_verification.authorized ? 'var(--fg-primary)' : 'var(--fg-error)' }}>{rawData.executive_verification.status}</strong>
              <span style={{ color: 'var(--fg-muted)' }}> — Cross-checked claimed name against SEBI Trust Chain.</span>
            </div>
          )}
          <div><strong>Frame-by-Frame Breakdown:</strong></div>
          <ul style={{ paddingLeft: '20px', lineHeight: '1.5', maxHeight: '150px', overflowY: 'auto', background: 'rgba(255,255,255,0.05)', padding: '10px' }}>
            {rawData.per_face_results && rawData.per_face_results.map((res, i) => (
              <li key={i}>
                Frame {i + 1}: <strong style={{ color: (res.label || '').toUpperCase() === 'FAKE' ? 'var(--fg-error)' : 'var(--fg-primary)' }}>{res.label}</strong> ({(res.fake_probability * 100).toFixed(1)}% confident)
              </li>
            ))}
          </ul>
        </div>
      );
    }

    // Fallback if not mapped
    return <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace' }}>{JSON.stringify(rawData, null, 2)}</pre>;
  };

  const renderActiveForm = () => {
    switch (activeContext) {
      case 'mail': return <MailForm onSubmit={processIngestion} isScanning={isScanning} activeVerdict={activeVerdict} />;
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
        <div style={{ flex: 1 }}>
          {currentView !== 'home' && (
            <button className="nav-btn" onClick={handleGoHome} style={{ fontSize: '1.2rem' }}>
              ← BACK TO HOME
            </button>
          )}
        </div>
        <div style={{ flex: 1, textAlign: 'center', fontSize: '1.5em', fontWeight: 'bold' }}>
          <span>NUNM.AI</span>
        </div>
        <div className="flex-row gap-lg" style={{ color: 'var(--fg-secondary)', flex: 1, justifyContent: 'flex-end' }}>
          <span>STATUS: {isScanning ? 'ANALYZING...' : 'ONLINE'}</span>
        </div>
      </div>

      {/* Main Center Area */}
      <div className="main-pane">
        {currentView === 'home' ? (
          <div className="home-grid">
             <div className="home-card" onClick={() => handleSelectModule('mail')}>
               <h2 className="default-text">NUNM.AI MAIL</h2>
               <p className="hover-text">Check if this email is a scam</p>
             </div>
             <div className="home-card" onClick={() => handleSelectModule('vision')}>
               <h2 className="default-text">NUNM.AI VISION</h2>
               <p className="hover-text">Check if this video is fake</p>
             </div>
             <div className="home-card" onClick={() => handleSelectModule('voice')}>
               <h2 className="default-text">NUNM.AI VOICE</h2>
               <p className="hover-text">Check if this voice call is real</p>
             </div>
             <div className="home-card" onClick={() => handleSelectModule('social')}>
               <h2 className="default-text">NUNM.AI SOCIAL</h2>
               <p className="hover-text">Check if this social post is manipulated</p>
             </div>
             <div className="home-card" onClick={handleVerifyAll} style={{ borderColor: 'var(--fg-secondary)' }}>
               <h2 className="default-text" style={{ color: 'var(--fg-secondary)' }}>NUNM.AI VERIFY</h2>
               <p className="hover-text" style={{ color: 'var(--fg-secondary)' }}>Generate unified threat report</p>
             </div>
          </div>
        ) : currentView === 'ingest' ? (
          <div className="flex-col gap-md" style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '0 20px' }}>
            
            {/* The Verdict shows up here once processing is done */}
            {activeVerdict && (
              <div className={`verdict-banner ${activeVerdict.type}`}>
                {activeVerdict.text}
                <div style={{ fontSize: '0.9rem', marginTop: '10px', color: 'var(--fg-muted)' }}>
                  (See terminal logs below for detailed metrics)
                </div>
              </div>
            )}

            <WindowPane title={`DATA INGESTION: ${activeContext.toUpperCase()}`}>
              {renderActiveForm()}
            </WindowPane>

            {/* NEW: Side-by-side explanation for Mail */}
            {activeVerdict && activeContext === 'mail' && activeVerdict.riskSignals && (
              <div className="flex-row gap-md" style={{ marginBottom: '10px' }}>
                <WindowPane title="WHY THIS WAS FLAGGED (RISK SIGNALS)" style={{ flex: 1, borderColor: 'var(--fg-error)' }}>
                  <ul style={{ color: 'var(--fg-error)', paddingLeft: '20px', fontSize: '1rem', lineHeight: '1.5' }}>
                    {activeVerdict.riskSignals.length > 0 ? (
                      activeVerdict.riskSignals.map((s, i) => (
                        <li key={i}>{formatSignal(s.feature)}</li>
                      ))
                    ) : (
                      <li>No major risk signals detected.</li>
                    )}
                  </ul>
                </WindowPane>
                <WindowPane title="REASSURING SIGNS (TRUST SIGNALS)" style={{ flex: 1, borderColor: 'var(--fg-primary)' }}>
                  <ul style={{ color: 'var(--fg-primary)', paddingLeft: '20px', fontSize: '1rem', lineHeight: '1.5' }}>
                    {activeVerdict.trustSignals.length > 0 ? (
                      activeVerdict.trustSignals.map((s, i) => (
                        <li key={i}>{formatSignal(s.feature)}</li>
                      ))
                    ) : (
                      <li>No strong cryptographic trust signals found.</li>
                    )}
                  </ul>
                </WindowPane>
              </div>
            )}

            {/* NEW: Detailed Metrics Box for Non-Mail modules */}
            {activeVerdict && activeVerdict.rawData && (
              <div style={{ marginBottom: '10px' }}>
                <WindowPane title="AI CONFIDENCE METRICS" style={{ borderColor: 'var(--fg-secondary)' }}>
                  <div className="flex-col gap-sm">
                    {/* Overall Confidence (if available) */}
                    {(activeVerdict.rawData.fake_probability !== undefined || activeVerdict.rawData.fused_risk_score !== undefined || activeVerdict.rawData.phishing_probability !== undefined) && (
                      <div style={{ fontSize: '1.2rem', color: 'var(--fg-error)', marginBottom: '10px' }}>
                        <strong>Overall Probability of AI Manipulation / Phishing: </strong>
                        {((activeVerdict.rawData.fake_probability ?? activeVerdict.rawData.fused_risk_score ?? activeVerdict.rawData.phishing_probability) * 100).toFixed(2)}%
                      </div>
                    )}
                    
                    {/* Scrollable details for laymen/judges */}
                    <div style={{ fontSize: '0.9rem', color: 'var(--fg-secondary)', marginBottom: '5px' }}>
                      Detailed Analysis Outputs (Scrollable)
                    </div>
                    <div style={{ border: '1px solid var(--border-color)', padding: '10px', height: 'auto', maxHeight: '300px', overflowY: 'auto', background: '#000', color: 'var(--fg-primary)', fontSize: '0.85rem' }}>
                      {renderHumanReadableMetrics(activeContext, activeVerdict.rawData)}
                    </div>
                  </div>
                </WindowPane>
              </div>
            )}
            
            {/* Glossary helps new users */}
            <div style={{ padding: '20px', color: 'var(--fg-muted)', fontSize: '0.9rem' }}>
              <strong>Glossary: </strong> 
              <GlossaryTooltip term="Phishing" definition="A scam where attackers deceive people into revealing sensitive info." />, 
              <GlossaryTooltip term="Deepfake" definition="Synthetic media where a person's face or voice is digitally altered using AI." />, 
              <GlossaryTooltip term="GAN artifacts" definition="Visual glitches (like blurry edges) left behind by Generative Adversarial Networks during face swapping." />
            </div>
          </div>
        ) : currentView === 'verify' ? (
          <div className="flex-col gap-md" style={{ flex: 1, overflowY: 'auto', padding: '0 20px' }} ref={reportRef}>
             <div style={{ padding: '10px', background: 'var(--bg-color)', height: '100%' }} className="flex-row gap-md">
                <WindowPane title="FINAL VERIFICATION & SIGNATURE" style={{ flex: 1 }}>
                  <div className="flex-col gap-md" style={{ alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <QRCode payload={JSON.stringify({ app: "NUNM.AI", user: "Jonah", status: "VERIFIED" })} size={200} />
                    <div style={{ textAlign: 'center', marginTop: '10px' }}>
                      <TypewriterText text="VALID SIGNATURE GENERATED" delay={40} />
                      <br />
                      <span style={{ fontSize: '0.8em', color: 'var(--fg-secondary)' }}>NUNM.AI-VERIFY HASH: 0x8F9B2A...E4</span>
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
                    </div>
                  </div>
                </WindowPane>
             </div>
             
             {/* Only show download button on screen, not in PDF */}
             <div data-html2canvas-ignore style={{ display: 'flex', justifyContent: 'center', margin: '20px 0' }}>
               <button className="friendly-button" onClick={downloadPDF} disabled={isGenerating}>
                 {isGenerating ? 'Generating PDF...' : 'Download Security Report'}
               </button>
             </div>
          </div>
        ) : null}
      </div>

      {/* Bottom Console */}
      <div className="console-pane">
        <WindowPane title="SYSTEM LOGS">
          <div className="flex-col gap-sm" style={{ height: '100%' }}>
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px', paddingRight: '10px' }}>
              {history.map((line, i) => (
                <div key={i} style={{ color: line.type === 'user' ? 'var(--fg-secondary)' : 'var(--fg-primary)' }}>
                  {line.type === 'user' ? '> ' : ''}{line.text}
                </div>
              ))}
              <div ref={terminalEndRef} style={{ height: '1px' }} />
            </div>
            
            <div className="flex-row gap-md" style={{ alignItems: 'center' }}>
              <button 
                className="friendly-button" 
                style={{ padding: '5px 10px', fontSize: '0.8rem', width: 'auto' }} 
                onClick={exportLogsToJSON}
              >
                Export Logs (JSON)
              </button>
              <div style={{ flex: 1 }}>
                {/* Kept a small input just for the hacker aesthetic, though not functional for tasks */}
                <TerminalInput prompt={`guest@nunm.ai:~$`} onSubmit={(cmd) => logToTerminal(`${cmd}`, 'user')} />
              </div>
            </div>
          </div>
        </WindowPane>
      </div>
    </div>
  );
}

export default App;
