import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Option {
  value: string;
  label: string;
}

interface Props {
  options: Option[];
  value: string;
  onChange: (val: string) => void;
  label?: string;
}

export default function CustomDropdown({ options, value, onChange, label }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const selectedOption = options.find(opt => opt.value === value) || options[0];

  const toggleDropdown = () => setIsOpen(prev => !prev);

  // Close dropdown on click outside
  useEffect(() => {
    const clickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', clickOutside);
    return () => document.removeEventListener('mousedown', clickOutside);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (isOpen) {
        if (highlightedIndex >= 0 && highlightedIndex < options.length) {
          onChange(options[highlightedIndex].value);
        }
        setIsOpen(false);
      } else {
        setIsOpen(true);
        // Highlight active item
        const idx = options.findIndex(opt => opt.value === value);
        setHighlightedIndex(idx >= 0 ? idx : 0);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        setHighlightedIndex(0);
      } else {
        setHighlightedIndex(prev => (prev + 1) % options.length);
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        setHighlightedIndex(options.length - 1);
      } else {
        setHighlightedIndex(prev => (prev - 1 + options.length) % options.length);
      }
    } else if (e.key === 'Tab') {
      setIsOpen(false);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      setHighlightedIndex(-1);
    }
  }, [isOpen]);

  return (
    <div 
      ref={containerRef} 
      className="custom-dropdown-container" 
      style={{ position: 'relative', width: '100%', marginBottom: '0.6rem' }}
    >
      {label && <span className="sidebar-label">{label}</span>}
      
      {/* Trigger Button */}
      <button
        type="button"
        className="sidebar-input"
        onClick={toggleDropdown}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          textAlign: 'left',
          cursor: 'pointer',
          userSelect: 'none'
        }}
      >
        <span>{selectedOption ? selectedOption.label : 'Select...'}</span>
        <motion.span
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.15 }}
          style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}
        >
          ▼
        </motion.span>
      </button>

      {/* Options Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.ul
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.12 }}
            role="listbox"
            className="custom-dropdown-menu"
            style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              zIndex: 100,
              marginTop: '6px',
              padding: '6px 0',
              borderRadius: 'var(--radius-sm)',
              listStyle: 'none',
              maxHeight: '260px',
              overflowY: 'auto',
              outline: 'none'
            }}
          >
            {options.map((opt, idx) => {
              const isSelected = opt.value === value;
              const isHighlighted = idx === highlightedIndex;

              return (
                <li
                  key={opt.value}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    onChange(opt.value);
                    setIsOpen(false);
                  }}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  style={{
                    color: isSelected 
                      ? 'var(--cyan)' 
                      : (isHighlighted ? 'var(--text-primary)' : 'var(--text-secondary)'),
                    background: isHighlighted 
                      ? 'rgba(var(--cyan-rgb), 0.12)'
                      : 'transparent',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                  className={`custom-dropdown-option dropdown-option-item ${isHighlighted ? 'highlighted' : ''}`}
                >
                  <span>{opt.label}</span>
                  {isSelected && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--cyan)' }}>✓</span>
                  )}
                </li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
