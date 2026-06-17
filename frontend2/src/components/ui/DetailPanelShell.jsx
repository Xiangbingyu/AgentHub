import './DetailPanelShell.css';

export default function DetailPanelShell({
  title,
  description,
  tag,
  emptyMessage,
  children,
  className = '',
}) {
  const classes = ['detail-panel-shell', className].filter(Boolean).join(' ');

  return (
    <section className={classes}>
      <div className="detail-panel-header">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        {tag ? <span className="detail-panel-tag">{tag}</span> : null}
      </div>

      <div className="detail-panel-content">
        {children ?? <div className="detail-panel-empty">{emptyMessage}</div>}
      </div>
    </section>
  );
}
