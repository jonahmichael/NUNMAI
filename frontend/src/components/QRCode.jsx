import React from 'react';

const QRCode = ({ size = 12 }) => {
  // Generate a random block of ASCII characters simulating a QR code.
  // Using solid blocks █ and empty spaces to make it look like a real barcode/QR.
  const rows = [];
  
  for (let i = 0; i < size; i++) {
    let row = '';
    for (let j = 0; j < size * 2; j++) {
      // Create a pattern. We'll force the corners to look somewhat like QR alignment patterns,
      // and random blocks elsewhere.
      const isTopLeft = (i < 3 && j < 6);
      const isTopRight = (i < 3 && j >= size * 2 - 6);
      const isBottomLeft = (i >= size - 3 && j < 6);
      
      if (isTopLeft || isTopRight || isBottomLeft) {
        // Alignment box pattern: outline is solid, center is hollow
        const border = (i === 0 || j === 0 || i === 2 || j === 5 || j === size * 2 - 1 || j === size * 2 - 6 || i === size - 1 || i === size - 3);
        row += border ? '█' : ' ';
      } else {
        row += Math.random() > 0.5 ? '█' : ' ';
      }
    }
    rows.push(row);
  }

  return (
    <pre style={{ margin: 0, lineHeight: 1, color: 'var(--fg-primary)' }}>
      {rows.map((row, idx) => (
        <div key={idx}>{row}</div>
      ))}
    </pre>
  );
};

export default QRCode;
