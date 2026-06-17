import './PanelHeader.css';

export default function PanelHeader({ title, subtitle, action, children, className = '' }) {
  const classes = ['panel-header', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <div className="panel-header-top">
        <h2 className="panel-header-title">{title}</h2>
        {action}
      </div>
      {subtitle ? <p className="panel-header-subtitle">{subtitle}</p> : null}
      {children ? <div className="panel-header-extra">{children}</div> : null}
    </div>
  );
}
