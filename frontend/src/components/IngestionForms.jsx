import React, { useState, useEffect } from 'react';
import ScannerFrame from './ScannerFrame';

export const MailForm = ({ onSubmit, isScanning }) => {
  const [rawEmail, setRawEmail] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [attachment, setAttachment] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setAttachment(e.target.files[0]);
    }
  };

  return (
    <div className="flex-col gap-md" style={{ height: '100%', overflowY: 'auto' }}>
      <div style={{ color: 'var(--fg-secondary)' }}>POST /scan-email</div>
      <textarea 
        placeholder="Paste raw_email_source (headers + body)..." 
        value={rawEmail} 
        onChange={e => setRawEmail(e.target.value)}
        style={{ flex: 1, minHeight: '80px', resize: 'none', background: 'rgba(0,0,0,0.3)' }}
      />
      <textarea 
        placeholder="Paste plain body_text (optional)..." 
        value={bodyText} 
        onChange={e => setBodyText(e.target.value)}
        style={{ flex: 1, minHeight: '80px', resize: 'none', background: 'rgba(0,0,0,0.3)' }}
      />
      
      <div style={{ padding: '10px', background: 'rgba(0,0,0,0.3)' }}>
        <div style={{ marginBottom: '5px', color: 'var(--fg-muted)' }}>ATTACHMENT (OPTIONAL PDF/DOC)</div>
        <input type="file" onChange={handleFileChange} disabled={isScanning} style={{ colorScheme: 'dark' }} />
      </div>

      <button 
        onClick={() => onSubmit({ rawEmail, bodyText, attachment })}
        disabled={isScanning}
        style={{ border: '1px solid var(--fg-primary)', padding: '5px' }}
      >
        [ SUBMIT PAYLOAD ]
      </button>
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
      if (type === 'VISION' && selected.type.startsWith('video/')) {
        setPreviewUrl(URL.createObjectURL(selected));
      }
    }
  };

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  return (
    <div className="flex-col gap-md" style={{ height: '100%' }}>
      <div style={{ color: 'var(--fg-secondary)' }}>POST /scan-{type === 'VISION' ? 'video' : 'audio'}</div>
      
      <ScannerFrame isScanning={isScanning}>
        <div style={{ padding: '0', display: 'flex', flexDirection: 'column', height: '150px', width: '100%', position: 'relative', justifyContent: 'center', alignItems: 'center' }}>
          {previewUrl ? (
            <video 
              src={previewUrl} 
              autoPlay 
              loop 
              muted 
              style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.5 }}
            />
          ) : (
            <label style={{ cursor: 'pointer', color: 'var(--fg-primary)', textAlign: 'center', width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <input type="file" accept={type === 'VISION' ? 'video/*' : 'audio/*'} style={{ display: 'none' }} onChange={handleFileChange} />
              {file ? `[FILE LOADED] ${file.name}` : `CLICK TO BROWSE & UPLOAD ${type}`}
            </label>
          )}
          {previewUrl && (
            <div style={{ position: 'absolute', background: 'rgba(0,0,0,0.7)', padding: '5px' }}>
              {file.name}
            </div>
          )}
        </div>
      </ScannerFrame>

      <button 
        onClick={() => onSubmit({ file })}
        disabled={isScanning || !file}
        style={{ border: '1px solid var(--fg-primary)', padding: '5px', opacity: file ? 1 : 0.5 }}
      >
        [ SUBMIT PAYLOAD ]
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
    <div className="flex-col gap-md" style={{ height: '100%', overflowY: 'auto' }}>
      <div style={{ color: 'var(--fg-secondary)' }}>POST /scan-post</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <input name="handle" placeholder="@handle" onChange={handleChange} />
        <input name="account_created_date" type="date" onChange={handleChange} style={{ colorScheme: 'dark' }} />
        <input name="followers" placeholder="Followers count" type="number" onChange={handleChange} />
        <input name="following" placeholder="Following count" type="number" onChange={handleChange} />
        <input name="posts_per_day" placeholder="Posts per day" type="number" onChange={handleChange} />
      </div>
      <textarea name="post_text" placeholder="Post caption/body..." onChange={handleChange} style={{ height: '60px', background: 'rgba(0,0,0,0.3)' }} />
      <textarea name="bio_text" placeholder="Account bio..." onChange={handleChange} style={{ height: '60px', background: 'rgba(0,0,0,0.3)' }} />
      
      <ScannerFrame isScanning={isScanning}>
        <label style={{ padding: '10px', color: 'var(--fg-muted)', cursor: 'pointer', textAlign: 'center', width: '100%' }}>
          <input type="file" accept="image/*" style={{ display: 'none' }} />
          CLICK TO ATTACH OPTIONAL IMAGE
        </label>
      </ScannerFrame>

      <button 
        onClick={() => onSubmit(formData)}
        disabled={isScanning}
        style={{ border: '1px solid var(--fg-primary)', padding: '5px' }}
      >
        [ SUBMIT PAYLOAD ]
      </button>
    </div>
  );
};
