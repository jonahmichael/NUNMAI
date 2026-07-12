import React from 'react';
import './WindowPane.css';

const WindowPane = ({ title, children, style }) => {
  return (
    <div className="window-pane" style={style}>
      <div className="window-header">
        <span>+--- {title} ---+</span>
      </div>
      <div className="window-content">
        {children}
      </div>
    </div>
  );
};

export default WindowPane;
