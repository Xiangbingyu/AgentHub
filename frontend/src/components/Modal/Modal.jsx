import { useEffect } from 'react';
import { X } from 'lucide-react';
import './Modal.css';

// 轻量受控弹窗：遮罩点击 / ESC / 关闭按钮均可关闭，内容区阻止冒泡。
export default function Modal({ open, title, onClose, children }) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose?.();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-overlay" onClick={() => onClose?.()}>
      <div
        className="modal-card"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h3>{title}</h3>
          <button type="button" className="modal-close" aria-label="关闭" onClick={() => onClose?.()}>
            <X size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
