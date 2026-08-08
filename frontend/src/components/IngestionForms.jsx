import React, { useState, useEffect } from 'react';
import ScannerFrame from './ScannerFrame';

export const MailForm = ({ onSubmit, isScanning, activeVerdict }) => {
  const [rawEmail, setRawEmail] = useState('');
  const [bodyText, setBodyText] = useState(''); // Kept for compatibility

  // Replaces the textarea with a div highlighting the triggered words
  const renderHighlighted = () => {
    let text = rawEmail;
    if (activeVerdict && activeVerdict.textMatches) {
        let allMatches = [];
        Object.values(activeVerdict.textMatches).forEach(arr => {
            allMatches = allMatches.concat(arr);
        });
        
        // Deduplicate
        allMatches = [...new Set(allMatches)];
        
        if (allMatches.length > 0) {
            // Escape regex special characters from match words just in case
            const escapedMatches = allMatches.map(m => m.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
            const regex = new RegExp(`\\b(${escapedMatches.join('|')})\\b`, 'gi');
            const parts = text.split(regex);
            
            return (
                <div className="friendly-input" style={{ height: '250px', overflowY: 'auto', whiteSpace: 'pre-wrap', backgroundColor: '#000', color: 'var(--fg-secondary)', border: '1px solid var(--fg-error)', cursor: 'default' }}>
                    {parts.map((part, i) => {
                        if (allMatches.some(m => m.toLowerCase() === part.toLowerCase())) {
                            return <span key={i} style={{ color: '#ff4444', textDecoration: 'underline', fontWeight: 'bold' }}>{part}</span>;
                        }
                        return part;
                    })}
                </div>
            );
        }
    }
    // Fallback if no specific word matches but scan is complete
    return <div className="friendly-input" style={{ height: '250px', overflowY: 'auto', whiteSpace: 'pre-wrap', cursor: 'default' }}>{rawEmail}</div>;
  };

  return (
    <div className="flex-col gap-md">
      <div className="guided-subtitle">
        {activeVerdict 
          ? "Scan complete. Specific risk factors (like urgency or financial triggers) are highlighted below:" 
          : "Paste the email below. We'll check the sender, links, and language for phishing signs."}
      </div>
      
      {activeVerdict ? (
        renderHighlighted()
      ) : (
        <textarea 
          className="friendly-input"
          placeholder="Paste full email here..." 
          value={rawEmail} 
          onChange={e => setRawEmail(e.target.value)}
          style={{ height: '150px', resize: 'vertical' }}
        />
      )}
      
      {!activeVerdict && (
        <button 
          className="friendly-button"
          onClick={() => onSubmit({ rawEmail, bodyText: rawEmail })}
          disabled={isScanning}
        >
          Check This Email
        </button>
      )}
    </div>
  );
};

export const VisionVoiceForm = ({ type, onSubmit, isScanning }) => {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      // Create preview for both Video and Audio
      if (selected.type.startsWith('video/') || selected.type.startsWith('audio/') || type === 'VOICE') {
        setPreviewUrl(URL.createObjectURL(selected));
      }
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const subtitle = type === 'VISION' 
    ? "Upload a video. We'll analyze it frame-by-frame for deepfake artifacts."
    : "Upload an audio clip. We'll analyze the voice frequencies for AI cloning signatures.";

  const buttonText = type === 'VISION' ? "Scan Video" : "Scan Audio";

  return (
    <div className="flex-col gap-md" style={{ height: '100%' }}>
      <div className="guided-subtitle">{subtitle}</div>
      
      <ScannerFrame isScanning={isScanning}>
        <div style={{ padding: '0', display: 'flex', flexDirection: 'column', height: '200px', width: '100%', position: 'relative', justifyContent: 'center', alignItems: 'center' }}>
          {previewUrl && type === 'VISION' ? (
            <video 
              src={previewUrl} 
              autoPlay 
              loop 
              muted 
              style={{ width: '100%', height: '100%', objectFit: 'contain', opacity: 0.5 }}
            />
          ) : previewUrl && type === 'VOICE' ? (
             <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', height: '100%', justifyContent: 'center' }}>
                <style>{`
                  @keyframes audioWave {
                    0% { height: 10px; opacity: 0.5; }
                    100% { height: 60px; opacity: 1; }
                  }
                  .wave-bar {
                    width: 6px;
                    background: var(--fg-primary);
                    border-radius: 3px;
                    animation: audioWave 0.5s infinite ease-in-out alternate;
                  }
                `}</style>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', height: '70px', marginBottom: '10px' }}>
                  {[0.4, 0.7, 0.5, 0.9, 0.3, 0.8, 0.6, 0.9, 0.5, 0.7, 0.4].map((duration, idx) => (
                    <div key={idx} className="wave-bar" style={{ animationDuration: `${duration}s` }} />
                  ))}
                </div>
                <div style={{ color: 'var(--fg-secondary)', fontSize: '0.9rem', marginBottom: '10px' }}>
                  {file.name}
                </div>
                <audio src={previewUrl} controls style={{ height: '30px', width: '250px' }} />
             </div>
          ) : (
            <label style={{ cursor: 'pointer', color: 'var(--fg-primary)', textAlign: 'center', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <input type="file" accept={type === 'VISION' ? 'video/*' : 'audio/*'} style={{ display: 'none' }} onChange={handleFileChange} />
              {file ? `File Selected: ${file.name}` : `Click to Browse & Upload`}
            </label>
          )}
          {previewUrl && type === 'VISION' && (
            <div style={{ position: 'absolute', background: 'rgba(0,0,0,0.7)', padding: '5px' }}>
              {file.name}
            </div>
          )}
        </div>
      </ScannerFrame>

      <button 
        className="friendly-button"
        onClick={() => onSubmit({ file })}
        disabled={isScanning || !file}
      >
        {buttonText}
      </button>
    </div>
  );
};

export const SocialForm = ({ onSubmit, isScanning }) => {
  const [formData, setFormData] = useState({
    handle: '', post_text: '', bio_text: '', account_created_date: '',
    posts_per_day: '', followers: '', following: ''
  });

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  return (
    <div className="flex-col gap-md">
      <div className="guided-subtitle">
        Enter the social media post and account details. We'll check for bot activity and manipulation.
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <input className="friendly-input" name="handle" placeholder="@username" onChange={handleChange} />
        <input className="friendly-input" name="followers" placeholder="Followers count" type="number" onChange={handleChange} />
      </div>
      
      <textarea 
        className="friendly-input" 
        name="post_text" 
        placeholder="Paste the post caption or text here..." 
        onChange={handleChange} 
        style={{ height: '80px', resize: 'vertical' }} 
      />
      
      <button 
        className="friendly-button"
        onClick={() => onSubmit(formData)}
        disabled={isScanning}
      >
        Check Social Post
      </button>
    </div>
  );
};
