import React from 'react';
import './ScannerFrame.css';

const ScannerFrame = ({ children, isScanning }) => {
  return (
    <div className="scanner-container">
      {children}
      {isScanning && <div className="scanner-line"></div>}
    </div>
  );
};

export default ScannerFrame;
