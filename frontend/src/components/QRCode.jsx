import React from 'react';
import { QRCodeSVG } from 'qrcode.react';

const QRCode = ({ payload = "NUNMI-VERIFY: NO_DATA", size = 180 }) => {
  return (
    <div style={{ background: '#fff', padding: '10px', display: 'inline-block' }}>
      <QRCodeSVG 
        value={payload} 
        size={size} 
        bgColor={"#ffffff"} 
        fgColor={"#000000"} 
        level={"M"} 
      />
    </div>
  );
};

export default QRCode;
