import React from 'react';

const ProgressBar = ({ percent = 0, width = 20 }) => {
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;

  const filledChars = '|'.repeat(filled);
  const emptyChars = '.'.repeat(empty);

  return (
    <span className="progress-bar">
      [{filledChars}{emptyChars}] {percent}%
    </span>
  );
};

export default ProgressBar;
