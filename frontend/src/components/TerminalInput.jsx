import React, { useState, useRef } from 'react';
import './TerminalInput.css';

const TerminalInput = ({ prompt = "root@nunmai:~$", onSubmit }) => {
  const [input, setInput] = useState('');
  const inputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (onSubmit && input.trim()) {
        onSubmit(input.trim());
      }
      setInput('');
    }
  };

  const focusInput = () => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  return (
    <div className="terminal-input-container" onClick={focusInput}>
      <span className="terminal-prompt">{prompt}</span>
      <div className="input-display">
        <span>{input}</span>
        <span className="cursor animate-blink">█</span>
      </div>
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value.toUpperCase())}
        onKeyDown={handleKeyDown}
        className="hidden-input"
        autoFocus
        autoComplete="off"
        spellCheck="false"
      />
    </div>
  );
};

export default TerminalInput;
