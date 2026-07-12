import React, { useState } from 'react';
import ScannerFrame from './ScannerFrame';

export const MailForm = ({ onSubmit, isScanning }) => {
  const [rawEmail, setRawEmail] = useState('');
  const [bodyText, setBodyText] = useState('');

  return (
    <div className="flex-col gap-md" style={{ height: '100%' }}>
      <div style={{ color: 'var(--fg-secondary)' }}>POST /scan-email</div>
      <textarea 
        placeholder="Paste raw_email_source (headers + body)..." 
        value={rawEmail} 
        onChange={e => setRawEmail(e.target.value)}
        style={{ flex: 1, minHeight: '100px', resize: 'none', background: 'rgba(0,0,0,0.3)' }}
      />
      <textarea 
        placeholder="Paste plain body_text (optional)..." 
        value={bodyText} 
        onChange={e => setBodyText(e.target.value)}
        style={{ flex: 1, minHeight: '100px', resize: 'none', background: 'rgba(0,0,0,0.3)' }}
      />
      <button 
        onClick={() => onSubmit({ rawEmail, bodyText })}
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

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="flex-col gap-md" style={{ height: '100%' }}>
      <div style={{ color: 'var(--fg-secondary)' }}>POST /scan-{type === 'VISION' ? 'video' : 'audio'}</div>
      <div 
        onDragOver={e => e.preventDefault()} 
        onDrop={handleDrop}
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
      >
        <ScannerFrame isScanning={isScanning}>
          <div style={{ padding: '20px', textAlign: 'center', color: file ? 'var(--fg-primary)' : 'var(--fg-muted)' }}>
            {file ? `[FILE LOADED] ${file.name}` : `DRAG & DROP ${type} FILE HERE`}
          </div>
        </ScannerFrame>
      </div>
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
        <div style={{ padding: '10px', color: 'var(--fg-muted)' }}>OPTIONAL IMAGE UPLOAD ZONE</div>
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
